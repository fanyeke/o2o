from sqlalchemy import Column, BigInteger, String, Text, DateTime, ForeignKey
from sqlalchemy import Index
from sqlalchemy.orm import relationship
from app.db.base import Base


class ApprovalLog(Base):
    __tablename__ = "approval_log"
    __table_args__ = (
        Index("idx_case_created", "case_id", "created_at"),
        Index("idx_operator", "operator_id"),
        {"schema": "application"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    case_id = Column(BigInteger, ForeignKey("application.decision_case.id"), nullable=False)
    operator_id = Column(String(64), nullable=False)
    operator_name = Column(String(128), nullable=True)
    action = Column(String(64), nullable=False)
    comment = Column(Text, nullable=True)
    previous_status = Column(String(64), nullable=True)
    new_status = Column(String(64), nullable=True)
    created_at = Column(DateTime, nullable=True)

    # Relationships
    case = relationship("DecisionCase", back_populates="approval_logs")