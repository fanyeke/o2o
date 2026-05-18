from sqlalchemy import Column, BigInteger, String, Text, Float, Boolean, Integer, DateTime, JSON, ForeignKey, Numeric
from sqlalchemy import Index
from sqlalchemy.orm import relationship
from app.db.base import Base


class Recommendation(Base):
    """Recommendation model with complete trace fields for M7 observability.

    Trace fields ensure full observability of agent decisions:
    - rule_id: Which rule triggered this recommendation
    - model_version: ML model version used for prediction
    - feature_version: Feature engineering version
    - prediction_summary: ML prediction output summary
    - prompt_version: Prompt template version
    - llm_model: LLM model used (e.g., deepseek-v4-flash)
    - llm_latency_ms: LLM API call latency
    - approval_operator: Who approved this recommendation
    - action_execution_id: Linked action execution
    """

    __tablename__ = "recommendation"
    __table_args__ = (
        Index("idx_case", "case_id"),
        Index("idx_created", "created_at"),
        Index("idx_rule_id", "rule_id"),
        Index("idx_llm_model", "llm_model"),
        {"schema": "application"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    case_id = Column(BigInteger, ForeignKey("application.decision_case.id"), nullable=False)

    # Recommendation content
    summary = Column(Text, nullable=True)
    evidence_list = Column(JSON, nullable=False)
    suggested_actions = Column(JSON, nullable=False)
    risk_alerts = Column(Text, nullable=True)
    confidence_score = Column(Float, nullable=False)
    requires_approval = Column(Boolean, nullable=False, default=False)

    # M4 High Standard: New fields for enhanced analysis
    model_signal = Column(JSON, nullable=True)      # ML prediction signal (prediction_score, signal_type, confidence_interval)
    business_risk = Column(JSON, nullable=True)     # Business risk assessment (risk_level, potential_revenue_impact, affected_users)
    limitations = Column(JSON, nullable=True)       # Analysis limitations list

    # M7 Observability trace fields
    rule_id = Column(String(128), nullable=True)  # Trigger rule ID
    tool_trace = Column(JSON, nullable=True)  # Tool execution records
    model_version = Column(String(32), nullable=True)  # ML model version (e.g., "v1.0.0")
    feature_version = Column(String(32), nullable=True)  # Feature engineering version
    prediction_summary = Column(JSON, nullable=True)  # ML prediction output
    prompt_version = Column(String(32), nullable=True)  # Prompt template version
    llm_model = Column(String(64), nullable=True)  # LLM model name
    llm_latency_ms = Column(Integer, nullable=True)  # LLM response latency in ms
    llm_raw_output = Column(Text, nullable=True)  # Raw LLM output (sanitized)
    llm_tokens_used = Column(Integer, nullable=True)  # Token usage
    approval_operator = Column(String(64), nullable=True)  # Approval operator ID
    action_execution_id = Column(BigInteger, nullable=True)  # Linked action execution

    created_at = Column(DateTime, nullable=True)

    # Relationships
    case = relationship("DecisionCase", back_populates="recommendations")