"""Event model."""

import enum

from sqlalchemy import JSON, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from angie.db.session import Base
from angie.models.base import TimestampMixin, new_uuid


class EventType(enum.StrEnum):
    USER_MESSAGE = "user_message"
    CRON = "cron"
    WEBHOOK = "webhook"
    TASK_COMPLETE = "task_complete"
    TASK_FAILED = "task_failed"
    SYSTEM = "system"
    CHANNEL_MESSAGE = "channel_message"
    API_CALL = "api_call"


class Event(Base, TimestampMixin):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    type: Mapped[EventType] = mapped_column(
        Enum(EventType, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        index=True,
    )
    source_channel: Mapped[str | None] = mapped_column(String(50))
    user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    processed: Mapped[bool] = mapped_column(default=False, index=True)
    task_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("tasks.id"))

    def __repr__(self) -> str:
        return f"<Event {self.type!r} id={self.id!r}>"
