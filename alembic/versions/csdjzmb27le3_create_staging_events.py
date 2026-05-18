"""create staging events

Revision ID: csdjzmb27le3
Revises: 84a9ab83bcf4
Create Date: 2026-05-17 10:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'csdjzmb27le3'
down_revision: Union[str, None] = '84a9ab83bcf4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create staging schema
    op.execute(sa.schema.CreateSchema('staging'))

    # Create coupon_receipt_event table
    op.create_table('coupon_receipt_event',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.String(length=64), nullable=False),
        sa.Column('merchant_id', sa.String(length=64), nullable=False),
        sa.Column('coupon_id', sa.String(length=64), nullable=False),
        sa.Column('discount_rate', sa.String(length=64), nullable=True),
        sa.Column('distance', sa.Float(), nullable=True),
        sa.Column('date_received', sa.Date(), nullable=False),
        sa.Column('is_redeemed', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('date_redeemed', sa.Date(), nullable=True),
        sa.Column('redeem_days', sa.Integer(), nullable=True),
        sa.Column('predicted_probability', sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        schema='staging'
    )

    # Create indexes for coupon_receipt_event
    op.create_index('idx_user_date', 'coupon_receipt_event', ['user_id', 'date_received'], schema='staging')
    op.create_index('idx_merchant_date', 'coupon_receipt_event', ['merchant_id', 'date_received'], schema='staging')
    op.create_index('idx_coupon', 'coupon_receipt_event', ['coupon_id'], schema='staging')

    # Create consumption_event table
    op.create_table('consumption_event',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.String(length=64), nullable=False),
        sa.Column('merchant_id', sa.String(length=64), nullable=False),
        sa.Column('coupon_id', sa.String(length=64), nullable=True),
        sa.Column('discount_rate', sa.String(length=64), nullable=True),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('amount', sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        schema='staging'
    )

    # Create indexes for consumption_event
    op.create_index('idx_user_date_cons', 'consumption_event', ['user_id', 'date'], schema='staging')
    op.create_index('idx_merchant_date_cons', 'consumption_event', ['merchant_id', 'date'], schema='staging')


def downgrade() -> None:
    # Drop consumption_event indexes and table
    op.drop_index('idx_merchant_date_cons', table_name='consumption_event', schema='staging')
    op.drop_index('idx_user_date_cons', table_name='consumption_event', schema='staging')
    op.drop_table('consumption_event', schema='staging')

    # Drop coupon_receipt_event indexes and table
    op.drop_index('idx_coupon', table_name='coupon_receipt_event', schema='staging')
    op.drop_index('idx_merchant_date', table_name='coupon_receipt_event', schema='staging')
    op.drop_index('idx_user_date', table_name='coupon_receipt_event', schema='staging')
    op.drop_table('coupon_receipt_event', schema='staging')

    # Drop staging schema
    op.execute(sa.schema.DropSchema('staging', cascade=True))