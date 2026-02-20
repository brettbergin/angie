"""Celery workers — task and workflow execution."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from celery import shared_task

logger = logging.getLogger(__name__)


# ── DB helpers ────────────────────────────────────────────────────────────────


async def _update_task_in_db(
    task_id: str, status: str, output_data: dict, error: str | None
) -> None:
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


# ── D3: Intent routing ────────────────────────────────────────────────────────


def _resolve_agent(task_dict: dict[str, Any]):
    """D3 — route task to correct agent via registry keyword matching."""
    from angie.agents.registry import get_registry

    registry = get_registry()
    agent_slug = task_dict.get("agent_slug")

    if agent_slug:
        agent = registry.get(agent_slug)
        if agent:
            return agent

    # Keyword-based intent routing (fast, no LLM needed for routing)
    agent = registry.resolve(task_dict)
    if agent:
        return agent

    logger.warning("No agent matched for task: %s", task_dict.get("title"))
    return None


# ── D2: Channel reply ─────────────────────────────────────────────────────────


async def _send_reply(source_channel: str | None, user_id: str | None, text: str) -> None:
    """D2 — send task result back to the originating channel."""
    if not source_channel or not user_id:
        return
    try:
        from angie.channels.base import get_channel_manager

        mgr = get_channel_manager()
        await mgr.send(user_id, text, channel_type=source_channel)
    except Exception as exc:
        logger.warning("Channel reply failed (%s): %s", source_channel, exc)


# ── Tasks ─────────────────────────────────────────────────────────────────────


@shared_task(bind=True, name="angie.queue.workers.execute_task", max_retries=3)
def execute_task(self, task_dict: dict[str, Any]) -> dict[str, Any]:
    """Execute a single AngieTask and write result + reply back."""
    task_id = task_dict.get("id")
    source_channel = task_dict.get("source_channel")
    user_id = task_dict.get("user_id")
    logger.info("Executing task %s", task_id)

    try:
        agent = _resolve_agent(task_dict)
        if agent is None:
            raise ValueError(f"No agent found for task '{task_dict.get('title')}'")

        result = asyncio.run(agent.execute(task_dict))

        if task_id:
            asyncio.run(_update_task_in_db(task_id, "success", result, None))

        # D2: reply to originating channel
        summary = result.get("summary") or result.get("message") or "✅ Task complete."
        asyncio.run(_send_reply(source_channel, user_id, summary))

        return {"status": "success", "result": result, "task_id": task_id}

    except Exception as exc:
        logger.exception("Task %s failed: %s", task_id, exc)
        if task_id:
            try:
                asyncio.run(_update_task_in_db(task_id, "failure", {}, str(exc)))
            except Exception:
                pass
        asyncio.run(_send_reply(source_channel, user_id, f"❌ Task failed: {exc}"))
        raise self.retry(exc=exc, countdown=2**self.request.retries) from exc


@shared_task(bind=True, name="angie.queue.workers.execute_workflow", max_retries=1)
def execute_workflow(self, workflow_id: str, task_dict: dict[str, Any]) -> dict[str, Any]:
    """Execute a multi-step workflow (D4: loads steps from DB)."""
    from angie.core.workflows import WorkflowExecutor

    logger.info("Executing workflow %s", workflow_id)
    try:
        executor = WorkflowExecutor()
        result = asyncio.run(executor.run(workflow_id, task_dict))
        return {"status": "success", "result": result, "workflow_id": workflow_id}
    except Exception as exc:
        logger.exception("Workflow %s failed: %s", workflow_id, exc)
        raise self.retry(exc=exc, countdown=5) from exc
