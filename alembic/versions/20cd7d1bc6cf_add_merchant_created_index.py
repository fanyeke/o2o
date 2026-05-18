"""add merchant_created composite index

Task: T119 - Add composite index for case search optimization
Phase: 6 - US4 案例检索功能

Revision ID: 20cd7d1bc6cf
Revises: t04oqaniym4w
Create Date: 2026-05-17 23:32:17.111487
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20cd7d1bc6cf'
down_revision: Union[str, None] = 't04oqaniym4w'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add composite index for merchant_id and created_at (T119).

    This index optimizes queries that filter by merchant_id and sort by created_at,
    which is a common pattern in case search operations.
    """
    # Create composite index for merchant_id and created_at
    # This optimizes queries filtering by merchant and ordering by date
    op.create_index(
        'idx_merchant_created',
        'decision_case',
        ['merchant_id', 'created_at'],
        schema='application'
    )


def downgrade() -> None:
    """Remove the composite index."""
    op.drop_index('idx_merchant_created', table_name='decision_case', schema='application')
