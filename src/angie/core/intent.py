"""Intent dispatch — bridge between chat and the event/task system."""

from __future__ import annotations

import logging
from typing import Any

from angie.core.events import AngieEvent
from angie.core.tasks import AngieTask, get_dispatcher
from angie.models.event import EventType

logger = logging.getLogger(__name__)


async def dispatch_task(
    *,
    title: str,
    intent: str,
    user_id: str,
    conversation_id: str | None = None,
    agent_slug: str | None = None,
    team_slug: str | None = None,
    parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create an event + task and enqueue for async execution.

    Called by the chat agent's ``dispatch_task`` tool when the LLM
    decides a user message requires real work rather than conversation.

    If ``team_slug`` is provided, resolve the first capable agent via
    the team's agent list and use that agent_slug for dispatch.

    Returns a confirmation dict the LLM can use to acknowledge the user.
    """
    # Resolve team_slug to an agent_slug if provided
    resolved_agent = agent_slug
    if team_slug and not agent_slug:
        try:
            from sqlalchemy import select as sa_select

            from angie.db.session import get_session_factory
            from angie.models.team import Team

            factory = get_session_factory()
            async with factory() as session:
                result = await session.execute(sa_select(Team).where(Team.slug == team_slug))
                team = result.scalar_one_or_none()
                if team and team.agent_slugs:
                    # Use the first agent in the team as default
                    resolved_agent = team.agent_slugs[0]
                    logger.info("Resolved team %r to agent %r", team_slug, resolved_agent)
        except Exception as exc:
            logger.warning("Could not resolve team %r: %s", team_slug, exc)
    payload: dict[str, Any] = {
        "intent": intent,
        "conversation_id": conversation_id,
        "parameters": parameters or {},
    }

    # Persist a Task row so it shows up in the Tasks page
    task_record_id: str | None = None
    event_record_id: str | None = None
    try:
        from angie.db.session import get_session_factory
        from angie.models.event import Event
        from angie.models.task import Task

        factory = get_session_factory()
        async with factory() as session:
            # Persist the event
            event_record = Event(
                type=EventType.USER_MESSAGE,
                payload=payload,
                source_channel="web",
                user_id=user_id,
            )
            session.add(event_record)
            await session.flush()
            await session.refresh(event_record)
            event_record_id = event_record.id

            # Persist the task
            task_record = Task(
                user_id=user_id,
                title=title,
                input_data={
                    "intent": intent,
                    "conversation_id": conversation_id,
                    "parameters": parameters or {},
                },
                source_channel="web",
            )
            session.add(task_record)
            await session.flush()
            await session.refresh(task_record)
            task_record_id = task_record.id
            await session.commit()
    except Exception as exc:
        logger.error("Failed to persist event/task records: %s", exc)

    # Build the AngieEvent (in-memory, for task dispatch)
    event = AngieEvent(
        type=EventType.USER_MESSAGE,
        payload=payload,
        source_channel="web",
        user_id=user_id,
    )
    if event_record_id:
        event.id = event_record_id

    # Build the AngieTask for Celery
    task = AngieTask(
        title=title,
        user_id=user_id,
        input_data=payload,
        agent_slug=resolved_agent,
        source_event_id=event.id,
        source_channel="web",
    )
    if task_record_id:
        task.id = task_record_id

    # Dispatch to Celery
    try:
        celery_id = get_dispatcher().dispatch(task)
        logger.info(
            "Dispatched task %r (celery=%s, agent=%s, team=%s)",
            title,
            celery_id,
            resolved_agent or "auto",
            team_slug or "none",
        )

        # Update the DB record with the celery task ID
        if task_record_id:
            try:
                from angie.db.session import get_session_factory
                from angie.models.task import Task, TaskStatus

                factory = get_session_factory()
                async with factory() as session:
                    record = await session.get(Task, task_record_id)
                    if record:
                        record.celery_task_id = celery_id
                        record.status = TaskStatus.QUEUED
                        await session.commit()
            except Exception as exc:
                logger.warning("Failed to update task with celery ID: %s", exc)

        return {
            "dispatched": True,
            "task_id": task_record_id or task.id,
            "celery_id": celery_id,
            "title": title,
            "agent": resolved_agent or "auto-resolved",
            "team": team_slug,
        }
    except Exception as exc:
        logger.error("Failed to dispatch task: %s", exc)
        return {
            "dispatched": False,
            "error": str(exc),
            "title": title,
        }
