"""add connections table

Revision ID: a1b2c3d4e5f6
Revises: 5b015091bf9f
Create Date: 2026-02-22 00:20:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "5b015091bf9f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "connections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("service_type", sa.String(50), nullable=False, index=True),
        sa.Column("display_name", sa.String(100), nullable=True),
        sa.Column("auth_type", sa.String(20), nullable=False),
        sa.Column("credentials_encrypted", sa.Text(), nullable=False),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refresh_token_encrypted", sa.Text(), nullable=True),
        sa.Column("scopes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="connected"),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint("user_id", "service_type", name="uq_user_service"),
    )


def downgrade() -> None:
    op.drop_table("connections")
