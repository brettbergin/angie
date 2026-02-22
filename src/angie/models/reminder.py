"""Reminder model — user reminders and todos with optional scheduling."""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from angie.db.session import Base
from angie.models.base import TimestampMixin, new_uuid


class ReminderStatus(enum.StrEnum):
    PENDING = "pending"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class Reminder(Base, TimestampMixin):
    __tablename__ = "reminders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    deliver_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cron_expression: Mapped[str | None] = mapped_column(String(100))
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[ReminderStatus] = mapped_column(
        Enum(ReminderStatus, values_callable=lambda e: [m.value for m in e]),
        default=ReminderStatus.PENDING,
    )
    channel: Mapped[str | None] = mapped_column(String(50))
    scheduled_job_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("scheduled_jobs.id", ondelete="SET NULL"), index=True
    )

    user: Mapped[User] = relationship(back_populates="reminders")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Reminder {self.message[:30]!r} id={self.id!r}>"
