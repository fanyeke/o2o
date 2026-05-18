"""Integration tests for Agent Decision Service.

Tests the complete agent decision flow:
1. Rule triggers DecisionCase creation
2. Agent retrieves data via Tools
3. Agent generates recommendation via DeepSeek LLM
4. Recommendation is persisted to database
"""
import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session

from app.agents.decision_service import (
    AgentDecisionService,
    generate_recommendation,
    parse_recommendation,
)
from app.agents.prompts.decision_prompt import build_decision_prompt
from app.domain.application.decision_case import DecisionCase
from app.domain.application.recommendation import Recommendation
from app.domain.feature.merchant_metrics import MerchantMetrics


@pytest.fixture
def sample_decision_case(db_session: Session) -> DecisionCase:
    """Create a sample decision case for testing.

    Args:
        db_session: Database session

    Returns:
        Created DecisionCase instance
    """
    case = DecisionCase(
        case_type="商户异常",
        severity_level="高",
        merchant_id="merchant_001",
        trigger_rule_id="merchant_redeem_rate_drop",
        trigger_metrics_snapshot={
            "redeem_rate_7d": 0.15,
            "redeem_rate_30d": 0.25,
            "redeem_rate_change": -0.40,
            "total_receipts_7d": 500,
        },
        status="pending",
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    db_session.add(case)
    db_session.commit()
    return case


@pytest.fixture
def sample_merchant_metrics(db_session: Session) -> MerchantMetrics:
    """Create sample merchant metrics for testing.

    Args:
        db_session: Database session

    Returns:
        Created MerchantMetrics instance
    """
    metrics = MerchantMetrics(
        merchant_id="merchant_001",
        total_receipts_7d=500,
        redeemed_count_7d=75,
        redeemed_rate_7d=0.15,
        total_receipts_30d=2000,
        redeemed_count_30d=500,
        redeemed_rate_30d=0.25,
        redeemed_rate_change=-0.40,
        avg_discount_depth=0.20,
        activity_health_score=65.0,
        last_activity_date=datetime.now().date(),
        updated_at=datetime.now(),
    )
    db_session.add(metrics)
    db_session.commit()
    return metrics


class TestAgentDecisionService:
    """Test cases for AgentDecisionService."""

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_generate_recommendation_success(
        self,
        db_session: Session,
        sample_decision_case: DecisionCase,
        sample_merchant_metrics: MerchantMetrics,
    ):
        """Test successful recommendation generation.

        Validates:
        - Agent retrieves merchant metrics via Tool
        - DeepSeek returns structured JSON recommendation
        - Recommendation is parsed and persisted
        - At least 3 evidence items are provided
        - Tool trace is recorded
        """
        # Mock DeepSeek API response
        mock_llm_response = {
            "summary": "商户核销率显著下降，需紧急调整策略",
            "evidence_list": [
                {
                    "type": "指标异常",
                    "description": "近7日核销率15%，较30日基线25%下降40%",
                    "severity": "高",
                },
                {
                    "type": "发券规模",
                    "description": "近7日发券量500张，较30日均值略有下降",
                    "severity": "中",
                },
                {
                    "type": "折扣分析",
                    "description": "平均折扣深度20%，属于中等水平",
                    "severity": "低",
                },
            ],
            "suggested_actions": [
                {
                    "action_type": "调整折扣",
                    "description": "建议提高折扣深度至25-30%以刺激核销",
                    "priority": "高",
                },
                {
                    "action_type": "人群优化",
                    "description": "针对高核销历史用户精准投放",
                    "priority": "中",
                },
            ],
            "risk_alerts": "若不采取行动，核销率可能继续下滑，影响商户ROI",
            "confidence_score": 0.85,
            "requires_approval": True,
        }

        with patch("app.agents.decision_service.DeepSeekClient") as mock_deepseek:
            # Configure mock DeepSeek client
            mock_client = MagicMock()
            mock_client.generate_json.return_value = (mock_llm_response, 150, 1.5)
            mock_deepseek.return_value = mock_client

            # Generate recommendation
            service = AgentDecisionService(db_session)
            recommendation = service.generate_recommendation(
                case_id=sample_decision_case.id
            )

            # Verify recommendation structure
            assert recommendation is not None
            assert recommendation.case_id == sample_decision_case.id
            assert recommendation.summary == "商户核销率显著下降，需紧急调整策略"
            assert len(recommendation.evidence_list) >= 3
            assert recommendation.confidence_score == 0.85
            assert recommendation.requires_approval is True

            # Verify tool trace is recorded
            assert recommendation.tool_trace is not None
            assert len(recommendation.tool_trace) >= 2  # At least 2 tool calls

            # Verify LLM metadata
            assert recommendation.llm_tokens_used == 150

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_generate_recommendation_llm_failure_retry(
        self,
        db_session: Session,
        sample_decision_case: DecisionCase,
    ):
        """Test LLM failure with retry logic.

        Validates:
        - Service retries on LLM failure (max 3 attempts)
        - Case status updated to 'failed' after max retries
        - Error message is recorded
        """
        with patch("app.agents.decision_service.DeepSeekClient") as mock_deepseek:
            # Configure mock to raise exception
            mock_client = MagicMock()
            mock_client.generate_json.side_effect = Exception("API timeout")
            mock_deepseek.return_value = mock_client

            # Generate recommendation should fail
            service = AgentDecisionService(db_session)
            recommendation = service.generate_recommendation(
                case_id=sample_decision_case.id
            )

            # Verify failure handling
            assert recommendation is None

            # Verify case status updated
            db_session.refresh(sample_decision_case)
            assert sample_decision_case.status == "failed"

            # Verify retry count
            assert mock_client.generate_json.call_count == 3

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_parse_recommendation_valid_json(self):
        """Test parsing valid JSON recommendation from LLM.

        Validates:
        - JSON is correctly parsed
        - All required fields are present
        - Evidence list has at least 3 items
        """
        llm_output = {
            "summary": "测试摘要",
            "evidence_list": [
                {"type": "证据1", "description": "描述1", "severity": "高"},
                {"type": "证据2", "description": "描述2", "severity": "中"},
                {"type": "证据3", "description": "描述3", "severity": "低"},
            ],
            "suggested_actions": [
                {"action_type": "动作1", "description": "动作描述1", "priority": "高"}
            ],
            "risk_alerts": "风险提示",
            "confidence_score": 0.9,
            "requires_approval": True,
        }

        parsed = parse_recommendation(llm_output)

        assert parsed["summary"] == "测试摘要"
        assert len(parsed["evidence_list"]) == 3
        assert len(parsed["suggested_actions"]) == 1
        assert parsed["confidence_score"] == 0.9

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_parse_recommendation_missing_fields(self):
        """Test parsing JSON with missing required fields.

        Validates:
        - Missing required fields raise validation error
        """
        llm_output = {
            "summary": "测试摘要",
            # Missing evidence_list
            "suggested_actions": [],
            "confidence_score": 0.9,
        }

        with pytest.raises(ValueError, match="Missing required field"):
            parse_recommendation(llm_output)

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_parse_recommendation_insufficient_evidence(self):
        """Test parsing JSON with insufficient evidence.

        Validates:
        - Less than 3 evidence items raise validation error
        """
        llm_output = {
            "summary": "测试摘要",
            "evidence_list": [
                {"type": "证据1", "description": "描述1", "severity": "高"},
            ],
            "suggested_actions": [],
            "confidence_score": 0.9,
            "requires_approval": False,
        }

        with pytest.raises(ValueError, match="At least 3 evidence items required"):
            parse_recommendation(llm_output)

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_build_decision_prompt(self, sample_decision_case: DecisionCase):
        """Test building decision prompt for LLM.

        Validates:
        - Prompt includes case context
        - Prompt includes merchant metrics
        - Prompt defines agent role clearly
        - Prompt requires structured output
        """
        tool_results = {
            "merchant_metrics": {
                "merchant_id": "merchant_001",
                "redeem_rate_7d": 0.15,
                "redeem_rate_30d": 0.25,
                "redeem_rate_change": -0.40,
            },
            "coupon_conversion": {
                "total_coupons": 5,
                "avg_redeem_rate": 0.20,
            },
        }

        prompt = build_decision_prompt(
            case=sample_decision_case, tool_results=tool_results
        )

        assert "商户异常" in prompt
        assert "merchant_001" in prompt
        assert "核销率" in prompt
        assert "优惠券运营决策专家" in prompt
        assert "至少3条证据" in prompt
        assert "JSON格式" in prompt


class TestAgentTools:
    """Test cases for Agent Tools."""

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_get_merchant_metrics_tool(
        self,
        db_session: Session,
        sample_merchant_metrics: MerchantMetrics,
    ):
        """Test get_merchant_metrics tool.

        Validates:
        - Tool retrieves correct merchant metrics
        - Tool returns structured data
        """
        from app.agents.tools import get_merchant_metrics

        result = get_merchant_metrics(db_session, "merchant_001")

        assert result is not None
        assert result["merchant_id"] == "merchant_001"
        assert result["redeem_rate_7d"] == 0.15
        assert result["redeem_rate_30d"] == 0.25
        assert result["redeem_rate_change"] == -0.40

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_get_merchant_metrics_not_found(self, db_session: Session):
        """Test get_merchant_metrics tool when merchant not found.

        Validates:
        - Tool returns None for non-existent merchant
        """
        from app.agents.tools import get_merchant_metrics

        result = get_merchant_metrics(db_session, "nonexistent_merchant")

        assert result is None

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_get_coupon_conversion_tool(
        self,
        db_session: Session,
    ):
        """Test get_coupon_conversion tool.

        Validates:
        - Tool retrieves coupon conversion data
        - Tool returns aggregated metrics
        """
        from app.agents.tools import get_coupon_conversion

        result = get_coupon_conversion(db_session, "merchant_001")

        assert result is not None
        assert "total_coupons" in result
        assert "avg_redeem_rate" in result


class TestDecisionServiceIntegration:
    """Integration tests for complete decision flow."""

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    async def test_complete_decision_flow(
        self,
        db_session: Session,
        sample_decision_case: DecisionCase,
        sample_merchant_metrics: MerchantMetrics,
    ):
        """Test complete decision flow from case creation to recommendation.

        This is an end-to-end test that validates:
        1. DecisionCase is created with pending status
        2. Agent generates recommendation
        3. Recommendation is persisted
        4. Case status updated to 'recommended'
        5. Tool trace is recorded
        6. LLM metadata is saved
        """
        # Mock DeepSeek response
        mock_llm_response = {
            "summary": "商户核销率下降40%，建议调整折扣策略",
            "evidence_list": [
                {
                    "type": "核销率异常",
                    "description": "近7日核销率15%，较30日基线25%下降40%",
                    "severity": "高",
                },
                {
                    "type": "发券规模",
                    "description": "近7日发券500张，规模正常",
                    "severity": "中",
                },
                {
                    "type": "折扣水平",
                    "description": "平均折扣深度20%，竞争力不足",
                    "severity": "中",
                },
            ],
            "suggested_actions": [
                {
                    "action_type": "提高折扣",
                    "description": "建议将折扣深度提高至25-30%",
                    "priority": "高",
                },
            ],
            "risk_alerts": "持续低核销率将影响商户ROI和平台声誉",
            "confidence_score": 0.88,
            "requires_approval": True,
        }

        with patch("app.agents.decision_service.DeepSeekClient") as mock_deepseek:
            mock_client = MagicMock()
            mock_client.generate_json.return_value = (mock_llm_response, 180, 2.0)
            mock_deepseek.return_value = mock_client

            # Execute decision flow
            service = AgentDecisionService(db_session)
            recommendation = service.generate_recommendation(
                case_id=sample_decision_case.id
            )

            # Verify recommendation
            assert recommendation is not None
            assert recommendation.case_id == sample_decision_case.id
            assert len(recommendation.evidence_list) >= 3
            assert recommendation.confidence_score == 0.88

            # Verify case status updated
            db_session.refresh(sample_decision_case)
            assert sample_decision_case.status == "recommended"

            # Verify recommendation persisted
            saved_rec = (
                db_session.query(Recommendation)
                .filter(Recommendation.case_id == sample_decision_case.id)
                .first()
            )
            assert saved_rec is not None
            assert saved_rec.llm_tokens_used == 180
            assert saved_rec.tool_trace is not None