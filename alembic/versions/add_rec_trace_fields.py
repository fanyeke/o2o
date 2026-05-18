"""Add trace fields to recommendation for M7 observability.

Revision ID: add_rec_trace_fields
Revises: t1me_leak_fix001
Create Date: 2026-05-18

Adds trace fields for complete observability:
- rule_id: Trigger rule ID
- model_version: ML model version
- feature_version: Feature engineering version
- prediction_summary: ML prediction output
- prompt_version: Prompt template version
- llm_model: LLM model name
- llm_latency_ms: LLM latency in milliseconds
- approval_operator: Approval operator ID
- action_execution_id: Linked action execution ID
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'add_rec_trace_fields'
down_revision: Union[str, None] = 't1me_leak_fix001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add trace fields to recommendation table."""

    # Add rule_id column
    op.add_column(
        'recommendation',
        sa.Column('rule_id', sa.String(length=128), nullable=True),
        schema='application'
    )

    # Add model_version column
    op.add_column(
        'recommendation',
        sa.Column('model_version', sa.String(length=32), nullable=True),
        schema='application'
    )

    # Add feature_version column
    op.add_column(
        'recommendation',
        sa.Column('feature_version', sa.String(length=32), nullable=True),
        schema='application'
    )

    # Add prediction_summary column (JSON)
    op.add_column(
        'recommendation',
        sa.Column('prediction_summary', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        schema='application'
    )

    # Add prompt_version column
    op.add_column(
        'recommendation',
        sa.Column('prompt_version', sa.String(length=32), nullable=True),
        schema='application'
    )

    # Add llm_model column
    op.add_column(
        'recommendation',
        sa.Column('llm_model', sa.String(length=64), nullable=True),
        schema='application'
    )

    # Add llm_latency_ms column
    op.add_column(
        'recommendation',
        sa.Column('llm_latency_ms', sa.Integer(), nullable=True),
        schema='application'
    )

    # Add approval_operator column
    op.add_column(
        'recommendation',
        sa.Column('approval_operator', sa.String(length=64), nullable=True),
        schema='application'
    )

    # Add action_execution_id column
    op.add_column(
        'recommendation',
        sa.Column('action_execution_id', sa.BigInteger(), nullable=True),
        schema='application'
    )

    # Create indexes for queryable trace fields
    op.create_index(
        'idx_rule_id',
        'recommendation',
        ['rule_id'],
        schema='application'
    )

    op.create_index(
        'idx_llm_model',
        'recommendation',
        ['llm_model'],
        schema='application'
    )


def downgrade() -> None:
    """Remove trace fields from recommendation table."""

    # Drop indexes
    op.drop_index('idx_llm_model', table_name='recommendation', schema='application')
    op.drop_index('idx_rule_id', table_name='recommendation', schema='application')

    # Drop columns
    op.drop_column('recommendation', 'action_execution_id', schema='application')
    op.drop_column('recommendation', 'approval_operator', schema='application')
    op.drop_column('recommendation', 'llm_latency_ms', schema='application')
    op.drop_column('recommendation', 'llm_model', schema='application')
    op.drop_column('recommendation', 'prompt_version', schema='application')
    op.drop_column('recommendation', 'prediction_summary', schema='application')
    op.drop_column('recommendation', 'feature_version', schema='application')
    op.drop_column('recommendation', 'model_version', schema='application')
    op.drop_column('recommendation', 'rule_id', schema='application')