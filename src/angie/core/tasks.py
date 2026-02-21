"""AngieTask dataclass and task dispatcher."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from angie.core.events import AngieEvent


@dataclass
class AngieTask:
    """A unit of work created from an event and placed on a Celery queue."""

    title: str
    user_id: str
    input_data: dict[str, Any] = field(default_factory=dict)
    agent_slug: str | None = None
    workflow_id: str | None = None
    source_event_id: str | None = None
    source_channel: str | None = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "user_id": self.user_id,
            "input_data": self.input_data,
            "agent_slug": self.agent_slug,
            "workflow_id": self.workflow_id,
            "source_event_id": self.source_event_id,
            "source_channel": self.source_channel,
            "created_at": self.created_at.isoformat(),
        }


class TaskDispatcher:
    """Creates AngieTasks from events and enqueues them via Celery."""

    def dispatch(self, task: AngieTask) -> str:
        """Enqueue a task. Returns the Celery task ID."""
        from angie.queue.celery_app import celery_app

        result = celery_app.send_task(
            "angie.queue.workers.execute_task",
            args=[task.to_dict()],
            queue="tasks",
        )
        return result.id

    def dispatch_from_event(self, event: AngieEvent, agent_slug: str | None = None) -> AngieTask:
        """Create and enqueue a task from an event."""
        task = AngieTask(
            title=f"Task from {event.type.value} event",
            user_id=event.user_id or "system",
            input_data=event.payload,
            agent_slug=agent_slug,
            source_event_id=event.id,
            source_channel=event.source_channel,
        )
        celery_id = self.dispatch(task)
        task.id = celery_id
        return task


_dispatcher: TaskDispatcher | None = None


def get_dispatcher() -> TaskDispatcher:
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = TaskDispatcher()
    return _dispatcher
