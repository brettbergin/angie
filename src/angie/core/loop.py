"""Angie daemon — main event loop."""

from __future__ import annotations

import asyncio
import signal
import time

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

    On startup:
      1. Verifies all dependencies are reachable
      2. Starts cron engine and channel listeners
      3. Starts the initiative engine for proactive scans
      4. Enters a tick-based health monitoring loop
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self.cron = CronEngine()
        self.dispatcher = get_dispatcher()
        self._running = False
        self._channel_manager = None
        self._initiative_task: asyncio.Task | None = None
        self._start_time: float = 0.0

    async def start(self) -> None:
        logger.info("Angie is waking up...")
        self._start_time = time.monotonic()

        # Verify dependencies before starting
        await self._verify_dependencies()

        await self.cron.start()

        # Initialize channels
        from angie.channels.base import get_channel_manager

        self._channel_manager = get_channel_manager()
        await self._channel_manager.start_all()

        # Start initiative engine
        from angie.core.initiative import InitiativeEngine

        self.initiative = InitiativeEngine()
        self._initiative_task = asyncio.create_task(self.initiative.start())

        # Wire subscription manager into event router
        from angie.core.subscriptions import get_subscription_manager

        sub_mgr = get_subscription_manager()

        @router.on(EventType.TASK_COMPLETE, EventType.TASK_FAILED)
        async def _notify_subscribers(event: AngieEvent) -> None:
            await sub_mgr.notify(event)

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
        logger.info("Angie is online")

        try:
            await self._run_forever()
        finally:
            await self.shutdown()

    async def _run_forever(self) -> None:
        """Tick-based health monitoring loop."""
        tick_interval = 10  # seconds between health ticks
        while self._running:
            try:
                await self._health_tick()
            except Exception:
                logger.exception("Health tick failed")
            await asyncio.sleep(tick_interval)

    async def _health_tick(self) -> None:
        """Periodic health check and maintenance."""
        await self._check_channel_health()
        await self._cleanup_stale_tasks()

    async def _check_channel_health(self) -> None:
        """Verify all channels are still connected. Reconnect if needed."""
        if not self._channel_manager:
            return
        for name, channel in self._channel_manager._channels.items():
            try:
                healthy = await channel.health_check()
                if not healthy:
                    logger.warning("Channel %s unhealthy, attempting reconnect", name)
                    try:
                        await channel.stop()
                        await channel.start()
                        logger.info("Channel %s reconnected", name)
                    except Exception:
                        logger.exception("Channel %s reconnect failed", name)
            except Exception:
                logger.exception("Channel health check failed: %s", name)

    async def _cleanup_stale_tasks(self) -> None:
        """Mark tasks stuck in 'queued' status for >30 minutes as 'failed'."""
        try:
            from datetime import UTC, datetime, timedelta

            from sqlalchemy import select

            from angie.db.session import get_session_factory
            from angie.models.task import Task, TaskStatus

            cutoff = datetime.now(UTC) - timedelta(minutes=30)
            async with get_session_factory()() as session:
                result = await session.execute(
                    select(Task).where(
                        Task.status == TaskStatus.PENDING,
                        Task.created_at < cutoff,
                    )
                )
                stale = result.scalars().all()
                for task in stale:
                    task.status = TaskStatus.FAILURE
                    task.error = "Task timed out in queue"
                    logger.warning("Marked stale task %s as failed", task.id)
                if stale:
                    await session.commit()
        except Exception:
            logger.debug("Stale task cleanup failed", exc_info=True)

    async def _verify_dependencies(self) -> None:
        """Check DB, Redis, and Celery are reachable before starting."""
        # Test DB connection
        try:
            from angie.db.session import get_session_factory

            async with get_session_factory()() as session:
                await session.execute(
                    __import__("sqlalchemy").text("SELECT 1")
                )
            logger.info("DB connection verified")
        except Exception as exc:
            logger.warning("DB connection check failed: %s", exc)

        # Test Redis connection
        try:
            import redis

            r = redis.from_url(self.settings.redis_url)
            r.ping()
            r.close()
            logger.info("Redis connection verified")
        except Exception as exc:
            logger.warning("Redis connection check failed: %s", exc)

    @property
    def uptime_seconds(self) -> float:
        """Return seconds since the daemon started."""
        if not self._start_time:
            return 0.0
        return time.monotonic() - self._start_time

    async def shutdown(self) -> None:
        logger.info("Angie is shutting down...")
        self._running = False
        if self._initiative_task:
            self._initiative_task.cancel()
            try:
                await self._initiative_task
            except asyncio.CancelledError:
                pass
        self.cron.shutdown()
        if self._channel_manager:
            await self._channel_manager.stop_all()
        logger.info("Angie offline. Goodbye.")

    def handle_signal(self, sig: int) -> None:
        logger.info("Received signal %s, shutting down gracefully", sig)
        self._running = False


async def run_daemon() -> None:
    loop_obj = AngieLoop()
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig: loop_obj.handle_signal(s))
    await loop_obj.start()
