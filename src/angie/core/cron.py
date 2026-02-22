"""Cron scheduler — evaluates cron expressions and fires events."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from angie.core.events import AngieEvent, router
from angie.models.event import EventType

logger = logging.getLogger(__name__)

# Human-readable field names for error messages
_FIELD_NAMES = ("minute", "hour", "day-of-month", "month", "day-of-week")


def validate_cron_expression(expression: str) -> tuple[bool, str]:
    """Validate a 5-part cron expression. Returns (is_valid, error_message)."""
    parts = expression.strip().split()
    if len(parts) != 5:
        return False, f"Expected 5 fields (minute hour day month weekday), got {len(parts)}"
    try:
        CronTrigger(
            minute=parts[0],
            hour=parts[1],
            day=parts[2],
            month=parts[3],
            day_of_week=parts[4],
            timezone="UTC",
        )
    except (ValueError, KeyError) as exc:
        return False, f"Invalid cron expression: {exc}"
    return True, ""


def cron_to_human(expression: str) -> str:
    """Convert a 5-part cron expression to a human-readable description."""
    parts = expression.strip().split()
    if len(parts) != 5:
        return expression

    minute, hour, day, month, dow = parts

    # Common patterns
    if parts == ["*", "*", "*", "*", "*"]:
        return "Every minute"
    if minute.startswith("*/"):
        n = minute[2:]
        if hour == "*" and day == "*" and month == "*" and dow == "*":
            return f"Every {n} minutes"
    if hour.startswith("*/"):
        n = hour[2:]
        if minute == "0" and day == "*" and month == "*" and dow == "*":
            return f"Every {n} hours"
    if minute != "*" and hour != "*" and day == "*" and month == "*":
        try:
            time_str = f"{int(hour):d}:{int(minute):02d} UTC"
        except ValueError:
            return expression
        if dow == "*":
            return f"Every day at {time_str}"
        if dow == "1-5":
            return f"Weekdays at {time_str}"
        if dow == "0,6":
            return f"Weekends at {time_str}"
        dow_names = {
            "0": "Sunday",
            "1": "Monday",
            "2": "Tuesday",
            "3": "Wednesday",
            "4": "Thursday",
            "5": "Friday",
            "6": "Saturday",
            "sun": "Sunday",
            "mon": "Monday",
            "tue": "Tuesday",
            "wed": "Wednesday",
            "thu": "Thursday",
            "fri": "Friday",
            "sat": "Saturday",
        }
        dow_label = dow_names.get(dow.lower(), dow)
        return f"Every {dow_label} at {time_str}"
    if minute != "*" and hour != "*" and day != "*" and month == "*" and dow == "*":
        try:
            time_str = f"{int(hour):d}:{int(minute):02d} UTC"
            suffix = _ordinal(int(day))
        except ValueError:
            return expression
        return f"{suffix} of every month at {time_str}"

    return expression


def _ordinal(n: int) -> str:
    """Return ordinal string for a number (1st, 2nd, 3rd, etc.)."""
    if 11 <= n % 100 <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


class CronEngine:
    """APScheduler-backed cron scheduler that emits AngieEvents.

    On startup, loads enabled ScheduledJobs from DB.  A periodic sync task
    re-reads DB every 60 s so API / agent changes are picked up automatically.
    """

    def __init__(self) -> None:
        self.scheduler = AsyncIOScheduler(timezone="UTC")
        self._jobs: dict[str, dict[str, Any]] = {}
        self._sync_task: asyncio.Task | None = None

    async def start(self) -> None:
        self.scheduler.start()
        logger.info("CronEngine started")
        await self.sync_from_db()
        self._sync_task = asyncio.create_task(self._sync_loop())

    def shutdown(self) -> None:
        if self._sync_task and not self._sync_task.done():
            self._sync_task.cancel()
        self.scheduler.shutdown(wait=False)
        logger.info("CronEngine stopped")

    # ------------------------------------------------------------------
    # DB sync
    # ------------------------------------------------------------------

    async def _sync_loop(self) -> None:
        """Periodically sync scheduled jobs from DB."""
        while True:
            await asyncio.sleep(60)
            try:
                await self.sync_from_db()
            except Exception:  # noqa: BLE001
                logger.exception("CronEngine sync error")

    async def sync_from_db(self) -> None:
        """Load enabled ScheduledJobs from DB, reconcile with in-memory jobs."""
        from sqlalchemy import select

        from angie.db.session import get_session_factory
        from angie.models.schedule import ScheduledJob

        async with get_session_factory()() as session:
            result = await session.execute(
                select(ScheduledJob).where(ScheduledJob.is_enabled.is_(True))
            )
            db_jobs = {job.id: job for job in result.scalars().all()}

        # Remove jobs that are no longer in DB or disabled
        stale = set(self._jobs.keys()) - set(db_jobs.keys())
        for job_id in stale:
            try:
                self.scheduler.remove_job(job_id)
            except Exception:  # noqa: BLE001
                pass
            self._jobs.pop(job_id, None)
            logger.info("Removed stale cron job %s", job_id)

        # Add or update jobs from DB
        for job_id, job_record in db_jobs.items():
            existing = self._jobs.get(job_id)
            if existing and existing.get("expression") == job_record.cron_expression:
                continue  # unchanged
            self._register_job(job_record)

        logger.debug("CronEngine sync complete: %d active jobs", len(self._jobs))

    def _register_job(self, job_record: Any) -> None:
        """Register a single ScheduledJob with APScheduler."""
        parts = job_record.cron_expression.split()
        if len(parts) != 5:
            logger.warning(
                "Invalid cron expression for job %s: %s", job_record.id, job_record.cron_expression
            )
            return

        minute, hour, day, month, day_of_week = parts

        job_id = job_record.id
        try:
            trigger = CronTrigger(
                minute=minute,
                hour=hour,
                day=day,
                month=month,
                day_of_week=day_of_week,
                timezone="UTC",
            )
        except (ValueError, KeyError):
            logger.exception(
                "Invalid cron trigger for job %s (%s): %s",
                job_record.name,
                job_id,
                job_record.cron_expression,
            )
            return

        user_id = job_record.user_id
        agent_slug = job_record.agent_slug
        payload = {
            "task_name": job_record.name,
            "job_id": job_id,
            "agent_slug": agent_slug,
            **(job_record.task_payload or {}),
        }

        async def _fire() -> None:
            event = AngieEvent(
                type=EventType.CRON,
                user_id=user_id,
                payload=payload,
                source_channel="cron",
            )
            await router.dispatch(event)
            await self._update_last_run(job_id)

        job = self.scheduler.add_job(
            _fire,
            trigger=trigger,
            id=job_id,
            replace_existing=True,
        )
        next_run = job.next_run_time
        self._jobs[job_id] = {
            "expression": job_record.cron_expression,
            "next_run": str(next_run),
        }
        # Persist next_run_at so the UI/API can display it immediately
        if next_run is not None:
            task = asyncio.create_task(self._update_next_run_at(job_id, next_run))

            def _log_update_error(t: asyncio.Task[Any]) -> None:
                try:
                    t.result()
                except Exception:  # noqa: BLE001
                    logger.exception("Background update_next_run_at failed for job %s", job_id)

            task.add_done_callback(_log_update_error)
            self._jobs[job_id]["next_run_update_task"] = task
        logger.info(
            "Registered cron job %s (%s): %s", job_record.name, job_id, job_record.cron_expression
        )

    async def _update_next_run_at(self, job_id: str, next_run: datetime | None) -> None:
        """Update next_run_at in DB when a job is registered."""
        from sqlalchemy import update as sa_update

        from angie.db.session import get_session_factory
        from angie.models.schedule import ScheduledJob

        try:
            async with get_session_factory()() as session:
                await session.execute(
                    sa_update(ScheduledJob)
                    .where(ScheduledJob.id == job_id)
                    .values(next_run_at=next_run)
                )
                await session.commit()
        except Exception:  # noqa: BLE001
            logger.exception("Failed to update next_run_at for job %s", job_id)

    async def _update_last_run(self, job_id: str) -> None:
        """Update last_run_at and next_run_at in DB after a job fires."""
        from sqlalchemy import update

        from angie.db.session import get_session_factory
        from angie.models.schedule import ScheduledJob

        now = datetime.now(UTC)
        apscheduler_job = self.scheduler.get_job(job_id)
        next_run = apscheduler_job.next_run_time if apscheduler_job else None

        try:
            async with get_session_factory()() as session:
                await session.execute(
                    update(ScheduledJob)
                    .where(ScheduledJob.id == job_id)
                    .values(last_run_at=now, next_run_at=next_run)
                )
                await session.commit()
        except Exception:  # noqa: BLE001
            logger.exception("Failed to update last_run_at for job %s", job_id)

    # ------------------------------------------------------------------
    # Direct management (used by daemon loop event handler)
    # ------------------------------------------------------------------

    def add_cron(
        self,
        job_id: str,
        expression: str,
        user_id: str,
        agent_slug: str | None = None,
        payload: dict | None = None,
    ) -> None:
        """Register a cron expression that fires an AngieEvent (in-memory only)."""
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
        self._jobs[job_id] = {"expression": expression, "next_run": str(job.next_run_time)}
        logger.info("Registered cron job %s: %s", job_id, expression)

    def remove_cron(self, job_id: str) -> None:
        self.scheduler.remove_job(job_id)
        self._jobs.pop(job_id, None)
        logger.info("Removed cron job %s", job_id)

    def list_crons(self) -> list[dict[str, Any]]:
        return [
            {"id": job.id, "next_run": str(job.next_run_time)} for job in self.scheduler.get_jobs()
        ]
