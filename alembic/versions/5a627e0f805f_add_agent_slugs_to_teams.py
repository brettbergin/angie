"""add agent_slugs to teams

Revision ID: 5a627e0f805f
Revises: 0001_initial
Create Date: 2026-02-20 23:47:14.204770
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "5a627e0f805f"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("teams", sa.Column("agent_slugs", sa.JSON(), nullable=True))
    op.execute("UPDATE teams SET agent_slugs = '[]' WHERE agent_slugs IS NULL")
    op.alter_column("teams", "agent_slugs", nullable=False, existing_type=sa.JSON())


def downgrade() -> None:
    op.drop_column("teams", "agent_slugs")
    # ### end Alembic commands ###
