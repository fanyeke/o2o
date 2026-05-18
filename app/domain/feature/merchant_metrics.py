from sqlalchemy import Column, String, Integer, Float, Date, DateTime
from app.db.base import Base


class MerchantMetrics(Base):
    __tablename__ = "merchant_metrics"
    __table_args__ = {"schema": "feature"}

    merchant_id = Column(String(64), primary_key=True)
    total_receipts_7d = Column(Integer, nullable=True)
    redeemed_count_7d = Column(Integer, nullable=True)
    redeemed_rate_7d = Column(Float, nullable=True)
    total_receipts_30d = Column(Integer, nullable=True)
    redeemed_count_30d = Column(Integer, nullable=True)
    redeemed_rate_30d = Column(Float, nullable=True)
    redeemed_rate_change = Column(Float, nullable=True)
    avg_discount_depth = Column(Float, nullable=True)
    activity_health_score = Column(Float, nullable=True)
    last_activity_date = Column(Date, nullable=True)
    updated_at = Column(DateTime, nullable=True)