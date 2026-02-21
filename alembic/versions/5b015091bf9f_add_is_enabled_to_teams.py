"""add is_enabled to teams

Revision ID: 5b015091bf9f
Revises: d98b34da3ebf
Create Date: 2026-02-21 23:36:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "5b015091bf9f"
down_revision: Union[str, None] = "d98b34da3ebf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "teams",
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    op.drop_column("teams", "is_enabled")
