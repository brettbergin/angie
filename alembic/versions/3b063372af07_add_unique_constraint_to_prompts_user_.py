"""add unique constraint to prompts user_id type name

Revision ID: 3b063372af07
Revises: a1b2c3d4e5f6
Create Date: 2026-02-21 22:55:15.821169
"""

from typing import Sequence, Union

from alembic import op

revision: str = "3b063372af07"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_prompt_user_type_name", "prompts", ["user_id", "type", "name"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_prompt_user_type_name", "prompts", type_="unique")
