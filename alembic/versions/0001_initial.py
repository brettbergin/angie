"""initial

Revision ID: 0001_initial
Revises: 
Create Date: 2025-01-01 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("username", sa.String(100), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("is_superuser", sa.Boolean(), default=False),
        sa.Column("timezone", sa.String(50), default="UTC"),
        sa.Column("preferred_channel", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), nullable=False),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("username"),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_username", "users", ["username"])

    op.create_table(
        "agents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("module_path", sa.String(255), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), default=True),
        sa.Column("capabilities", sa.JSON(), default=list),
        sa.Column("config", sa.JSON(), default=dict),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), nullable=False),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_agents_name", "agents", ["name"])
    op.create_index("ix_agents_slug", "agents", ["slug"])

    op.create_table(
        "teams",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("goal", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), nullable=False),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_teams_name", "teams", ["name"])
    op.create_index("ix_teams_slug", "teams", ["slug"])

    op.create_table(
        "team_agents",
        sa.Column("team_id", sa.String(36), sa.ForeignKey("teams.id"), primary_key=True),
        sa.Column("agent_id", sa.String(36), sa.ForeignKey("agents.id"), primary_key=True),
        sa.Column("role", sa.String(100), nullable=True),
    )

    op.create_table(
        "workflows",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("team_id", sa.String(36), sa.ForeignKey("teams.id"), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), default=True),
        sa.Column("trigger_event", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), nullable=False),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_workflows_name", "workflows", ["name"])
    op.create_index("ix_workflows_slug", "workflows", ["slug"])

    op.create_table(
        "tasks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("agent_id", sa.String(36), sa.ForeignKey("agents.id"), nullable=True),
        sa.Column("workflow_id", sa.String(36), sa.ForeignKey("workflows.id"), nullable=True),
        sa.Column("celery_task_id", sa.String(255), nullable=True),
        sa.Column(
            "status",
            sa.Enum("pending", "queued", "running", "success", "failure", "cancelled", "retrying"),
            nullable=False,
            default="pending",
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("input_data", sa.JSON(), default=dict),
        sa.Column("output_data", sa.JSON(), default=dict),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("source_channel", sa.String(50), nullable=True),
        sa.Column("retry_count", sa.Integer(), default=0),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_tasks_celery_task_id", "tasks", ["celery_task_id"])
    op.create_index("ix_tasks_status", "tasks", ["status"])

    op.create_table(
        "workflow_steps",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workflow_id", sa.String(36), sa.ForeignKey("workflows.id"), nullable=False),
        sa.Column("agent_id", sa.String(36), sa.ForeignKey("agents.id"), nullable=True),
        sa.Column("order", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("config", sa.JSON(), default=dict),
        sa.Column("on_failure", sa.String(20), default="stop"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), nullable=False),
    )

    op.create_table(
        "events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "type",
            sa.Enum(
                "user_message", "cron", "webhook", "task_complete",
                "task_failed", "system", "channel_message", "api_call",
            ),
            nullable=False,
        ),
        sa.Column("source_channel", sa.String(50), nullable=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("payload", sa.JSON(), default=dict),
        sa.Column("processed", sa.Boolean(), default=False),
        sa.Column("task_id", sa.String(36), sa.ForeignKey("tasks.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_events_type", "events", ["type"])
    op.create_index("ix_events_processed", "events", ["processed"])

    op.create_table(
        "prompts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("agent_id", sa.String(36), sa.ForeignKey("agents.id"), nullable=True),
        sa.Column(
            "type",
            sa.Enum("system", "angie", "agent", "user"),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("version", sa.Integer(), default=1),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_prompts_type", "prompts", ["type"])

    op.create_table(
        "channel_configs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "type",
            sa.Enum("slack", "discord", "imessage", "email", "web_chat"),
            nullable=False,
        ),
        sa.Column("is_enabled", sa.Boolean(), default=True),
        sa.Column("config", sa.JSON(), default=dict),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_channel_configs_type", "channel_configs", ["type"])


def downgrade() -> None:
    op.drop_table("channel_configs")
    op.drop_table("prompts")
    op.drop_table("events")
    op.drop_table("workflow_steps")
    op.drop_table("tasks")
    op.drop_table("workflows")
    op.drop_table("team_agents")
    op.drop_table("teams")
    op.drop_table("agents")
    op.drop_table("users")
