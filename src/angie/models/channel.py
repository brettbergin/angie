"""Channel configuration model."""

import enum

from sqlalchemy import JSON, Boolean, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from angie.db.session import Base
from angie.models.base import TimestampMixin, new_uuid


class ChannelType(enum.StrEnum):
    SLACK = "slack"
    DISCORD = "discord"
    IMESSAGE = "imessage"
    EMAIL = "email"
    WEB = "web"


class ChannelConfig(Base, TimestampMixin):
    __tablename__ = "channel_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    type: Mapped[ChannelType] = mapped_column(
        Enum(ChannelType, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        index=True,
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    config: Mapped[dict] = mapped_column(JSON, default=dict)

    user: Mapped["User"] = relationship(back_populates="channel_configs")  # noqa: F821

    def __repr__(self) -> str:
        return f"<ChannelConfig type={self.type!r} user={self.user_id!r}>"
