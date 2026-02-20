"""Task manager agent."""

from __future__ import annotations

from typing import Any, ClassVar

from angie.agents.base import BaseAgent


class TaskManagerAgent(BaseAgent):
    name: ClassVar[str] = "Task Manager"
    slug: ClassVar[str] = "task-manager"
    description: ClassVar[str] = "List, cancel, and retry Angie tasks."
    capabilities: ClassVar[list[str]] = ["task", "cancel task", "retry task", "list tasks"]

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        action = task.get("input_data", {}).get("action", "list")

        if action == "list":
            return await self._list_tasks(task["input_data"])
        elif action == "cancel":
            return await self._cancel_task(task["input_data"])
        elif action == "retry":
            return await self._retry_task(task["input_data"])
        else:
            return {"error": f"Unknown action: {action}"}

    async def _list_tasks(self, data: dict[str, Any]) -> dict[str, Any]:
        # TODO: query DB with filters
        return {"tasks": []}

    async def _cancel_task(self, data: dict[str, Any]) -> dict[str, Any]:
        task_id = data.get("task_id", "")
        from angie.queue.celery_app import celery_app
        celery_app.control.revoke(task_id, terminate=True)
        return {"cancelled": True, "task_id": task_id}

    async def _retry_task(self, data: dict[str, Any]) -> dict[str, Any]:
        # TODO: re-enqueue task
        return {"retried": True}
