"""Task model."""

import enum

from sqlalchemy import JSON, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from angie.db.session import Base
from angie.models.base import TimestampMixin, new_uuid


class TaskStatus(enum.StrEnum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class Task(Base, TimestampMixin):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    agent_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("agents.id"))
    workflow_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("workflows.id"))
    celery_task_id: Mapped[str | None] = mapped_column(String(255), index=True)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, values_callable=lambda obj: [e.value for e in obj]),
        default=TaskStatus.PENDING, nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    input_data: Mapped[dict] = mapped_column(JSON, default=dict)
    output_data: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    source_channel: Mapped[str | None] = mapped_column(String(50))
    retry_count: Mapped[int] = mapped_column(default=0)

    user: Mapped["User"] = relationship(back_populates="tasks")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Task {self.id!r} status={self.status!r}>"
