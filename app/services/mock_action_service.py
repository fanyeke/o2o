"""Mock Action Service for simulating external system actions.

Task: T088-T091
Phase: 4 - US1 Approval Callback Flow

Mock Actions:
- execute_pause_activity: Simulate pausing merchant activity
- execute_adjust_discount: Simulate adjusting coupon discount
- execute_send_coupon: Simulate sending coupon to users
"""

import logging
import time
from typing import Dict, Any
from sqlalchemy.orm import Session
from app.repositories.action_execution_repository import ActionExecutionRepository

logger = logging.getLogger(__name__)


class MockActionService:
    """Service for executing mock actions (simulating external system operations)."""

    def __init__(self, db: Session):
        """Initialize service.

        Args:
            db: Database session
        """
        self.db = db
        self.execution_repo = ActionExecutionRepository(db)

    def execute_pause_activity(
        self, case_id: int, recommendation_id: int, action_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute pause activity mock action.

        Simulates pausing merchant activity for a specified duration.

        Args:
            case_id: Decision case ID
            recommendation_id: Recommendation ID
            action_params: Action parameters (merchant_id, duration)

        Returns:
            Execution result with status, message, duration_ms
        """
        start_time = time.time()

        merchant_id = action_params.get("merchant_id")
        duration = action_params.get("duration", "7天")

        logger.info(
            f"Mock Action: Pausing activity for merchant {merchant_id} for {duration}"
        )

        # Simulate execution delay (mock operation)
        time.sleep(0.05)  # 50ms mock delay

        execution_result = f"已模拟暂停商户 {merchant_id} 的活动，时长 {duration}"

        # Record execution
        duration_ms = int((time.time() - start_time) * 1000)
        self.execution_repo.create(
            case_id=case_id,
            recommendation_id=recommendation_id,
            action_type="暂停活动",
            action_params=action_params,
            execution_status="success",
            execution_result=execution_result,
            duration_ms=duration_ms,
        )

        logger.info(f"Mock Action completed: {execution_result}")

        return {
            "status": "success",
            "message": execution_result,
            "duration_ms": duration_ms,
        }

    def execute_adjust_discount(
        self, case_id: int, recommendation_id: int, action_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute adjust discount mock action.

        Simulates adjusting coupon discount rate.

        Args:
            case_id: Decision case ID
            recommendation_id: Recommendation ID
            action_params: Action parameters (coupon_id, new_discount)

        Returns:
            Execution result with status, message, duration_ms
        """
        start_time = time.time()

        coupon_id = action_params.get("coupon_id")
        new_discount = action_params.get("new_discount")

        logger.info(
            f"Mock Action: Adjusting discount for coupon {coupon_id} to {new_discount}"
        )

        # Simulate execution delay
        time.sleep(0.05)

        execution_result = (
            f"已模拟调整优惠券 {coupon_id} 的折扣率至 {new_discount}"
        )

        duration_ms = int((time.time() - start_time) * 1000)
        self.execution_repo.create(
            case_id=case_id,
            recommendation_id=recommendation_id,
            action_type="调整折扣",
            action_params=action_params,
            execution_status="success",
            execution_result=execution_result,
            duration_ms=duration_ms,
        )

        logger.info(f"Mock Action completed: {execution_result}")

        return {
            "status": "success",
            "message": execution_result,
            "duration_ms": duration_ms,
        }

    def execute_send_coupon(
        self, case_id: int, recommendation_id: int, action_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute send coupon mock action.

        Simulates sending coupon to specified users.

        Args:
            case_id: Decision case ID
            recommendation_id: Recommendation ID
            action_params: Action parameters (user_ids, coupon_id)

        Returns:
            Execution result with status, message, duration_ms
        """
        start_time = time.time()

        user_ids = action_params.get("user_ids", [])
        coupon_id = action_params.get("coupon_id")

        logger.info(
            f"Mock Action: Sending coupon {coupon_id} to {len(user_ids)} users"
        )

        # Simulate execution delay
        time.sleep(0.05)

        execution_result = (
            f"已模拟向 {len(user_ids)} 位用户发送优惠券 {coupon_id}"
        )

        duration_ms = int((time.time() - start_time) * 1000)
        self.execution_repo.create(
            case_id=case_id,
            recommendation_id=recommendation_id,
            action_type="发送优惠券",
            action_params=action_params,
            execution_status="success",
            execution_result=execution_result,
            duration_ms=duration_ms,
        )

        logger.info(f"Mock Action completed: {execution_result}")

        return {
            "status": "success",
            "message": execution_result,
            "duration_ms": duration_ms,
        }

    def execute_action(
        self,
        case_id: int,
        recommendation_id: int,
        action_type: str,
        action_params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute action based on action type.

        Args:
            case_id: Decision case ID
            recommendation_id: Recommendation ID
            action_type: Action type (暂停活动, 调整折扣, 发送优惠券)
            action_params: Action parameters

        Returns:
            Execution result

        Raises:
            ValueError: If action type is unknown
        """
        if action_type == "暂停活动":
            return self.execute_pause_activity(
                case_id, recommendation_id, action_params
            )
        elif action_type == "调整折扣":
            return self.execute_adjust_discount(
                case_id, recommendation_id, action_params
            )
        elif action_type == "发送优惠券":
            return self.execute_send_coupon(
                case_id, recommendation_id, action_params
            )
        elif action_type == "调整人群":
            # Placeholder for future implementation
            logger.warning(f"Action type '{action_type}' not implemented yet")
            return {
                "status": "failed",
                "message": f"动作类型 '{action_type}' 尚未实现",
                "duration_ms": 0,
            }
        else:
            logger.error(f"Unknown action type: {action_type}")
            raise ValueError(f"未知的动作类型: {action_type}")