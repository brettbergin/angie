"""Connection model — per-user credential storage for service integrations."""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from angie.db.session import Base
from angie.models.base import TimestampMixin, new_uuid


class ConnectionStatus(enum.StrEnum):
    CONNECTED = "connected"
    EXPIRED = "expired"
    ERROR = "error"
    DISCONNECTED = "disconnected"


class AuthType(enum.StrEnum):
    OAUTH2 = "oauth2"
    API_KEY = "api_key"
    TOKEN = "token"
    CREDENTIALS = "credentials"


class Connection(Base, TimestampMixin):
    __tablename__ = "connections"
    __table_args__ = (UniqueConstraint("user_id", "service_type", name="uq_user_service"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    service_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    display_name: Mapped[str | None] = mapped_column(String(100))
    auth_type: Mapped[AuthType] = mapped_column(
        Enum(
            AuthType,
            native_enum=False,
            length=20,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )
    credentials_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    refresh_token_encrypted: Mapped[str | None] = mapped_column(Text)
    scopes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ConnectionStatus] = mapped_column(
        Enum(
            ConnectionStatus,
            native_enum=False,
            length=20,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        default=ConnectionStatus.CONNECTED,
        server_default=ConnectionStatus.CONNECTED.value,
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict | None] = mapped_column(JSON)

    def __repr__(self) -> str:
        return f"<Connection {self.service_type!r} user={self.user_id!r} status={self.status!r}>"
