"""Integration tests for DecisionCase query APIs.

Task: T093-T096
Phase: 4 - DecisionCase Query APIs
"""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.core.database import get_db
from app.domain.application.decision_case import DecisionCase
from app.domain.application.recommendation import Recommendation
from app.domain.application.approval_log import ApprovalLog
from app.domain.application.action_execution import ActionExecution


@pytest.fixture
def client_with_db(db_session: Session):
    """Create a test client with database dependency override.

    Args:
        db_session: Database session from fixture

    Returns:
        TestClient instance
    """
    # Override the get_db dependency
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    # Clean up dependency overrides
    app.dependency_overrides.clear()


def create_case(
    db: Session,
    case_type="商户异常",
    severity_level="高",
    merchant_id="merchant_001",
    trigger_rule_id="rule_001",
    trigger_metrics_snapshot={},
    status="pending",
    created_at=None,
    updated_at=None,
) -> DecisionCase:
    """Helper function to create a DecisionCase with timestamps.

    Args:
        db: Database session
        case_type: Case type
        severity_level: Severity level
        merchant_id: Merchant ID
        trigger_rule_id: Trigger rule ID
        trigger_metrics_snapshot: Metrics snapshot
        status: Case status
        created_at: Creation timestamp (defaults to now)
        updated_at: Update timestamp (defaults to now)

    Returns:
        Created DecisionCase instance
    """
    now = created_at or datetime.now()
    case = DecisionCase(
        case_type=case_type,
        severity_level=severity_level,
        merchant_id=merchant_id,
        trigger_rule_id=trigger_rule_id,
        trigger_metrics_snapshot=trigger_metrics_snapshot,
        status=status,
        created_at=now,
        updated_at=updated_at or now,
    )
    db.add(case)
    db.flush()
    return case


