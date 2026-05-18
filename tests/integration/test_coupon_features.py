import pytest
"""Integration tests for coupon feature engineering."""

from datetime import date
from sqlalchemy import text
from app.features.coupon_features import calculate_coupon_metrics
from app.domain.staging.coupon_receipt_event import CouponReceiptEvent


@pytest.mark.skip(reason="需要PostgreSQL数据库环境")
def test_calculate_coupon_metrics_basic(clean_db):
    """Test basic coupon metrics calculation."""
    # Create sample coupon receipt events
    events = [
        {
            "user_id": "user_001",
            "merchant_id": "merchant_001",
            "coupon_id": "coupon_001",
            "discount_rate": "200:50",
            "distance": 500.0,
            "date_received": date(2016, 5, 1),
            "is_redeemed": True,
            "date_redeemed": date(2016, 5, 10),
            "redeem_days": 9,
        },
        {
            "user_id": "user_002",
            "merchant_id": "merchant_001",
            "coupon_id": "coupon_001",
            "discount_rate": "200:50",
            "distance": 1000.0,
            "date_received": date(2016, 5, 2),
            "is_redeemed": False,
            "date_redeemed": None,
            "redeem_days": None,
        },
        {
            "user_id": "user_003",
            "merchant_id": "merchant_001",
            "coupon_id": "coupon_001",
            "discount_rate": "200:50",
            "distance": 500.0,
            "date_received": date(2016, 5, 3),
            "is_redeemed": True,
            "date_redeemed": date(2016, 5, 15),
            "redeem_days": 12,
        },
    ]

    clean_db.bulk_insert_mappings(CouponReceiptEvent, events)
    clean_db.commit()

    # Calculate metrics
    metrics_list = calculate_coupon_metrics(clean_db)

    # Should return one coupon metric
    assert len(metrics_list) == 1

    # Verify metric values
    metrics = metrics_list[0]
    assert metrics.coupon_id == "coupon_001"
    assert metrics.merchant_id == "merchant_001"
    assert metrics.discount_type == "满减"
    assert metrics.discount_rate == "200:50"
    assert metrics.threshold_amount == 200.0
    assert metrics.discount_amount == 50.0
    assert metrics.discount_value == 0.25
    assert metrics.total_receipts == 3
    assert metrics.redeemed_count == 2
    assert metrics.redeemed_rate == 2 / 3
    assert metrics.avg_redeem_days == (9 + 12) / 2  # Average of redeemed events only
    assert metrics.updated_at is not None


@pytest.mark.skip(reason="需要PostgreSQL数据库环境")
def test_calculate_coupon_metrics_with_discount_rate(clean_db):
    """Test coupon metrics with discount rate format."""
    events = [
        {
            "user_id": "user_001",
            "merchant_id": "merchant_002",
            "coupon_id": "coupon_002",
            "discount_rate": "0.9",
            "distance": 500.0,
            "date_received": date(2016, 5, 1),
            "is_redeemed": True,
            "date_redeemed": date(2016, 5, 5),
            "redeem_days": 4,
        },
        {
            "user_id": "user_002",
            "merchant_id": "merchant_002",
            "coupon_id": "coupon_002",
            "discount_rate": "0.9",
            "distance": 1000.0,
            "date_received": date(2016, 5, 2),
            "is_redeemed": True,
            "date_redeemed": date(2016, 5, 8),
            "redeem_days": 6,
        },
    ]

    clean_db.bulk_insert_mappings(CouponReceiptEvent, events)
    clean_db.commit()

    metrics_list = calculate_coupon_metrics(clean_db)

    assert len(metrics_list) == 1

    metrics = metrics_list[0]
    assert metrics.coupon_id == "coupon_002"
    assert metrics.discount_type == "折扣"
    assert abs(metrics.discount_value - 0.1) < 0.0001  # Use approximate comparison for float
    assert metrics.threshold_amount is None
    assert metrics.discount_amount is None
    assert metrics.total_receipts == 2
    assert metrics.redeemed_count == 2
    assert metrics.redeemed_rate == 1.0
    assert metrics.avg_redeem_days == 5.0


@pytest.mark.skip(reason="需要PostgreSQL数据库环境")
def test_calculate_coupon_metrics_multiple_coupons(clean_db):
    """Test metrics calculation for multiple coupons."""
    events = [
        # Coupon 001
        {
            "user_id": "user_001",
            "merchant_id": "merchant_001",
            "coupon_id": "coupon_001",
            "discount_rate": "200:50",
            "distance": 500.0,
            "date_received": date(2016, 5, 1),
            "is_redeemed": True,
            "date_redeemed": date(2016, 5, 5),
            "redeem_days": 4,
        },
        # Coupon 002
        {
            "user_id": "user_002",
            "merchant_id": "merchant_002",
            "coupon_id": "coupon_002",
            "discount_rate": "0.9",
            "distance": 1000.0,
            "date_received": date(2016, 5, 2),
            "is_redeemed": False,
            "date_redeemed": None,
            "redeem_days": None,
        },
        # Coupon 003
        {
            "user_id": "user_003",
            "merchant_id": "merchant_001",
            "coupon_id": "coupon_003",
            "discount_rate": "100:20",
            "distance": 500.0,
            "date_received": date(2016, 5, 3),
            "is_redeemed": True,
            "date_redeemed": date(2016, 5, 6),
            "redeem_days": 3,
        },
    ]

    clean_db.bulk_insert_mappings(CouponReceiptEvent, events)
    clean_db.commit()

    metrics_list = calculate_coupon_metrics(clean_db)

    # Should return 3 coupon metrics
    assert len(metrics_list) == 3

    # Sort by coupon_id for predictable order
    metrics_list.sort(key=lambda m: m.coupon_id)

    # Verify coupon_001
    assert metrics_list[0].coupon_id == "coupon_001"
    assert metrics_list[0].total_receipts == 1
    assert metrics_list[0].redeemed_rate == 1.0

    # Verify coupon_002
    assert metrics_list[1].coupon_id == "coupon_002"
    assert metrics_list[1].total_receipts == 1
    assert metrics_list[1].redeemed_rate == 0.0

    # Verify coupon_003
    assert metrics_list[2].coupon_id == "coupon_003"
    assert metrics_list[2].total_receipts == 1
    assert metrics_list[2].redeemed_rate == 1.0


