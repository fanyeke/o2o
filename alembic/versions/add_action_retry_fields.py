"""Add retry support fields to action_execution.

Revision ID: add_action_retry_fields
Revises: add_rec_trace_fields
Create Date: 2026-05-18

Adds fields for action execution retry support:
- idempotency_key: Unique key to prevent duplicate execution
- retry_count: Current retry attempt count
- max_retries: Maximum allowed retries (default 3)
- created_at: Creation timestamp
- updated_at: Last update timestamp
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_action_retry_fields'
down_revision: Union[str, None] = 'add_rec_trace_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add retry support fields to action_execution table."""

    # Add idempotency_key column
    op.add_column(
        'action_execution',
        sa.Column('idempotency_key', sa.String(length=255), nullable=True),
        schema='application'
    )

    # Add retry_count column
    op.add_column(
        'action_execution',
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        schema='application'
    )

    # Add max_retries column
    op.add_column(
        'action_execution',
        sa.Column('max_retries', sa.Integer(), nullable=False, server_default='3'),
        schema='application'
    )

    # Add created_at column
    op.add_column(
        'action_execution',
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        schema='application'
    )

    # Add updated_at column
    op.add_column(
        'action_execution',
        sa.Column('updated_at', sa.TIMESTAMP(), nullable=True),
        schema='application'
    )

    # Create unique index for idempotency_key
    op.create_index(
        'idx_idempotency_key',
        'action_execution',
        ['idempotency_key'],
        unique=True,
        schema='application'
    )

    # Update execution_status to be NOT NULL with default
    op.alter_column(
        'action_execution',
        'execution_status',
        existing_type=sa.String(length=32),
        nullable=False,
        server_default='pending',
        schema='application'
    )


def downgrade() -> None:
    """Remove retry support fields from action_execution table."""

    # Drop index
    op.drop_index('idx_idempotency_key', table_name='action_execution', schema='application')

    # Revert execution_status nullable
    op.alter_column(
        'action_execution',
        'execution_status',
        existing_type=sa.String(length=32),
        nullable=True,
        schema='application'
    )

    # Drop columns
    op.drop_column('action_execution', 'updated_at', schema='application')
    op.drop_column('action_execution', 'created_at', schema='application')
    op.drop_column('action_execution', 'max_retries', schema='application')
    op.drop_column('action_execution', 'retry_count', schema='application')
    op.drop_column('action_execution', 'idempotency_key', schema='application')