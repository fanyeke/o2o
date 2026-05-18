"""Example usage of Agent Tools.

This script demonstrates how Agent Tools can be used to query
merchant and coupon metrics for decision-making.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from unittest.mock import Mock
from datetime import datetime, date
from app.agents.tools import get_merchant_metrics, get_coupon_conversion
from app.domain.feature.merchant_metrics import MerchantMetrics
from app.domain.feature.coupon_metrics import CouponMetrics
import json


def create_mock_db_with_merchant():
    """Create a mock database session with sample merchant data."""
    mock_db = Mock()

    # Create sample merchant
    merchant = MerchantMetrics(
        merchant_id="merchant_001",
        total_receipts_7d=100,
        redeemed_count_7d=45,
        redeemed_rate_7d=0.45,
        total_receipts_30d=400,
        redeemed_count_30d=260,
        redeemed_rate_30d=0.65,
        redeemed_rate_change=-0.30,  # 30% drop!
        avg_discount_depth=0.25,
        activity_health_score=0.72,
        last_activity_date=date(2016, 6, 15),
        updated_at=datetime(2016, 6, 15, 10, 0, 0)
    )

    # Mock query
    mock_query = Mock()
    mock_filter = Mock()
    mock_filter.first.return_value = merchant
    mock_query.filter.return_value = mock_filter
    mock_db.query.return_value = mock_query

    return mock_db


def create_mock_db_with_coupon():
    """Create a mock database session with sample coupon data."""
    mock_db = Mock()

    # Create sample coupon
    coupon = CouponMetrics(
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
    mock_filter.first.return_value = coupon
    mock_query.filter.return_value = mock_filter
    mock_db.query.return_value = mock_query

    return mock_db


def main():
    """Demonstrate Agent Tool usage."""
    print("=" * 60)
    print("Agent Tools Usage Example")
    print("=" * 60)

    # Example 1: Query merchant metrics
    print("\n1. Query Merchant Metrics")
    print("-" * 60)
    mock_db = create_mock_db_with_merchant()
    result = get_merchant_metrics(mock_db, merchant_id="merchant_001")

    print("Merchant ID:", result["merchant_id"])
    print("\nMetrics:")
    for key, value in result["metrics"].items():
        print(f"  {key}: {value}")

    print("\nEvidence ({} items):".format(len(result["evidence"])))
    for i, evidence in enumerate(result["evidence"], 1):
        print(f"  {i}. [{evidence['type']}] {evidence['content']}")

    # Example 2: Query coupon conversion
    print("\n2. Query Coupon Conversion")
    print("-" * 60)
    mock_db = create_mock_db_with_coupon()
    result = get_coupon_conversion(mock_db, coupon_id="coupon_001")

    print("Coupon ID:", result["coupon_id"])
    print("Merchant ID:", result["merchant_id"])
    print("\nConversion Metrics:")
    for key, value in result["conversion_metrics"].items():
        print(f"  {key}: {value}")

    print("\nEvidence ({} items):".format(len(result["evidence"])))
    for i, evidence in enumerate(result["evidence"], 1):
        print(f"  {i}. [{evidence['type']}] {evidence['content']}")

    # Example 3: JSON serialization (for LLM Tool Calling)
    print("\n3. JSON Serialization for LLM")
    print("-" * 60)
    json_output = json.dumps(result, ensure_ascii=False, indent=2)
    print("JSON Output (ready for LLM context):")
    print(json_output[:200] + "..." if len(json_output) > 200 else json_output)

    print("\n" + "=" * 60)
    print("Summary:")
    print("  - Tools return JSON-serializable data")
    print("  - Evidence items >= 3 (for LLM decision-making)")
    print("  - Suitable for LLM Tool Calling format")
    print("=" * 60)


if __name__ == "__main__":
    main()