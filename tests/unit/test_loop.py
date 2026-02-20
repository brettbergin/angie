"""Tests for core/loop.py — AngieLoop daemon."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DB_PASSWORD", "test-password")


@pytest.fixture(autouse=True)
def clear_event_router():
    """Reset global EventRouter state between loop tests to prevent handler accumulation."""
    from angie.core.events import router
    # Save original state
    original_catch_all = router._catch_all.copy()
    original_handlers = {k: v.copy() for k, v in router._handlers.items()}
    yield
    # Restore original state
    router._catch_all = original_catch_all
    router._handlers = original_handlers


def _make_settings():
    from angie.config import Settings
    return Settings(secret_key="test-secret", db_password="testpass")


async def test_loop_start_and_shutdown():
    from angie.core.loop import AngieLoop

    mock_cron = MagicMock()
    mock_dispatcher = MagicMock()
    mock_channel_manager = AsyncMock()

    with (
        patch("angie.config.get_settings", return_value=_make_settings()),
        patch("angie.core.loop.CronEngine", return_value=mock_cron),
        patch("angie.core.loop.get_dispatcher", return_value=mock_dispatcher),
        patch("angie.channels.base.get_channel_manager", return_value=mock_channel_manager),
    ):
        loop = AngieLoop()

        # Patch _run_forever to return immediately
        async def _quick_run():
            pass

        loop._run_forever = _quick_run
        await loop.start()

    mock_cron.start.assert_called_once()
    mock_cron.shutdown.assert_called_once()
    mock_channel_manager.start_all.assert_called_once()
    mock_channel_manager.stop_all.assert_called_once()


async def test_loop_shutdown_stops_running():
    from angie.core.loop import AngieLoop

    mock_cron = MagicMock()
    mock_dispatcher = MagicMock()

    with (
        patch("angie.config.get_settings", return_value=_make_settings()),
        patch("angie.core.loop.CronEngine", return_value=mock_cron),
        patch("angie.core.loop.get_dispatcher", return_value=mock_dispatcher),
    ):
        loop = AngieLoop()
        loop._running = True
        await loop.shutdown()

    assert loop._running is False
    mock_cron.shutdown.assert_called_once()


async def test_loop_shutdown_with_channel_manager():
    from angie.core.loop import AngieLoop

    mock_cron = MagicMock()
    mock_dispatcher = MagicMock()
    mock_channel_manager = AsyncMock()

    with (
        patch("angie.config.get_settings", return_value=_make_settings()),
        patch("angie.core.loop.CronEngine", return_value=mock_cron),
        patch("angie.core.loop.get_dispatcher", return_value=mock_dispatcher),
    ):
        loop = AngieLoop()
        loop._running = True
        loop._channel_manager = mock_channel_manager

        await loop.shutdown()

    mock_channel_manager.stop_all.assert_called_once()


def test_loop_handle_signal():
    from angie.core.loop import AngieLoop

    mock_cron = MagicMock()
    mock_dispatcher = MagicMock()

    with (
        patch("angie.config.get_settings", return_value=_make_settings()),
        patch("angie.core.loop.CronEngine", return_value=mock_cron),
        patch("angie.core.loop.get_dispatcher", return_value=mock_dispatcher),
    ):
        loop = AngieLoop()
        loop._running = True
        loop.handle_signal(15)

    assert loop._running is False


async def test_loop_dispatch_channel_message():
    """Test that channel messages get dispatched to the task queue."""
    from angie.core.loop import AngieLoop
    from angie.core.events import AngieEvent
    from angie.models.event import EventType

    mock_cron = MagicMock()
    mock_dispatcher = MagicMock()
    mock_channel_manager = AsyncMock()

    with (
        patch("angie.config.get_settings", return_value=_make_settings()),
        patch("angie.core.loop.CronEngine", return_value=mock_cron),
        patch("angie.core.loop.get_dispatcher", return_value=mock_dispatcher),
        patch("angie.channels.base.get_channel_manager", return_value=mock_channel_manager),
    ):
        loop = AngieLoop()

        async def _quick_run():
            # Simulate a CHANNEL_MESSAGE event
            event = AngieEvent(
                type=EventType.CHANNEL_MESSAGE,
                payload={"text": "Hello Angie"},
                user_id="user1",
                source_channel="slack",
            )
            from angie.core.events import router
            await router.dispatch(event)

        loop._run_forever = _quick_run
        await loop.start()

    # Dispatcher should have been called once
    mock_dispatcher.dispatch.assert_called_once()


async def test_loop_dispatch_ignores_task_complete():
    """Test that TASK_COMPLETE events are not dispatched."""
    from angie.core.loop import AngieLoop
    from angie.core.events import AngieEvent
    from angie.models.event import EventType

    mock_cron = MagicMock()
    mock_dispatcher = MagicMock()
    mock_channel_manager = AsyncMock()

    with (
        patch("angie.config.get_settings", return_value=_make_settings()),
        patch("angie.core.loop.CronEngine", return_value=mock_cron),
        patch("angie.core.loop.get_dispatcher", return_value=mock_dispatcher),
        patch("angie.channels.base.get_channel_manager", return_value=mock_channel_manager),
    ):
        loop = AngieLoop()

        async def _quick_run():
            event = AngieEvent(
                type=EventType.TASK_COMPLETE,
                payload={"result": "done"},
            )
            from angie.core.events import router
            await router.dispatch(event)

        loop._run_forever = _quick_run
        await loop.start()

    # TASK_COMPLETE should NOT be dispatched
    mock_dispatcher.dispatch.assert_not_called()


async def test_run_daemon():
    """Test the run_daemon convenience function."""
    from angie.core.loop import run_daemon

    with patch("angie.core.loop.AngieLoop.start", new=AsyncMock()):
        await run_daemon()
