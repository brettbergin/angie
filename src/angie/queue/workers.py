"""Celery workers — task and workflow execution."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from celery import shared_task

logger = logging.getLogger(__name__)


async def _update_task_in_db(task_id: str, status: str, output_data: dict, error: str | None) -> None:
    from sqlalchemy import select

    from angie.db.session import get_session_factory
    from angie.models.task import Task, TaskStatus

    async with get_session_factory()() as session:
        result = await session.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()
        if task:
            task.status = TaskStatus(status)
            task.output_data = output_data
            task.error = error
            await session.commit()


@shared_task(bind=True, name="angie.queue.workers.execute_task", max_retries=3)
def execute_task(self, task_dict: dict[str, Any]) -> dict[str, Any]:
    """Execute a single AngieTask and write result back to DB."""
    from angie.agents.registry import get_registry

    task_id = task_dict.get("id")
    agent_slug = task_dict.get("agent_slug")
    logger.info("Executing task %s via agent %s", task_id, agent_slug)

    try:
        registry = get_registry()
        agent = registry.get(agent_slug) if agent_slug else registry.resolve(task_dict)

        if agent is None:
            raise ValueError(f"No agent found for task {task_id}")

        result = asyncio.run(agent.execute(task_dict))

        if task_id:
            asyncio.run(_update_task_in_db(task_id, "success", result, None))

        return {"status": "success", "result": result, "task_id": task_id}

    except Exception as exc:
        logger.exception("Task %s failed: %s", task_id, exc)
        if task_id:
            try:
                asyncio.run(_update_task_in_db(task_id, "failure", {}, str(exc)))
            except Exception:
                pass
        raise self.retry(exc=exc, countdown=2**self.request.retries) from exc


@shared_task(bind=True, name="angie.queue.workers.execute_workflow", max_retries=1)
def execute_workflow(self, workflow_id: str, task_dict: dict[str, Any]) -> dict[str, Any]:
    """Execute a multi-step workflow."""
    from angie.core.workflows import WorkflowExecutor

    logger.info("Executing workflow %s", workflow_id)
    try:
        executor = WorkflowExecutor()
        result = asyncio.run(executor.run(workflow_id, task_dict))
        return {"status": "success", "result": result, "workflow_id": workflow_id}
    except Exception as exc:
        logger.exception("Workflow %s failed: %s", workflow_id, exc)
        raise self.retry(exc=exc, countdown=5) from exc
