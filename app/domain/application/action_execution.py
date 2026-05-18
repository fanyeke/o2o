from sqlalchemy import Column, BigInteger, String, Text, Integer, DateTime, JSON, ForeignKey
from sqlalchemy import Index
from sqlalchemy.orm import relationship
from app.db.base import Base
from datetime import datetime
import uuid


class ActionExecution(Base):
    """Action execution record with state machine and retry support.

    State Machine:
        pending -> action_pending -> action_running -> executed/action_failed/timeout
        action_failed -> action_pending (retry)

    Attributes:
        idempotency_key: Unique key to prevent duplicate execution
        retry_count: Current retry attempt count
        max_retries: Maximum allowed retries (default 3)
    """
    __tablename__ = "action_execution"
    __table_args__ = (
        Index("idx_case_status", "case_id", "execution_status"),
        Index("idx_idempotency_key", "idempotency_key", unique=True),
        {"schema": "application"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    case_id = Column(BigInteger, ForeignKey("application.decision_case.id"), nullable=False)
    recommendation_id = Column(BigInteger, ForeignKey("application.recommendation.id"), nullable=False)
    action_type = Column(String(64), nullable=False)
    action_params = Column(JSON, nullable=True)
    execution_status = Column(String(64), nullable=False, default="pending")
    execution_result = Column(Text, nullable=True)
    executed_at = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    idempotency_key = Column(String(255), nullable=True, unique=True)
    retry_count = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=3)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.utcnow)

    # Relationships
    case = relationship("DecisionCase", back_populates="action_executions")

    @staticmethod
    def generate_idempotency_key(case_id: int, recommendation_id: int, action_type: str) -> str:
        """Generate a unique idempotency key.

        Format: case_{case_id}_rec_{rec_id}_action_{action_type}_{uuid}
        """
        unique_id = uuid.uuid4().hex[:8]
        return f"case_{case_id}_rec_{recommendation_id}_action_{action_type}_{unique_id}"

    @property
    def is_retryable(self) -> bool:
        """Check if execution can be retried."""
        return self.retry_count < self.max_retries

    @property
    def is_terminal_state(self) -> bool:
        """Check if execution is in a terminal state."""
        return self.execution_status in ["executed", "rejected"]

    def increment_retry(self) -> "ActionExecution":
        """Increment retry count and reset to pending."""
        self.retry_count += 1
        self.execution_status = "action_pending"
        self.updated_at = datetime.utcnow()
        return self