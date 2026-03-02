"""Cron task manager agent."""

from __future__ import annotations

import uuid
from datetime import datetime
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
        "You manage recurring and one-time scheduled tasks using cron expressions.\n\n"
        "Available tools:\n"
        "- create_scheduled_task: Create a scheduled task. Convert natural language\n"
        "  schedules to 5-part cron expressions (minute hour day month weekday).\n"
        "  Examples:\n"
        "    'every day at midnight' → '0 0 * * *'\n"
        "    'weekdays at 9 AM'     → '0 9 * * 1-5'\n"
        "    'every 5 minutes'      → '*/5 * * * *'\n"
        "    'every Sunday at 3 PM' → '0 15 * * 0'\n"
        "    'first of every month' → '0 0 1 * *'\n"
        "  For one-time tasks, use '@once' as the expression and provide run_at\n"
        "  (ISO 8601 datetime in UTC) for when it should fire.\n"
        "  Example: 'remind me tomorrow at 9 AM' → expression='@once',\n"
        "    run_at='2026-03-02T09:00:00Z'\n"
        "  All times are in UTC.\n"
        "  Minimum interval: 1 minute. Do not schedule more frequently.\n"
        "- delete_scheduled_task: Remove a scheduled task by its job ID.\n"
        "- list_scheduled_tasks: List all currently scheduled tasks.\n\n"
        "When the user describes a schedule in natural language, convert it to a\n"
        "5-part cron expression (or '@once' for one-time tasks) and create the task."
    )

    def build_pydantic_agent(self, user_id: str = "", conversation_id: str = "") -> Agent:
        from pydantic_ai import Agent

        agent: Agent[None, str] = Agent(system_prompt=self.get_system_prompt())
        _user_id = user_id
        _conversation_id = conversation_id

        @agent.tool_plain
        async def create_scheduled_task(
            expression: str,
            task_name: str,
            description: str = "",
            agent_slug: str = "",
            run_at: str = "",
        ) -> dict:
            """Create a scheduled task using a 5-part cron expression or '@once' with run_at."""
            if not expression:
                return {"error": "expression is required (5-part cron or '@once')"}
            if not _user_id:
                return {"error": "user_id not available in task context"}
            if not task_name or not task_name.strip():
                return {"error": "task_name is required"}

            from angie.core.cron import validate_cron_expression

            valid, err = validate_cron_expression(expression)
            if not valid:
                return {"error": err}

            next_run_at = None
            if expression.strip() == "@once":
                if not run_at:
                    return {"error": "run_at is required for @once expressions"}
                from datetime import UTC, datetime

                try:
                    next_run_at = datetime.fromisoformat(run_at.replace("Z", "+00:00"))
                except ValueError:
                    return {"error": f"Invalid run_at datetime: {run_at}"}
                if next_run_at.tzinfo is None:
                    next_run_at = next_run_at.replace(tzinfo=UTC)
                if next_run_at <= datetime.now(UTC):
                    return {"error": "run_at must be in the future"}

            job_id = str(uuid.uuid4())
            try:
                return await _create_job_in_db(
                    job_id=job_id,
                    user_id=_user_id,
                    name=task_name.strip(),
                    description=description,
                    cron_expression=expression,
                    agent_slug=agent_slug or "cron",
                    next_run_at=next_run_at,
                    conversation_id=_conversation_id or None,
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
        input_data = task.get("input_data", {})
        user_id = task.get("user_id", "")
        conversation_id = input_data.get("conversation_id", "")

        job_id = input_data.get("job_id")
        if job_id:
            task_name = input_data.get("task_name", "")
            intent = (
                f"A scheduled cron job just fired (job_id={job_id}). "
                f"The job name is '{task_name}'. "
                f"Your task: {intent}. "
                f"Execute the described task. If this is a reminder or notification, "
                f"acknowledge it clearly and provide any helpful context. "
                f"If the task involves listing or managing schedules, use your tools."
            )
        self.logger.info("CronAgent intent=%r user_id=%s", intent, user_id)
        try:
            # Build a fresh agent with user_id baked into tool closures
            agent = self.build_pydantic_agent(user_id=user_id, conversation_id=conversation_id)
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
    next_run_at: datetime | None = None,
    conversation_id: str | None = None,
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
        next_run_at=next_run_at,
        conversation_id=conversation_id,
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
