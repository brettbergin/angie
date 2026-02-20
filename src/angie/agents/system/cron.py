"""Cron task manager agent."""

from __future__ import annotations

import uuid
from typing import Any, ClassVar

from angie.agents.base import BaseAgent


class CronAgent(BaseAgent):
    name: ClassVar[str] = "Cron Manager"
    slug: ClassVar[str] = "cron"
    description: ClassVar[str] = "Create, delete, and list cron scheduled tasks."
    capabilities: ClassVar[list[str]] = ["cron", "schedule", "recurring", "scheduled task"]

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        action = task.get("input_data", {}).get("action", "list")
        self.logger.info("CronAgent executing action: %s", action)

        if action == "create":
            return await self._create_cron(task.get("input_data", {}))
        elif action == "delete":
            return await self._delete_cron(task.get("input_data", {}))
        else:
            return await self._list_crons(task)

    async def _create_cron(self, data: dict[str, Any]) -> dict[str, Any]:
        expression = data.get("expression", "")
        task_name = data.get("task_name", "")
        user_id = data.get("user_id", "")
        agent_slug = data.get("agent_slug")
        job_id = data.get("job_id") or str(uuid.uuid4())

        if not expression:
            return {"error": "expression is required (5-part cron: '* * * * *')"}
        if not user_id:
            return {"error": "user_id is required"}

        try:
            from angie.core.cron import CronEngine

            engine = CronEngine()
            engine.start()
            engine.add_cron(
                job_id=job_id,
                expression=expression,
                user_id=user_id,
                agent_slug=agent_slug,
                payload={"task_name": task_name},
            )
            return {
                "created": True,
                "job_id": job_id,
                "expression": expression,
                "task_name": task_name,
            }
        except Exception as exc:  # noqa: BLE001
            self.logger.exception("Failed to create cron")
            return {"error": str(exc)}

    async def _delete_cron(self, data: dict[str, Any]) -> dict[str, Any]:
        job_id = data.get("job_id", "")
        if not job_id:
            return {"error": "job_id is required"}
        try:
            from angie.core.cron import CronEngine

            engine = CronEngine()
            engine.start()
            engine.remove_cron(job_id)
            return {"deleted": True, "job_id": job_id}
        except Exception as exc:  # noqa: BLE001
            self.logger.exception("Failed to delete cron")
            return {"error": str(exc)}

    async def _list_crons(self, task: dict[str, Any]) -> dict[str, Any]:
        try:
            from angie.core.cron import CronEngine

            engine = CronEngine()
            engine.start()
            return {"crons": engine.list_crons()}
        except Exception as exc:  # noqa: BLE001
            self.logger.exception("Failed to list crons")
            return {"error": str(exc)}
