"""Unit tests for the event system."""

import pytest

from angie.core.events import AngieEvent, EventRouter
from angie.models.event import EventType


def test_angie_event_creation():
    event = AngieEvent(
        type=EventType.USER_MESSAGE,
        payload={"message": "hello"},
        user_id="user-1",
        source_channel="slack",
    )
    assert event.type == EventType.USER_MESSAGE
    assert event.payload["message"] == "hello"
    assert event.user_id == "user-1"
    assert event.id is not None


def test_angie_event_to_dict():
    event = AngieEvent(type=EventType.CRON, payload={"job": "daily_report"})
    d = event.to_dict()
    assert d["type"] == "cron"
    assert d["payload"]["job"] == "daily_report"


@pytest.mark.asyncio
async def test_event_router_dispatch():
    router = EventRouter()
    received = []

    @router.on(EventType.USER_MESSAGE)
    async def handler(event: AngieEvent):
        received.append(event)

    event = AngieEvent(type=EventType.USER_MESSAGE, payload={"msg": "test"})
    await router.dispatch(event)
    assert len(received) == 1
    assert received[0].payload["msg"] == "test"


@pytest.mark.asyncio
async def test_event_router_catch_all():
    router = EventRouter()
    received = []

    @router.on_any()
    async def catch_all(event: AngieEvent):
        received.append(event.type)

    await router.dispatch(AngieEvent(type=EventType.CRON))
    await router.dispatch(AngieEvent(type=EventType.SYSTEM))
    assert EventType.CRON in received
    assert EventType.SYSTEM in received


@pytest.mark.asyncio
async def test_event_router_no_handlers():
    router = EventRouter()
    # Should not raise
    await router.dispatch(AngieEvent(type=EventType.WEBHOOK))
