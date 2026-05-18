"""Celery task for async action execution.

M5 High-Standard: Async execution chain
审批 -> approval_log -> action_execution (action_pending) -> Celery task -> action_running -> executed/action_failed

State transitions:
- action_pending -> action_running (when task starts)
- action_running -> executed (success)
- action_running -> action_failed (failure)
- action_running -> timeout (timeout)
- action_failed -> action_pending (retry via retry_action_task)
"""

import logging
import time
from typing import Dict, Any, Optional
from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.repositories.action_execution_repository import ActionExecutionRepository
from app.services.mock_action_service import MockActionService
from app.domain.application.action_execution import ActionExecution
from app.domain.application.decision_case import DecisionCase

logger = logging.getLogger(__name__)

# Valid action types for execution
VALID_ACTION_TYPES = {
    "pause_coupon_distribution": "暂停活动",
    "暂停活动": "暂停活动",
    "adjust_discount": "调整折扣",
    "调整折扣": "调整折扣",
    "send_coupon": "发送优惠券",
    "发送优惠券": "发送优惠券",
    "adjust_targeting": "调整人群",
    "调整人群": "调整人群",
    "no_action": None,  # Special case - no execution needed
}

# Task timeout in seconds
EXECUTION_TIMEOUT = 30  # 30 seconds timeout


@shared_task(
    name="app.tasks.action_executor.execute_action_task",
    bind=True,
    max_retries=3,
    soft_time_limit=EXECUTION_TIMEOUT,
    acks_late=True,
    reject_on_worker_lost=True,
)
def execute_action_task(
    self,
    execution_id: int,
    case_id: int,
    recommendation_id: int,
    action_type: str,
    action_params: Dict[str, Any],
    idempotency_key: str,
) -> Dict[str, Any]:
    """Execute action asynchronously via Celery.

    Args:
        execution_id: Action execution record ID
        case_id: Decision case ID
        recommendation_id: Recommendation ID
        action_type: Action type to execute
        action_params: Action parameters
        idempotency_key: Idempotency key for duplicate prevention

    Returns:
        Execution result with status and duration
    """
    db: Session = SessionLocal()
    repo = ActionExecutionRepository(db)
    mock_service = MockActionService(db)

    start_time = time.time()

    try:
        # Check idempotency - if already executed, return early
        existing = repo.find_by_idempotency_key(idempotency_key)
        if existing and existing.execution_status in ["executed", "action_running"]:
            logger.info(
                f"Action {idempotency_key} already in status {existing.execution_status}, skipping"
            )
            return {
                "status": "skipped",
                "message": "Already executed or running",
                "execution_id": existing.id,
            }

        # Get execution record
        execution = repo.find_by_id(execution_id)
        if not execution:
            logger.error(f"Execution record {execution_id} not found")
            raise ValueError(f"Execution record {execution_id} not found")

        # Update status to action_running
        execution = repo.update_status(
            execution_id=execution_id,
            execution_status="action_running",
        )

        # Check for unknown action type
        normalized_type = VALID_ACTION_TYPES.get(action_type)
        if normalized_type is None and action_type != "no_action":
            # Unknown action type - mark as failed
            logger.error(f"Unknown action type: {action_type}")
            execution = repo.update_status(
                execution_id=execution_id,
                execution_status="action_failed",
                execution_result=f"Unknown action type: {action_type}",
                duration_ms=0,
            )
            db.commit()
            return {
                "status": "failed",
                "message": f"Unknown action type: {action_type}",
                "execution_id": execution_id,
            }

        if action_type == "no_action":
            # No action needed - mark as executed
            execution = repo.update_status(
                execution_id=execution_id,
                execution_status="executed",
                execution_result="No action required",
                duration_ms=0,
            )
            db.commit()
            return {
                "status": "success",
                "message": "No action required",
                "execution_id": execution_id,
            }

        # Execute the mock action
        logger.info(f"Executing action {action_type} for case {case_id}")
        result = mock_service.execute_action(
            case_id=case_id,
            recommendation_id=recommendation_id,
            action_type=action_type,
            action_params=action_params,
        )

        duration_ms = int((time.time() - start_time) * 1000)

        # Update execution status based on result
        if result.get("status") == "success":
            execution = repo.update_status(
                execution_id=execution_id,
                execution_status="executed",
                execution_result=result.get("message"),
                duration_ms=duration_ms,
            )

            # Update case status to executed
            case = db.query(DecisionCase).filter(DecisionCase.id == case_id).first()
            if case:
                case.status = "executed"
                case.updated_at = datetime.utcnow()
                db.flush()

            db.commit()

            logger.info(
                f"Action {action_type} executed successfully for case {case_id}, "
                f"duration: {duration_ms}ms"
            )

            return {
                "status": "success",
                "message": result.get("message"),
                "duration_ms": duration_ms,
                "execution_id": execution_id,
            }
        else:
            # Action failed
            execution = repo.update_status(
                execution_id=execution_id,
                execution_status="action_failed",
                execution_result=result.get("message"),
                duration_ms=duration_ms,
            )
            db.commit()

            logger.error(
                f"Action {action_type} failed for case {case_id}: {result.get('message')}"
            )

            # Retry if possible
            if execution.retry_count < execution.max_retries:
                logger.info(f"Retrying action {execution_id}, attempt {execution.retry_count + 1}")
                raise self.retry(exc=Exception(result.get("message")), countdown=5)

            return {
                "status": "failed",
                "message": result.get("message"),
                "duration_ms": duration_ms,
                "execution_id": execution_id,
                "retry_exhausted": True,
            }

    except SoftTimeLimitExceeded:
        # Task timeout
        duration_ms = int((time.time() - start_time) * 1000)
        execution = repo.update_status(
            execution_id=execution_id,
            execution_status="timeout",
            execution_result="Task execution timeout",
            duration_ms=duration_ms,
        )
        db.commit()

        logger.error(f"Action {execution_id} timed out after {duration_ms}ms")

        return {
            "status": "timeout",
            "message": "Task execution timeout",
            "duration_ms": duration_ms,
            "execution_id": execution_id,
        }

    except Exception as e:
        # Unexpected error
        duration_ms = int((time.time() - start_time) * 1000)
        logger.error(f"Action execution failed: {e}")

        execution = repo.find_by_id(execution_id)
        if execution:
            execution = repo.update_status(
                execution_id=execution_id,
                execution_status="action_failed",
                execution_result=str(e),
                duration_ms=duration_ms,
            )
            db.commit()

        # Retry if possible
        if execution and execution.retry_count < execution.max_retries:
            logger.info(f"Retrying action {execution_id} due to error: {e}")
            raise self.retry(exc=e, countdown=5)

        return {
            "status": "failed",
            "message": str(e),
            "duration_ms": duration_ms,
            "execution_id": execution_id,
            "retry_exhausted": True,
        }

    finally:
        db.close()