class TestGetCasesList:
    """Test GET /api/v1/cases endpoint."""

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_list_cases_empty_db(self, client_with_db, clean_db):
        """Test listing cases when database is empty."""
        # Arrange - database is already clean from fixture
        # Act
        response = client_with_db.get("/api/v1/cases")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["limit"] == 20
        assert data["offset"] == 0
        assert data["data"] == []

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_list_cases_default_pagination(self, client_with_db, clean_db):
        """Test listing cases with default pagination."""
        # Arrange
        create_case(
            clean_db,
            merchant_id="merchant_001",
            trigger_metrics_snapshot={"redeemed_rate": 0.45},
        )
        clean_db.commit()

        # Act
        response = client_with_db.get("/api/v1/cases")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["limit"] == 20
        assert data["offset"] == 0
        assert len(data["data"]) == 1
        assert data["data"][0]["merchant_id"] == "merchant_001"

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_list_cases_with_limit_and_offset(self, client_with_db, clean_db):
        """Test listing cases with custom pagination."""
        # Arrange
        for i in range(5):
            create_case(clean_db, merchant_id=f"merchant_{i:03d}")
        clean_db.commit()

        # Act - get first 2
        response = client_with_db.get("/api/v1/cases?limit=2&offset=0")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 5
        assert data["limit"] == 2
        assert data["offset"] == 0
        assert len(data["data"]) == 2

        # Act - get next 2
        response = client_with_db.get("/api/v1/cases?limit=2&offset=2")

        # Assert
        data = response.json()
        assert len(data["data"]) == 2

        # Act - get last 1
        response = client_with_db.get("/api/v1/cases?limit=2&offset=4")

        # Assert
        data = response.json()
        assert len(data["data"]) == 1

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_list_cases_filter_by_status(self, client_with_db, clean_db):
        """Test listing cases filtered by status."""
        # Arrange
        statuses = ["pending", "recommended", "approved", "rejected"]
        for status in statuses:
            create_case(clean_db, merchant_id=f"merchant_{status}", status=status)
        clean_db.commit()

        # Act - filter by pending
        response = client_with_db.get("/api/v1/cases?status=pending")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["data"][0]["status"] == "pending"

        # Act - filter by recommended
        response = client_with_db.get("/api/v1/cases?status=recommended")

        # Assert
        data = response.json()
        assert data["total"] == 1
        assert data["data"][0]["status"] == "recommended"

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_list_cases_filter_by_merchant_id(self, client_with_db, clean_db):
        """Test listing cases filtered by merchant_id."""
        # Arrange
        for i in range(3):
            create_case(clean_db, merchant_id="merchant_001", trigger_rule_id=f"rule_{i}")
        create_case(clean_db, merchant_id="merchant_002", trigger_rule_id="rule_other")
        clean_db.commit()

        # Act
        response = client_with_db.get("/api/v1/cases?merchant_id=merchant_001")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        for case in data["data"]:
            assert case["merchant_id"] == "merchant_001"

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_list_cases_filter_by_case_type(self, client_with_db, clean_db):
        """Test listing cases filtered by case_type."""
        # Arrange
        case_types = ["商户异常", "券策略复核", "用户召回"]
        for case_type in case_types:
            create_case(clean_db, case_type=case_type, trigger_rule_id=f"rule_{case_type}")
        clean_db.commit()

        # Act
        response = client_with_db.get("/api/v1/cases?case_type=商户异常")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["data"][0]["case_type"] == "商户异常"

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_list_cases_filter_by_date_range(self, client_with_db, clean_db):
        """Test listing cases filtered by created_at date range."""
        # Arrange
        base_time = datetime(2026, 5, 17, 10, 0, 0)

        create_case(
            clean_db,
            merchant_id="merchant_old",
            trigger_rule_id="rule_old",
            created_at=base_time - timedelta(days=7),
            updated_at=base_time - timedelta(days=7),
        )

        create_case(
            clean_db,
            merchant_id="merchant_new",
            trigger_rule_id="rule_new",
            created_at=base_time,
            updated_at=base_time,
        )
        clean_db.commit()

        # Act - filter by start date
        start_date = (base_time - timedelta(days=1)).isoformat()
        response = client_with_db.get(f"/api/v1/cases?start_date={start_date}")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["data"][0]["merchant_id"] == "merchant_new"

        # Act - filter by end date
        end_date = (base_time - timedelta(days=5)).isoformat()
        response = client_with_db.get(f"/api/v1/cases?end_date={end_date}")

        # Assert
        data = response.json()
        assert data["total"] == 1
        assert data["data"][0]["merchant_id"] == "merchant_old"

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_list_cases_combined_filters(self, client_with_db, clean_db):
        """Test listing cases with multiple filters combined."""
        # Arrange
        create_case(clean_db, merchant_id="merchant_001", status="pending")
        create_case(clean_db, merchant_id="merchant_001", status="recommended")
        create_case(clean_db, case_type="券策略复核", merchant_id="merchant_001", status="pending")
        clean_db.commit()

        # Act - filter by merchant_id + status
        response = client_with_db.get("/api/v1/cases?merchant_id=merchant_001&status=pending")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        for case in data["data"]:
            assert case["merchant_id"] == "merchant_001"
            assert case["status"] == "pending"

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_list_cases_invalid_status(self, client_with_db, clean_db):
        """Test listing cases with invalid status parameter."""
        # Act
        response = client_with_db.get("/api/v1/cases?status=invalid_status")

        # Assert - should return 400 or 422
        assert response.status_code in [400, 422]


