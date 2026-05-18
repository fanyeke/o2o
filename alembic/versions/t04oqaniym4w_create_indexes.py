"""create indexes

Revision ID: t04oqaniym4w
Revises: l1bh31djnsai
Create Date: 2026-05-17 13:00:00.000000
"""
from typing import Sequence, Union
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 't04oqaniym4w'
down_revision: Union[str, None] = 'l1bh31djnsai'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Additional performance indexes for staging tables
    # Index for querying by user and coupon (redeemed status check)
    op.create_index(
        'idx_user_coupon_redeemed',
        'coupon_receipt_event',
        ['user_id', 'coupon_id', 'is_redeemed'],
        schema='staging'
    )

    # Index for querying by merchant and coupon
    op.create_index(
        'idx_merchant_coupon',
        'coupon_receipt_event',
        ['merchant_id', 'coupon_id'],
        schema='staging'
    )

    # Index for date range queries on receipt events
    op.create_index(
        'idx_date_received',
        'coupon_receipt_event',
        ['date_received'],
        schema='staging'
    )

    # Index for querying by coupon in consumption events
    op.create_index(
        'idx_coupon_cons',
        'consumption_event',
        ['coupon_id'],
        schema='staging',
        postgresql_where='coupon_id IS NOT NULL'
    )

    # Additional performance indexes for feature tables
    # Index for health score queries
    op.create_index(
        'idx_health_score',
        'merchant_metrics',
        ['activity_health_score'],
        schema='feature'
    )

    # Index for last activity date queries
    op.create_index(
        'idx_last_activity',
        'merchant_metrics',
        ['last_activity_date'],
        schema='feature'
    )

    # Index for user redeemed rate queries
    op.create_index(
        'idx_redeemed_rate',
        'user_metrics',
        ['redeemed_rate_30d'],
        schema='feature'
    )

    # Index for coupon redeemed rate queries
    op.create_index(
        'idx_coupon_redeemed_rate',
        'coupon_metrics',
        ['redeemed_rate'],
        schema='feature'
    )

    # Index for coupon discount type queries
    op.create_index(
        'idx_discount_type',
        'coupon_metrics',
        ['discount_type'],
        schema='feature'
    )


def downgrade() -> None:
    # Drop staging table indexes
    op.drop_index('idx_date_received', table_name='coupon_receipt_event', schema='staging')
    op.drop_index('idx_merchant_coupon', table_name='coupon_receipt_event', schema='staging')
    op.drop_index('idx_user_coupon_redeemed', table_name='coupon_receipt_event', schema='staging')
    op.drop_index('idx_coupon_cons', table_name='consumption_event', schema='staging')

    # Drop feature table indexes
    op.drop_index('idx_discount_type', table_name='coupon_metrics', schema='feature')
    op.drop_index('idx_coupon_redeemed_rate', table_name='coupon_metrics', schema='feature')
    op.drop_index('idx_redeemed_rate', table_name='user_metrics', schema='feature')
    op.drop_index('idx_last_activity', table_name='merchant_metrics', schema='feature')
    op.drop_index('idx_health_score', table_name='merchant_metrics', schema='feature')