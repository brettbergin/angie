"""Agent model."""

from sqlalchemy import JSON, Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from angie.db.session import Base
from angie.models.base import TimestampMixin, new_uuid


class Agent(Base, TimestampMixin):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    module_path: Mapped[str] = mapped_column(String(255), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    capabilities: Mapped[list] = mapped_column(JSON, default=list)
    config: Mapped[dict] = mapped_column(JSON, default=dict)

    # Relationships
    team_agents: Mapped[list["TeamAgent"]] = relationship(back_populates="agent")  # noqa: F821
    workflow_steps: Mapped[list["WorkflowStep"]] = relationship(back_populates="agent")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Agent {self.name!r}>"
