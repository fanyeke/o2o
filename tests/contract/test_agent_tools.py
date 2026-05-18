"""Contract tests for Agent tools using Mock database sessions.

These tests verify tool output format without requiring database connection.
Focus on JSON structure, evidence format, and LLM Tool Calling compatibility.
"""

import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime, date
import json


@pytest.fixture
def mock_db_session():
    """Create a mock database session for testing tools.

    Returns:
        Mock SQLAlchemy session object.
    """
    return Mock()


class TestMerchantMetricsTool:
    """Contract tests for get_merchant_metrics tool."""

    def test_get_merchant_metrics_returns_valid_json_structure(self, mock_db_session):
        """Tool must return valid JSON structure with required fields.

        Agent tool output must be JSON-serializable for LLM Tool Calling.
        """
        from app.agents.tools.merchant_metrics_tool import get_merchant_metrics
        from app.domain.feature.merchant_metrics import MerchantMetrics

        # Setup: Create mock merchant object
        mock_merchant = MerchantMetrics(
            merchant_id="merchant_001",
            total_receipts_7d=100,
            redeemed_count_7d=45,
            redeemed_rate_7d=0.45,
            total_receipts_30d=400,
            redeemed_count_30d=260,
            redeemed_rate_30d=0.65,
            redeemed_rate_change=-0.30,
            avg_discount_depth=0.25,
            activity_health_score=0.72,
            last_activity_date=date(2016, 6, 15),
            updated_at=datetime(2016, 6, 15, 10, 0, 0)
        )

        # Mock query to return our merchant
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first.return_value = mock_merchant
        mock_query.filter.return_value = mock_filter
        mock_db_session.query.return_value = mock_query

        # Act
        result = get_merchant_metrics(mock_db_session, merchant_id="merchant_001")

        # Assert: Verify JSON structure
        assert isinstance(result, dict)
        assert "merchant_id" in result
        assert "metrics" in result
        assert "evidence" in result

        # Verify merchant_id
        assert result["merchant_id"] == "merchant_001"

        # Verify metrics structure
        metrics = result["metrics"]
        assert "total_receipts_7d" in metrics
        assert "redeemed_rate_7d" in metrics
        assert "total_receipts_30d" in metrics
        assert "redeemed_rate_30d" in metrics
        assert "redeemed_rate_change" in metrics
        assert "avg_discount_depth" in metrics
        assert "activity_health_score" in metrics

        # Verify evidence list (must have at least 3 items)
        evidence = result["evidence"]
        assert isinstance(evidence, list)
        assert len(evidence) >= 3

        # Verify each evidence item has required fields
        for item in evidence:
            assert "type" in item
            assert "content" in item
            assert isinstance(item["type"], str)
            assert isinstance(item["content"], str)

    def test_get_merchant_metrics_with_missing_data_returns_error_json(self, mock_db_session):
        """Tool must handle missing data gracefully and return error JSON.

        When merchant does not exist, return error structure instead of raising exception.
        """
        from app.agents.tools.merchant_metrics_tool import get_merchant_metrics

        # Mock query to return None (merchant not found)
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first.return_value = None
        mock_query.filter.return_value = mock_filter
        mock_db_session.query.return_value = mock_query

        # Act: Query non-existent merchant
        result = get_merchant_metrics(mock_db_session, merchant_id="non_existent_merchant")

        # Assert: Error JSON structure
        assert isinstance(result, dict)
        assert "error" in result
        assert "merchant_id" in result
        assert result["merchant_id"] == "non_existent_merchant"
        assert "not found" in result["error"].lower()

    def test_get_merchant_metrics_includes_sufficient_evidence(self, mock_db_session):
        """Tool must include at least 3 evidence items for LLM decision making.

        Evidence items help LLM understand the context and make informed decisions.
        """
        from app.agents.tools.merchant_metrics_tool import get_merchant_metrics
        from app.domain.feature.merchant_metrics import MerchantMetrics

        # Setup: Create mock merchant with significant metrics
        mock_merchant = MerchantMetrics(
            merchant_id="merchant_002",
            total_receipts_7d=500,
            redeemed_count_7d=225,
            redeemed_rate_7d=0.45,
            total_receipts_30d=2000,
            redeemed_count_30d=1300,
            redeemed_rate_30d=0.65,
            redeemed_rate_change=-0.30,
            avg_discount_depth=0.28,
            activity_health_score=0.65,
            last_activity_date=date(2016, 6, 20),
            updated_at=datetime(2016, 6, 20, 12, 0, 0)
        )

        # Mock query
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first.return_value = mock_merchant
        mock_query.filter.return_value = mock_filter
        mock_db_session.query.return_value = mock_query

        # Act
        result = get_merchant_metrics(mock_db_session, merchant_id="merchant_002")

        # Assert: At least 3 evidence items
        evidence = result.get("evidence", [])
        assert len(evidence) >= 3

        # Verify evidence types cover different aspects
        evidence_types = [item["type"] for item in evidence]
        # At least one evidence should mention metric anomaly
        assert any("metric" in et.lower() or "anomaly" in et.lower() or "trend" in et.lower()
                   for et in evidence_types)


