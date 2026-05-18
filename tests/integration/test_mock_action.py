"""Integration tests for approval callback and mock action execution.

Task: T100
Phase: 4 - US1 Approval Callback Flow
Tests: T083-T092 (Approval API, Service, Mock Actions)
"""

import pytest
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient
from fastapi import Depends
from unittest.mock import patch, MagicMock
import time

from app.main import app
from app.core.database import get_db
from app.domain.application.decision_case import DecisionCase
from app.domain.application.recommendation import Recommendation
from app.domain.application.approval_log import ApprovalLog
from app.domain.application.action_execution import ActionExecution


@pytest.fixture
def client(db_session: Session):
    """Create test client with database dependency override.

    Args:
        db_session: Database session from conftest

    Returns:
        TestClient instance with overridden database dependency
    """
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def sample_decision_case(clean_db: Session):
    """Create a sample decision case with recommendation for testing.

    Args:
        clean_db: Database session with clean tables

    Returns:
        Created decision case
    """
    db_session = clean_db
    # Create decision case
    case = DecisionCase(
        case_type="商户异常",
        severity_level="高",
        merchant_id="merchant_001",
        trigger_rule_id="merchant_redeemed_rate_drop",
        trigger_metrics_snapshot={
            "redeemed_rate_7d": 0.45,
            "redeemed_rate_30d": 0.65,
            "redeemed_rate_change": -0.30,
        },
        status="recommended",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(case)
    db_session.flush()

    # Create recommendation
    recommendation = Recommendation(
        case_id=case.id,
        summary="建议暂停商户merchant_001活动7天，核销率异常下降",
        evidence_list=[
            {
                "type": "指标异常",
                "content": "商户核销率下降25%",
                "source": "get_merchant_metrics",
            },
            {
                "type": "券策略问题",
                "content": "高折扣券转化率仅5%",
                "source": "get_coupon_conversion",
            },
            {
                "type": "历史对比",
                "content": "上周同期核销率为65%",
                "source": "get_merchant_metrics",
            },
        ],
        suggested_actions=[
            {
                "action_type": "暂停活动",
                "params": {"merchant_id": "merchant_001", "duration": "7天"},
                "risk_level": "高",
            }
        ],
        risk_alerts="暂停活动可能导致短期收入下降",
        confidence_score=0.85,
        requires_approval=True,
        created_at=datetime.utcnow(),
    )
    db_session.add(recommendation)
    db_session.commit()

    return case


class TestApprovalCallback:
    """Test approval callback API endpoint."""

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_approve_case_success(self, client, clean_db, sample_decision_case):
        """Test successful approval of a decision case.

        Given: A decision case in 'recommended' status
        When: Approval callback is received with 'approve' action
        Then: Case status should be 'approved', approval log created, mock action executed
        """
        case = sample_decision_case

        # Mock approval callback request
        callback_data = {
            "type": "card_action",
            "action": {
                "value": {
                    "case_id": case.id,
                    "action_type": "approve",
                    "operator_id": "user_feishu_001",
                    "comment": "同意暂停活动",
                }
            },
            "token": "test_verification_token",
            "timestamp": int(time.time()),
            "sign": "test_signature",  # In real scenario, this should be HMAC-SHA256
        }

        response = client.post("/api/v1/approvals/callback", json=callback_data)

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["case_id"] == case.id
        assert data["new_status"] == "approved"

        # Verify decision case status updated
        db_session = clean_db
        updated_case = (
            db_session.query(DecisionCase).filter(DecisionCase.id == case.id).first()
        )
        assert updated_case.status == "approved"

        # Verify approval log created
        approval_log = (
            db_session.query(ApprovalLog)
            .filter(ApprovalLog.case_id == case.id)
            .first()
        )
        assert approval_log is not None
        assert approval_log.operator_id == "user_feishu_001"
        assert approval_log.action == "approve"
        assert approval_log.comment == "同意暂停活动"
        assert approval_log.previous_status == "recommended"
        assert approval_log.new_status == "approved"

        # Verify action execution created (mock action executed)
        action_exec = (
            db_session.query(ActionExecution)
            .filter(ActionExecution.case_id == case.id)
            .first()
        )
        assert action_exec is not None
        assert action_exec.action_type == "暂停活动"
        assert action_exec.execution_status == "success"

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_reject_case_success(self, client, clean_db, sample_decision_case):
        """Test successful rejection of a decision case.

        Given: A decision case in 'recommended' status
        When: Approval callback is received with 'reject' action
        Then: Case status should be 'rejected', approval log created, no mock action executed
        """
        case = sample_decision_case

        callback_data = {
            "type": "card_action",
            "action": {
                "value": {
                    "case_id": case.id,
                    "action_type": "reject",
                    "operator_id": "user_feishu_002",
                    "comment": "不同意暂停",
                }
            },
            "token": "test_verification_token",
            "timestamp": int(time.time()),
            "sign": "test_signature",
        }

        response = client.post("/api/v1/approvals/callback", json=callback_data)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["new_status"] == "rejected"

        # Verify no action execution for rejected cases
        db_session = clean_db
        action_exec = (
            db_session.query(ActionExecution)
            .filter(ActionExecution.case_id == case.id)
            .first()
        )
        assert action_exec is None

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_concurrent_approval_conflict(self, client, clean_db, sample_decision_case):
        """Test concurrent approval conflict handling with optimistic locking.

        Given: A decision case in 'recommended' status
        When: Two concurrent approval requests are received
        Then: Only first should succeed, second should return 409 conflict
        """
        case = sample_decision_case

        callback_data = {
            "type": "card_action",
            "action": {
                "value": {
                    "case_id": case.id,
                    "action_type": "approve",
                    "operator_id": "user_feishu_001",
                    "comment": "同意",
                }
            },
            "token": "test_verification_token",
            "timestamp": int(time.time()),
            "sign": "test_signature",
        }

        # First approval should succeed
        response1 = client.post("/api/v1/approvals/callback", json=callback_data)
        assert response1.status_code == 200

        # Update operator_id to simulate different user
        callback_data["action"]["value"]["operator_id"] = "user_feishu_002"
        callback_data["action"]["value"]["comment"] = "也同意"

        # Second approval should fail with 409 conflict
        response2 = client.post("/api/v1/approvals/callback", json=callback_data)
        assert response2.status_code == 409
        assert "状态冲突" in response2.json()["error"]["message"]

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_approve_nonexistent_case(self, client, clean_db):
        """Test approval of a non-existent case.

        Given: No decision case exists
        When: Approval callback is received with invalid case_id
        Then: Should return 404 not found
        """
        callback_data = {
            "type": "card_action",
            "action": {
                "value": {
                    "case_id": 99999,
                    "action_type": "approve",
                    "operator_id": "user_feishu_001",
                    "comment": "同意",
                }
            },
            "token": "test_verification_token",
            "timestamp": int(time.time()),
            "sign": "test_signature",
        }

        response = client.post("/api/v1/approvals/callback", json=callback_data)

        assert response.status_code == 404
        assert "不存在" in response.json()["error"]["message"]

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_approve_invalid_status(self, client, clean_db, sample_decision_case):
        """Test approval of a case with invalid status.

        Given: A decision case in 'pending' status (not 'recommended')
        When: Approval callback is received
        Then: Should return 400 bad request
        """
        case = sample_decision_case
        db_session = clean_db

        # Update case status to pending
        case.status = "pending"
        db_session.commit()

        callback_data = {
            "type": "card_action",
            "action": {
                "value": {
                    "case_id": case.id,
                    "action_type": "approve",
                    "operator_id": "user_feishu_001",
                    "comment": "同意",
                }
            },
            "token": "test_verification_token",
            "timestamp": int(time.time()),
            "sign": "test_signature",
        }

        response = client.post("/api/v1/approvals/callback", json=callback_data)

        assert response.status_code == 400
        assert "状态不允许" in response.json()["error"]["message"]


class TestMockActionService:
    """Test mock action service execution."""

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_execute_pause_activity(self, clean_db, sample_decision_case):
        """Test pause activity mock action.

        Given: An approved decision case with pause activity action
        When: Mock action service executes the action
        Then: Should log execution and return success status
        """
        from app.services.mock_action_service import MockActionService

        case = sample_decision_case
        db_session = clean_db

        # Get recommendation
        recommendation = (
            db_session.query(Recommendation)
            .filter(Recommendation.case_id == case.id)
            .first()
        )

        action_params = {"merchant_id": "merchant_001", "duration": "7天"}

        service = MockActionService(db_session)
        result = service.execute_pause_activity(
            case_id=case.id,
            recommendation_id=recommendation.id,
            action_params=action_params,
        )

        assert result["status"] == "success"
        assert "暂停活动" in result["message"]
        assert result["duration_ms"] > 0

        # Verify action execution record created
        action_exec = (
            db_session.query(ActionExecution)
            .filter(
                ActionExecution.case_id == case.id,
                ActionExecution.action_type == "暂停活动",
            )
            .first()
        )
        assert action_exec is not None
        assert action_exec.execution_status == "success"
        assert action_exec.duration_ms == result["duration_ms"]

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_execute_adjust_discount(self, clean_db, sample_decision_case):
        """Test adjust discount mock action.

        Given: An approved decision case with adjust discount action
        When: Mock action service executes the action
        Then: Should log execution and return success status
        """
        from app.services.mock_action_service import MockActionService

        case = sample_decision_case
        db_session = clean_db

        recommendation = (
            db_session.query(Recommendation)
            .filter(Recommendation.case_id == case.id)
            .first()
        )

        action_params = {"coupon_id": "coupon_001", "new_discount": "0.85"}

        service = MockActionService(db_session)
        result = service.execute_adjust_discount(
            case_id=case.id,
            recommendation_id=recommendation.id,
            action_params=action_params,
        )

        assert result["status"] == "success"
        assert "调整折扣" in result["message"]
        assert result["duration_ms"] > 0

        action_exec = (
            db_session.query(ActionExecution)
            .filter(
                ActionExecution.case_id == case.id,
                ActionExecution.action_type == "调整折扣",
            )
            .first()
        )
        assert action_exec is not None
        assert action_exec.execution_status == "success"

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_execute_send_coupon(self, clean_db, sample_decision_case):
        """Test send coupon mock action.

        Given: An approved decision case with send coupon action
        When: Mock action service executes the action
        Then: Should log execution and return success status
        """
        from app.services.mock_action_service import MockActionService

        case = sample_decision_case
        db_session = clean_db

        recommendation = (
            db_session.query(Recommendation)
            .filter(Recommendation.case_id == case.id)
            .first()
        )

        action_params = {
            "user_ids": ["user_001", "user_002"],
            "coupon_id": "coupon_001",
        }

        service = MockActionService(db_session)
        result = service.execute_send_coupon(
            case_id=case.id,
            recommendation_id=recommendation.id,
            action_params=action_params,
        )

        assert result["status"] == "success"
        assert "发送优惠券" in result["message"]
        assert result["duration_ms"] > 0

        action_exec = (
            db_session.query(ActionExecution)
            .filter(
                ActionExecution.case_id == case.id,
                ActionExecution.action_type == "发送优惠券",
            )
            .first()
        )
        assert action_exec is not None
        assert action_exec.execution_status == "success"


class TestApprovalLog:
    """Test approval log tracking."""

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_approval_log_created_on_approve(self, clean_db, sample_decision_case):
        """Test approval log is created when case is approved.

        Given: A decision case in 'recommended' status
        When: Case is approved
        Then: Approval log should record complete approval chain
        """
        from app.services.approval_service import ApprovalService

        case = sample_decision_case
        db_session = clean_db

        service = ApprovalService(db_session)
        service.process_approval(
            case_id=case.id,
            action_type="approve",
            operator_id="user_feishu_001",
            operator_name="运营人员A",
            comment="同意暂停活动",
        )

        # Verify approval log
        logs = (
            db_session.query(ApprovalLog)
            .filter(ApprovalLog.case_id == case.id)
            .order_by(ApprovalLog.created_at)
            .all()
        )

        assert len(logs) == 1
        assert logs[0].operator_id == "user_feishu_001"
        assert logs[0].operator_name == "运营人员A"
        assert logs[0].action == "approve"
        assert logs[0].comment == "同意暂停活动"
        assert logs[0].previous_status == "recommended"
        assert logs[0].new_status == "approved"

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_multiple_approval_logs_for_regenerate(self, clean_db, sample_decision_case):
        """Test multiple approval logs when case is rejected and regenerated.

        Given: A decision case that was rejected and then regenerated
        When: Multiple approvals and rejections occur
        Then: Approval log should track complete chain
        """
        from app.services.approval_service import ApprovalService

        case = sample_decision_case
        db_session = clean_db

        service = ApprovalService(db_session)

        # First: reject
        service.process_approval(
            case_id=case.id,
            action_type="reject",
            operator_id="user_feishu_001",
            comment="不同意，请重新分析",
        )

        # Simulate regenerate recommendation
        case.status = "recommended"
        db_session.commit()

        # Second: approve
        service.process_approval(
            case_id=case.id,
            action_type="approve",
            operator_id="user_feishu_002",
            comment="同意新方案",
        )

        # Verify all logs
        logs = (
            db_session.query(ApprovalLog)
            .filter(ApprovalLog.case_id == case.id)
            .order_by(ApprovalLog.created_at)
            .all()
        )

        assert len(logs) == 2
        assert logs[0].action == "reject"
        assert logs[0].previous_status == "recommended"
        assert logs[0].new_status == "rejected"
        assert logs[1].action == "approve"
        assert logs[1].previous_status == "recommended"
        assert logs[1].new_status == "approved"