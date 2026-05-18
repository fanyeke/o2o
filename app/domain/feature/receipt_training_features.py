"""Domain model for receipt training features (time-leakage-safe).

This model represents features computed for ML training where ALL
historical features are computed using only data BEFORE each receipt's
date_received, preventing future data from leaking into training features.

Time leakage prevention rules:
1. All receipt counts/metrics use WHERE date_received < current receipt's date_received
2. All redeemed counts/metrics use WHERE is_redeemed=true AND date_redeemed < current receipt's date_received
3. No features can use information from the current receipt or future receipts
"""

from sqlalchemy import Column, String, Integer, Float, Boolean, Date, TIMESTAMP, text
from app.db.base import Base


class ReceiptTrainingFeatures(Base):
    """Time-leakage-safe features for ML model training.

    Each row represents features for a single receipt event, computed
    using only historical data available BEFORE that receipt's date_received.

    Example:
        Receipt ID: user123_merchant456_coupon789_20160515
        as_of_date: 2016-05-15

        user_redeemed_rate_30d_before: computed from receipts
            WHERE user_id=user123 AND date_received < 2016-05-15
            AND date_received >= 2016-04-15

        merchant_redeemed_count_7d_before: computed from receipts
            WHERE merchant_id=merchant456 AND date_received < 2016-05-15
            AND date_received >= 2016-05-08
            AND (is_redeemed=false OR date_redeemed < 2016-05-15)

    This ensures no future information leaks into training features.
    """

    __tablename__ = "receipt_training_features"
    __table_args__ = {"schema": "feature"}

    # Primary identifiers
    receipt_id = Column(String(128), primary_key=True, nullable=False)
    user_id = Column(String(64), nullable=False)
    merchant_id = Column(String(64), nullable=False)
    coupon_id = Column(String(64), nullable=False)
    as_of_date = Column(Date, nullable=False)

    # User historical features (as-of as_of_date)
    user_receipts_30d_before = Column(Integer, nullable=True)
    user_redeemed_count_30d_before = Column(Integer, nullable=True)
    user_redeemed_rate_30d_before = Column(Float, nullable=True)
    user_avg_distance_before = Column(Float, nullable=True)

    # Merchant historical features (as-of as_of_date)
    merchant_receipts_7d_before = Column(Integer, nullable=True)
    merchant_redeemed_count_7d_before = Column(Integer, nullable=True)
    merchant_redeemed_rate_7d_before = Column(Float, nullable=True)
    merchant_receipts_30d_before = Column(Integer, nullable=True)
    merchant_redeemed_count_30d_before = Column(Integer, nullable=True)
    merchant_redeemed_rate_30d_before = Column(Float, nullable=True)
    merchant_avg_discount_depth_before = Column(Float, nullable=True)

    # Coupon historical features (as-of as_of_date)
    coupon_total_receipts_before = Column(Integer, nullable=True)
    coupon_redeemed_count_before = Column(Integer, nullable=True)
    coupon_redeemed_rate_before = Column(Float, nullable=True)
    coupon_avg_redeem_days_before = Column(Float, nullable=True)

    # Static receipt features
    discount_type = Column(String(20), nullable=True)
    discount_value = Column(Float, nullable=True)
    threshold_amount = Column(Float, nullable=True)
    discount_amount = Column(Float, nullable=True)
    distance = Column(Integer, nullable=True)

    # Time features
    day_of_week = Column(Integer, nullable=True)
    month = Column(Integer, nullable=True)
    day_of_month = Column(Integer, nullable=True)

    # Target label
    label_is_redeemed = Column(Boolean, nullable=True)

    # Metadata
    feature_version = Column(String(32), nullable=False, server_default="v1_time_safe")
    computed_at = Column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    def __repr__(self):
        return f"<ReceiptTrainingFeatures(receipt_id={self.receipt_id}, as_of_date={self.as_of_date}, redeemed={self.label_is_redeemed})>"