import pytest
"""Integration tests for data cleaning service."""

from datetime import date
from sqlalchemy import text
from app.services.data_cleaning_service import DataCleaningService
from app.domain.staging.coupon_receipt_event import CouponReceiptEvent
from app.domain.staging.consumption_event import ConsumptionEvent


@pytest.mark.skip(reason="需要PostgreSQL数据库环境")
def test_transform_to_coupon_receipt_event(clean_db, sample_raw_data):
    """Test transformation of raw data to coupon receipt events."""
    service = DataCleaningService(clean_db)

    # Process all batches
    total_events = 0
    for batch in service.transform_to_coupon_receipt_event(batch_size=2):
        total_events += len(batch)
        clean_db.bulk_insert_mappings(CouponReceiptEvent, batch)
        clean_db.commit()

    # Should have 4 receipt events (one per raw record)
    assert total_events == 4

    # Verify data in database
    result = clean_db.execute(
        text("SELECT * FROM staging.coupon_receipt_event ORDER BY user_id")
    ).mappings().fetchall()

    assert len(result) == 4

    # Check first record (redeemed within 15 days)
    record_1 = result[0]
    assert record_1["user_id"] == "user_001"
    assert record_1["is_redeemed"] is True
    assert record_1["redeem_days"] == 9
    assert record_1["distance"] == 500.0
    assert record_1["date_received"] == date(2016, 5, 1)
    assert record_1["date_redeemed"] == date(2016, 5, 10)

    # Check second record (redeemed after 15 days - should not count)
    record_2 = result[1]
    assert record_2["user_id"] == "user_002"
    assert record_2["is_redeemed"] is False
    assert record_2["redeem_days"] is None
    assert record_2["distance"] == -1.0  # Empty distance converted to -1

    # Check third record (not redeemed)
    record_3 = result[2]
    assert record_3["user_id"] == "user_003"
    assert record_3["is_redeemed"] is False
    assert record_3["redeem_days"] is None
    assert record_3["date_redeemed"] is None

    # Check fourth record (redeemed immediately)
    record_4 = result[3]
    assert record_4["user_id"] == "user_004"
    assert record_4["is_redeemed"] is True
    assert record_4["redeem_days"] == 0
    assert record_4["distance"] == -1.0  # Null distance converted to -1


@pytest.mark.skip(reason="需要PostgreSQL数据库环境")
def test_transform_to_consumption_event(clean_db, sample_raw_data):
    """Test transformation of raw data to consumption events."""
    service = DataCleaningService(clean_db)

    # Process all batches
    total_events = 0
    for batch in service.transform_to_consumption_event(batch_size=2):
        total_events += len(batch)
        clean_db.bulk_insert_mappings(ConsumptionEvent, batch)
        clean_db.commit()

    # Should have 3 consumption events (only records with date)
    assert total_events == 3

    # Verify data in database
    result = clean_db.execute(
        text("SELECT * FROM staging.consumption_event ORDER BY user_id")
    ).mappings().fetchall()

    assert len(result) == 3

    # Check first consumption (user_001)
    record_1 = result[0]
    assert record_1["user_id"] == "user_001"
    assert record_1["coupon_id"] == "coupon_001"
    assert record_1["discount_rate"] == "200:50"
    assert record_1["date"] == date(2016, 5, 10)
    assert record_1["amount"] is not None  # Should have simulated amount

    # Check second consumption (user_002)
    record_2 = result[1]
    assert record_2["user_id"] == "user_002"
    assert record_2["coupon_id"] == "coupon_002"
    assert record_2["discount_rate"] == "0.9"

    # Check third consumption (user_004)
    record_3 = result[2]
    assert record_3["user_id"] == "user_004"
    assert record_3["coupon_id"] == "coupon_004"
    assert record_3["discount_rate"] == "0.8"


@pytest.mark.skip(reason="需要PostgreSQL数据库环境")
def test_null_distance_handling(clean_db, sample_raw_data):
    """Test that null/empty distances are converted to -1."""
    service = DataCleaningService(clean_db)

    for batch in service.transform_to_coupon_receipt_event(batch_size=10):
        clean_db.bulk_insert_mappings(CouponReceiptEvent, batch)
        clean_db.commit()

    result = clean_db.execute(
        text("SELECT user_id, distance FROM staging.coupon_receipt_event ORDER BY user_id")
    ).mappings().fetchall()

    # user_002 has empty distance, should be -1
    assert result[1]["distance"] == -1.0

    # user_004 has null distance, should be -1
    assert result[3]["distance"] == -1.0

    # user_001 and user_003 have valid distances
    assert result[0]["distance"] == 500.0
    assert result[2]["distance"] == 1000.0