class TestGetCaseDetail:
    """Test GET /api/v1/cases/{case_id} endpoint."""

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_get_case_detail_not_found(self, client_with_db, clean_db):
        """Test getting non-existent case detail."""
        # Act
        response = client_with_db.get("/api/v1/cases/999")

        # Assert
        assert response.status_code == 404

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_get_case_detail_basic(self, client_with_db, clean_db):
        """Test getting case detail without related data."""
        # Arrange
        case = create_case(
            clean_db,
            trigger_metrics_snapshot={"redeemed_rate": 0.45},
        )
        clean_db.commit()
        case_id = case.id

        # Act
        response = client_with_db.get(f"/api/v1/cases/{case_id}")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == case_id
        assert data["case_type"] == "商户异常"
        assert data["severity_level"] == "高"
        assert data["merchant_id"] == "merchant_001"
        assert data["trigger_rule_id"] == "rule_001"
        assert data["status"] == "pending"
        assert data["trigger_metrics_snapshot"]["redeemed_rate"] == 0.45

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_get_case_detail_with_recommendation(self, client_with_db, clean_db):
        """Test getting case detail with recommendation."""
        # Arrange
        case = create_case(clean_db, status="recommended")
        clean_db.flush()

        now = datetime.now()
        recommendation = Recommendation(
            case_id=case.id,
            summary="建议暂停该商户的优惠券活动",
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
            risk_alerts="暂停活动可能影响商户短期营收",
            confidence_score=0.85,
            requires_approval=True,
            created_at=now,
        )
        clean_db.add(recommendation)
        clean_db.commit()
        case_id = case.id

        # Act
        response = client_with_db.get(f"/api/v1/cases/{case_id}")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == case_id
        assert data["recommendation"] is not None
        assert data["recommendation"]["summary"] == "建议暂停该商户的优惠券活动"
        assert len(data["recommendation"]["evidence_list"]) == 3
        assert data["recommendation"]["confidence_score"] == 0.85
        assert data["recommendation"]["requires_approval"] is True

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_get_case_detail_with_approval_logs(self, client_with_db, clean_db):
        """Test getting case detail with approval logs."""
        # Arrange
        case = create_case(clean_db, status="approved")
        clean_db.flush()

        now = datetime.now()
        log1 = ApprovalLog(
            case_id=case.id,
            operator_id="user_001",
            operator_name="张三",
            action="approve",
            comment="同意该建议",
            previous_status="recommended",
            new_status="approved",
            created_at=now,
        )
        log2 = ApprovalLog(
            case_id=case.id,
            operator_id="user_002",
            operator_name="李四",
            action="approve",
            comment="我也同意",
            previous_status="recommended",
            new_status="approved",
            created_at=now + timedelta(seconds=10),
        )
        clean_db.add_all([log1, log2])
        clean_db.commit()
        case_id = case.id

        # Act
        response = client_with_db.get(f"/api/v1/cases/{case_id}")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == case_id
        assert len(data["approval_logs"]) == 2
        assert data["approval_logs"][0]["operator_name"] == "张三"
        assert data["approval_logs"][1]["operator_name"] == "李四"

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_get_case_detail_with_action_executions(self, client_with_db, clean_db):
        """Test getting case detail with action executions."""
        # Arrange
        case = create_case(clean_db, status="executed")
        clean_db.flush()

        now = datetime.now()
        recommendation = Recommendation(
            case_id=case.id,
            summary="建议暂停活动",
            evidence_list=[],
            suggested_actions=[],
            risk_alerts="",
            confidence_score=0.9,
            requires_approval=True,
            created_at=now,
        )
        clean_db.add(recommendation)
        clean_db.flush()

        execution = ActionExecution(
            case_id=case.id,
            recommendation_id=recommendation.id,
            action_type="暂停活动",
            action_params={"merchant_id": "merchant_001"},
            execution_status="success",
            execution_result="活动已暂停",
            executed_at=now,
            duration_ms=150,
        )
        clean_db.add(execution)
        clean_db.commit()
        case_id = case.id

        # Act
        response = client_with_db.get(f"/api/v1/cases/{case_id}")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == case_id
        assert len(data["action_executions"]) == 1
        assert data["action_executions"][0]["action_type"] == "暂停活动"
        assert data["action_executions"][0]["execution_status"] == "success"

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_get_case_detail_full_workflow(self, client_with_db, clean_db):
        """Test getting case detail with complete workflow data."""
        # Arrange
        case = create_case(
            clean_db,
            trigger_metrics_snapshot={"redeemed_rate_7d": 0.45},
            status="executed",
        )
        clean_db.flush()

        now = datetime.now()
        recommendation = Recommendation(
            case_id=case.id,
            summary="建议暂停活动",
            evidence_list=[
                {"type": "指标异常", "content": "核销率下降25%"}
            ],
            suggested_actions=[
                {"action_type": "暂停活动", "params": {}, "risk_level": "高"}
            ],
            risk_alerts="可能影响营收",
            confidence_score=0.88,
            requires_approval=True,
            created_at=now,
        )
        clean_db.add(recommendation)
        clean_db.flush()

        log = ApprovalLog(
            case_id=case.id,
            operator_id="user_001",
            operator_name="审批人",
            action="approve",
            comment="同意",
            previous_status="recommended",
            new_status="approved",
            created_at=now + timedelta(seconds=5),
        )
        clean_db.add(log)

        execution = ActionExecution(
            case_id=case.id,
            recommendation_id=recommendation.id,
            action_type="暂停活动",
            action_params={},
            execution_status="success",
            execution_result="已执行",
            executed_at=now + timedelta(seconds=10),
            duration_ms=100,
        )
        clean_db.add(execution)
        clean_db.commit()
        case_id = case.id

        # Act
        response = client_with_db.get(f"/api/v1/cases/{case_id}")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == case_id
        assert data["case_type"] == "商户异常"
        assert data["status"] == "executed"
        assert data["recommendation"] is not None
        assert len(data["approval_logs"]) == 1
        assert len(data["action_executions"]) == 1