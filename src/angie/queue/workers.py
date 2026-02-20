"""Celery workers — task and workflow execution."""

from __future__ import annotations

import logging
from typing import Any

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, name="angie.queue.workers.execute_task", max_retries=3)
def execute_task(self, task_dict: dict[str, Any]) -> dict[str, Any]:
    """Execute a single AngieTask."""
    from angie.agents.registry import get_registry

    task_id = task_dict.get("id")
    agent_slug = task_dict.get("agent_slug")
    logger.info("Executing task %s via agent %s", task_id, agent_slug)

    try:
        registry = get_registry()
        agent = registry.get(agent_slug) if agent_slug else registry.resolve(task_dict)

        if agent is None:
            raise ValueError(f"No agent found for task {task_id}")

        import asyncio
        result = asyncio.run(agent.execute(task_dict))
        return {"status": "success", "result": result, "task_id": task_id}

    except Exception as exc:
        logger.exception("Task %s failed: %s", task_id, exc)
        raise self.retry(exc=exc, countdown=2 ** self.request.retries) from exc


@shared_task(bind=True, name="angie.queue.workers.execute_workflow", max_retries=1)
def execute_workflow(self, workflow_id: str, task_dict: dict[str, Any]) -> dict[str, Any]:
    """Execute a multi-step workflow."""
    from angie.core.workflows import WorkflowExecutor

    logger.info("Executing workflow %s", workflow_id)
    try:
        import asyncio
        executor = WorkflowExecutor()
        result = asyncio.run(executor.run(workflow_id, task_dict))
        return {"status": "success", "result": result, "workflow_id": workflow_id}
    except Exception as exc:
        logger.exception("Workflow %s failed: %s", workflow_id, exc)
        raise self.retry(exc=exc, countdown=5) from exc
