"""create feature metrics

Revision ID: pei3cdtab9wt
Revises: csdjzmb27le3
Create Date: 2026-05-17 11:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'pei3cdtab9wt'
down_revision: Union[str, None] = 'csdjzmb27le3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create feature schema
    op.execute(sa.schema.CreateSchema('feature'))

    # Create merchant_metrics table
    op.create_table('merchant_metrics',
        sa.Column('merchant_id', sa.String(length=64), nullable=False),
        sa.Column('total_receipts_7d', sa.Integer(), nullable=True),
        sa.Column('redeemed_count_7d', sa.Integer(), nullable=True),
        sa.Column('redeemed_rate_7d', sa.Float(), nullable=True),
        sa.Column('total_receipts_30d', sa.Integer(), nullable=True),
        sa.Column('redeemed_count_30d', sa.Integer(), nullable=True),
        sa.Column('redeemed_rate_30d', sa.Float(), nullable=True),
        sa.Column('redeemed_rate_change', sa.Float(), nullable=True),
        sa.Column('avg_discount_depth', sa.Float(), nullable=True),
        sa.Column('total_coupons_types', sa.Integer(), nullable=True),
        sa.Column('activity_health_score', sa.Float(), nullable=True),
        sa.Column('last_activity_date', sa.Date(), nullable=True),
        sa.Column('updated_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('merchant_id'),
        schema='feature'
    )

    # Create user_metrics table
    op.create_table('user_metrics',
        sa.Column('user_id', sa.String(length=64), nullable=False),
        sa.Column('total_receipts_30d', sa.Integer(), nullable=True),
        sa.Column('redeemed_count_30d', sa.Integer(), nullable=True),
        sa.Column('redeemed_rate_30d', sa.Float(), nullable=True),
        sa.Column('avg_distance', sa.Float(), nullable=True),
        sa.Column('last_receipt_date', sa.Date(), nullable=True),
        sa.Column('updated_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('user_id'),
        schema='feature'
    )

    # Create coupon_metrics table
    op.create_table('coupon_metrics',
        sa.Column('coupon_id', sa.String(length=64), nullable=False),
        sa.Column('merchant_id', sa.String(length=64), nullable=False),
        sa.Column('discount_type', sa.String(length=32), nullable=True),
        sa.Column('discount_rate', sa.String(length=64), nullable=True),
        sa.Column('discount_value', sa.Float(), nullable=True),
        sa.Column('threshold_amount', sa.Float(), nullable=True),
        sa.Column('discount_amount', sa.Float(), nullable=True),
        sa.Column('total_receipts', sa.Integer(), nullable=True),
        sa.Column('redeemed_count', sa.Integer(), nullable=True),
        sa.Column('redeemed_rate', sa.Float(), nullable=True),
        sa.Column('avg_redeem_days', sa.Float(), nullable=True),
        sa.Column('updated_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('coupon_id'),
        schema='feature'
    )

    # Create indexes for foreign keys
    op.create_index('idx_merchant_id', 'coupon_metrics', ['merchant_id'], schema='feature')


def downgrade() -> None:
    # Drop coupon_metrics index and table
    op.drop_index('idx_merchant_id', table_name='coupon_metrics', schema='feature')
    op.drop_table('coupon_metrics', schema='feature')

    # Drop user_metrics table
    op.drop_table('user_metrics', schema='feature')

    # Drop merchant_metrics table
    op.drop_table('merchant_metrics', schema='feature')

    # Drop feature schema
    op.execute(sa.schema.DropSchema('feature', cascade=True))