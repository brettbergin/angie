"""Workflow executor — runs ordered steps across agents (D4: loads from DB)."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class WorkflowExecutor:
    """Executes a Workflow by loading its steps from DB and running in order."""

    async def run(self, workflow_id: str, context: dict[str, Any]) -> dict[str, Any]:
        from sqlalchemy import select

        from angie.agents.registry import get_registry
        from angie.db.session import get_session_factory
        from angie.models.workflow import Workflow, WorkflowStep

        logger.info("Running workflow %s", workflow_id)
        registry = get_registry()
        results: list[dict[str, Any]] = []

        async with get_session_factory()() as session:
            # Load workflow
            wf = await session.get(Workflow, workflow_id)
            if not wf:
                return {"status": "failed", "error": f"Workflow {workflow_id!r} not found"}
            if not wf.is_enabled:
                return {"status": "skipped", "error": "Workflow is disabled"}

            # Load steps ordered
            steps_result = await session.execute(
                select(WorkflowStep)
                .where(WorkflowStep.workflow_id == workflow_id)
                .order_by(WorkflowStep.order)
            )
            steps = steps_result.scalars().all()

        if not steps:
            # Fall back to inline steps in context (for testing / ad-hoc)
            steps = context.get("steps", [])  # type: ignore[assignment]

        step_context = dict(context)

        for i, step in enumerate(steps):
            if isinstance(step, WorkflowStep):
                agent_slug = step.config.get("agent_slug")
                on_failure = step.on_failure
                step_task = {"title": step.name, "input_data": step_context, **step.config}
            else:
                # dict-based step (test/ad-hoc)
                agent_slug = step.get("agent_slug")
                on_failure = step.get("on_failure", "stop")
                step_task = {**step, "input_data": step_context}

            agent = registry.get(agent_slug) if agent_slug else None

            if agent is None:
                error = f"Step {i}: agent {agent_slug!r} not found"
                logger.error(error)
                if on_failure == "stop":
                    return {"status": "failed", "error": error, "results": results}
                continue

            try:
                result = await agent.execute(step_task)
                results.append({"step": i, "agent": agent_slug, "result": result})
                step_context.update(result)
            except Exception as exc:
                error = f"Step {i} ({agent_slug}) failed: {exc}"
                logger.exception(error)
                if on_failure == "stop":
                    return {"status": "failed", "error": error, "results": results}

        return {"status": "success", "results": results}
