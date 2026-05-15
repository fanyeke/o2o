from sqlalchemy import Column, BigInteger, String
from app.db.base import Base


class OfflineTrain(Base):
    __tablename__ = "offline_train"
    __table_args__ = {"schema": "raw"}

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(String(64), nullable=False, index=True)
    merchant_id = Column(String(64), nullable=False, index=True)
    coupon_id = Column(String(64), nullable=True)
    discount_rate = Column(String(64), nullable=True)
    distance = Column(String(16), nullable=True)
    date_received = Column(String(16), nullable=True)
    date = Column(String(16), nullable=True)
