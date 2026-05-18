"""Unit tests for Recommendation trace fields and observability.

M7 Observability acceptance criteria tests:
1. test_recommendation_has_all_trace_fields
2. test_decision_trace_complete_rate_100_percent
3. test_llm_logs_sanitized
4. test_failure_reason_queryable
5. test_action_execution_duration_recorded

These tests are designed to be independent and not require database fixtures.
Database-dependent tests are marked with integration test markers.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy import inspect

from app.domain.application.recommendation import Recommendation
from app.domain.application.decision_case import DecisionCase
from app.domain.application.action_execution import ActionExecution


class TestRecommendationTraceFields:
    """Test 1: Verify Recommendation has all required trace fields."""

    def test_recommendation_has_all_trace_fields(self):
        """Recommendation must have all observability trace fields.

        Required fields:
        - rule_id: ID of the rule that triggered this case
        - tool_trace: List of tool execution records
        - model_version: ML model version used
        - feature_version: Feature engineering version
        - prediction_summary: ML prediction summary
        - prompt_version: Prompt template version
        - llm_model: LLM model name used
        - llm_latency_ms: LLM response latency in milliseconds
        - approval_operator: ID of operator who approved
        - action_execution_id: ID of executed action
        """
        # Get column names from Recommendation model
        mapper = inspect(Recommendation)
        column_names = {column.key for column in mapper.columns}

        # Required trace fields for M7 observability
        required_trace_fields = {
            # Already existing fields
            "id",
            "case_id",
            "summary",
            "evidence_list",
            "suggested_actions",
            "risk_alerts",
            "confidence_score",
            "requires_approval",
            "tool_trace",
            "llm_raw_output",
            "llm_tokens_used",
            "created_at",
            # New fields for M7 observability
            "rule_id",           # Trigger rule ID
            "model_version",     # ML model version
            "feature_version",   # Feature engineering version
            "prediction_summary", # ML prediction summary JSON
            "prompt_version",    # Prompt template version
            "llm_model",         # LLM model name
            "llm_latency_ms",    # LLM response latency
            "approval_operator", # Approval operator ID
            "action_execution_id", # Linked action execution ID
        }

        missing_fields = required_trace_fields - column_names

        assert not missing_fields, (
            f"Recommendation model missing trace fields: {missing_fields}. "
            f"Current columns: {column_names}"
        )

    def test_recommendation_field_types_correct(self):
        """Verify new trace fields have correct types."""
        mapper = inspect(Recommendation)

        # Check field types
        field_types = {col.key: type(col.type).__name__ for col in mapper.columns}

        # Verify string fields
        string_fields = ["rule_id", "model_version", "feature_version",
                        "prompt_version", "llm_model", "approval_operator"]
        for field in string_fields:
            if field in field_types:
                assert field_types[field] in ("String", "VARCHAR", "StringType"), (
                    f"Field {field} should be String type, got {field_types[field]}"
                )

        # Verify integer fields
        integer_fields = ["llm_latency_ms", "action_execution_id", "llm_tokens_used"]
        for field in integer_fields:
            if field in field_types:
                assert field_types[field] in ("Integer", "INTEGER", "BigInteger"), (
                    f"Field {field} should be Integer type, got {field_types[field]}"
                )

        # Verify JSON fields
        json_fields = ["tool_trace", "prediction_summary"]
        for field in json_fields:
            if field in field_types:
                assert field_types[field] in ("JSON", "JSONB"), (
                    f"Field {field} should be JSON type, got {field_types[field]}"
                )


class TestDecisionTraceCompleteness:
    """Test 2: Verify 100% trace completeness for decisions."""

    def test_trace_completeness_validation_on_create(self):
        """Trace completeness should be validated on creation."""
        # This test verifies that creating a recommendation with all
        # trace fields works correctly

        # Test that Recommendation can be created with required fields
        recommendation = Recommendation(
            case_id=1,
            evidence_list=[{"type": "test", "description": "test"}],
            suggested_actions=[{"action_type": "test", "params": {}}],
            confidence_score=0.9,
            requires_approval=False,
            rule_id="rule_001",
            tool_trace=[],
            model_version="v1.0.0",
            feature_version="v1.0.0",
            prediction_summary={},
            prompt_version="v1.0.0",
            llm_model="deepseek-v4-flash",
            llm_latency_ms=1000,
        )

        # All fields should be set
        assert recommendation.rule_id == "rule_001"
        assert recommendation.model_version == "v1.0.0"
        assert recommendation.llm_latency_ms == 1000
        assert recommendation.tool_trace == []
        assert recommendation.prediction_summary == {}
        assert recommendation.prompt_version == "v1.0.0"
        assert recommendation.llm_model == "deepseek-v4-flash"

    def test_trace_field_defaults(self):
        """Trace fields should support None defaults."""
        # Create recommendation without trace fields (using defaults)
        recommendation = Recommendation(
            case_id=1,
            evidence_list=[{"type": "test", "description": "test"}],
            suggested_actions=[{"action_type": "test", "params": {}}],
            confidence_score=0.9,
            requires_approval=False,
        )

        # Optional trace fields should be None
        assert recommendation.rule_id is None
        assert recommendation.model_version is None
        assert recommendation.llm_latency_ms is None


class TestLLMLogsSanitization:
    """Test 3: Verify LLM logs are sanitized."""

    def test_llm_logs_sanitized(self):
        """LLM raw output should not contain sensitive data.

        Sensitive data includes:
        - API keys
        - Passwords
        - PII (phone numbers, IDs)
        - Credit card numbers
        """
        from app.agents.decision_service import sanitize_llm_output

        # Test data with sensitive information
        raw_output = """
        {
            "summary": "商户分析报告",
            "evidence_list": [
                {"type": "用户数据", "description": "用户手机号: 13812345678"}
            ],
            "api_key": "sk-proj-xxxxxxxxxxxx",
            "password": "secret123",
            "id_card": "310101199001011234"
        }
        """

        sanitized = sanitize_llm_output(raw_output)

        # Sensitive data should be masked
        assert "sk-proj-" not in sanitized
        assert "secret123" not in sanitized
        assert "13812345678" not in sanitized
        assert "310101199001011234" not in sanitized

        # Non-sensitive data should be preserved
        assert "商户分析报告" in sanitized

    def test_llm_logs_phone_number_masked(self):
        """Phone numbers should be masked in logs."""
        from app.agents.decision_service import sanitize_llm_output

        raw_output = "联系手机：13912345678，备用电话：021-12345678"
        sanitized = sanitize_llm_output(raw_output)

        # Phone numbers should be masked
        assert "13912345678" not in sanitized
        assert "021-12345678" not in sanitized
        assert "***" in sanitized or "xxx" in sanitized.lower() or "*" in sanitized

    def test_llm_logs_api_key_masked(self):
        """API keys should be masked in logs."""
        from app.agents.decision_service import sanitize_llm_output

        raw_output = '{"api_key": "sk-xxxxxxxxxxxxxx", "token": "ghp_xxxxxxxxxxxx"}'
        sanitized = sanitize_llm_output(raw_output)

        assert "sk-xxxxxxxxxxxxxx" not in sanitized
        assert "ghp_xxxxxxxxxxxx" not in sanitized

    def test_sanitize_preserves_structure(self):
        """Sanitization should preserve JSON structure."""
        from app.agents.decision_service import sanitize_llm_output
        import json

        raw_output = '{"summary": "测试", "api_key": "secret123"}'
        sanitized = sanitize_llm_output(raw_output)

        # Should still be valid JSON
        parsed = json.loads(sanitized)
        assert parsed["summary"] == "测试"
        assert parsed["api_key"] != "secret123"
        assert "***REDACTED***" in parsed["api_key"]


class TestFailureReasonQueryable:
    """Test 4: Verify failure reasons are queryable (model-level tests)."""

    def test_tool_trace_structure_for_failure(self):
        """Tool trace should have structured failure information."""
        # Create recommendation with failure trace
        recommendation = Recommendation(
            case_id=1,
            evidence_list=[{"type": "test", "description": "test"}],
            suggested_actions=[{"action_type": "test", "params": {}}],
            confidence_score=0.0,
            requires_approval=False,
            tool_trace=[
                {
                    "tool_name": "get_merchant_metrics",
                    "error": "Connection timeout",
                    "error_type": "llm_timeout",
                    "timestamp": datetime.now().isoformat(),
                }
            ],
            llm_raw_output='{"error": "LLM API call failed after 3 retries"}',
            llm_model="deepseek-v4-flash",
        )

        # Verify tool trace structure
        assert recommendation.tool_trace is not None
        assert len(recommendation.tool_trace) > 0
        assert "error" in recommendation.tool_trace[0]
        assert "error_type" in recommendation.tool_trace[0]

    def test_failure_reason_multiple_types(self):
        """Different failure types should be distinguishable."""
        failure_types = [
            ("llm_timeout", "LLM API timeout after 30 seconds"),
            ("tool_error", "Database connection failed"),
            ("parse_error", "Failed to parse LLM JSON response"),
        ]

        for failure_type, failure_message in failure_types:
            recommendation = Recommendation(
                case_id=1,
                evidence_list=[{"type": "test", "description": "test"}],
                suggested_actions=[{"action_type": "test", "params": {}}],
                confidence_score=0.0,
                requires_approval=False,
                rule_id=f"rule_{failure_type}",
                tool_trace=[
                    {
                        "tool_name": "test_tool",
                        "error": failure_message,
                        "error_type": failure_type,
                        "timestamp": datetime.now().isoformat(),
                    }
                ],
            )

            # Verify each failure type is captured
            assert recommendation.tool_trace[0]["error_type"] == failure_type
            assert recommendation.tool_trace[0]["error"] == failure_message


class TestActionExecutionDuration:
    """Test 5: Verify action execution duration is recorded (model-level tests)."""

    def test_action_execution_duration_field_exists(self):
        """ActionExecution must have duration_ms field."""
        mapper = inspect(ActionExecution)
        column_names = {column.key for column in mapper.columns}

        assert "duration_ms" in column_names, (
            f"ActionExecution missing duration_ms field. "
            f"Current columns: {column_names}"
        )

    def test_action_execution_duration_type(self):
        """duration_ms should be Integer type."""
        mapper = inspect(ActionExecution)
        field_types = {col.key: type(col.type).__name__ for col in mapper.columns}

        assert field_types["duration_ms"] in ("Integer", "INTEGER"), (
            f"duration_ms should be Integer type, got {field_types['duration_ms']}"
        )

    def test_action_execution_duration_can_be_set(self):
        """duration_ms can be set on ActionExecution."""
        action = ActionExecution(
            case_id=1,
            recommendation_id=1,
            action_type="调整折扣",
            execution_status="success",
            duration_ms=150,
        )

        assert action.duration_ms == 150

    def test_action_execution_duration_zero_valid(self):
        """Duration can be 0 for instant mock actions."""
        action = ActionExecution(
            case_id=1,
            recommendation_id=1,
            action_type="暂停活动",
            execution_status="success",
            duration_ms=0,
        )

        assert action.duration_ms == 0

    def test_action_execution_duration_none_valid(self):
        """Duration can be None for pending actions."""
        action = ActionExecution(
            case_id=1,
            recommendation_id=1,
            action_type="发送优惠券",
            execution_status="pending",
        )

        assert action.duration_ms is None


# Integration tests that require database
@pytest.mark.integration
class TestRecommendationTraceFieldsIntegration:
    """Integration tests for trace completeness with database."""

    def test_decision_trace_complete_rate_100_percent(self, db_session, clean_db):
        """Every recommendation must have complete trace fields.

        This integration test verifies database persistence of trace fields.
        """
        # Create a decision case first
        case = DecisionCase(
            case_type="商户异常",
            severity_level="高",
            merchant_id="merchant_001",
            status="pending",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        db_session.add(case)
        db_session.commit()

        # Create recommendation with trace fields
        recommendation = Recommendation(
            case_id=case.id,
            summary="测试推荐",
            evidence_list=[
                {"type": "证据1", "description": "描述1"},
                {"type": "证据2", "description": "描述2"},
                {"type": "证据3", "description": "描述3"},
            ],
            suggested_actions=[{"action_type": "调整折扣", "params": {"discount": 0.9}}],
            confidence_score=0.85,
            requires_approval=True,
            rule_id="rule_merchant_redeem_rate_drop",
            tool_trace=[
                {"tool_name": "get_merchant_metrics", "timestamp": datetime.now().isoformat()}
            ],
            model_version="v1.0.0",
            feature_version="v1.2.0",
            prediction_summary={"redeem_probability": 0.75},
            prompt_version="v1.0.0",
            llm_model="deepseek-v4-flash",
            llm_latency_ms=1500,
            llm_tokens_used=500,
            created_at=datetime.now(),
        )

        db_session.add(recommendation)
        db_session.commit()

        # Verify all trace fields are populated
        saved_rec = db_session.query(Recommendation).filter_by(case_id=case.id).first()

        assert saved_rec is not None
        assert saved_rec.rule_id == "rule_merchant_redeem_rate_drop"
        assert saved_rec.tool_trace is not None
        assert len(saved_rec.tool_trace) > 0
        assert saved_rec.model_version == "v1.0.0"
        assert saved_rec.feature_version == "v1.2.0"
        assert saved_rec.prediction_summary is not None
        assert saved_rec.prediction_summary["redeem_probability"] == 0.75
        assert saved_rec.prompt_version == "v1.0.0"
        assert saved_rec.llm_model == "deepseek-v4-flash"
        assert saved_rec.llm_latency_ms == 1500


@pytest.mark.integration
class TestFailureReasonQueryableIntegration:
    """Integration tests for failure reason queryability with database."""

    def test_failure_reason_queryable(self, db_session, clean_db):
        """Failed decisions should have queryable failure reasons."""
        case = DecisionCase(
            case_type="商户异常",
            severity_level="高",
            merchant_id="merchant_001",
            status="failed",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        db_session.add(case)
        db_session.commit()

        recommendation = Recommendation(
            case_id=case.id,
            evidence_list=[{"type": "test", "description": "test"}],
            suggested_actions=[{"action_type": "test", "params": {}}],
            confidence_score=0.0,
            requires_approval=False,
            rule_id="rule_001",
            tool_trace=[{"tool_name": "get_merchant_metrics", "error": "Connection timeout"}],
            llm_raw_output='{"error": "LLM API call failed after 3 retries"}',
            llm_model="deepseek-v4-flash",
            created_at=datetime.now(),
        )
        db_session.add(recommendation)
        db_session.commit()

        # Query for failed decisions
        failed_recommendations = (
            db_session.query(Recommendation)
            .join(DecisionCase)
            .filter(DecisionCase.status == "failed")
            .all()
        )

        assert len(failed_recommendations) == 1
        assert "error" in failed_recommendations[0].tool_trace[0]


@pytest.mark.integration
class TestActionExecutionDurationIntegration:
    """Integration tests for action execution duration with database."""

    def test_action_execution_duration_recorded(self, db_session, clean_db):
        """ActionExecution must record execution duration in milliseconds."""
        case = DecisionCase(
            case_type="商户异常",
            merchant_id="merchant_001",
            status="approved",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        db_session.add(case)
        db_session.commit()

        recommendation = Recommendation(
            case_id=case.id,
            evidence_list=[{"type": "test", "description": "test"}],
            suggested_actions=[{"action_type": "调整折扣", "params": {"discount": 0.9}}],
            confidence_score=0.85,
            requires_approval=True,
            rule_id="rule_001",
            created_at=datetime.now(),
        )
        db_session.add(recommendation)
        db_session.commit()

        action = ActionExecution(
            case_id=case.id,
            recommendation_id=recommendation.id,
            action_type="调整折扣",
            action_params={"discount": 0.9},
            execution_status="success",
            execution_result="折扣已从0.85调整为0.9",
            executed_at=datetime.now(),
            duration_ms=150,
        )
        db_session.add(action)
        db_session.commit()

        saved_action = db_session.query(ActionExecution).filter_by(case_id=case.id).first()

        assert saved_action is not None
        assert saved_action.duration_ms is not None
        assert saved_action.duration_ms == 150