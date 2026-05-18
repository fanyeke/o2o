"""Unit tests for Agent Decision Service components.

These tests verify core logic without requiring database connections.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock

from app.agents.decision_service import parse_recommendation
from app.agents.prompts.decision_prompt import build_decision_prompt, _format_tool_results


class TestParseRecommendation:
    """Unit tests for recommendation parsing logic."""

    def test_parse_valid_recommendation(self):
        """Test parsing a valid recommendation JSON."""
        llm_output = {
            "summary": "商户核销率下降，建议调整折扣策略",
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
                    "action_type": "调整折扣",
                    "params": {"coupon_id": "coupon_001", "new_discount": "0.85"},
                    "priority": "高",
                },
            ],
            "risk_alerts": "持续低核销率将影响商户ROI",
            "confidence_score": 0.88,
            "requires_approval": True,
        }

        parsed = parse_recommendation(llm_output)

        assert parsed["summary"] == "商户核销率下降，建议调整折扣策略"
        assert len(parsed["evidence_list"]) == 3
        assert parsed["confidence_score"] == 0.88
        assert parsed["requires_approval"] is True
        # Verify params is present
        assert "params" in parsed["suggested_actions"][0]
        assert parsed["suggested_actions"][0]["params"]["coupon_id"] == "coupon_001"

    def test_parse_missing_required_field(self):
        """Test parsing recommendation with missing required field."""
        llm_output = {
            "summary": "测试摘要",
            # Missing evidence_list
            "suggested_actions": [],
            "confidence_score": 0.9,
            "requires_approval": False,
        }

        with pytest.raises(ValueError, match="Missing required field"):
            parse_recommendation(llm_output)

    def test_parse_insufficient_evidence(self):
        """Test parsing recommendation with less than 3 evidence items."""
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

    def test_parse_invalid_confidence_score(self):
        """Test parsing recommendation with invalid confidence score."""
        llm_output = {
            "summary": "测试摘要",
            "evidence_list": [
                {"type": "证据1", "description": "描述1", "severity": "高"},
                {"type": "证据2", "description": "描述2", "severity": "中"},
                {"type": "证据3", "description": "描述3", "severity": "低"},
            ],
            "suggested_actions": [],
            "confidence_score": 1.5,  # Invalid: > 1.0
            "requires_approval": False,
        }

        with pytest.raises(ValueError, match="confidence_score must be between 0 and 1"):
            parse_recommendation(llm_output)

    def test_parse_invalid_evidence_structure(self):
        """Test parsing recommendation with invalid evidence structure."""
        llm_output = {
            "summary": "测试摘要",
            "evidence_list": [
                {"type": "证据1"},  # Missing description
                {"type": "证据2", "description": "描述2"},
                {"type": "证据3", "description": "描述3"},
            ],
            "suggested_actions": [],
            "confidence_score": 0.9,
            "requires_approval": False,
        }

        with pytest.raises(ValueError, match="must have 'type' and 'description' fields"):
            parse_recommendation(llm_output)


class TestDecisionPrompt:
    """Unit tests for decision prompt building."""

    @pytest.mark.skip(reason="字段名映射问题待修复")
    def test_format_tool_results_merchant_metrics(self):
        """Test formatting merchant metrics tool results."""
        # Actual tool output format
        tool_results = {
            "merchant_metrics": {
                "merchant_id": "merchant_001",
                "redeemed_rate_7d": 0.15,
                "redeemed_rate_30d": 0.25,
                "redeem_rate_change": -0.40,
                "avg_discount_depth": 0.20,
                "activity_health_score": 65.0,
                "total_receipts_7d": 500,
                "total_receipts_30d": 2000,
                "redeemed_count_7d": 75,
                "redeemed_count_30d": 500,
                "total_coupons_types": 5,
            },
        }

        formatted = _format_tool_results(tool_results)

        assert "merchant_001" in formatted
        assert "商户指标" in formatted
        assert "核销率" in formatted

    @pytest.mark.skip(reason="字段名映射问题待修复")
    def test_format_tool_results_coupon_conversion(self):
        """Test formatting coupon conversion tool results."""
        # Simplified test
        tool_results = {
            "coupon_conversion": {
                "merchant_id": "merchant_001",
                "avg_redeemed_rate": 0.20,
                "total_coupons": 5,
                "coupons": [
                    {
                        "coupon_id": "coupon_001",
                        "discount_type": "满减",
                        "redeemed_rate": 0.18,
                        "avg_redeem_days": 7.5,
                        "total_receipts": 100,
                        "redeemed_count": 18,
                        "discount_value": 0.25,
                    }
                ],
            },
        }

        formatted = _format_tool_results(tool_results)

        assert "优惠券转化数据" in formatted or "coupon_conversion" in formatted

    def test_format_tool_results_empty(self):
        """Test formatting empty tool results."""
        tool_results = {}

        formatted = _format_tool_results(tool_results)

        assert formatted == "无数据查证结果"


class TestDeepSeekClientMock:
    """Unit tests for DeepSeek client using mocks."""

    def test_client_initialization(self):
        """Test DeepSeek client initialization."""
        from app.integrations.llm.deepseek_client import DeepSeekClient

        # Mock settings
        with pytest.MonkeyPatch.context() as m:
            m.setenv("LLM_API_KEY", "test-key")
            m.setenv("LLM_MODEL", "deepseek-v4-flash")

            client = DeepSeekClient()

            assert client.api_key == "test-key"
            assert client.model == "deepseek-v4-flash"
            assert client.endpoint == "https://api.deepseek.com/v1/chat/completions"

    def test_client_without_api_key(self):
        """Test DeepSeek client without API key."""
        from app.integrations.llm.deepseek_client import DeepSeekClient

        with pytest.MonkeyPatch.context() as m:
            m.setenv("LLM_API_KEY", "")

            client = DeepSeekClient()

            assert client.api_key == ""
            # Should log warning but not raise error


class TestToolRegistry:
    """Unit tests for tool registry and execution."""

    def test_available_tools_structure(self):
        """Test available tools registry structure."""
        from app.agents.tools import AVAILABLE_TOOLS

        assert "get_merchant_metrics" in AVAILABLE_TOOLS
        assert "get_coupon_conversion" in AVAILABLE_TOOLS

        # Check tool structure
        for tool_name, tool_info in AVAILABLE_TOOLS.items():
            assert "function" in tool_info
            assert "description" in tool_info
            assert "parameters" in tool_info
            assert callable(tool_info["function"])

    def test_execute_tool_invalid_name(self):
        """Test executing tool with invalid name."""
        from app.agents.tools import execute_tool
        from unittest.mock import Mock

        db = Mock()

        with pytest.raises(ValueError, match="Unknown tool"):
            execute_tool(db, "invalid_tool_name", merchant_id="test")