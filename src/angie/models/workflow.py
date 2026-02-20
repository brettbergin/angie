"""Workflow and WorkflowStep models."""

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from angie.db.session import Base
from angie.models.base import TimestampMixin, new_uuid


class WorkflowStep(Base, TimestampMixin):
    __tablename__ = "workflow_steps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    workflow_id: Mapped[str] = mapped_column(String(36), ForeignKey("workflows.id"), nullable=False)
    agent_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("agents.id"))
    order: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    on_failure: Mapped[str] = mapped_column(String(20), default="stop")  # stop | continue | retry

    workflow: Mapped["Workflow"] = relationship(back_populates="steps")
    agent: Mapped["Agent"] = relationship(back_populates="workflow_steps")  # noqa: F821


class Workflow(Base, TimestampMixin):
    __tablename__ = "workflows"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    team_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("teams.id"))
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    trigger_event: Mapped[str | None] = mapped_column(String(100))

    team: Mapped["Team"] = relationship(back_populates="workflows")  # noqa: F821
    steps: Mapped[list[WorkflowStep]] = relationship(
        back_populates="workflow",
        order_by="WorkflowStep.order",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Workflow {self.name!r}>"
