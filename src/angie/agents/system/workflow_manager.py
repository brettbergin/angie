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
    instructions: ClassVar[str] = (
        "You manage and trigger Angie workflows — ordered sequences of steps across agents.\n\n"
        "Available tools:\n"
        "- list_workflows: List all workflows. Set enabled_only=true to filter to active ones.\n"
        "- trigger_workflow: Start a workflow by its ID. The workflow is dispatched to "
        "the Celery queue and executed asynchronously.\n\n"
        "When the user asks to run a workflow, list available workflows first so they can "
        "choose the correct one."
    )

    def build_pydantic_agent(self) -> Agent:
        from pydantic_ai import Agent

        agent: Agent[None, str] = Agent(system_prompt=self.get_system_prompt())

        @agent.tool_plain
        async def list_workflows(enabled_only: bool = False) -> dict:
            """List all available Angie workflows."""
            from sqlalchemy import select

            from angie.db.session import get_session_factory
            from angie.models.workflow import Workflow

            factory = get_session_factory()
            async with factory() as session:
                stmt = select(Workflow).order_by(Workflow.name)
                if enabled_only:
                    stmt = stmt.where(Workflow.is_enabled.is_(True))
                result = await session.execute(stmt)
                workflows = result.scalars().all()
                return {
                    "workflows": [
                        {
                            "id": w.id,
                            "name": w.name,
                            "slug": w.slug,
                            "description": w.description,
                            "is_enabled": w.is_enabled,
                            "trigger_event": w.trigger_event,
                        }
                        for w in workflows
                    ]
                }

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
