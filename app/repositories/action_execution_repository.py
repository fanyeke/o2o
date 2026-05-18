"""Repository for ActionExecution entity.

Task: T092
Phase: 4 - US1 Approval Callback Flow
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
    ) -> ActionExecution:
        """Create a new action execution record.

        Args:
            case_id: Decision case ID
            recommendation_id: Recommendation ID
            action_type: Action type (暂停活动, 调整折扣, 发送优惠券, 调整人群)
            action_params: Action parameters (JSON)
            execution_status: Execution status (pending, success, failed, timeout)
            execution_result: Execution result description
            duration_ms: Execution duration in milliseconds

        Returns:
            Created ActionExecution record
        """
        execution = ActionExecution(
            case_id=case_id,
            recommendation_id=recommendation_id,
            action_type=action_type,
            action_params=action_params,
            execution_status=execution_status,
            execution_result=execution_result,
            duration_ms=duration_ms,
            executed_at=datetime.utcnow() if execution_status != "pending" else None,
        )
        self.db.add(execution)
        self.db.flush()
        return execution

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
            .order_by(ActionExecution.executed_at)
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
        execution = (
            self.db.query(ActionExecution)
            .filter(ActionExecution.id == execution_id)
            .first()
        )
        if execution:
            execution.execution_status = execution_status
            execution.execution_result = execution_result
            execution.duration_ms = duration_ms
            if execution_status != "pending":
                execution.executed_at = datetime.utcnow()
            self.db.flush()
        return execution