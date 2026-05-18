import pytest
"""Integration tests for case search functionality.

Task: T122 - 案例检索集成测试
Phase: 6 - US4 案例检索功能
"""

from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.domain.application.decision_case import DecisionCase
from app.domain.application.recommendation import Recommendation
from app.domain.application.approval_log import ApprovalLog
from app.domain.application.action_execution import ActionExecution

client = TestClient(app)


def create_test_cases(db_session: Session):
    """创建测试决策案例数据.

    Args:
        db_session: 数据库会话
    """
    now = datetime.now()
    base_time = now - timedelta(days=30)

    cases = [
        # 案例 1: 商户异常，7天前创建，pending 状态
        DecisionCase(
            case_type="商户异常",
            severity_level="高",
            merchant_id="merchant_001",
            trigger_rule_id="redeem_rate_drop",
            trigger_metrics_snapshot={"redeemed_rate_7d": 0.45, "redeemed_rate_30d": 0.65},
            status="pending",
            created_at=base_time + timedelta(days=23),  # 7天前
            updated_at=base_time + timedelta(days=23),
        ),
        # 案例 2: 商户异常，3天前创建，recommended 状态
        DecisionCase(
            case_type="商户异常",
            severity_level="中",
            merchant_id="merchant_001",
            trigger_rule_id="redeem_rate_drop",
            trigger_metrics_snapshot={"redeemed_rate_7d": 0.50, "redeemed_rate_30d": 0.70},
            status="recommended",
            created_at=base_time + timedelta(days=27),  # 3天前
            updated_at=base_time + timedelta(days=27),
        ),
        # 案例 3: 券策略复核，5天前创建，executed 状态
        DecisionCase(
            case_type="券策略复核",
            severity_level="高",
            merchant_id="merchant_002",
            coupon_id="coupon_001",
            trigger_rule_id="low_conversion_rate",
            trigger_metrics_snapshot={"redeemed_rate": 0.05},
            status="executed",
            created_at=base_time + timedelta(days=25),  # 5天前
            updated_at=base_time + timedelta(days=25),
        ),
        # 案例 4: 用户召回，1天前创建，rejected 状态
        DecisionCase(
            case_type="用户召回",
            severity_level="低",
            user_id="user_001",
            trigger_rule_id="inactive_user",
            trigger_metrics_snapshot={"last_activity": "30d_ago"},
            status="rejected",
            created_at=base_time + timedelta(days=29),  # 1天前
            updated_at=base_time + timedelta(days=29),
        ),
        # 案例 5: 商户异常，今天创建，pending 状态
        DecisionCase(
            case_type="商户异常",
            severity_level="高",
            merchant_id="merchant_002",
            trigger_rule_id="redeem_rate_drop",
            trigger_metrics_snapshot={"redeemed_rate_7d": 0.30, "redeemed_rate_30d": 0.60},
            status="pending",
            created_at=now,
            updated_at=now,
        ),
    ]

    db_session.add_all(cases)
    db_session.commit()

    return cases


def create_test_recommendation(db_session: Session, case_id: int):
    """创建测试推荐建议.

    Args:
        db_session: 数据库会话
        case_id: 案例ID
    """
    recommendation = Recommendation(
        case_id=case_id,
        summary="建议暂停商户活动并优化优惠券策略",
        evidence_list=[
            {"type": "指标异常", "content": "核销率下降30%", "source": "get_merchant_metrics"},
            {"type": "券策略问题", "content": "高折扣券转化率仅5%", "source": "get_coupon_conversion"},
            {"type": "历史对比", "content": "上周同期核销率为65%", "source": "get_merchant_metrics"},
        ],
        suggested_actions=[
            {"action_type": "暂停活动", "params": {"duration": "7天"}, "risk_level": "高"},
        ],
        risk_alerts="可能导致短期内用户活跃度下降",
        confidence_score=0.85,
        requires_approval=True,
        created_at=datetime.now(),
    )
    db_session.add(recommendation)
    db_session.commit()
    return recommendation


