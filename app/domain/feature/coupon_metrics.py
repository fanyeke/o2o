from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey
from app.db.base import Base


class CouponMetrics(Base):
    __tablename__ = "coupon_metrics"
    __table_args__ = {"schema": "feature"}

    coupon_id = Column(String(64), primary_key=True)
    merchant_id = Column(String(64), ForeignKey("feature.merchant_metrics.merchant_id"), nullable=False)
    discount_type = Column(String(64), nullable=True)
    discount_rate = Column(String(64), nullable=True)
    discount_value = Column(Float, nullable=True)
    threshold_amount = Column(Float, nullable=True)
    discount_amount = Column(Float, nullable=True)
    total_receipts = Column(Integer, nullable=True)
    redeemed_count = Column(Integer, nullable=True)
    redeemed_rate = Column(Float, nullable=True)
    avg_redeem_days = Column(Float, nullable=True)
    updated_at = Column(DateTime, nullable=True)