"""Add M4 high standard fields to recommendation.

Revision ID: add_m4_high_standard_fields
Revises: add_action_retry_fields
Create Date: 2026-05-18

Adds fields for M4 high standard enhanced analysis:
- model_signal: ML prediction signal (prediction_score, signal_type, confidence_interval)
- business_risk: Business risk assessment (risk_level, potential_revenue_impact, affected_users)
- limitations: Analysis limitations list
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'add_m4_high_standard_fields'
down_revision: Union[str, None] = 'update_action_status_constraint'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add M4 high standard fields to recommendation table."""

    # Add model_signal column (JSON)
    op.add_column(
        'recommendation',
        sa.Column('model_signal', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        schema='application'
    )

    # Add business_risk column (JSON)
    op.add_column(
        'recommendation',
        sa.Column('business_risk', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        schema='application'
    )

    # Add limitations column (JSON)
    op.add_column(
        'recommendation',
        sa.Column('limitations', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        schema='application'
    )


def downgrade() -> None:
    """Remove M4 high standard fields from recommendation table."""

    op.drop_column('recommendation', 'limitations', schema='application')
    op.drop_column('recommendation', 'business_risk', schema='application')
    op.drop_column('recommendation', 'model_signal', schema='application')