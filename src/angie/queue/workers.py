"""Celery workers — task and workflow execution."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from celery import shared_task

from angie.db.session import reset_engine

logger = logging.getLogger(__name__)


# ── DB helpers ────────────────────────────────────────────────────────────────


async def _update_task_in_db(
    task_id: str, status: str, output_data: dict, error: str | None
) -> None:
    from sqlalchemy import select
    from sqlalchemy import update as sa_update

    from angie.db.session import get_session_factory
    from angie.models.event import Event
    from angie.models.task import Task, TaskStatus

    async with get_session_factory()() as session:
        task_updated = False
        event_updated = False

        result = await session.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()
        if task:
            task.status = TaskStatus(status)
            task.output_data = output_data
            task.error = error
            task_updated = True

        # Mark the originating event as processed
        event_result = await session.execute(
            sa_update(Event).where(Event.task_id == task_id).values(processed=True)
        )
        event_updated = event_result.rowcount is not None and event_result.rowcount > 0

        if task_updated or event_updated:
            await session.commit()


async def _deliver_chat_result(
    conversation_id: str,
    user_id: str,
    text: str,
) -> None:
    """Persist a task result as a ChatMessage and push via WebSocket."""
    from sqlalchemy import func

    from angie.db.session import get_session_factory
    from angie.models.conversation import ChatMessage, Conversation, MessageRole

    # Persist the result as an assistant message in the conversation
    try:
        factory = get_session_factory()
        async with factory() as session:
            msg = ChatMessage(
                conversation_id=conversation_id,
                role=MessageRole.ASSISTANT,
                content=text,
            )
            session.add(msg)
            # Touch conversation updated_at
            convo = await session.get(Conversation, conversation_id)
            if convo:
                convo.updated_at = func.now()
            await session.commit()
    except Exception as exc:
        logger.warning("Failed to persist chat result to conversation: %s", exc)

    # Push via WebSocket if user is connected
    try:
        from angie.api.routers.chat import _web_channel

        await _web_channel.send(
            user_id,
            text,
            conversation_id=conversation_id,
        )
    except Exception as exc:
        logger.debug("WebSocket push failed (user may be offline): %s", exc)


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


async def _run_task(task_dict: dict[str, Any]) -> dict[str, Any]:
    """Run agent, persist results, and deliver reply — all in one event loop."""
    reset_engine()

    task_id = task_dict.get("id")
    source_channel = task_dict.get("source_channel")
    user_id = task_dict.get("user_id")
    input_data = task_dict.get("input_data", {})
    conversation_id = input_data.get("conversation_id")

    agent = _resolve_agent(task_dict)
    if agent is None:
        raise ValueError(f"No agent found for task '{task_dict.get('title')}'")

    result = await agent.execute(task_dict)

    if task_id:
        await _update_task_in_db(task_id, "success", result, None)

    summary = (
        result.get("summary")
        or result.get("message")
        or result.get("result")
        or result.get("error")
        or "✅ Task complete."
    )

    if conversation_id and user_id:
        await _deliver_chat_result(conversation_id, user_id, summary)
    else:
        await _send_reply(source_channel, user_id, summary)

    return {"status": "success", "result": result, "task_id": task_id}


@shared_task(bind=True, name="angie.queue.workers.execute_task", max_retries=3)
def execute_task(self, task_dict: dict[str, Any]) -> dict[str, Any]:
    """Execute a single AngieTask and write result + reply back."""
    task_id = task_dict.get("id")
    input_data = task_dict.get("input_data", {})
    conversation_id = input_data.get("conversation_id")
    user_id = task_dict.get("user_id")
    source_channel = task_dict.get("source_channel")
    logger.info("Executing task %s", task_id)

    try:
        return asyncio.run(_run_task(task_dict))
    except Exception as exc:
        logger.exception("Task %s failed: %s", task_id, exc)
        if task_id:
            try:
                asyncio.run(_update_task_in_db(task_id, "failure", {}, str(exc)))
            except Exception:
                pass

        error_msg = f"❌ Task failed: {exc}"
        try:
            if conversation_id and user_id:
                asyncio.run(_deliver_chat_result(conversation_id, user_id, error_msg))
            else:
                asyncio.run(_send_reply(source_channel, user_id, error_msg))
        except Exception:
            pass

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
