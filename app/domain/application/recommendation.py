from sqlalchemy import Column, BigInteger, String, Text, Float, Boolean, Integer, DateTime, JSON, ForeignKey
from sqlalchemy import Index
from sqlalchemy.orm import relationship
from app.db.base import Base


class Recommendation(Base):
    __tablename__ = "recommendation"
    __table_args__ = (
        Index("idx_case", "case_id"),
        Index("idx_created", "created_at"),
        {"schema": "application"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    case_id = Column(BigInteger, ForeignKey("application.decision_case.id"), nullable=False)
    summary = Column(Text, nullable=True)
    evidence_list = Column(JSON, nullable=False)
    suggested_actions = Column(JSON, nullable=False)
    risk_alerts = Column(Text, nullable=True)
    confidence_score = Column(Float, nullable=False)
    requires_approval = Column(Boolean, nullable=False, default=False)
    tool_trace = Column(JSON, nullable=True)
    llm_raw_output = Column(Text, nullable=True)
    llm_tokens_used = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=True)

    # Relationships
    case = relationship("DecisionCase", back_populates="recommendations")