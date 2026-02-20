"""Cron task manager agent."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any, ClassVar

from angie.agents.base import BaseAgent

if TYPE_CHECKING:
    from pydantic_ai import Agent


class CronAgent(BaseAgent):
    name: ClassVar[str] = "Cron Manager"
    slug: ClassVar[str] = "cron"
    description: ClassVar[str] = "Create, delete, and list cron scheduled tasks."
    capabilities: ClassVar[list[str]] = ["cron", "schedule", "recurring", "scheduled task"]

    def build_pydantic_agent(self) -> Agent:
        from pydantic_ai import Agent

        agent: Agent[None, str] = Agent(system_prompt=self.get_system_prompt())

        @agent.tool_plain
        def create_scheduled_task(
            expression: str,
            task_name: str,
            user_id: str,
            agent_slug: str = "",
            job_id: str = "",
        ) -> dict:
            """Create a recurring scheduled task using a 5-part cron expression."""
            if not expression:
                return {"error": "expression is required (5-part cron: '* * * * *')"}
            if not user_id:
                return {"error": "user_id is required"}
            _job_id = job_id or str(uuid.uuid4())
            try:
                from angie.core.cron import CronEngine

                engine = CronEngine()
                engine.start()
                engine.add_cron(
                    job_id=_job_id,
                    expression=expression,
                    user_id=user_id,
                    agent_slug=agent_slug or None,
                    payload={"task_name": task_name},
                )
                return {
                    "created": True,
                    "job_id": _job_id,
                    "expression": expression,
                    "task_name": task_name,
                }
            except Exception as exc:  # noqa: BLE001
                return {"error": str(exc)}

        @agent.tool_plain
        def delete_scheduled_task(job_id: str) -> dict:
            """Delete a scheduled task by its job ID."""
            if not job_id:
                return {"error": "job_id is required"}
            try:
                from angie.core.cron import CronEngine

                engine = CronEngine()
                engine.start()
                engine.remove_cron(job_id)
                return {"deleted": True, "job_id": job_id}
            except Exception as exc:  # noqa: BLE001
                return {"error": str(exc)}

        @agent.tool_plain
        def list_scheduled_tasks() -> dict:
            """List all currently scheduled tasks."""
            try:
                from angie.core.cron import CronEngine

                engine = CronEngine()
                engine.start()
                return {"crons": engine.list_crons()}
            except Exception as exc:  # noqa: BLE001
                return {"error": str(exc)}

        return agent

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        from angie.llm import get_llm_model

        intent = self._extract_intent(task, fallback="list scheduled tasks")
        self.logger.info("CronAgent intent=%r", intent)
        try:
            result = await self._get_agent().run(intent, model=get_llm_model())
            return {"result": str(result.output)}
        except Exception as exc:  # noqa: BLE001
            self.logger.exception("CronAgent error")
            return {"error": str(exc)}
