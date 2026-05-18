"""Add indexes for time-safe feature computation performance."""

from alembic import op
import sqlalchemy as sa

revision = 'add_time_safe_indexes'
down_revision = 'add_m4_high_standard_fields'
branch_labels = None
depends_on = None

def upgrade():
    # User index: user_id + date_received + date_redeemed
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_receipt_event_user_date
        ON staging.coupon_receipt_event (user_id, date_received, date_redeemed)
    """)

    # Merchant index: merchant_id + date_received + date_redeemed
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_receipt_event_merchant_date
        ON staging.coupon_receipt_event (merchant_id, date_received, date_redeemed)
    """)

    # Coupon index: coupon_id + date_received + date_redeemed
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_receipt_event_coupon_date
        ON staging.coupon_receipt_event (coupon_id, date_received, date_redeemed)
    """)

    # Composite index for feature queries
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_receipt_event_composite
        ON staging.coupon_receipt_event (user_id, merchant_id, coupon_id, date_received)
    """)

def downgrade():
    op.execute("DROP INDEX IF EXISTS staging.idx_receipt_event_user_date")
    op.execute("DROP INDEX IF EXISTS staging.idx_receipt_event_merchant_date")
    op.execute("DROP INDEX IF EXISTS staging.idx_receipt_event_coupon_date")
    op.execute("DROP INDEX IF EXISTS staging.idx_receipt_event_composite")