@pytest.mark.skip(reason="需要PostgreSQL数据库环境")
def test_redeem_days_calculation(clean_db, sample_raw_data):
    """Test calculation of redeem_days field."""
    service = DataCleaningService(clean_db)

    for batch in service.transform_to_coupon_receipt_event(batch_size=10):
        clean_db.bulk_insert_mappings(CouponReceiptEvent, batch)
        clean_db.commit()

    result = clean_db.execute(
        text(
            "SELECT user_id, redeem_days, is_redeemed FROM staging.coupon_receipt_event ORDER BY user_id"
        )
    ).mappings().fetchall()

    # user_001: redeemed after 9 days (within 15)
    assert result[0]["redeem_days"] == 9
    assert result[0]["is_redeemed"] is True

    # user_002: redeemed after 19 days (outside 15, not counted)
    assert result[1]["redeem_days"] is None
    assert result[1]["is_redeemed"] is False

    # user_003: not redeemed
    assert result[2]["redeem_days"] is None
    assert result[2]["is_redeemed"] is False

    # user_004: redeemed same day (0 days)
    assert result[3]["redeem_days"] == 0
    assert result[3]["is_redeemed"] is True


@pytest.mark.skip(reason="需要PostgreSQL数据库环境")
def test_clean_all_data(clean_db, sample_raw_data):
    """Test complete data cleaning process."""
    service = DataCleaningService(clean_db)

    result = service.clean_all_data(batch_size=2)

    # Should process all records
    assert result["receipt_events"] == 4
    assert result["consumption_events"] == 3

    # Verify tables were truncated before insert
    receipt_count = clean_db.execute(
        text("SELECT COUNT(*) FROM staging.coupon_receipt_event")
    ).scalar()
    consumption_count = clean_db.execute(
        text("SELECT COUNT(*) FROM staging.consumption_event")
    ).scalar()

    assert receipt_count == 4
    assert consumption_count == 3


@pytest.mark.skip(reason="需要PostgreSQL数据库环境")
def test_empty_raw_data(clean_db):
    """Test handling of empty raw data."""
    service = DataCleaningService(clean_db)

    result = service.clean_all_data(batch_size=100)

    assert result["receipt_events"] == 0
    assert result["consumption_events"] == 0


@pytest.mark.skip(reason="需要PostgreSQL数据库环境")
def test_simulate_amount(clean_db):
    """Test amount simulation based on discount rate."""
    service = DataCleaningService(clean_db)

    # Test threshold:discount format
    amount_1 = service._simulate_amount("200:50")
    assert amount_1 == 300.0  # threshold * 1.5

    # Test discount rate format
    amount_2 = service._simulate_amount("0.9")
    assert amount_2 == 200.0  # fixed amount

    # Test null/empty
    assert service._simulate_amount(None) is None
    assert service._simulate_amount("") is None
    assert service._simulate_amount("  ") is None


@pytest.mark.skip(reason="需要PostgreSQL数据库环境")
def test_parse_date(clean_db):
    """Test date parsing."""
    service = DataCleaningService(clean_db)

    # Valid date
    assert service._parse_date("2016-05-01") == date(2016, 5, 1)

    # Invalid formats
    assert service._parse_date(None) is None
    assert service._parse_date("") is None
    assert service._parse_date("  ") is None
    assert service._parse_date("invalid") is None


@pytest.mark.skip(reason="需要PostgreSQL数据库环境")
def test_parse_distance(clean_db):
    """Test distance parsing."""
    service = DataCleaningService(clean_db)

    # Valid distances
    assert service._parse_distance("500") == 500.0
    assert service._parse_distance("1000.5") == 1000.5

    # Null/empty distances
    assert service._parse_distance(None) == -1.0
    assert service._parse_distance("") == -1.0
    assert service._parse_distance("  ") == -1.0
    assert service._parse_distance("invalid") == -1.0