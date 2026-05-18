"""Update action_execution status constraint for M5.

Revision ID: update_action_status_constraint
Revises: add_action_retry_fields
Create Date: 2026-05-18

Updates execution_status check constraint to support:
- action_pending (waiting for async execution)
- action_running (Celery task executing)
- action_failed (execution failed, retryable)
- timeout (task timeout, retryable)
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'update_action_status_constraint'
down_revision: Union[str, None] = 'add_action_retry_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Update execution_status check constraint."""

    # Drop old check constraint
    op.drop_constraint(
        'ck_action_execution_status',
        'action_execution',
        schema='application'
    )

    # Create new check constraint with extended status values
    op.create_check_constraint(
        'ck_action_execution_status',
        'action_execution',
        "execution_status IN ('pending', 'action_pending', 'action_running', 'executed', 'action_failed', 'timeout', 'success', 'failed')",
        schema='application'
    )

    # Drop old decision_case status check constraint
    op.drop_constraint(
        'ck_decision_case_status',
        'decision_case',
        schema='application'
    )

    # Create new check constraint with extended status values
    op.create_check_constraint(
        'ck_decision_case_status',
        'decision_case',
        "status IN ('pending', 'recommended', 'approved', 'rejected', 'action_pending', 'action_running', 'executed', 'action_failed', 'completed', 'failed')",
        schema='application'
    )


def downgrade() -> None:
    """Revert to original status constraints."""

    # Drop new constraints
    op.drop_constraint(
        'ck_action_execution_status',
        'action_execution',
        schema='application'
    )

    op.drop_constraint(
        'ck_decision_case_status',
        'decision_case',
        schema='application'
    )

    # Restore original constraints
    op.create_check_constraint(
        'ck_action_execution_status',
        'action_execution',
        "execution_status IN ('pending', 'success', 'failed', 'timeout')",
        schema='application'
    )

    op.create_check_constraint(
        'ck_decision_case_status',
        'decision_case',
        "status IN ('pending', 'recommended', 'approved', 'rejected', 'executed', 'completed', 'failed')",
        schema='application'
    )