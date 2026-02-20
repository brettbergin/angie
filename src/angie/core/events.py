"""Event system — base classes, types, and router."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from angie.models.event import EventType


@dataclass
class AngieEvent:
    """Base event that flows through the Angie event loop."""

    type: EventType
    payload: dict[str, Any] = field(default_factory=dict)
    source_channel: str | None = None
    user_id: str | None = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "payload": self.payload,
            "source_channel": self.source_channel,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat(),
        }


HandlerFn = Callable[[AngieEvent], Coroutine[Any, Any, None]]


class EventRouter:
    """Routes events to registered async handlers."""

    def __init__(self) -> None:
        self._handlers: dict[EventType, list[HandlerFn]] = {}
        self._catch_all: list[HandlerFn] = []

    def on(self, *event_types: EventType) -> Callable[[HandlerFn], HandlerFn]:
        """Decorator to register a handler for one or more event types."""

        def decorator(fn: HandlerFn) -> HandlerFn:
            for et in event_types:
                self._handlers.setdefault(et, []).append(fn)
            return fn

        return decorator

    def on_any(self) -> Callable[[HandlerFn], HandlerFn]:
        """Decorator to register a catch-all handler."""

        def decorator(fn: HandlerFn) -> HandlerFn:
            self._catch_all.append(fn)
            return fn

        return decorator

    async def dispatch(self, event: AngieEvent) -> None:
        """Dispatch an event to all matching handlers."""
        handlers = self._handlers.get(event.type, []) + self._catch_all
        for handler in handlers:
            await handler(event)


# Global router instance
router = EventRouter()