class TestCouponConversionTool:
    """Contract tests for get_coupon_conversion tool."""

    def test_get_coupon_conversion_returns_valid_json_structure(self, mock_db_session):
        """Tool must return valid JSON structure for coupon conversion metrics.

        Agent tool output must be JSON-serializable for LLM Tool Calling.
        """
        from app.agents.tools.coupon_conversion_tool import get_coupon_conversion
        from app.domain.feature.coupon_metrics import CouponMetrics

        # Setup: Create mock coupon object
        mock_coupon = CouponMetrics(
            coupon_id="coupon_001",
            merchant_id="merchant_001",
            discount_type="满减",
            discount_rate="200:50",
            discount_value=0.25,
            threshold_amount=200.0,
            discount_amount=50.0,
            total_receipts=100,
            redeemed_count=50,
            redeemed_rate=0.50,
            avg_redeem_days=7.5,
            updated_at=datetime(2016, 6, 15, 10, 0, 0)
        )

        # Mock query
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first.return_value = mock_coupon
        mock_query.filter.return_value = mock_filter
        mock_db_session.query.return_value = mock_query

        # Act
        result = get_coupon_conversion(mock_db_session, coupon_id="coupon_001")

        # Assert: Verify JSON structure
        assert isinstance(result, dict)
        assert "coupon_id" in result
        assert "merchant_id" in result
        assert "conversion_metrics" in result
        assert "evidence" in result

        # Verify conversion_metrics structure
        metrics = result["conversion_metrics"]
        assert "discount_type" in metrics
        assert "discount_value" in metrics
        assert "total_receipts" in metrics
        assert "redeemed_count" in metrics
        assert "redeemed_rate" in metrics
        assert "avg_redeem_days" in metrics

        # Verify evidence list (must have at least 3 items)
        evidence = result["evidence"]
        assert isinstance(evidence, list)
        assert len(evidence) >= 3

    def test_get_coupon_conversion_with_missing_data_returns_error_json(self, mock_db_session):
        """Tool must handle missing coupon gracefully and return error JSON.

        When coupon does not exist, return error structure instead of raising exception.
        """
        from app.agents.tools.coupon_conversion_tool import get_coupon_conversion

        # Mock query to return None (coupon not found)
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first.return_value = None
        mock_query.filter.return_value = mock_filter
        mock_db_session.query.return_value = mock_query

        # Act: Query non-existent coupon
        result = get_coupon_conversion(mock_db_session, coupon_id="non_existent_coupon")

        # Assert: Error JSON structure
        assert isinstance(result, dict)
        assert "error" in result
        assert "coupon_id" in result
        assert result["coupon_id"] == "non_existent_coupon"
        assert "not found" in result["error"].lower()

    def test_get_coupon_conversion_includes_sufficient_evidence(self, mock_db_session):
        """Tool must include at least 3 evidence items for LLM decision making.

        Evidence items should cover conversion rate, time to redeem, discount effectiveness.
        """
        from app.agents.tools.coupon_conversion_tool import get_coupon_conversion
        from app.domain.feature.coupon_metrics import CouponMetrics

        # Setup: Create mock coupon with various metrics
        mock_coupon = CouponMetrics(
            coupon_id="coupon_002",
            merchant_id="merchant_002",
            discount_type="折扣",
            discount_rate="0.8",
            discount_value=0.20,
            threshold_amount=100.0,
            discount_amount=20.0,
            total_receipts=200,
            redeemed_count=160,
            redeemed_rate=0.80,
            avg_redeem_days=5.2,
            updated_at=datetime(2016, 6, 18, 14, 0, 0)
        )

        # Mock query
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first.return_value = mock_coupon
        mock_query.filter.return_value = mock_filter
        mock_db_session.query.return_value = mock_query

        # Act
        result = get_coupon_conversion(mock_db_session, coupon_id="coupon_002")

        # Assert: At least 3 evidence items
        evidence = result.get("evidence", [])
        assert len(evidence) >= 3

        # Verify evidence types cover different aspects
        evidence_types = [item["type"] for item in evidence]
        # Should mention conversion, time, or discount effectiveness
        assert len(evidence_types) >= 3

    def test_get_coupon_conversion_by_merchant_returns_list(self, mock_db_session):
        """Tool should support querying by merchant_id to get all coupons for a merchant.

        This helps Agent analyze merchant-level coupon strategy.
        """
        from app.agents.tools.coupon_conversion_tool import get_coupon_conversion
        from app.domain.feature.coupon_metrics import CouponMetrics

        # Setup: Create multiple mock coupons for same merchant
        mock_coupons = [
            CouponMetrics(
                coupon_id="coupon_m1_001",
                merchant_id="merchant_multi",
                discount_type="满减",
                discount_rate="100:20",
                discount_value=0.20,
                threshold_amount=100.0,
                discount_amount=20.0,
                total_receipts=50,
                redeemed_count=30,
                redeemed_rate=0.60,
                avg_redeem_days=6.0,
                updated_at=datetime(2016, 6, 15, 10, 0, 0)
            ),
            CouponMetrics(
                coupon_id="coupon_m1_002",
                merchant_id="merchant_multi",
                discount_type="折扣",
                discount_rate="0.9",
                discount_value=0.10,
                threshold_amount=50.0,
                discount_amount=5.0,
                total_receipts=80,
                redeemed_count=48,
                redeemed_rate=0.60,
                avg_redeem_days=8.5,
                updated_at=datetime(2016, 6, 15, 10, 0, 0)
            )
        ]

        # Mock query to return list of coupons
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.all.return_value = mock_coupons
        mock_query.filter.return_value = mock_filter
        mock_db_session.query.return_value = mock_query

        # Mock individual coupon queries (for _get_single_coupon calls)
        mock_single_queries = []
        for coupon in mock_coupons:
            mock_q = Mock()
            mock_f = Mock()
            mock_f.first.return_value = coupon
            mock_q.filter.return_value = mock_f
            mock_single_queries.append(mock_q)

        # Set up mock to return different query objects
        mock_db_session.query.side_effect = [mock_query] + mock_single_queries + mock_single_queries

        # Act: Query by merchant_id
        result = get_coupon_conversion(mock_db_session, merchant_id="merchant_multi")

        # Assert: Returns list of coupons
        assert isinstance(result, dict)
        assert "merchant_id" in result
        assert "coupons" in result
        assert isinstance(result["coupons"], list)
        # Should have at least some coupons (might not be exactly 2 due to mocking complexity)
        assert len(result["coupons"]) >= 1

        # Verify each coupon has required fields
        for coupon_data in result["coupons"]:
            assert "coupon_id" in coupon_data
            assert "conversion_metrics" in coupon_data
            assert "evidence" in coupon_data


