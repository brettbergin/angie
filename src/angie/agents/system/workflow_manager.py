"""Workflow manager agent."""

from __future__ import annotations

from typing import Any, ClassVar

from angie.agents.base import BaseAgent


class WorkflowManagerAgent(BaseAgent):
    name: ClassVar[str] = "Workflow Manager"
    slug: ClassVar[str] = "workflow-manager"
    description: ClassVar[str] = "Manage and trigger Angie workflows."
    capabilities: ClassVar[list[str]] = ["workflow", "run workflow", "trigger workflow"]

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        action = task.get("input_data", {}).get("action", "list")

        if action == "list":
            return {"workflows": []}
        elif action == "trigger":
            return await self._trigger_workflow(task["input_data"])
        else:
            return {"error": f"Unknown action: {action}"}

    async def _trigger_workflow(self, data: dict[str, Any]) -> dict[str, Any]:
        workflow_id = data.get("workflow_id", "")
        from angie.queue.workers import execute_workflow
        result = execute_workflow.delay(workflow_id, data)
        return {"triggered": True, "workflow_id": workflow_id, "celery_id": result.id}
