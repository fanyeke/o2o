from sqlalchemy import Column, BigInteger, String, Text, Integer, DateTime, JSON, ForeignKey
from sqlalchemy import Index
from sqlalchemy.orm import relationship
from app.db.base import Base


class ActionExecution(Base):
    __tablename__ = "action_execution"
    __table_args__ = (
        Index("idx_case_status", "case_id", "execution_status"),
        {"schema": "application"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    case_id = Column(BigInteger, ForeignKey("application.decision_case.id"), nullable=False)
    recommendation_id = Column(BigInteger, ForeignKey("application.recommendation.id"), nullable=False)
    action_type = Column(String(64), nullable=False)
    action_params = Column(JSON, nullable=True)
    execution_status = Column(String(64), nullable=True)
    execution_result = Column(Text, nullable=True)
    executed_at = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, nullable=True)

    # Relationships
    case = relationship("DecisionCase", back_populates="action_executions")