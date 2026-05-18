from sqlalchemy import Column, BigInteger, String, DateTime, JSON
from sqlalchemy import Index
from sqlalchemy.orm import relationship
from app.db.base import Base


class DecisionCase(Base):
    __tablename__ = "decision_case"
    __table_args__ = (
        Index("idx_merchant_status", "merchant_id", "status"),
        Index("idx_status_created", "status", "created_at"),
        Index("idx_type_date", "case_type", "created_at"),
        {"schema": "application"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    case_type = Column(String(64), nullable=False)
    severity_level = Column(String(64), nullable=True)
    merchant_id = Column(String(64), nullable=True)
    coupon_id = Column(String(64), nullable=True)
    user_id = Column(String(64), nullable=True)
    trigger_rule_id = Column(String(64), nullable=True)
    trigger_metrics_snapshot = Column(JSON, nullable=True)
    status = Column(String(64), nullable=False)
    created_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True)

    # Relationships
    recommendations = relationship("Recommendation", back_populates="case", lazy="dynamic")
    approval_logs = relationship("ApprovalLog", back_populates="case", lazy="dynamic")
    action_executions = relationship("ActionExecution", back_populates="case", lazy="dynamic")