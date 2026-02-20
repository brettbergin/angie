"""Workflow manager agent."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from angie.agents.base import BaseAgent

if TYPE_CHECKING:
    from pydantic_ai import Agent


class WorkflowManagerAgent(BaseAgent):
    name: ClassVar[str] = "Workflow Manager"
    slug: ClassVar[str] = "workflow-manager"
    description: ClassVar[str] = "Manage and trigger Angie workflows."
    capabilities: ClassVar[list[str]] = ["workflow", "run workflow", "trigger workflow"]

    def build_pydantic_agent(self) -> Agent:
        from pydantic_ai import Agent

        agent: Agent[None, str] = Agent(system_prompt=self.get_system_prompt())

        @agent.tool_plain
        def list_workflows() -> dict:
            """List all available Angie workflows."""
            return {"workflows": []}

        @agent.tool_plain
        def trigger_workflow(workflow_id: str) -> dict:
            """Trigger an Angie workflow by its ID."""
            from angie.queue.workers import execute_workflow

            result = execute_workflow.delay(workflow_id, {})
            return {"triggered": True, "workflow_id": workflow_id, "celery_id": result.id}

        return agent

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        from angie.llm import get_llm_model

        intent = self._extract_intent(task, fallback="list workflows")
        self.logger.info("WorkflowManagerAgent intent=%r", intent)
        try:
            result = await self._get_agent().run(intent, model=get_llm_model())
            return {"result": str(result.output)}
        except Exception as exc:  # noqa: BLE001
            self.logger.exception("WorkflowManagerAgent error")
            return {"error": str(exc)}
