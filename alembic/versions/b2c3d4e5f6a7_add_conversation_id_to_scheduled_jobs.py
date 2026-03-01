"""add conversation_id to scheduled_jobs

Revision ID: b2c3d4e5f6a7
Revises: f7a8b9c0d1e2
Create Date: 2026-03-01 12:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "f7a8b9c0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "scheduled_jobs",
        sa.Column("conversation_id", sa.String(length=36), nullable=True),
    )
    op.create_foreign_key(
        "fk_scheduled_jobs_conversation_id",
        "scheduled_jobs",
        "conversations",
        ["conversation_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_scheduled_jobs_conversation_id", "scheduled_jobs", type_="foreignkey")
    op.drop_column("scheduled_jobs", "conversation_id")
