"""Cron scheduler — evaluates cron expressions and fires events."""

from __future__ import annotations

import logging
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from angie.core.events import AngieEvent, router
from angie.models.event import EventType

logger = logging.getLogger(__name__)


class CronEngine:
    """APScheduler-backed cron scheduler that emits AngieEvents."""

    def __init__(self) -> None:
        self.scheduler = AsyncIOScheduler(timezone="UTC")
        self._jobs: dict[str, Any] = {}

    def start(self) -> None:
        self.scheduler.start()
        logger.info("CronEngine started")

    def shutdown(self) -> None:
        self.scheduler.shutdown(wait=False)
        logger.info("CronEngine stopped")

    def add_cron(
        self,
        job_id: str,
        expression: str,
        user_id: str,
        agent_slug: str | None = None,
        payload: dict | None = None,
    ) -> None:
        """Register a cron expression that fires an AngieEvent."""
        # Parse "* * * * *" format
        parts = expression.split()
        if len(parts) != 5:
            raise ValueError(f"Invalid cron expression: {expression!r}")

        minute, hour, day, month, day_of_week = parts
        trigger = CronTrigger(
            minute=minute,
            hour=hour,
            day=day,
            month=month,
            day_of_week=day_of_week,
            timezone="UTC",
        )

        async def _fire() -> None:
            event = AngieEvent(
                type=EventType.CRON,
                user_id=user_id,
                payload={"job_id": job_id, "agent_slug": agent_slug, **(payload or {})},
                source_channel="cron",
            )
            await router.dispatch(event)

        job = self.scheduler.add_job(_fire, trigger=trigger, id=job_id, replace_existing=True)
        self._jobs[job_id] = job
        logger.info("Registered cron job %s: %s", job_id, expression)

    def remove_cron(self, job_id: str) -> None:
        self.scheduler.remove_job(job_id)
        self._jobs.pop(job_id, None)
        logger.info("Removed cron job %s", job_id)

    def list_crons(self) -> list[dict[str, Any]]:
        return [
            {"id": job.id, "next_run": str(job.next_run_time)} for job in self.scheduler.get_jobs()
        ]
