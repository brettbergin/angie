"""add agent_slug to chat_messages

Revision ID: f7a8b9c0d1e2
Revises: 30abb0111546
Create Date: 2026-02-28 12:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f7a8b9c0d1e2"
down_revision: Union[str, None] = "30abb0111546"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "chat_messages",
        sa.Column("agent_slug", sa.String(length=100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("chat_messages", "agent_slug")
