"""ScheduledJob model — persistent cron schedule definitions."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from angie.db.session import Base
from angie.models.base import TimestampMixin, new_uuid


class ScheduledJob(Base, TimestampMixin):
    __tablename__ = "scheduled_jobs"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_scheduled_job_user_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    cron_expression: Mapped[str] = mapped_column(String(50), nullable=False)
    agent_slug: Mapped[str | None] = mapped_column(String(100))
    task_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="scheduled_jobs")  # noqa: F821

    def __repr__(self) -> str:
        return f"<ScheduledJob {self.name!r} id={self.id!r}>"
