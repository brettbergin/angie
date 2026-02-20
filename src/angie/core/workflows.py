"""Workflow executor — runs ordered steps across agents."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class WorkflowExecutor:
    """Executes a Workflow by running its steps in order."""

    async def run(self, workflow_id: str, context: dict[str, Any]) -> dict[str, Any]:
        from angie.agents.registry import get_registry

        logger.info("Running workflow %s", workflow_id)
        registry = get_registry()
        results: list[dict[str, Any]] = []

        # TODO: load workflow + steps from DB
        # For now this is a stub that can be wired up once DB is live
        steps: list[dict[str, Any]] = context.get("steps", [])

        step_context = dict(context)
        for i, step in enumerate(steps):
            agent_slug = step.get("agent_slug")
            agent = registry.get(agent_slug) if agent_slug else None

            if agent is None:
                error = f"Step {i}: agent {agent_slug!r} not found"
                logger.error(error)
                if step.get("on_failure", "stop") == "stop":
                    return {"status": "failed", "error": error, "results": results}
                continue

            try:
                step_task = {**step, "input_data": step_context}
                result = await agent.execute(step_task)
                results.append({"step": i, "agent": agent_slug, "result": result})
                step_context.update(result)
            except Exception as exc:
                error = f"Step {i} failed: {exc}"
                logger.exception(error)
                if step.get("on_failure", "stop") == "stop":
                    return {"status": "failed", "error": error, "results": results}

        return {"status": "success", "results": results}
