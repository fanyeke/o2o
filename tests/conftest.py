"""Pytest configuration and fixtures."""

import pytest
import os
from sqlalchemy import text
from sqlalchemy.orm import Session

# Force test environment before importing app modules
os.environ["APP_ENV"] = "test"

from app.core.database import SessionLocal, engine
from app.domain.raw.offline_train import OfflineTrain
from app.domain.staging.coupon_receipt_event import CouponReceiptEvent
from app.domain.staging.consumption_event import ConsumptionEvent


@pytest.fixture
def db_session() -> Session:
    """Create a database session for testing.

    Yields:
        Database session
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def clean_db(db_session: Session):
    """Clean database tables before and after tests.

    Args:
        db_session: Database session
    """
    # Clean tables before test
    db_session.execute(text("TRUNCATE TABLE application.approval_log CASCADE"))
    db_session.execute(text("TRUNCATE TABLE application.action_execution CASCADE"))
    db_session.execute(text("TRUNCATE TABLE application.recommendation CASCADE"))
    db_session.execute(text("TRUNCATE TABLE application.decision_case CASCADE"))
    db_session.execute(text("TRUNCATE TABLE staging.coupon_receipt_event CASCADE"))
    db_session.execute(text("TRUNCATE TABLE staging.consumption_event CASCADE"))
    db_session.execute(text("TRUNCATE TABLE raw.offline_train CASCADE"))
    db_session.execute(text("TRUNCATE TABLE feature.merchant_metrics CASCADE"))
    db_session.execute(text("TRUNCATE TABLE feature.user_metrics CASCADE"))
    db_session.execute(text("TRUNCATE TABLE feature.coupon_metrics CASCADE"))
    db_session.commit()

    yield db_session

    # Clean tables after test
    db_session.execute(text("TRUNCATE TABLE application.approval_log CASCADE"))
    db_session.execute(text("TRUNCATE TABLE application.action_execution CASCADE"))
    db_session.execute(text("TRUNCATE TABLE application.recommendation CASCADE"))
    db_session.execute(text("TRUNCATE TABLE application.decision_case CASCADE"))
    db_session.execute(text("TRUNCATE TABLE staging.coupon_receipt_event CASCADE"))
    db_session.execute(text("TRUNCATE TABLE staging.consumption_event CASCADE"))
    db_session.execute(text("TRUNCATE TABLE raw.offline_train CASCADE"))
    db_session.execute(text("TRUNCATE TABLE feature.merchant_metrics CASCADE"))
    db_session.execute(text("TRUNCATE TABLE feature.user_metrics CASCADE"))
    db_session.execute(text("TRUNCATE TABLE feature.coupon_metrics CASCADE"))
    db_session.commit()


@pytest.fixture
def sample_raw_data(db_session: Session):
    """Create sample raw data for testing.

    Args:
        db_session: Database session

    Returns:
        List of created records
    """
    records = [
        # Redeemed within 15 days
        {
            "user_id": "user_001",
            "merchant_id": "merchant_001",
            "coupon_id": "coupon_001",
            "discount_rate": "200:50",
            "distance": "500",
            "date_received": "2016-05-01",
            "date": "2016-05-10",  # Redeemed after 9 days
        },
        # Redeemed after 15 days (should not count as redeemed)
        {
            "user_id": "user_002",
            "merchant_id": "merchant_001",
            "coupon_id": "coupon_002",
            "discount_rate": "0.9",
            "distance": "",  # Empty distance
            "date_received": "2016-05-01",
            "date": "2016-05-20",  # Redeemed after 19 days
        },
        # Not redeemed
        {
            "user_id": "user_003",
            "merchant_id": "merchant_002",
            "coupon_id": "coupon_003",
            "discount_rate": "100:20",
            "distance": "1000",
            "date_received": "2016-05-05",
            "date": None,  # Not redeemed
        },
        # Redeemed immediately (0 days)
        {
            "user_id": "user_004",
            "merchant_id": "merchant_002",
            "coupon_id": "coupon_004",
            "discount_rate": "0.8",
            "distance": None,  # Null distance
            "date_received": "2016-05-10",
            "date": "2016-05-10",  # Same day redemption
        },
    ]

    db_session.bulk_insert_mappings(OfflineTrain, records)
    db_session.commit()

    return records