"""Reminders agent — natural-language task and reminder management."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any, ClassVar

from sqlalchemy.exc import IntegrityError

from angie.agents.base import BaseAgent

if TYPE_CHECKING:
    from pydantic_ai import Agent


class RemindersAgent(BaseAgent):
    name: ClassVar[str] = "Reminders"
    slug: ClassVar[str] = "reminders"
    category: ClassVar[str] = "Productivity Agents"
    description: ClassVar[str] = (
        "Create reminders, todos, and recurring follow-ups from natural language."
    )
    capabilities: ClassVar[list[str]] = [
        "reminder",
        "remind",
        "todo",
        "follow up",
        "follow-up",
        "task",
        "schedule reminder",
    ]
    instructions: ClassVar[str] = (
        "You manage reminders and todos using natural language.\n\n"
        "Available tools:\n"
        "- create_reminder: Set a one-time reminder. Parse natural language dates like\n"
        "  'in 2 hours', 'tomorrow at 3pm', 'next Tuesday', 'end of day'.\n"
        "- create_recurring: Set a recurring reminder with a 5-part cron expression.\n"
        "  Convert natural language: 'every Monday at 9am' → '0 9 * * 1'\n"
        "- list_reminders: Show all pending reminders for the user.\n"
        "- complete_reminder: Mark a reminder as delivered/done.\n"
        "- cancel_reminder: Cancel a pending reminder.\n"
        "- create_todo: Create a simple todo item (no delivery time).\n"
        "- list_todos: List todos filtered by status.\n\n"
        "When parsing dates, prefer the user's intent. If ambiguous, ask for clarification.\n"
        "All times are in UTC unless the user specifies a timezone.\n"
        "Always confirm the parsed date/time back to the user."
    )

    def build_pydantic_agent(self, user_id: str = "") -> Agent:
        from pydantic_ai import Agent

        agent: Agent[None, str] = Agent(system_prompt=self.get_system_prompt())
        _user_id = user_id

        @agent.tool_plain
        async def create_reminder(message: str, when: str) -> dict:
            """Create a one-time reminder. ``when`` is a natural language datetime string."""
            if not message or not message.strip():
                return {"error": "message is required"}
            if not _user_id:
                return {"error": "user_id not available in task context"}
            if not when or not when.strip():
                return {"error": "when is required (e.g. 'tomorrow at 3pm', 'in 2 hours')"}

            import dateparser

            parsed = dateparser.parse(when, settings={"PREFER_DATES_FROM": "future"})
            if parsed is None:
                return {"error": f"Could not parse date/time from: {when!r}"}

            try:
                return await _create_reminder_in_db(
                    user_id=_user_id,
                    message=message.strip(),
                    deliver_at=parsed,
                )
            except Exception as exc:  # noqa: BLE001
                return {"error": str(exc)}

        @agent.tool_plain
        async def create_recurring(message: str, cron_expr: str) -> dict:
            """Create a recurring reminder using a 5-part cron expression."""
            if not message or not message.strip():
                return {"error": "message is required"}
            if not _user_id:
                return {"error": "user_id not available in task context"}
            if not cron_expr or not cron_expr.strip():
                return {"error": "cron_expr is required (5-part: '* * * * *')"}

            from angie.core.cron import validate_cron_expression

            valid, err = validate_cron_expression(cron_expr)
            if not valid:
                return {"error": err}

            try:
                return await _create_recurring_in_db(
                    user_id=_user_id,
                    message=message.strip(),
                    cron_expression=cron_expr.strip(),
                )
            except Exception as exc:  # noqa: BLE001
                return {"error": str(exc)}

        @agent.tool_plain
        async def list_reminders() -> dict:
            """List all pending reminders for the current user."""
            if not _user_id:
                return {"error": "user_id not available in task context"}
            try:
                return await _list_reminders_from_db(_user_id)
            except Exception as exc:  # noqa: BLE001
                return {"error": str(exc)}

        @agent.tool_plain
        async def complete_reminder(reminder_id: str) -> dict:
            """Mark a reminder as delivered/completed."""
            if not reminder_id:
                return {"error": "reminder_id is required"}
            try:
                return await _update_reminder_status(reminder_id, "delivered")
            except Exception as exc:  # noqa: BLE001
                return {"error": str(exc)}

        @agent.tool_plain
        async def cancel_reminder(reminder_id: str) -> dict:
            """Cancel a pending reminder."""
            if not reminder_id:
                return {"error": "reminder_id is required"}
            try:
                return await _cancel_reminder_in_db(reminder_id)
            except Exception as exc:  # noqa: BLE001
                return {"error": str(exc)}

        @agent.tool_plain
        async def create_todo(title: str, priority: str = "normal") -> dict:
            """Create a simple todo item with no delivery time."""
            if not title or not title.strip():
                return {"error": "title is required"}
            if not _user_id:
                return {"error": "user_id not available in task context"}
            try:
                return await _create_reminder_in_db(
                    user_id=_user_id,
                    message=f"[{priority.upper()}] {title.strip()}",
                )
            except Exception as exc:  # noqa: BLE001
                return {"error": str(exc)}

        @agent.tool_plain
        async def list_todos(status: str = "pending") -> dict:
            """List todos filtered by status (pending, delivered, cancelled)."""
            if not _user_id:
                return {"error": "user_id not available in task context"}
            try:
                return await _list_reminders_from_db(_user_id, status=status)
            except Exception as exc:  # noqa: BLE001
                return {"error": str(exc)}

        return agent

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        from angie.llm import get_llm_model

        intent = self._extract_intent(task, fallback="list my reminders")
        user_id = task.get("user_id", "")
        self.logger.info("RemindersAgent intent=%r user_id=%s", intent, user_id)
        try:
            agent = self.build_pydantic_agent(user_id=user_id)
            result = await agent.run(intent, model=get_llm_model())
            return {"result": str(result.output)}
        except Exception as exc:  # noqa: BLE001
            self.logger.exception("RemindersAgent error")
            return {"error": str(exc)}


# ------------------------------------------------------------------
# DB helpers
# ------------------------------------------------------------------


async def _create_reminder_in_db(
    *,
    user_id: str,
    message: str,
    deliver_at: Any | None = None,
) -> dict:
    from angie.db.session import get_session_factory
    from angie.models.reminder import Reminder

    reminder = Reminder(
        id=str(uuid.uuid4()),
        user_id=user_id,
        message=message,
        deliver_at=deliver_at,
        is_recurring=False,
    )
    async with get_session_factory()() as session:
        session.add(reminder)
        await session.commit()
        await session.refresh(reminder)

    result: dict[str, Any] = {
        "created": True,
        "reminder_id": reminder.id,
        "message": reminder.message,
    }
    if deliver_at:
        result["deliver_at"] = str(deliver_at)
    return result


async def _create_recurring_in_db(
    *,
    user_id: str,
    message: str,
    cron_expression: str,
) -> dict:
    from angie.core.cron import cron_to_human
    from angie.db.session import get_session_factory
    from angie.models.reminder import Reminder
    from angie.models.schedule import ScheduledJob

    job_id = str(uuid.uuid4())
    reminder_id = str(uuid.uuid4())

    job = ScheduledJob(
        id=job_id,
        user_id=user_id,
        name=f"reminder:{reminder_id}",
        description=message,
        cron_expression=cron_expression,
        agent_slug="reminders",
        task_payload={"reminder_id": reminder_id, "message": message},
        is_enabled=True,
    )
    reminder = Reminder(
        id=reminder_id,
        user_id=user_id,
        message=message,
        cron_expression=cron_expression,
        is_recurring=True,
        scheduled_job_id=job_id,
    )

    try:
        async with get_session_factory()() as session:
            session.add(job)
            session.add(reminder)
            await session.commit()
    except IntegrityError:
        return {"error": "A recurring reminder with this message already exists"}

    return {
        "created": True,
        "reminder_id": reminder_id,
        "message": message,
        "cron_expression": cron_expression,
        "human_readable": cron_to_human(cron_expression),
        "is_recurring": True,
    }


async def _list_reminders_from_db(user_id: str, status: str = "pending") -> dict:
    from sqlalchemy import select

    from angie.db.session import get_session_factory
    from angie.models.reminder import Reminder, ReminderStatus

    status_enum = ReminderStatus(status)

    async with get_session_factory()() as session:
        stmt = (
            select(Reminder)
            .where(Reminder.user_id == user_id, Reminder.status == status_enum)
            .order_by(Reminder.created_at)
        )
        result = await session.execute(stmt)
        reminders = result.scalars().all()

    return {
        "reminders": [
            {
                "id": r.id,
                "message": r.message,
                "deliver_at": str(r.deliver_at) if r.deliver_at else None,
                "is_recurring": r.is_recurring,
                "cron_expression": r.cron_expression,
                "status": r.status.value,
                "created_at": str(r.created_at),
            }
            for r in reminders
        ]
    }


async def _update_reminder_status(reminder_id: str, status: str) -> dict:
    from angie.db.session import get_session_factory
    from angie.models.reminder import Reminder, ReminderStatus

    async with get_session_factory()() as session:
        reminder = await session.get(Reminder, reminder_id)
        if not reminder:
            return {"error": f"Reminder {reminder_id} not found"}
        reminder.status = ReminderStatus(status)
        await session.commit()

    return {"updated": True, "reminder_id": reminder_id, "status": status}


async def _cancel_reminder_in_db(reminder_id: str) -> dict:
    from angie.db.session import get_session_factory
    from angie.models.reminder import Reminder, ReminderStatus
    from angie.models.schedule import ScheduledJob

    async with get_session_factory()() as session:
        reminder = await session.get(Reminder, reminder_id)
        if not reminder:
            return {"error": f"Reminder {reminder_id} not found"}
        reminder.status = ReminderStatus.CANCELLED

        # Remove associated ScheduledJob if recurring
        if reminder.scheduled_job_id:
            job = await session.get(ScheduledJob, reminder.scheduled_job_id)
            if job:
                await session.delete(job)

        await session.commit()

    return {"cancelled": True, "reminder_id": reminder_id}
