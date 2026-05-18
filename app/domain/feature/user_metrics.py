from sqlalchemy import Column, String, Integer, Float, Date, DateTime
from app.db.base import Base


class UserMetrics(Base):
    __tablename__ = "user_metrics"
    __table_args__ = {"schema": "feature"}

    user_id = Column(String(64), primary_key=True)
    total_receipts_30d = Column(Integer, nullable=True)
    redeemed_count_30d = Column(Integer, nullable=True)
    redeemed_rate_30d = Column(Float, nullable=True)
    avg_distance = Column(Float, nullable=True)
    last_receipt_date = Column(Date, nullable=True)
    updated_at = Column(DateTime, nullable=True)