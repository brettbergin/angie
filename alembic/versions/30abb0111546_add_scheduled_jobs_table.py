"""add scheduled_jobs table

Revision ID: 30abb0111546
Revises: 3b063372af07
Create Date: 2026-02-21 23:15:25.784618
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '30abb0111546'
down_revision: Union[str, None] = '3b063372af07'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('scheduled_jobs',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('cron_expression', sa.String(length=50), nullable=False),
    sa.Column('agent_slug', sa.String(length=100), nullable=True),
    sa.Column('task_payload', sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default=sa.text('1')),
    sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('next_run_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'name', name='uq_scheduled_job_user_name')
    )
    op.create_index(op.f('ix_scheduled_jobs_is_enabled'), 'scheduled_jobs', ['is_enabled'], unique=False)
    op.create_index(op.f('ix_scheduled_jobs_user_id'), 'scheduled_jobs', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_scheduled_jobs_user_id'), table_name='scheduled_jobs')
    op.drop_index(op.f('ix_scheduled_jobs_is_enabled'), table_name='scheduled_jobs')
    op.drop_table('scheduled_jobs')