@shared_task(
    name="app.tasks.action_executor.retry_action_task",
    bind=True,
    max_retries=1,
)
def retry_action_task(self, execution_id: int) -> Dict[str, Any]:
    """Retry a failed action execution.

    Args:
        execution_id: Action execution record ID

    Returns:
        Retry result
    """
    db: Session = SessionLocal()
    repo = ActionExecutionRepository(db)

    try:
        execution = repo.find_by_id(execution_id)
        if not execution:
            raise ValueError(f"Execution record {execution_id} not found")

        # Check if retryable
        if not execution.is_retryable:
            logger.warning(
                f"Action {execution_id} not retryable: "
                f"retry_count={execution.retry_count}, max_retries={execution.max_retries}"
            )
            return {
                "status": "failed",
                "message": "Max retries exceeded",
                "execution_id": execution_id,
            }

        # Increment retry count
        execution = repo.increment_retry(execution_id)
        db.commit()

        logger.info(
            f"Retrying action {execution_id}, attempt {execution.retry_count}"
        )

        # Dispatch new execution task
        execute_action_task.delay(
            execution_id=execution.id,
            case_id=execution.case_id,
            recommendation_id=execution.recommendation_id,
            action_type=execution.action_type,
            action_params=execution.action_params or {},
            idempotency_key=execution.idempotency_key,
        )

        return {
            "status": "success",
            "message": f"Retry initiated, attempt {execution.retry_count}",
            "execution_id": execution_id,
        }

    except Exception as e:
        logger.error(f"Retry action failed: {e}")
        return {
            "status": "failed",
            "message": str(e),
            "execution_id": execution_id,
        }

    finally:
        db.close()


@shared_task(name="app.tasks.action_executor.process_pending_executions")
def process_pending_executions() -> Dict[str, Any]:
    """Process all pending action executions.

    Called periodically by Celery beat to ensure pending actions are executed.

    Returns:
        Processing result with count of dispatched tasks
    """
    db: Session = SessionLocal()
    repo = ActionExecutionRepository(db)

    try:
        pending_executions = repo.find_pending_executions()

        dispatched = 0
        for execution in pending_executions:
            execute_action_task.delay(
                execution_id=execution.id,
                case_id=execution.case_id,
                recommendation_id=execution.recommendation_id,
                action_type=execution.action_type,
                action_params=execution.action_params or {},
                idempotency_key=execution.idempotency_key,
            )
            dispatched += 1

        logger.info(f"Dispatched {dispatched} pending action executions")

        return {
            "status": "success",
            "dispatched": dispatched,
        }

    except Exception as e:
        logger.error(f"Process pending executions failed: {e}")
        return {
            "status": "failed",
            "message": str(e),
            "dispatched": 0,
        }

    finally:
        db.close()