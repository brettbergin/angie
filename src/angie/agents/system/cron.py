"""Cron task manager agent."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any, ClassVar

from sqlalchemy.exc import IntegrityError

from angie.agents.base import BaseAgent

if TYPE_CHECKING:
    from pydantic_ai import Agent


class CronAgent(BaseAgent):
    name: ClassVar[str] = "Cron Manager"
    slug: ClassVar[str] = "cron"
    category: ClassVar[str] = "System Agents"
    description: ClassVar[str] = "Create, delete, and list cron scheduled tasks."
    capabilities: ClassVar[list[str]] = ["cron", "schedule", "recurring", "scheduled task"]
    instructions: ClassVar[str] = (
        "You manage recurring scheduled tasks using cron expressions.\n\n"
        "Available tools:\n"
        "- create_scheduled_task: Create a recurring task. Convert natural language\n"
        "  schedules to 5-part cron expressions (minute hour day month weekday).\n"
        "  Examples:\n"
        "    'every day at midnight' → '0 0 * * *'\n"
        "    'weekdays at 9 AM'     → '0 9 * * 1-5'\n"
        "    'every 5 minutes'      → '*/5 * * * *'\n"
        "    'every Sunday at 3 PM' → '0 15 * * 0'\n"
        "    'first of every month' → '0 0 1 * *'\n"
        "  All times are in UTC.\n"
        "  Minimum interval: 1 minute. Do not schedule more frequently.\n"
        "- delete_scheduled_task: Remove a scheduled task by its job ID.\n"
        "- list_scheduled_tasks: List all currently scheduled tasks.\n\n"
        "When the user describes a schedule in natural language, convert it to a\n"
        "5-part cron expression and create the task."
    )

    def build_pydantic_agent(self, user_id: str = "") -> Agent:
        from pydantic_ai import Agent

        agent: Agent[None, str] = Agent(system_prompt=self.get_system_prompt())
        _user_id = user_id

        @agent.tool_plain
        async def create_scheduled_task(
            expression: str,
            task_name: str,
            description: str = "",
            agent_slug: str = "",
        ) -> dict:
            """Create a recurring scheduled task using a 5-part cron expression."""
            if not expression:
                return {"error": "expression is required (5-part cron: '* * * * *')"}
            if not _user_id:
                return {"error": "user_id not available in task context"}
            if not task_name or not task_name.strip():
                return {"error": "task_name is required"}

            from angie.core.cron import validate_cron_expression

            valid, err = validate_cron_expression(expression)
            if not valid:
                return {"error": err}

            job_id = str(uuid.uuid4())
            try:
                return await _create_job_in_db(
                    job_id=job_id,
                    user_id=_user_id,
                    name=task_name.strip(),
                    description=description,
                    cron_expression=expression,
                    agent_slug=agent_slug or None,
                )
            except Exception as exc:  # noqa: BLE001
                return {"error": str(exc)}

        @agent.tool_plain
        async def delete_scheduled_task(job_id: str) -> dict:
            """Delete a scheduled task by its job ID."""
            if not job_id:
                return {"error": "job_id is required"}
            try:
                return await _delete_job_from_db(job_id)
            except Exception as exc:  # noqa: BLE001
                return {"error": str(exc)}

        @agent.tool_plain
        async def list_scheduled_tasks() -> dict:
            """List all currently scheduled tasks for the current user."""
            if not _user_id:
                return {"error": "user_id not available in task context"}
            try:
                return await _list_jobs_from_db(_user_id)
            except Exception as exc:  # noqa: BLE001
                return {"error": str(exc)}

        return agent

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        from angie.llm import get_llm_model

        intent = self._extract_intent(task, fallback="list scheduled tasks")
        user_id = task.get("user_id", "")
        self.logger.info("CronAgent intent=%r user_id=%s", intent, user_id)
        try:
            # Build a fresh agent with user_id baked into tool closures
            agent = self.build_pydantic_agent(user_id=user_id)
            result = await agent.run(intent, model=get_llm_model())
            return {"result": str(result.output)}
        except Exception as exc:  # noqa: BLE001
            self.logger.exception("CronAgent error")
            return {"error": str(exc)}


# ------------------------------------------------------------------
# DB helpers (run in worker's async context)
# ------------------------------------------------------------------


async def _create_job_in_db(
    *,
    job_id: str,
    user_id: str,
    name: str,
    description: str,
    cron_expression: str,
    agent_slug: str | None,
) -> dict:
    from angie.core.cron import cron_to_human
    from angie.db.session import get_session_factory
    from angie.models.schedule import ScheduledJob

    job = ScheduledJob(
        id=job_id,
        user_id=user_id,
        name=name,
        description=description or None,
        cron_expression=cron_expression,
        agent_slug=agent_slug,
        task_payload={},
        is_enabled=True,
    )
    try:
        async with get_session_factory()() as session:
            session.add(job)
            await session.commit()
            await session.refresh(job)
    except IntegrityError:
        return {"error": f"A schedule named '{name}' already exists"}

    return {
        "created": True,
        "job_id": job_id,
        "name": name,
        "expression": cron_expression,
        "human_readable": cron_to_human(cron_expression),
    }


async def _delete_job_from_db(job_id: str) -> dict:
    from angie.db.session import get_session_factory
    from angie.models.schedule import ScheduledJob

    async with get_session_factory()() as session:
        job = await session.get(ScheduledJob, job_id)
        if not job:
            return {"error": f"Job {job_id} not found"}
        await session.delete(job)
        await session.commit()
    return {"deleted": True, "job_id": job_id}


async def _list_jobs_from_db(user_id: str) -> dict:
    from sqlalchemy import select

    from angie.core.cron import cron_to_human
    from angie.db.session import get_session_factory
    from angie.models.schedule import ScheduledJob

    async with get_session_factory()() as session:
        stmt = (
            select(ScheduledJob).where(ScheduledJob.user_id == user_id).order_by(ScheduledJob.name)
        )
        result = await session.execute(stmt)
        jobs = result.scalars().all()

    return {
        "schedules": [
            {
                "id": j.id,
                "name": j.name,
                "expression": j.cron_expression,
                "human_readable": cron_to_human(j.cron_expression),
                "agent_slug": j.agent_slug,
                "is_enabled": j.is_enabled,
                "last_run_at": str(j.last_run_at) if j.last_run_at else None,
                "next_run_at": str(j.next_run_at) if j.next_run_at else None,
            }
            for j in jobs
        ]
    }