@pytest.mark.skip(reason="需要PostgreSQL数据库环境")
def test_calculate_coupon_metrics_with_specific_coupon_ids(clean_db):
    """Test metrics calculation for specific coupon IDs."""
    events = [
        {
            "user_id": "user_001",
            "merchant_id": "merchant_001",
            "coupon_id": "coupon_001",
            "discount_rate": "200:50",
            "distance": 500.0,
            "date_received": date(2016, 5, 1),
            "is_redeemed": True,
            "date_redeemed": date(2016, 5, 5),
            "redeem_days": 4,
        },
        {
            "user_id": "user_002",
            "merchant_id": "merchant_002",
            "coupon_id": "coupon_002",
            "discount_rate": "0.9",
            "distance": 1000.0,
            "date_received": date(2016, 5, 2),
            "is_redeemed": False,
            "date_redeemed": None,
            "redeem_days": None,
        },
    ]

    clean_db.bulk_insert_mappings(CouponReceiptEvent, events)
    clean_db.commit()

    # Calculate metrics only for coupon_001
    metrics_list = calculate_coupon_metrics(clean_db, coupon_ids=["coupon_001"])

    # Should return only one metric
    assert len(metrics_list) == 1
    assert metrics_list[0].coupon_id == "coupon_001"


@pytest.mark.skip(reason="需要PostgreSQL数据库环境")
def test_calculate_coupon_metrics_no_redeemed_events(clean_db):
    """Test metrics calculation when no events are redeemed."""
    events = [
        {
            "user_id": "user_001",
            "merchant_id": "merchant_001",
            "coupon_id": "coupon_001",
            "discount_rate": "200:50",
            "distance": 500.0,
            "date_received": date(2016, 5, 1),
            "is_redeemed": False,
            "date_redeemed": None,
            "redeem_days": None,
        },
        {
            "user_id": "user_002",
            "merchant_id": "merchant_001",
            "coupon_id": "coupon_001",
            "discount_rate": "200:50",
            "distance": 1000.0,
            "date_received": date(2016, 5, 2),
            "is_redeemed": False,
            "date_redeemed": None,
            "redeem_days": None,
        },
    ]

    clean_db.bulk_insert_mappings(CouponReceiptEvent, events)
    clean_db.commit()

    metrics_list = calculate_coupon_metrics(clean_db)

    assert len(metrics_list) == 1

    metrics = metrics_list[0]
    assert metrics.total_receipts == 2
    assert metrics.redeemed_count == 0
    assert metrics.redeemed_rate == 0.0
    assert metrics.avg_redeem_days is None  # No redeemed events


@pytest.mark.skip(reason="需要PostgreSQL数据库环境")
def test_calculate_coupon_metrics_empty_database(clean_db):
    """Test metrics calculation with empty database."""
    metrics_list = calculate_coupon_metrics(clean_db)

    # Should return empty list
    assert len(metrics_list) == 0


@pytest.mark.skip(reason="需要PostgreSQL数据库环境")
def test_calculate_coupon_metrics_with_null_discount_rate(clean_db):
    """Test metrics calculation with null discount rate."""
    events = [
        {
            "user_id": "user_001",
            "merchant_id": "merchant_001",
            "coupon_id": "coupon_001",
            "discount_rate": None,  # Null discount rate
            "distance": 500.0,
            "date_received": date(2016, 5, 1),
            "is_redeemed": True,
            "date_redeemed": date(2016, 5, 5),
            "redeem_days": 4,
        },
    ]

    clean_db.bulk_insert_mappings(CouponReceiptEvent, events)
    clean_db.commit()

    metrics_list = calculate_coupon_metrics(clean_db)

    assert len(metrics_list) == 1

    metrics = metrics_list[0]
    assert metrics.discount_type is None
    assert metrics.discount_value is None
    assert metrics.threshold_amount is None
    assert metrics.discount_amount is None


@pytest.mark.skip(reason="需要PostgreSQL数据库环境")
def test_calculate_coupon_metrics_zero_receipts(clean_db):
    """Test metrics calculation when total_receipts is zero (should not happen but edge case)."""
    # This test case is theoretical - actual query should not return coupons with zero receipts
    # But we test the redemption rate calculation logic
    pass  # Cannot create this scenario through normal data insertion