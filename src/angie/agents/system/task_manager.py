"""Task manager agent."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from angie.agents.base import BaseAgent

if TYPE_CHECKING:
    from pydantic_ai import Agent


class TaskManagerAgent(BaseAgent):
    name: ClassVar[str] = "Task Manager"
    slug: ClassVar[str] = "task-manager"
    description: ClassVar[str] = "List, cancel, and retry Angie tasks."
    capabilities: ClassVar[list[str]] = ["task", "cancel task", "retry task", "list tasks"]

    def build_pydantic_agent(self) -> Agent:
        from pydantic_ai import Agent

        agent: Agent[None, str] = Agent(system_prompt=self.get_system_prompt())

        @agent.tool_plain
        def list_tasks(status: str = "") -> dict:
            """List Angie tasks, optionally filtered by status."""
            # TODO: query DB with filters
            return {"tasks": []}

        @agent.tool_plain
        def cancel_task(task_id: str) -> dict:
            """Cancel a running Angie task by its ID."""
            from angie.queue.celery_app import celery_app

            celery_app.control.revoke(task_id, terminate=True)
            return {"cancelled": True, "task_id": task_id}

        @agent.tool_plain
        def retry_task(task_id: str) -> dict:
            """Retry a previously failed Angie task by its ID."""
            # TODO: re-enqueue task
            return {"retried": True, "task_id": task_id}

        return agent

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        from angie.llm import get_llm_model

        intent = self._extract_intent(task, fallback="list tasks")
        self.logger.info("TaskManagerAgent intent=%r", intent)
        try:
            result = await self._get_agent().run(intent, model=get_llm_model())
            return {"result": str(result.output)}
        except Exception as exc:  # noqa: BLE001
            self.logger.exception("TaskManagerAgent error")
            return {"error": str(exc)}
