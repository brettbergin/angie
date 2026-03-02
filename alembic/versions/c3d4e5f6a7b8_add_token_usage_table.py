"""add token_usage table

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-03-01 18:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "token_usage",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("agent_slug", sa.String(length=100), nullable=True),
        sa.Column("provider", sa.String(length=50), nullable=True),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("request_count", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("tool_call_count", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("estimated_cost_usd", sa.Float(), nullable=True, server_default="0"),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("task_id", sa.String(length=36), nullable=True),
        sa.Column("conversation_id", sa.String(length=36), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_token_usage_user_id"), "token_usage", ["user_id"])
    op.create_index(op.f("ix_token_usage_agent_slug"), "token_usage", ["agent_slug"])
    op.create_index(op.f("ix_token_usage_task_id"), "token_usage", ["task_id"])
    op.create_index(
        op.f("ix_token_usage_conversation_id"), "token_usage", ["conversation_id"]
    )
    op.create_index(op.f("ix_token_usage_created_at"), "token_usage", ["created_at"])


def downgrade() -> None:
    op.drop_index(op.f("ix_token_usage_created_at"), table_name="token_usage")
    op.drop_index(op.f("ix_token_usage_conversation_id"), table_name="token_usage")
    op.drop_index(op.f("ix_token_usage_task_id"), table_name="token_usage")
    op.drop_index(op.f("ix_token_usage_agent_slug"), table_name="token_usage")
    op.drop_index(op.f("ix_token_usage_user_id"), table_name="token_usage")
    op.drop_table("token_usage")
