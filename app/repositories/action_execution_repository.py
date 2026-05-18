"""Repository for ActionExecution entity.

Task: T092
Phase: 4 - US1 Approval Callback Flow

Updated for M5: Added idempotency key and retry support.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from app.domain.application.action_execution import ActionExecution


class ActionExecutionRepository:
    """Repository for managing action execution records."""

    def __init__(self, db: Session):
        """Initialize repository.

        Args:
            db: Database session
        """
        self.db = db

    def create(
        self,
        case_id: int,
        recommendation_id: int,
        action_type: str,
        action_params: dict,
        execution_status: str = "pending",
        execution_result: Optional[str] = None,
        duration_ms: Optional[int] = None,
        idempotency_key: Optional[str] = None,
        retry_count: int = 0,
        max_retries: int = 3,
    ) -> ActionExecution:
        """Create a new action execution record.

        Args:
            case_id: Decision case ID
            recommendation_id: Recommendation ID
            action_type: Action type (暂停活动, 调整折扣, 发送优惠券, 调整人群)
            action_params: Action parameters (JSON)
            execution_status: Execution status (pending, action_pending, action_running, executed, action_failed, timeout)
            execution_result: Execution result description
            duration_ms: Execution duration in milliseconds
            idempotency_key: Unique key for idempotency
            retry_count: Current retry count
            max_retries: Maximum retries allowed

        Returns:
            Created ActionExecution record
        """
        # Generate idempotency key if not provided
        if not idempotency_key:
            idempotency_key = ActionExecution.generate_idempotency_key(
                case_id, recommendation_id, action_type
            )

        execution = ActionExecution(
            case_id=case_id,
            recommendation_id=recommendation_id,
            action_type=action_type,
            action_params=action_params,
            execution_status=execution_status,
            execution_result=execution_result,
            duration_ms=duration_ms,
            idempotency_key=idempotency_key,
            retry_count=retry_count,
            max_retries=max_retries,
            executed_at=datetime.utcnow() if execution_status in ["executed", "action_failed", "timeout"] else None,
            created_at=datetime.utcnow(),
        )
        self.db.add(execution)
        self.db.flush()
        return execution

    def find_by_id(self, execution_id: int) -> Optional[ActionExecution]:
        """Find action execution by ID.

        Args:
            execution_id: Action execution ID

        Returns:
            ActionExecution record or None
        """
        return (
            self.db.query(ActionExecution)
            .filter(ActionExecution.id == execution_id)
            .first()
        )

    def find_by_case_id(self, case_id: int) -> list[ActionExecution]:
        """Find all action executions for a case.

        Args:
            case_id: Decision case ID

        Returns:
            List of ActionExecution records
        """
        return (
            self.db.query(ActionExecution)
            .filter(ActionExecution.case_id == case_id)
            .order_by(ActionExecution.created_at)
            .all()
        )

    def find_by_case_and_type(
        self, case_id: int, action_type: str
    ) -> Optional[ActionExecution]:
        """Find action execution by case_id and action_type.

        Args:
            case_id: Decision case ID
            action_type: Action type

        Returns:
            ActionExecution record or None
        """
        return (
            self.db.query(ActionExecution)
            .filter(
                ActionExecution.case_id == case_id,
                ActionExecution.action_type == action_type,
            )
            .first()
        )

    def find_by_idempotency_key(
        self, idempotency_key: str
    ) -> Optional[ActionExecution]:
        """Find action execution by idempotency key.

        Args:
            idempotency_key: Unique idempotency key

        Returns:
            ActionExecution record or None
        """
        return (
            self.db.query(ActionExecution)
            .filter(ActionExecution.idempotency_key == idempotency_key)
            .first()
        )

    def find_pending_executions(self) -> list[ActionExecution]:
        """Find all executions in action_pending status.

        Returns:
            List of ActionExecution records pending execution
        """
        return (
            self.db.query(ActionExecution)
            .filter(ActionExecution.execution_status == "action_pending")
            .order_by(ActionExecution.created_at)
            .all()
        )

    def find_retryable_executions(self) -> list[ActionExecution]:
        """Find all failed executions that can be retried.

        Returns:
            List of ActionExecution records that can be retried
        """
        return (
            self.db.query(ActionExecution)
            .filter(
                ActionExecution.execution_status.in_(["action_failed", "timeout"]),
                ActionExecution.retry_count < ActionExecution.max_retries,
            )
            .order_by(ActionExecution.created_at)
            .all()
        )

    def update_status(
        self,
        execution_id: int,
        execution_status: str,
        execution_result: Optional[str] = None,
        duration_ms: Optional[int] = None,
    ) -> ActionExecution:
        """Update execution status.

        Args:
            execution_id: Action execution ID
            execution_status: New status
            execution_result: Execution result
            duration_ms: Execution duration

        Returns:
            Updated ActionExecution record
        """
        execution = self.find_by_id(execution_id)
        if execution:
            execution.execution_status = execution_status
            execution.execution_result = execution_result
            execution.duration_ms = duration_ms
            execution.updated_at = datetime.utcnow()
            if execution_status in ["executed", "action_failed", "timeout"]:
                execution.executed_at = datetime.utcnow()
            self.db.flush()
        return execution

    def increment_retry(self, execution_id: int) -> ActionExecution:
        """Increment retry count and reset status to action_pending.

        Args:
            execution_id: Action execution ID

        Returns:
            Updated ActionExecution record
        """
        execution = self.find_by_id(execution_id)
        if execution:
            execution.increment_retry()
            self.db.flush()
        return execution