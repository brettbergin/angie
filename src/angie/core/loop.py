"""Angie daemon — main event loop."""

from __future__ import annotations

import asyncio
import signal

import structlog

from angie.config import get_settings
from angie.core.cron import CronEngine
from angie.core.events import AngieEvent, router
from angie.core.tasks import get_dispatcher
from angie.models.event import EventType

logger = structlog.get_logger(__name__)


class AngieLoop:
    """
    The Angie daemon.

    On each loop iteration:
      1. Polls for new events from channels
      2. Fires any ready cron jobs (via APScheduler)
      3. Dispatches events to the task queue
      4. Logs outcomes
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self.cron = CronEngine()
        self.dispatcher = get_dispatcher()
        self._running = False
        self._channel_manager = None

    async def start(self) -> None:
        logger.info("Angie is waking up... 🌟")
        self.cron.start()

        # Initialize channels
        from angie.channels.base import get_channel_manager

        self._channel_manager = get_channel_manager()
        await self._channel_manager.start_all()

        # Register default event → task handler
        @router.on_any()
        async def _dispatch_to_queue(event: AngieEvent) -> None:
            dispatchable = (
                EventType.USER_MESSAGE,
                EventType.CHANNEL_MESSAGE,
                EventType.CRON,
                EventType.WEBHOOK,
            )
            if event.type not in dispatchable:
                return
            # Use message text as task title for channel messages
            if event.type == EventType.CHANNEL_MESSAGE:
                text = event.payload.get("text", "")[:120]
                title = text if text else "Channel message"
            else:
                title = f"Task from {event.type.value} event"
            from angie.core.tasks import AngieTask

            task = AngieTask(
                title=title,
                user_id=event.user_id or "system",
                input_data=event.payload,
                source_event_id=event.id,
                source_channel=event.source_channel,
            )
            self.dispatcher.dispatch(task)
            logger.info("Dispatched task", task_title=title, event_type=event.type.value)

        self._running = True
        logger.info("Angie is online ✨")

        try:
            await self._run_forever()
        finally:
            await self.shutdown()

    async def _run_forever(self) -> None:
        while self._running:
            await asyncio.sleep(1)

    async def shutdown(self) -> None:
        logger.info("Angie is shutting down...")
        self._running = False
        self.cron.shutdown()
        if self._channel_manager:
            await self._channel_manager.stop_all()
        logger.info("Angie offline. Goodbye. 👋")

    def handle_signal(self, sig: int) -> None:
        logger.info("Received signal %s, shutting down gracefully", sig)
        self._running = False


async def run_daemon() -> None:
    loop_obj = AngieLoop()
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig: loop_obj.handle_signal(s))
    await loop_obj.start()
