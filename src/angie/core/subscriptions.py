"""Event subscription system — allows agents to subscribe to lifecycle events."""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from typing import Any

from angie.core.events import AngieEvent
from angie.models.event import EventType

logger = logging.getLogger(__name__)

CallbackFn = Callable[[AngieEvent], Coroutine[Any, Any, None]]


class SubscriptionManager:
    """Allows agents to subscribe to lifecycle events (task_complete, task_failed)."""

    def __init__(self) -> None:
        self._subscriptions: dict[str, list[CallbackFn]] = {}

    def subscribe(self, event_type: EventType, callback: CallbackFn) -> None:
        """Register a callback for a specific event type."""
        self._subscriptions.setdefault(event_type.value, []).append(callback)
        logger.debug("Subscription added for %s", event_type.value)

    def unsubscribe(self, event_type: EventType, callback: CallbackFn) -> None:
        """Remove a callback for a specific event type."""
        callbacks = self._subscriptions.get(event_type.value, [])
        if callback in callbacks:
            callbacks.remove(callback)

    async def notify(self, event: AngieEvent) -> None:
        """Notify all subscribers of an event."""
        for cb in self._subscriptions.get(event.type.value, []):
            try:
                await cb(event)
            except Exception:
                logger.exception("Subscription callback failed for %s", event.type.value)

    @property
    def subscription_count(self) -> int:
        """Total number of registered subscriptions."""
        return sum(len(cbs) for cbs in self._subscriptions.values())


_manager: SubscriptionManager | None = None


def get_subscription_manager() -> SubscriptionManager:
    global _manager
    if _manager is None:
        _manager = SubscriptionManager()
    return _manager
