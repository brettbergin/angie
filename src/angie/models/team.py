"""Team and TeamAgent models."""

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from angie.db.session import Base
from angie.models.base import TimestampMixin, new_uuid


class TeamAgent(Base):
    """Association table linking teams to agents."""

    __tablename__ = "team_agents"

    team_id: Mapped[str] = mapped_column(String(36), ForeignKey("teams.id"), primary_key=True)
    agent_id: Mapped[str] = mapped_column(String(36), ForeignKey("agents.id"), primary_key=True)
    role: Mapped[str | None] = mapped_column(String(100))

    team: Mapped["Team"] = relationship(back_populates="team_agents")
    agent: Mapped["Agent"] = relationship(back_populates="team_agents")  # noqa: F821


class Team(Base, TimestampMixin):
    __tablename__ = "teams"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    goal: Mapped[str | None] = mapped_column(Text)
    agent_slugs: Mapped[list] = mapped_column(JSON, default=list)

    team_agents: Mapped[list[TeamAgent]] = relationship(
        back_populates="team", cascade="all, delete-orphan"
    )
    workflows: Mapped[list["Workflow"]] = relationship(back_populates="team")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Team {self.name!r}>"
