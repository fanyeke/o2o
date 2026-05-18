"""Approval Service for processing approval callbacks.

Task: T086-T087
Phase: 4 - US1 Approval Callback Flow

Responsibilities:
- Process approval/reject actions
- Update decision case status
- Create approval logs
- Trigger mock action execution if approved
- Handle concurrent approval conflicts (optimistic locking)
"""

import logging
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.domain.application.decision_case import DecisionCase
from app.domain.application.recommendation import Recommendation
from app.domain.application.approval_log import ApprovalLog
from app.repositories.action_execution_repository import ActionExecutionRepository
from app.services.mock_action_service import MockActionService

logger = logging.getLogger(__name__)


class ApprovalService:
    """Service for processing approval callbacks."""

    def __init__(self, db: Session):
        """Initialize service.

        Args:
            db: Database session
        """
        self.db = db
        self.action_repo = ActionExecutionRepository(db)
        self.mock_action_service = MockActionService(db)

    def approve_case(
        self,
        case_id: str,
        approver_id: str,
        approval_comment: Optional[str] = None,
    ) -> dict:
        """Approve a decision case.

        Convenience method for approval workflow.

        Args:
            case_id: Decision case ID (string for compatibility with tests)
            approver_id: Approver ID
            approval_comment: Approval comment

        Returns:
            Processing result
        """
        return self.process_approval(
            case_id=int(case_id) if isinstance(case_id, str) else case_id,
            action_type="approve",
            operator_id=approver_id,
            operator_name=None,
            comment=approval_comment,
        )

    def reject_case(
        self,
        case_id: str,
        approver_id: str,
        rejection_reason: Optional[str] = None,
    ) -> dict:
        """Reject a decision case.

        Convenience method for rejection workflow.

        Args:
            case_id: Decision case ID (string for compatibility with tests)
            approver_id: Approver ID
            rejection_reason: Rejection reason

        Returns:
            Processing result
        """
        return self.process_approval(
            case_id=int(case_id) if isinstance(case_id, str) else case_id,
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
        """Process approval callback.

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
            raise ValueError(f"决策案例 {case_id} 不存在")

        # Validate case status (must be 'recommended' for approval)
        if case.status != "recommended":
            logger.error(
                f"Case {case_id} status '{case.status}' not allowed for approval"
            )
            raise ValueError(
                f"案例状态 '{case.status}' 不允许审批操作，必须为 'recommended' 状态"
            )

        previous_status = case.status

        try:
            # Update case status based on action
            if action_type == "approve":
                new_status = "approved"
                case.status = new_status
                case.updated_at = datetime.utcnow()
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
                    # Execute mock actions for approved case
                    self._execute_actions(
                        case_id=case_id,
                        recommendation_id=recommendation.id,
                        suggested_actions=recommendation.suggested_actions,
                    )

                    # Update case status to executed
                    case.status = "executed"
                    case.updated_at = datetime.utcnow()
                    self.db.flush()

                    new_status = "executed"

            elif action_type == "reject":
                new_status = "rejected"
                case.status = new_status
                case.updated_at = datetime.utcnow()
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

            else:
                logger.error(f"Invalid action type: {action_type}")
                raise ValueError(f"无效的审批动作类型: {action_type}")

            self.db.commit()

            logger.info(
                f"Approval processed: case {case_id}, action {action_type}, "
                f"status {previous_status} -> {new_status}"
            )

            return {
                "status": "success",
                "message": "审批处理成功",
                "case_id": case_id,
                "new_status": new_status,
            }

        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Concurrent approval conflict for case {case_id}: {e}")
            raise IntegrityError(
                f"案例 {case_id} 发生并发审批冲突，状态已被其他操作更新",
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
            created_at=datetime.utcnow(),
        )
        self.db.add(log)
        self.db.flush()

        logger.info(
            f"Approval log created: case {case_id}, operator {operator_id}, "
            f"action {action}, {previous_status} -> {new_status}"
        )

        return log

    def _execute_actions(
        self,
        case_id: int,
        recommendation_id: int,
        suggested_actions: list[dict],
    ) -> None:
        """Execute mock actions for approved case.

        Handles various action formats and ensures graceful failure for unknown types.
        Ensures idempotency by checking for existing executions.

        Args:
            case_id: Decision case ID
            recommendation_id: Recommendation ID
            suggested_actions: List of suggested actions
        """
        from sqlalchemy.exc import IntegrityError

        for action in suggested_actions:
            # Handle both "type" and "action_type" fields for compatibility
            action_type = action.get("type") or action.get("action_type")
            action_params = action.get("params", {})

            if not action_type:
                logger.error(f"Action missing type field: {action}")
                try:
                    self.action_repo.create(
                        case_id=case_id,
                        recommendation_id=recommendation_id,
                        action_type="unknown",
                        action_params=action,
                        execution_status="failed",
                        execution_result="动作缺少类型字段",
                        duration_ms=0,
                    )
                    self.db.commit()
                except IntegrityError:
                    self.db.rollback()
                    logger.error(f"Database constraint violation for unknown action type")
                continue

            # Handle "no_action" type - do nothing
            if action_type == "no_action":
                logger.info(f"No action needed for case {case_id}")
                try:
                    self.action_repo.create(
                        case_id=case_id,
                        recommendation_id=recommendation_id,
                        action_type="调整人群",  # Use a valid action type
                        action_params={"no_action": True},
                        execution_status="success",
                        execution_result="无需执行动作",
                        duration_ms=0,
                    )
                    self.db.commit()
                except IntegrityError:
                    self.db.rollback()
                    logger.error(f"Database constraint violation for no_action")
                continue

            # Check for existing execution (idempotency)
            existing = self.action_repo.find_by_case_and_type(case_id, action_type)
            if existing:
                logger.info(
                    f"Action {action_type} already executed for case {case_id}, "
                    f"status: {existing.execution_status}. Skipping duplicate execution."
                )
                continue

            try:
                result = self.mock_action_service.execute_action(
                    case_id=case_id,
                    recommendation_id=recommendation_id,
                    action_type=action_type,
                    action_params=action_params,
                )

                logger.info(
                    f"Mock action executed: {action_type} for case {case_id}, "
                    f"result: {result['status']}"
                )

            except ValueError as e:
                # Unknown action type - record as failed
                logger.error(
                    f"Unknown action type: {action_type} for case {case_id}, error: {e}"
                )
                try:
                    # Use a valid action type for database constraint
                    self.action_repo.create(
                        case_id=case_id,
                        recommendation_id=recommendation_id,
                        action_type="调整人群",  # Placeholder type
                        action_params={"original_type": action_type},
                        execution_status="failed",
                        execution_result=f"未知动作类型: {action_type}",
                        duration_ms=0,
                    )
                    self.db.commit()
                except IntegrityError:
                    self.db.rollback()
                    logger.error(f"Database constraint violation when recording failed action")
            except Exception as e:
                logger.error(
                    f"Mock action execution failed: {action_type} for case {case_id}, "
                    f"error: {e}"
                )
                # Record failed execution
                try:
                    self.action_repo.create(
                        case_id=case_id,
                        recommendation_id=recommendation_id,
                        action_type="调整人群",  # Placeholder type
                        action_params={"original_type": action_type},
                        execution_status="failed",
                        execution_result=f"执行失败: {str(e)}",
                        duration_ms=0,
                    )
                    self.db.commit()
                except IntegrityError:
                    self.db.rollback()
                    logger.error(f"Database constraint violation when recording failed action")

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