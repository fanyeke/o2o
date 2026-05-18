"""create application tables

Revision ID: l1bh31djnsai
Revises: pei3cdtab9wt
Create Date: 2026-05-17 12:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'l1bh31djnsai'
down_revision: Union[str, None] = 'pei3cdtab9wt'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create application schema
    op.execute(sa.schema.CreateSchema('application'))

    # Create decision_case table
    op.create_table('decision_case',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('case_type', sa.String(length=32), nullable=False),
        sa.Column('severity_level', sa.String(length=16), nullable=True),
        sa.Column('merchant_id', sa.String(length=64), nullable=True),
        sa.Column('coupon_id', sa.String(length=64), nullable=True),
        sa.Column('user_id', sa.String(length=64), nullable=True),
        sa.Column('trigger_rule_id', sa.String(length=128), nullable=True),
        sa.Column('trigger_metrics_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            "case_type IN ('商户异常', '券策略复核', '用户召回')",
            name='ck_decision_case_case_type'
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'recommended', 'approved', 'rejected', 'executed', 'completed', 'failed')",
            name='ck_decision_case_status'
        ),
        schema='application'
    )

    # Create indexes for decision_case
    op.create_index('idx_merchant_status', 'decision_case', ['merchant_id', 'status'], schema='application')
    op.create_index('idx_status_created', 'decision_case', ['status', 'created_at'], schema='application')
    op.create_index('idx_type_date', 'decision_case', ['case_type', 'created_at'], schema='application')

    # Create recommendation table
    op.create_table('recommendation',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('case_id', sa.BigInteger(), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('evidence_list', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('suggested_actions', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('risk_alerts', sa.Text(), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=False),
        sa.Column('requires_approval', sa.Boolean(), nullable=False),
        sa.Column('tool_trace', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('llm_raw_output', sa.Text(), nullable=True),
        sa.Column('llm_tokens_used', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['case_id'], ['application.decision_case.id'], ondelete='CASCADE'),
        sa.CheckConstraint(
            "confidence_score >= 0.0 AND confidence_score <= 1.0",
            name='ck_recommendation_confidence_score'
        ),
        schema='application'
    )

    # Create indexes for recommendation
    op.create_index('idx_case', 'recommendation', ['case_id'], schema='application')
    op.create_index('idx_created', 'recommendation', ['created_at'], schema='application')

    # Create action_execution table
    op.create_table('action_execution',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('case_id', sa.BigInteger(), nullable=False),
        sa.Column('recommendation_id', sa.BigInteger(), nullable=False),
        sa.Column('action_type', sa.String(length=64), nullable=False),
        sa.Column('action_params', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('execution_status', sa.String(length=32), nullable=True, server_default='pending'),
        sa.Column('execution_result', sa.Text(), nullable=True),
        sa.Column('executed_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['case_id'], ['application.decision_case.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['recommendation_id'], ['application.recommendation.id'], ondelete='CASCADE'),
        sa.CheckConstraint(
            "action_type IN ('暂停活动', '调整折扣', '发送优惠券', '调整人群')",
            name='ck_action_execution_action_type'
        ),
        sa.CheckConstraint(
            "execution_status IN ('pending', 'success', 'failed', 'timeout')",
            name='ck_action_execution_status'
        ),
        schema='application'
    )

    # Create indexes for action_execution
    op.create_index('idx_case_status', 'action_execution', ['case_id', 'execution_status'], schema='application')

    # Create approval_log table
    op.create_table('approval_log',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('case_id', sa.BigInteger(), nullable=False),
        sa.Column('operator_id', sa.String(length=64), nullable=False),
        sa.Column('operator_name', sa.String(length=128), nullable=True),
        sa.Column('action', sa.String(length=32), nullable=False),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('previous_status', sa.String(length=32), nullable=True),
        sa.Column('new_status', sa.String(length=32), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['case_id'], ['application.decision_case.id'], ondelete='CASCADE'),
        sa.CheckConstraint(
            "action IN ('approve', 'reject', 'regenerate', 'execute')",
            name='ck_approval_log_action'
        ),
        schema='application'
    )

    # Create indexes for approval_log
    op.create_index('idx_case_created', 'approval_log', ['case_id', 'created_at'], schema='application')
    op.create_index('idx_operator', 'approval_log', ['operator_id'], schema='application')


def downgrade() -> None:
    # Drop approval_log indexes and table
    op.drop_index('idx_operator', table_name='approval_log', schema='application')
    op.drop_index('idx_case_created', table_name='approval_log', schema='application')
    op.drop_table('approval_log', schema='application')

    # Drop action_execution index and table
    op.drop_index('idx_case_status', table_name='action_execution', schema='application')
    op.drop_table('action_execution', schema='application')

    # Drop recommendation indexes and table
    op.drop_index('idx_created', table_name='recommendation', schema='application')
    op.drop_index('idx_case', table_name='recommendation', schema='application')
    op.drop_table('recommendation', schema='application')

    # Drop decision_case indexes and table
    op.drop_index('idx_type_date', table_name='decision_case', schema='application')
    op.drop_index('idx_status_created', table_name='decision_case', schema='application')
    op.drop_index('idx_merchant_status', table_name='decision_case', schema='application')
    op.drop_table('decision_case', schema='application')

    # Drop application schema
    op.execute(sa.schema.DropSchema('application', cascade=True))