def create_test_approval_logs(db_session: Session, case_id: int):
    """创建测试审批记录.

    Args:
        db_session: 数据库会话
        case_id: 案例ID
    """
    now = datetime.now()

    logs = [
        ApprovalLog(
            case_id=case_id,
            operator_id="user_admin",
            operator_name="管理员",
            action="approve",
            comment="同意执行暂停活动",
            previous_status="recommended",
            new_status="approved",
            created_at=now - timedelta(hours=2),
        ),
        ApprovalLog(
            case_id=case_id,
            operator_id="user_manager",
            operator_name="运营经理",
            action="reject",
            comment="需要更多证据支持",
            previous_status="recommended",
            new_status="rejected",
            created_at=now - timedelta(hours=5),
        ),
        ApprovalLog(
            case_id=case_id,
            operator_id="user_admin",
            operator_name="管理员",
            action="regenerate",
            comment="重新生成建议",
            previous_status="rejected",
            new_status="recommended",
            created_at=now - timedelta(hours=4),
        ),
    ]

    db_session.add_all(logs)
    db_session.commit()

    return logs


def create_test_action_executions(db_session: Session, case_id: int, recommendation_id: int):
    """创建测试执行记录.

    Args:
        db_session: 数据库会话
        case_id: 案例ID
        recommendation_id: 建议ID
    """
    execution = ActionExecution(
        case_id=case_id,
        recommendation_id=recommendation_id,
        action_type="暂停活动",
        action_params={"duration": "7天"},
        execution_status="success",
        execution_result="已成功暂停商户 merchant_001 的所有活动",
        executed_at=datetime.now(),
        duration_ms=150,
    )
    db_session.add(execution)
    db_session.commit()
    return execution


class TestCaseSearchFilters:
    """测试案例检索筛选功能"""

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_list_cases_with_default_params(self, clean_db: Session):
        """测试默认参数查询案例列表"""
        create_test_cases(clean_db)

        response = client.get("/api/v1/cases/")
        assert response.status_code == 200

        data = response.json()
        assert "total" in data
        assert "limit" in data
        assert "offset" in data
        assert "data" in data

        # 默认返回所有案例
        assert data["total"] == 5
        assert len(data["data"]) == 5

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_list_cases_with_status_filter(self, clean_db: Session):
        """测试按状态筛选案例"""
        create_test_cases(clean_db)

        # 测试筛选 pending 状态
        response = client.get("/api/v1/cases/?status=pending")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 2
        assert all(case["status"] == "pending" for case in data["data"])

        # 测试筛选 recommended 状态
        response = client.get("/api/v1/cases/?status=recommended")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 1
        assert data["data"][0]["status"] == "recommended"

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_list_cases_with_case_type_filter(self, clean_db: Session):
        """测试按案例类型筛选"""
        create_test_cases(clean_db)

        # 测试筛选商户异常
        response = client.get("/api/v1/cases/?case_type=商户异常")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 3
        assert all(case["case_type"] == "商户异常" for case in data["data"])

        # 测试筛选券策略复核
        response = client.get("/api/v1/cases/?case_type=券策略复核")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 1
        assert data["data"][0]["case_type"] == "券策略复核"

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_list_cases_with_merchant_id_filter(self, clean_db: Session):
        """测试按商户ID筛选（T118）"""
        create_test_cases(clean_db)

        # 测试筛选 merchant_001
        response = client.get("/api/v1/cases/?merchant_id=merchant_001")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 2
        assert all(case["merchant_id"] == "merchant_001" for case in data["data"])

        # 测试筛选 merchant_002
        response = client.get("/api/v1/cases/?merchant_id=merchant_002")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 2
        assert all(case["merchant_id"] == "merchant_002" for case in data["data"])

        # 测试筛选不存在的商户
        response = client.get("/api/v1/cases/?merchant_id=merchant_999")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 0
        assert len(data["data"]) == 0

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_list_cases_with_created_after_filter(self, clean_db: Session):
        """测试按创建时间起始筛选（T117）"""
        create_test_cases(clean_db)

        # 筛选最近3天创建的案例
        now = datetime.now()
        three_days_ago = (now - timedelta(days=3)).isoformat()

        response = client.get(f"/api/v1/cases/?created_after={three_days_ago}")
        assert response.status_code == 200

        data = response.json()
        # 应该返回1天前和今天创建的案例
        assert data["total"] == 2

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_list_cases_with_created_before_filter(self, clean_db: Session):
        """测试按创建时间结束筛选（T117）"""
        create_test_cases(clean_db)

        # 筛选4天前创建的案例（应该包括案例1：7天前，案例3：5天前）
        now = datetime.now()
        four_days_ago = (now - timedelta(days=4)).isoformat()

        response = client.get(f"/api/v1/cases/?created_before={four_days_ago}")
        assert response.status_code == 200

        data = response.json()
        # 应该返回4天前及之前创建的案例（案例1：7天前，案例3：5天前）
        assert data["total"] >= 2

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_list_cases_with_time_range_filter(self, clean_db: Session):
        """测试按时间范围筛选（T117）"""
        create_test_cases(clean_db)

        # 筛选3-7天前创建的案例
        now = datetime.now()
        three_days_ago = (now - timedelta(days=3)).isoformat()
        seven_days_ago = (now - timedelta(days=7)).isoformat()

        response = client.get(
            f"/api/v1/cases/?created_after={seven_days_ago}&created_before={three_days_ago}"
        )
        assert response.status_code == 200

        data = response.json()
        # 应该返回3-7天前创建的案例
        assert data["total"] >= 1

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_list_cases_with_pagination(self, clean_db: Session):
        """测试分页功能"""
        create_test_cases(clean_db)

        # 测试 limit
        response = client.get("/api/v1/cases/?limit=2")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 5
        assert len(data["data"]) == 2
        assert data["limit"] == 2

        # 测试 offset
        response = client.get("/api/v1/cases/?limit=2&offset=2")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 5
        assert len(data["data"]) == 2
        assert data["offset"] == 2

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_list_cases_with_multiple_filters(self, clean_db: Session):
        """测试多条件组合筛选"""
        create_test_cases(clean_db)

        # 组合筛选：商户异常 + pending 状态 + merchant_001
        response = client.get(
            "/api/v1/cases/?case_type=商户异常&status=pending&merchant_id=merchant_001"
        )
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 1
        assert data["data"][0]["case_type"] == "商户异常"
        assert data["data"][0]["status"] == "pending"
        assert data["data"][0]["merchant_id"] == "merchant_001"


