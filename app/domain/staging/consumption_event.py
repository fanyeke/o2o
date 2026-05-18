from sqlalchemy import Column, BigInteger, String, Float, Date
from sqlalchemy import Index
from app.db.base import Base


class ConsumptionEvent(Base):
    __tablename__ = "consumption_event"
    __table_args__ = (
        Index("idx_user_date", "user_id", "date"),
        Index("idx_merchant_date", "merchant_id", "date"),
        {"schema": "staging"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(String(64), nullable=False)
    merchant_id = Column(String(64), nullable=False)
    coupon_id = Column(String(64), nullable=True)
    discount_rate = Column(String(64), nullable=True)
    date = Column(Date, nullable=False)
    amount = Column(Float, nullable=True)