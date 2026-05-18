"""Approval Service for processing approval callbacks.

Task: T086-T087
Phase: 4 - US1 Approval Callback Flow

M5 High-Standard Updates:
- Async execution via Celery
- Complete state machine: recommended->approved->action_pending->action_running->executed/action_failed
- Idempotency key for duplicate prevention
- Retry support for failed actions

Responsibilities:
- Process approval/reject actions
- Update decision case status
- Create approval logs
- Dispatch async action execution via Celery
- Handle concurrent approval conflicts (optimistic locking)
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.domain.application.decision_case import DecisionCase
from app.domain.application.recommendation import Recommendation
from app.domain.application.approval_log import ApprovalLog
from app.domain.application.action_execution import ActionExecution
from app.repositories.action_execution_repository import ActionExecutionRepository

logger = logging.getLogger(__name__)


def utcnow():
    """Return current UTC datetime (timezone-aware)."""
    return datetime.now(timezone.utc)


class ApprovalService:
    """Service for processing approval callbacks with async execution."""

    # Valid state transitions (M5 state machine)
    VALID_TRANSITIONS = {
        "recommended": ["approved", "rejected"],
        "approved": ["action_pending"],
        "action_pending": ["action_running", "action_failed"],
        "action_running": ["executed", "action_failed", "timeout"],
        "action_failed": ["action_pending"],  # Retry
        "timeout": ["action_pending"],  # Retry
        "executed": [],  # Terminal state
        "rejected": [],  # Terminal state
    }

    def __init__(self, db: Session):
        """Initialize service.

        Args:
            db: Database session
        """
        self.db = db
        self.action_repo = ActionExecutionRepository(db)

    def approve_case(
        self,
        case_id: int,
        approver_id: str,
        approval_comment: Optional[str] = None,
    ) -> dict:
        """Approve a decision case and dispatch async action execution.

        Convenience method for approval workflow.

        Args:
            case_id: Decision case ID
            approver_id: Approver ID
            approval_comment: Approval comment

        Returns:
            Processing result with new status
        """
        return self.process_approval(
            case_id=case_id,
            action_type="approve",
            operator_id=approver_id,
            operator_name=None,
            comment=approval_comment,
        )

    def reject_case(
        self,
        case_id: int,
        approver_id: str,
        rejection_reason: Optional[str] = None,
    ) -> dict:
        """Reject a decision case - no action execution.

        Convenience method for rejection workflow.

        Args:
            case_id: Decision case ID
            approver_id: Approver ID
            rejection_reason: Rejection reason

        Returns:
            Processing result with new status
        """
        return self.process_approval(
            case_id=case_id,
            action_type="reject",
            operator_id=approver_id,
            operator_name=None,
            comment=rejection_reason,
        )

    def process_approval(
        self,
        case_id: int,
        action_type: str,
        operator_id: str,
        operator_name: Optional[str] = None,
        comment: Optional[str] = None,
    ) -> dict:
        """Process approval callback with async action dispatch.

        Args:
            case_id: Decision case ID
            action_type: Approval action (approve or reject)
            operator_id: Operator ID (Feishu user ID or API token ID)
            operator_name: Operator name
            comment: Approval comment

        Returns:
            Processing result with new status

        Raises:
            ValueError: If case not found or invalid status
            IntegrityError: If concurrent approval conflict
        """
        # Get decision case
        case = (
            self.db.query(DecisionCase)
            .filter(DecisionCase.id == case_id)
            .first()
        )

        if not case:
            logger.error(f"Decision case {case_id} not found")
            raise ValueError(f"Decision case {case_id} not found")

        # Validate case status (must be 'recommended' for approval)
        if case.status != "recommended":
            logger.error(
                f"Case {case_id} status '{case.status}' not allowed for approval"
            )
            raise ValueError(
                f"Case status '{case.status}' cannot be approved, must be 'recommended'"
            )

        previous_status = case.status

        try:
            # Update case status based on action
            if action_type == "approve":
                # Step 1: Transition to approved
                new_status = "approved"
                case.status = new_status
                case.updated_at = utcnow()
                self.db.flush()

                # Create approval log
                self._create_approval_log(
                    case_id=case_id,
                    operator_id=operator_id,
                    operator_name=operator_name,
                    action=action_type,
                    comment=comment,
                    previous_status=previous_status,
                    new_status=new_status,
                )

                # Get recommendation for executing actions
                recommendation = (
                    self.db.query(Recommendation)
                    .filter(Recommendation.case_id == case_id)
                    .first()
                )

                if recommendation and recommendation.suggested_actions:
                    # Step 2: Create action execution records in action_pending state
                    action_executions = self._create_action_executions(
                        case_id=case_id,
                        recommendation_id=recommendation.id,
                        suggested_actions=recommendation.suggested_actions,
                    )

                    # Step 3: Dispatch async execution via Celery
                    self._dispatch_async_executions(action_executions)

                    # Step 4: Transition to action_pending (waiting for async execution)
                    case.status = "action_pending"
                    case.updated_at = utcnow()
                    self.db.flush()
                    new_status = "action_pending"
                else:
                    # No actions needed - directly mark as executed
                    case.status = "executed"
                    case.updated_at = utcnow()
                    self.db.flush()
                    new_status = "executed"

            elif action_type == "reject":
                new_status = "rejected"
                case.status = new_status
                case.updated_at = utcnow()
                self.db.flush()

                # Create approval log (no action execution for reject)
                self._create_approval_log(
                    case_id=case_id,
                    operator_id=operator_id,
                    operator_name=operator_name,
                    action=action_type,
                    comment=comment,
                    previous_status=previous_status,
                    new_status=new_status,
                )

            else:
                logger.error(f"Invalid action type: {action_type}")
                raise ValueError(f"Invalid action type: {action_type}")

            self.db.commit()

            logger.info(
                f"Approval processed: case {case_id}, action {action_type}, "
                f"status {previous_status} -> {new_status}"
            )

            return {
                "status": "success",
                "message": "Approval processed successfully",
                "case_id": case_id,
                "new_status": new_status,
            }

        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Concurrent approval conflict for case {case_id}: {e}")
            raise IntegrityError(
                f"Concurrent approval conflict for case {case_id}",
                params=e.params,
                orig=e.orig,
            )

    def _create_approval_log(
        self,
        case_id: int,
        operator_id: str,
        operator_name: Optional[str],
        action: str,
        comment: Optional[str],
        previous_status: str,
        new_status: str,
    ) -> ApprovalLog:
        """Create approval log record.

        Args:
            case_id: Decision case ID
            operator_id: Operator ID
            operator_name: Operator name
            action: Approval action
            comment: Approval comment
            previous_status: Previous case status
            new_status: New case status

        Returns:
            Created ApprovalLog record
        """
        log = ApprovalLog(
            case_id=case_id,
            operator_id=operator_id,
            operator_name=operator_name,
            action=action,
            comment=comment,
            previous_status=previous_status,
            new_status=new_status,
            created_at=utcnow(),
        )
        self.db.add(log)
        self.db.flush()

        logger.info(
            f"Approval log created: case {case_id}, operator {operator_id}, "
            f"action {action}, {previous_status} -> {new_status}"
        )

        return log

    def _create_action_executions(
        self,
        case_id: int,
        recommendation_id: int,
        suggested_actions: list[dict],
    ) -> list[ActionExecution]:
        """Create action execution records in action_pending state.

        Creates records with idempotency keys for async execution.

        Args:
            case_id: Decision case ID
            recommendation_id: Recommendation ID
            suggested_actions: List of suggested actions

        Returns:
            List of created ActionExecution records
        """
        executions = []

        for action in suggested_actions:
            action_type = action.get("type") or action.get("action_type")
            action_params = action.get("params", {})

            if not action_type:
                logger.error(f"Action missing type field: {action}")
                # Create failed execution for missing type
                execution = self.action_repo.create(
                    case_id=case_id,
                    recommendation_id=recommendation_id,
                    action_type="unknown",
                    action_params=action,
                    execution_status="action_failed",
                    execution_result="Action missing type field",
                    duration_ms=0,
                )
                executions.append(execution)
                continue

            # Check for existing execution (idempotency)
            idempotency_key = ActionExecution.generate_idempotency_key(
                case_id, recommendation_id, action_type
            )
            existing = self.action_repo.find_by_idempotency_key(idempotency_key)
            if existing:
                logger.info(
                    f"Action {action_type} already exists for case {case_id}, "
                    f"status: {existing.execution_status}. Skipping duplicate."
                )
                continue

            # Create execution record in action_pending state
            execution = self.action_repo.create(
                case_id=case_id,
                recommendation_id=recommendation_id,
                action_type=action_type,
                action_params=action_params,
                execution_status="action_pending",
                idempotency_key=idempotency_key,
            )
            executions.append(execution)

            logger.info(
                f"Action execution created: {action_type} for case {case_id}, "
                f"idempotency_key: {idempotency_key}"
            )

        self.db.commit()
        return executions

    def _dispatch_async_executions(self, executions: list[ActionExecution]) -> None:
        """Dispatch action executions via Celery.

        Args:
            executions: List of ActionExecution records to dispatch
        """
        try:
            from app.tasks.action_executor import execute_action_task

            for execution in executions:
                # Skip failed executions (e.g., missing type)
                if execution.execution_status == "action_failed":
                    continue

                execute_action_task.delay(
                    execution_id=execution.id,
                    case_id=execution.case_id,
                    recommendation_id=execution.recommendation_id,
                    action_type=execution.action_type,
                    action_params=execution.action_params or {},
                    idempotency_key=execution.idempotency_key,
                )

                logger.info(
                    f"Async execution dispatched: execution_id={execution.id}, "
                    f"action_type={execution.action_type}"
                )

        except Exception as e:
            logger.error(f"Failed to dispatch async executions: {e}")
            # Update execution status to failed
            for execution in executions:
                if execution.execution_status != "action_failed":
                    self.action_repo.update_status(
                        execution_id=execution.id,
                        execution_status="action_failed",
                        execution_result=f"Failed to dispatch: {str(e)}",
                    )
            self.db.commit()

    def retry_action(self, execution_id: int) -> dict:
        """Retry a failed action execution.

        Args:
            execution_id: Action execution ID

        Returns:
            Retry result
        """
        execution = self.action_repo.find_by_id(execution_id)
        if not execution:
            raise ValueError(f"Execution record {execution_id} not found")

        if not execution.is_retryable:
            return {
                "status": "failed",
                "message": f"Max retries exceeded: {execution.retry_count}/{execution.max_retries}",
                "execution_id": execution_id,
            }

        # Increment retry count
        execution = self.action_repo.increment_retry(execution_id)
        self.db.commit()

        # Dispatch retry execution
        try:
            from app.tasks.action_executor import execute_action_task

            execute_action_task.delay(
                execution_id=execution.id,
                case_id=execution.case_id,
                recommendation_id=execution.recommendation_id,
                action_type=execution.action_type,
                action_params=execution.action_params or {},
                idempotency_key=execution.idempotency_key,
            )

            logger.info(f"Action retry dispatched: execution_id={execution_id}")

            return {
                "status": "success",
                "message": f"Retry dispatched, attempt {execution.retry_count}",
                "execution_id": execution_id,
            }

        except Exception as e:
            logger.error(f"Failed to dispatch retry: {e}")
            return {
                "status": "failed",
                "message": str(e),
                "execution_id": execution_id,
            }

    def get_approval_history(self, case_id: int) -> list[ApprovalLog]:
        """Get approval history for a case.

        Args:
            case_id: Decision case ID

        Returns:
            List of ApprovalLog records ordered by created_at
        """
        return (
            self.db.query(ApprovalLog)
            .filter(ApprovalLog.case_id == case_id)
            .order_by(ApprovalLog.created_at)
            .all()
        )

    def is_valid_transition(self, from_state: str, to_state: str) -> bool:
        """Check if state transition is valid.

        Args:
            from_state: Current state
            to_state: Target state

        Returns:
            True if transition is valid
        """
        return to_state in self.VALID_TRANSITIONS.get(from_state, [])