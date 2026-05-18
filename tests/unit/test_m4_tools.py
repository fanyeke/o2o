"""Unit tests for prediction_summary_tool and campaign_simulation_tool.

M4 High Standard: Ensure >=80% coverage for new Agent tools.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import json


# =============================================================================
# Prediction Summary Tool Tests
# =============================================================================

class TestGetPredictionSummary:
    """Tests for get_prediction_summary tool."""

    def test_tool_exists_and_is_callable(self):
        """Verify tool function exists and is callable."""
        from app.agents.tools.prediction_summary_tool import get_prediction_summary

        assert callable(get_prediction_summary)

    def test_returns_valid_json_structure(self):
        """Test that tool returns valid JSON-serializable structure."""
        from app.agents.tools.prediction_summary_tool import get_prediction_summary

        # Mock database session
        mock_db = Mock()

        # Call tool
        result = get_prediction_summary(mock_db, merchant_id="m001")

        # Verify structure
        assert isinstance(result, dict)
        assert "target_type" in result
        assert "target_id" in result
        assert "prediction_score" in result
        assert "signal_type" in result
        assert "confidence_interval" in result
        assert "evidence" in result

    def test_prediction_score_in_valid_range(self):
        """Test that prediction_score is in [0, 1] range."""
        from app.agents.tools.prediction_summary_tool import get_prediction_summary

        mock_db = Mock()
        result = get_prediction_summary(mock_db, merchant_id="m001")

        assert 0 <= result["prediction_score"] <= 1

    def test_signal_type_classification(self):
        """Test signal type is correctly classified based on score."""
        from app.agents.tools.prediction_summary_tool import (
            get_prediction_summary,
            _classify_signal_type,
        )

        # Test classification function directly
        assert _classify_signal_type(0.8) == "high_redeem_probability"
        assert _classify_signal_type(0.6) == "medium_redeem_probability"
        assert _classify_signal_type(0.4) == "low_redeem_probability"
        assert _classify_signal_type(0.2) == "very_low_redeem_probability"

    def test_evidence_list_has_required_fields(self):
        """Test each evidence item has type, description, content, severity."""
        from app.agents.tools.prediction_summary_tool import get_prediction_summary

        mock_db = Mock()
        result = get_prediction_summary(mock_db, merchant_id="m001")

        for evidence in result.get("evidence", []):
            assert "type" in evidence
            assert "description" in evidence
            assert "content" in evidence
            assert "severity" in evidence

    def test_handles_missing_ml_service(self):
        """Test tool handles missing ML service gracefully."""
        from app.agents.tools.prediction_summary_tool import get_prediction_summary

        mock_db = Mock()
        # Should return mock data when ML service is unavailable
        result = get_prediction_summary(mock_db, merchant_id="m001")

        assert result is not None
        assert "prediction_score" in result
        # Mock flag indicates fallback
        assert result.get("_mock") == True

    def test_handles_user_id_parameter(self):
        """Test tool works with user_id parameter."""
        from app.agents.tools.prediction_summary_tool import get_prediction_summary

        mock_db = Mock()
        result = get_prediction_summary(mock_db, user_id="u001")

        assert result["target_type"] == "user"
        assert result["target_id"] == "u001"

    def test_handles_coupon_id_parameter(self):
        """Test tool works with coupon_id parameter."""
        from app.agents.tools.prediction_summary_tool import get_prediction_summary

        mock_db = Mock()
        result = get_prediction_summary(mock_db, coupon_id="c001")

        assert result["target_type"] == "coupon"
        assert result["target_id"] == "c001"

    def test_handles_no_parameters(self):
        """Test tool handles missing parameters."""
        from app.agents.tools.prediction_summary_tool import get_prediction_summary

        mock_db = Mock()
        result = get_prediction_summary(mock_db)

        assert "error" in result
        assert result["evidence"] == []


# =============================================================================
# Campaign Simulation Tool Tests
# =============================================================================

class TestSimulateCampaignEffect:
    """Tests for simulate_campaign_effect tool."""

    def test_tool_exists_and_is_callable(self):
        """Verify tool function exists and is callable."""
        from app.agents.tools.campaign_simulation_tool import simulate_campaign_effect

        assert callable(simulate_campaign_effect)

    def test_returns_valid_json_structure(self):
        """Test that tool returns valid JSON-serializable structure."""
        from app.agents.tools.campaign_simulation_tool import simulate_campaign_effect

        mock_db = Mock()
        result = simulate_campaign_effect(
            mock_db,
            merchant_id="m001",
            adjustment_type="change_discount",
            adjustment_params={"new_discount": 0.3},
        )

        assert isinstance(result, dict)
        assert "merchant_id" in result
        assert "adjustment_type" in result
        assert "simulation_result" in result
        assert "evidence" in result

    def test_simulation_result_has_required_fields(self):
        """Test simulation result contains expected metrics."""
        from app.agents.tools.campaign_simulation_tool import simulate_campaign_effect

        mock_db = Mock()
        result = simulate_campaign_effect(
            mock_db,
            merchant_id="m001",
            adjustment_type="change_discount",
        )

        sim = result["simulation_result"]
        assert "expected_redeem_rate" in sim
        assert "rate_change_percent" in sim
        assert "expected_volume" in sim
        assert "volume_change_percent" in sim
        assert "risk_level" in sim
        assert "confidence" in sim

    def test_change_discount_adjustment(self):
        """Test discount change simulation."""
        from app.agents.tools.campaign_simulation_tool import simulate_campaign_effect

        mock_db = Mock()
        result = simulate_campaign_effect(
            mock_db,
            merchant_id="m001",
            adjustment_type="change_discount",
            adjustment_params={"new_discount": 0.25},
        )

        # Discount reduction should increase redeem rate
        assert result["simulation_result"]["risk_level"] in ["low", "medium"]
        assert result["simulation_result"]["confidence"] > 0

    def test_adjust_target_users_adjustment(self):
        """Test target user adjustment simulation."""
        from app.agents.tools.campaign_simulation_tool import simulate_campaign_effect

        mock_db = Mock()
        result = simulate_campaign_effect(
            mock_db,
            merchant_id="m001",
            adjustment_type="adjust_target_users",
            adjustment_params={"target_segment": "high_value"},
        )

        # High-value targeting should increase rate
        assert result["simulation_result"]["expected_redeem_rate"] > 0

    def test_pause_distribution_adjustment(self):
        """Test pause distribution simulation."""
        from app.agents.tools.campaign_simulation_tool import simulate_campaign_effect

        mock_db = Mock()
        result = simulate_campaign_effect(
            mock_db,
            merchant_id="m001",
            adjustment_type="pause_distribution",
            adjustment_params={"duration": 7},
        )

        # Pause should have 0 volume and high risk
        assert result["simulation_result"]["expected_volume"] == 0
        assert result["simulation_result"]["risk_level"] == "high"

    def test_increase_distribution_adjustment(self):
        """Test increase distribution simulation."""
        from app.agents.tools.campaign_simulation_tool import simulate_campaign_effect

        mock_db = Mock()
        result = simulate_campaign_effect(
            mock_db,
            merchant_id="m001",
            adjustment_type="increase_distribution",
            adjustment_params={"increase_percent": 50},
        )

        # Volume should increase
        assert result["simulation_result"]["volume_change_percent"] == 50

    def test_send_reminder_adjustment(self):
        """Test send reminder simulation."""
        from app.agents.tools.campaign_simulation_tool import simulate_campaign_effect

        mock_db = Mock()
        result = simulate_campaign_effect(
            mock_db,
            merchant_id="m001",
            adjustment_type="send_reminder",
            adjustment_params={"reminder_type": "push"},
        )

        # Reminder should boost rate
        assert result["simulation_result"]["expected_redeem_rate"] > 0
        assert result["simulation_result"]["risk_level"] == "low"

    def test_invalid_adjustment_type(self):
        """Test handling of invalid adjustment type."""
        from app.agents.tools.campaign_simulation_tool import simulate_campaign_effect

        mock_db = Mock()
        result = simulate_campaign_effect(
            mock_db,
            merchant_id="m001",
            adjustment_type="invalid_type",
        )

        assert "error" in result

    def test_evidence_list_has_required_fields(self):
        """Test each evidence item has required fields."""
        from app.agents.tools.campaign_simulation_tool import simulate_campaign_effect

        mock_db = Mock()
        result = simulate_campaign_effect(
            mock_db,
            merchant_id="m001",
            adjustment_type="change_discount",
        )

        for evidence in result.get("evidence", []):
            assert "type" in evidence
            assert "description" in evidence
            assert "content" in evidence
            assert "severity" in evidence


# =============================================================================
# Parse Recommendation Tests (M4 High Standard)
# =============================================================================

class TestParseRecommendationM4:
    """Tests for parse_recommendation with M4 High Standard."""

    def test_parse_with_4_evidence_items(self):
        """Test parsing recommendation with 4 evidence items."""
        from app.agents.decision_service import parse_recommendation

        valid_input = {
            "summary": "Test summary",
            "evidence_list": [
                {"type": "a", "description": "1"},
                {"type": "b", "description": "2"},
                {"type": "c", "description": "3"},
                {"type": "d", "description": "4"},
            ],
            "suggested_actions": [
                {"action_type": "no_action", "params": {}}
            ],
            "confidence_score": 0.8,
            "requires_approval": False,
        }

        result = parse_recommendation(valid_input)
        assert len(result["evidence_list"]) >= 4

    def test_parse_rejects_3_evidence_items(self):
        """Test that parsing fails with only 3 evidence items."""
        from app.agents.decision_service import parse_recommendation

        invalid_input = {
            "summary": "Test",
            "evidence_list": [
                {"type": "a", "description": "1"},
                {"type": "b", "description": "2"},
                {"type": "c", "description": "3"},
            ],
            "suggested_actions": [],
            "confidence_score": 0.5,
            "requires_approval": False,
        }

        with pytest.raises(ValueError, match="At least 4 evidence items"):
            parse_recommendation(invalid_input)

    def test_parse_preserves_model_signal(self):
        """Test that model_signal field is preserved."""
        from app.agents.decision_service import parse_recommendation

        input_data = {
            "summary": "Test",
            "evidence_list": [
                {"type": "a", "description": "1"},
                {"type": "b", "description": "2"},
                {"type": "c", "description": "3"},
                {"type": "d", "description": "4"},
            ],
            "suggested_actions": [],
            "confidence_score": 0.8,
            "requires_approval": False,
            "model_signal": {
                "prediction_score": 0.72,
                "signal_type": "redeem_probability",
            },
        }

        result = parse_recommendation(input_data)
        assert "model_signal" in result
        assert result["model_signal"]["prediction_score"] == 0.72

    def test_parse_preserves_business_risk(self):
        """Test that business_risk field is preserved."""
        from app.agents.decision_service import parse_recommendation

        input_data = {
            "summary": "Test",
            "evidence_list": [
                {"type": "a", "description": "1"},
                {"type": "b", "description": "2"},
                {"type": "c", "description": "3"},
                {"type": "d", "description": "4"},
            ],
            "suggested_actions": [],
            "confidence_score": 0.8,
            "requires_approval": False,
            "business_risk": {
                "risk_level": "medium",
                "potential_revenue_impact": "-5%",
            },
        }

        result = parse_recommendation(input_data)
        assert "business_risk" in result
        assert result["business_risk"]["risk_level"] == "medium"

    def test_parse_preserves_limitations(self):
        """Test that limitations field is preserved."""
        from app.agents.decision_service import parse_recommendation

        input_data = {
            "summary": "Test",
            "evidence_list": [
                {"type": "a", "description": "1"},
                {"type": "b", "description": "2"},
                {"type": "c", "description": "3"},
                {"type": "d", "description": "4"},
            ],
            "suggested_actions": [],
            "confidence_score": 0.8,
            "requires_approval": False,
            "limitations": ["Data limited to 30 days", "No real-time data"],
        }

        result = parse_recommendation(input_data)
        assert "limitations" in result
        assert len(result["limitations"]) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])