class TestCaseDetailWithApprovalHistory:
    """测试案例详情包含审批历史（T120, T121）"""

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_get_case_detail_with_approval_logs(self, clean_db: Session):
        """测试获取案例详情包含完整审批记录（T120）"""
        cases = create_test_cases(clean_db)

        # 为案例3创建推荐建议（案例3状态为 executed）
        recommendation = create_test_recommendation(clean_db, cases[2].id)

        # 创建审批记录
        approval_logs = create_test_approval_logs(clean_db, cases[2].id)

        # 创建执行记录
        create_test_action_executions(clean_db, cases[2].id, recommendation.id)

        # 获取案例详情
        response = client.get(f"/api/v1/cases/{cases[2].id}")
        assert response.status_code == 200

        data = response.json()

        # 验证基本信息
        assert data["id"] == cases[2].id
        assert data["case_type"] == "券策略复核"
        assert data["status"] == "executed"
        assert data["merchant_id"] == "merchant_002"

        # 验证推荐建议存在
        assert data["recommendation"] is not None
        assert data["recommendation"]["summary"] == "建议暂停商户活动并优化优惠券策略"
        assert len(data["recommendation"]["evidence_list"]) == 3
        assert len(data["recommendation"]["suggested_actions"]) == 1

        # 验证审批记录存在并按时间排序（T121）
        assert len(data["approval_logs"]) == 3

        # 验证审批记录按时间升序排列（最早的在前）
        timestamps = [log["created_at"] for log in data["approval_logs"]]
        assert timestamps == sorted(timestamps)

        # 验证审批记录内容
        log_actions = [log["action"] for log in data["approval_logs"]]
        assert "approve" in log_actions
        assert "reject" in log_actions
        assert "regenerate" in log_actions

        # 验证执行记录存在（案例状态为 executed）
        assert len(data["action_executions"]) == 1
        assert data["action_executions"][0]["action_type"] == "暂停活动"
        assert data["action_executions"][0]["execution_status"] == "success"

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_get_case_detail_without_recommendation(self, clean_db: Session):
        """测试获取没有推荐建议的案例详情"""
        cases = create_test_cases(clean_db)

        # 案例1处于pending状态，还没有推荐建议
        response = client.get(f"/api/v1/cases/{cases[0].id}")
        assert response.status_code == 200

        data = response.json()

        assert data["id"] == cases[0].id
        assert data["status"] == "pending"
        assert data["recommendation"] is None
        assert len(data["approval_logs"]) == 0
        assert len(data["action_executions"]) == 0

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_get_nonexistent_case(self, clean_db: Session):
        """测试获取不存在的案例"""
        response = client.get("/api/v1/cases/99999")
        assert response.status_code == 404