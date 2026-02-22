"""Prompt model."""

import enum

from sqlalchemy import Boolean, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from angie.db.session import Base
from angie.models.base import TimestampMixin, new_uuid


class PromptType(enum.StrEnum):
    SYSTEM = "system"
    ANGIE = "angie"
    AGENT = "agent"
    USER = "user"


class Prompt(Base, TimestampMixin):
    __tablename__ = "prompts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"))
    agent_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("agents.id"))
    type: Mapped[PromptType] = mapped_column(
        Enum(PromptType, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(default=1)

    user: Mapped["User"] = relationship(back_populates="prompts")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Prompt type={self.type!r} name={self.name!r}>"
