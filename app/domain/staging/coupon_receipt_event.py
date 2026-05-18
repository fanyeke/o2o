from sqlalchemy import Column, BigInteger, String, Float, Date, Boolean, Integer
from sqlalchemy import Index
from app.db.base import Base


class CouponReceiptEvent(Base):
    __tablename__ = "coupon_receipt_event"
    __table_args__ = (
        Index("idx_user_date", "user_id", "date_received"),
        Index("idx_merchant_date", "merchant_id", "date_received"),
        Index("idx_coupon", "coupon_id"),
        {"schema": "staging"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(String(64), nullable=False)
    merchant_id = Column(String(64), nullable=False)
    coupon_id = Column(String(64), nullable=False)
    discount_rate = Column(String(64), nullable=True)
    distance = Column(Float, nullable=True)
    date_received = Column(Date, nullable=False)
    is_redeemed = Column(Boolean, nullable=True, default=False)
    date_redeemed = Column(Date, nullable=True)
    redeem_days = Column(Integer, nullable=True)
    predicted_probability = Column(Float, nullable=True)