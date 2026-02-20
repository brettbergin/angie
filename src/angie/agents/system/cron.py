"""Cron task manager agent."""

from __future__ import annotations

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
            return await self._create_cron(task["input_data"])
        elif action == "delete":
            return await self._delete_cron(task["input_data"])
        elif action == "list":
            return await self._list_crons()
        else:
            return {"error": f"Unknown action: {action}"}

    async def _create_cron(self, data: dict[str, Any]) -> dict[str, Any]:
        expression = data.get("expression", "")
        task_name = data.get("task_name", "")
        self.logger.info("Creating cron: %s -> %s", expression, task_name)
        # TODO: persist to DB and register with APScheduler
        return {"created": True, "expression": expression, "task_name": task_name}

    async def _delete_cron(self, data: dict[str, Any]) -> dict[str, Any]:
        cron_id = data.get("cron_id", "")
        self.logger.info("Deleting cron: %s", cron_id)
        # TODO: remove from DB and APScheduler
        return {"deleted": True, "cron_id": cron_id}

    async def _list_crons(self) -> dict[str, Any]:
        # TODO: query DB
        return {"crons": []}