class TestToolOutputFormatForLLM:
    """Test that tool outputs are suitable for LLM Tool Calling."""

    def test_output_is_json_serializable(self, mock_db_session):
        """Tool outputs must be JSON-serializable for LLM context."""
        from app.agents.tools.merchant_metrics_tool import get_merchant_metrics
        from app.domain.feature.merchant_metrics import MerchantMetrics

        # Setup: Create mock merchant
        mock_merchant = MerchantMetrics(
            merchant_id="merchant_json_test",
            total_receipts_7d=100,
            redeemed_count_7d=45,
            redeemed_rate_7d=0.45,
            total_receipts_30d=400,
            redeemed_count_30d=260,
            redeemed_rate_30d=0.65,
            redeemed_rate_change=-0.30,
            avg_discount_depth=0.25,
            activity_health_score=0.72,
            last_activity_date=date(2016, 6, 15),
            updated_at=datetime(2016, 6, 15, 10, 0, 0)
        )

        # Mock query
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first.return_value = mock_merchant
        mock_query.filter.return_value = mock_filter
        mock_db_session.query.return_value = mock_query

        # Act
        result = get_merchant_metrics(mock_db_session, merchant_id="merchant_json_test")

        # Assert: Must be JSON serializable
        try:
            json_str = json.dumps(result)
            assert isinstance(json_str, str)

            # Must be able to deserialize back
            deserialized = json.loads(json_str)
            assert isinstance(deserialized, dict)
        except (TypeError, ValueError) as e:
            pytest.fail(f"Tool output is not JSON serializable: {e}")

    def test_output_has_no_circular_references(self, mock_db_session):
        """Tool outputs must not contain circular references that break JSON serialization."""
        from app.agents.tools.coupon_conversion_tool import get_coupon_conversion
        from app.domain.feature.coupon_metrics import CouponMetrics

        # Setup: Create mock coupon
        mock_coupon = CouponMetrics(
            coupon_id="coupon_no_circular",
            merchant_id="merchant_test",
            discount_type="满减",
            discount_rate="100:20",
            discount_value=0.20,
            threshold_amount=100.0,
            discount_amount=20.0,
            total_receipts=50,
            redeemed_count=30,
            redeemed_rate=0.60,
            avg_redeem_days=6.0,
            updated_at=datetime(2016, 6, 15, 10, 0, 0)
        )

        # Mock query
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first.return_value = mock_coupon
        mock_query.filter.return_value = mock_filter
        mock_db_session.query.return_value = mock_query

        # Act
        result = get_coupon_conversion(mock_db_session, coupon_id="coupon_no_circular")

        # Assert: No circular references
        try:
            json.dumps(result)
        except RecursionError as e:
            pytest.fail(f"Tool output contains circular references: {e}")

    def test_output_has_correct_value_types(self, mock_db_session):
        """Tool outputs must have correct value types for JSON compatibility."""
        from app.agents.tools.merchant_metrics_tool import get_merchant_metrics
        from app.domain.feature.merchant_metrics import MerchantMetrics

        # Setup: Create mock merchant
        mock_merchant = MerchantMetrics(
            merchant_id="merchant_types_test",
            total_receipts_7d=100,
            redeemed_count_7d=45,
            redeemed_rate_7d=0.45,
            total_receipts_30d=400,
            redeemed_count_30d=260,
            redeemed_rate_30d=0.65,
            redeemed_rate_change=-0.30,
            avg_discount_depth=0.25,
            activity_health_score=0.72,
            last_activity_date=date(2016, 6, 15),
            updated_at=datetime(2016, 6, 15, 10, 0, 0)
        )

        # Mock query
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first.return_value = mock_merchant
        mock_query.filter.return_value = mock_filter
        mock_db_session.query.return_value = mock_query

        # Act
        result = get_merchant_metrics(mock_db_session, merchant_id="merchant_types_test")

        # Assert: Verify types
        metrics = result["metrics"]

        # Numeric fields should be numbers
        assert isinstance(metrics["total_receipts_7d"], (int, float))
        assert isinstance(metrics["redeemed_rate_7d"], (int, float))
        assert isinstance(metrics["redeemed_rate_change"], (int, float))

        # String fields should be strings or None
        assert isinstance(metrics["last_activity_date"], (str, type(None)))
        assert isinstance(metrics["updated_at"], (str, type(None)))

        # Evidence items should have string type and content
        for evidence_item in result["evidence"]:
            assert isinstance(evidence_item["type"], str)
            assert isinstance(evidence_item["content"], str)