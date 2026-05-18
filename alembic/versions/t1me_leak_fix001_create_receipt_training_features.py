"""create receipt_training_features for time leakage fix

Revision ID: t1me_leak_fix001
Revises: 20cd7d1bc6cf
Create Date: 2026-05-18 12:00:00.000000

This migration creates a time-leakage-safe feature table for ML training.
All features are computed using only data BEFORE each receipt's date_received,
preventing future data from leaking into training features.

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 't1me_leak_fix001'
down_revision: Union[str, None] = '20cd7d1bc6cf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create receipt_training_features table in feature schema
    # This table stores time-leakage-safe features for ML model training
    op.create_table(
        'receipt_training_features',
        # Primary identifiers
        sa.Column('receipt_id', sa.String(length=128), nullable=False),
        sa.Column('user_id', sa.String(length=64), nullable=False),
        sa.Column('merchant_id', sa.String(length=64), nullable=False),
        sa.Column('coupon_id', sa.String(length=64), nullable=False),
        sa.Column('as_of_date', sa.Date(), nullable=False),

        # User historical features (computed as-of as_of_date)
        sa.Column('user_receipts_30d_before', sa.Integer(), nullable=True),
        sa.Column('user_redeemed_count_30d_before', sa.Integer(), nullable=True),
        sa.Column('user_redeemed_rate_30d_before', sa.Float(), nullable=True),
        sa.Column('user_avg_distance_before', sa.Float(), nullable=True),

        # Merchant historical features (computed as-of as_of_date)
        sa.Column('merchant_receipts_7d_before', sa.Integer(), nullable=True),
        sa.Column('merchant_redeemed_count_7d_before', sa.Integer(), nullable=True),
        sa.Column('merchant_redeemed_rate_7d_before', sa.Float(), nullable=True),
        sa.Column('merchant_receipts_30d_before', sa.Integer(), nullable=True),
        sa.Column('merchant_redeemed_count_30d_before', sa.Integer(), nullable=True),
        sa.Column('merchant_redeemed_rate_30d_before', sa.Float(), nullable=True),
        sa.Column('merchant_avg_discount_depth_before', sa.Float(), nullable=True),

        # Coupon historical features (computed as-of as_of_date)
        sa.Column('coupon_total_receipts_before', sa.Integer(), nullable=True),
        sa.Column('coupon_redeemed_count_before', sa.Integer(), nullable=True),
        sa.Column('coupon_redeemed_rate_before', sa.Float(), nullable=True),
        sa.Column('coupon_avg_redeem_days_before', sa.Float(), nullable=True),

        # Static receipt features (not affected by time leakage)
        sa.Column('discount_type', sa.String(length=20), nullable=True),
        sa.Column('discount_value', sa.Float(), nullable=True),
        sa.Column('threshold_amount', sa.Float(), nullable=True),
        sa.Column('discount_amount', sa.Float(), nullable=True),
        sa.Column('distance', sa.Integer(), nullable=True),

        # Time features
        sa.Column('day_of_week', sa.Integer(), nullable=True),
        sa.Column('month', sa.Integer(), nullable=True),
        sa.Column('day_of_month', sa.Integer(), nullable=True),

        # Target label
        sa.Column('label_is_redeemed', sa.Boolean(), nullable=True),

        # Metadata
        sa.Column('feature_version', sa.String(length=32), nullable=False, server_default='v1_time_safe'),
        sa.Column('computed_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),

        sa.PrimaryKeyConstraint('receipt_id'),
        schema='feature'
    )

    # Create indexes for efficient queries
    op.create_index(
        'idx_receipt_training_as_of_date',
        'receipt_training_features',
        ['as_of_date'],
        schema='feature'
    )

    op.create_index(
        'idx_receipt_training_merchant_date',
        'receipt_training_features',
        ['merchant_id', 'as_of_date'],
        schema='feature'
    )

    op.create_index(
        'idx_receipt_training_user_date',
        'receipt_training_features',
        ['user_id', 'as_of_date'],
        schema='feature'
    )

    op.create_index(
        'idx_receipt_training_coupon_date',
        'receipt_training_features',
        ['coupon_id', 'as_of_date'],
        schema='feature'
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_receipt_training_coupon_date', table_name='receipt_training_features', schema='feature')
    op.drop_index('idx_receipt_training_user_date', table_name='receipt_training_features', schema='feature')
    op.drop_index('idx_receipt_training_merchant_date', table_name='receipt_training_features', schema='feature')
    op.drop_index('idx_receipt_training_as_of_date', table_name='receipt_training_features', schema='feature')

    # Drop table
    op.drop_table('receipt_training_features', schema='feature')