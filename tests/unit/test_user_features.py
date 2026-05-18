"""Unit tests for user feature calculation.

Tests the calculate_user_metrics function to ensure correct aggregation logic.
"""
import pytest
from datetime import datetime, timedelta, date
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from app.db.base import Base
import app.db.models  # noqa: F401 - Import models to register them with Base.metadata
from app.domain.staging.coupon_receipt_event import CouponReceiptEvent
from app.domain.feature.user_metrics import UserMetrics
from app.features.user_features import calculate_user_metrics


@pytest.fixture
def db_session():
    """Create a test database session with in-memory SQLite.

    SQLite doesn't support schemas, so we use execution_options
    to strip schema prefixes from table names.
    """
    engine = create_engine("sqlite:///:memory:")

    # Strip schemas for SQLite compatibility
    @event.listens_for(engine, "before_cursor_execute", retval=True)
    def _receive_before_cursor_execute(conn, cursor, statement, params, context, executemany):
        # Replace schema.table with table
        statement = statement.replace("staging.", "").replace("feature.", "").replace("application.", "").replace("raw.", "")
        return statement, params

    # Create tables only (skip indexes to avoid name conflicts in SQLite)
    # We'll create indexes manually with unique names if needed
    for table in Base.metadata.sorted_tables:
        table._prefixes = []  # Remove schema prefix
        # Skip indexes to avoid conflicts
        table.indexes.clear()

    # Create all tables (without indexes)
    Base.metadata.create_all(engine)

    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def sample_events(db_session: Session):
    """Create sample coupon receipt events for testing."""
    reference_date = date(2026, 5, 17)

    events = [
        # User 1: 5 receipts, 3 redeemed, distances: [1.5, 2.0, -1, 2.5, 3.0]
        CouponReceiptEvent(
            id=1,
            user_id="user_001",
            merchant_id="merchant_001",
            coupon_id="coupon_001",
            discount_rate="200:50",
            distance=1.5,
            date_received=reference_date - timedelta(days=5),
            is_redeemed=True,
            date_redeemed=reference_date - timedelta(days=3),
            redeem_days=2
        ),
        CouponReceiptEvent(
            id=2,
            user_id="user_001",
            merchant_id="merchant_001",
            coupon_id="coupon_002",
            discount_rate="0.9",
            distance=2.0,
            date_received=reference_date - timedelta(days=10),
            is_redeemed=True,
            date_redeemed=reference_date - timedelta(days=8),
            redeem_days=2
        ),
        CouponReceiptEvent(
            id=3,
            user_id="user_001",
            merchant_id="merchant_002",
            coupon_id="coupon_003",
            discount_rate="200:50",
            distance=-1,  # Unknown distance
            date_received=reference_date - timedelta(days=15),
            is_redeemed=False,
            date_redeemed=None,
            redeem_days=None
        ),
        CouponReceiptEvent(
            id=4,
            user_id="user_001",
            merchant_id="merchant_001",
            coupon_id="coupon_004",
            discount_rate="300:80",
            distance=2.5,
            date_received=reference_date - timedelta(days=20),
            is_redeemed=True,
            date_redeemed=reference_date - timedelta(days=17),
            redeem_days=3
        ),
        CouponReceiptEvent(
            id=5,
            user_id="user_001",
            merchant_id="merchant_002",
            coupon_id="coupon_005",
            discount_rate="0.85",
            distance=3.0,
            date_received=reference_date - timedelta(days=25),
            is_redeemed=False,
            date_redeemed=None,
            redeem_days=None
        ),

        # User 2: 2 receipts, 0 redeemed, all distances -1
        CouponReceiptEvent(
            id=6,
            user_id="user_002",
            merchant_id="merchant_001",
            coupon_id="coupon_006",
            discount_rate="200:50",
            distance=-1,
            date_received=reference_date - timedelta(days=7),
            is_redeemed=False,
            date_redeemed=None,
            redeem_days=None
        ),
        CouponReceiptEvent(
            id=7,
            user_id="user_002",
            merchant_id="merchant_002",
            coupon_id="coupon_007",
            discount_rate="0.9",
            distance=-1,
            date_received=reference_date - timedelta(days=12),
            is_redeemed=False,
            date_redeemed=None,
            redeem_days=None
        ),

        # User 3: Event outside 30-day window (should be excluded)
        CouponReceiptEvent(
            id=8,
            user_id="user_003",
            merchant_id="merchant_001",
            coupon_id="coupon_008",
            discount_rate="200:50",
            distance=5.0,
            date_received=reference_date - timedelta(days=35),  # Outside 30-day window
            is_redeemed=True,
            date_redeemed=reference_date - timedelta(days=33),
            redeem_days=2
        ),
    ]

    db_session.add_all(events)
    db_session.commit()
    return reference_date


def test_calculate_user_metrics_basic(db_session: Session, sample_events: date):
    """Test basic user metrics calculation."""
    results = calculate_user_metrics(db_session, reference_date=sample_events)

    # Should have 2 users (user_003 is outside 30-day window)
    assert len(results) == 2

    # Find user_001 results
    user_001 = next((u for u in results if u.user_id == "user_001"), None)
    assert user_001 is not None
    assert user_001.total_receipts_30d == 5
    assert user_001.redeemed_count_30d == 3
    assert user_001.redeemed_rate_30d == 0.6  # 3/5

    # Average distance should exclude -1: (1.5 + 2.0 + 2.5 + 3.0) / 4 = 2.25
    assert user_001.avg_distance == pytest.approx(2.25, rel=0.01)

    # Last receipt date should be the most recent one
    assert user_001.last_receipt_date == sample_events - timedelta(days=5)


def test_calculate_user_metrics_all_unknown_distances(db_session: Session, sample_events: date):
    """Test user with all unknown distances (-1)."""
    results = calculate_user_metrics(db_session, reference_date=sample_events)

    user_002 = next((u for u in results if u.user_id == "user_002"), None)
    assert user_002 is not None
    assert user_002.total_receipts_30d == 2
    assert user_002.redeemed_count_30d == 0
    assert user_002.redeemed_rate_30d == 0.0

    # All distances are -1, so avg_distance should be None
    assert user_002.avg_distance is None


def test_calculate_user_metrics_window_filtering(db_session: Session, sample_events: date):
    """Test that events outside 30-day window are excluded."""
    results = calculate_user_metrics(db_session, reference_date=sample_events)

    # user_003 should not appear in results (event is 35 days ago)
    user_003 = next((u for u in results if u.user_id == "user_003"), None)
    assert user_003 is None


def test_calculate_user_metrics_zero_receipts(db_session: Session):
    """Test user with no receipts in 30-day window."""
    # Create a user with event outside window
    reference_date = date(2026, 5, 17)
    event = CouponReceiptEvent(
        id=100,
        user_id="user_no_receipts",
        merchant_id="merchant_001",
        coupon_id="coupon_001",
        discount_rate="200:50",
        distance=5.0,
        date_received=reference_date - timedelta(days=40),
        is_redeemed=False,
        date_redeemed=None,
        redeem_days=None
    )
    db_session.add(event)
    db_session.commit()

    results = calculate_user_metrics(db_session, reference_date=reference_date)

    # User should not appear in results (no receipts in window)
    user_no_receipts = next(
        (u for u in results if u.user_id == "user_no_receipts"),
        None
    )
    assert user_no_receipts is None


def test_calculate_user_metrics_batch_processing(db_session: Session):
    """Test batch processing with small batch size."""
    reference_date = date(2026, 5, 17)

    # Create 15 users with 1 receipt each
    for i in range(15):
        event = CouponReceiptEvent(
            id=200 + i,
            user_id=f"user_{i:03d}",
            merchant_id="merchant_001",
            coupon_id=f"coupon_{i:03d}",
            discount_rate="200:50",
            distance=float(i % 5),
            date_received=reference_date - timedelta(days=i % 30),
            is_redeemed=(i % 2 == 0),
            date_redeemed=None,
            redeem_days=None
        )
        db_session.add(event)
    db_session.commit()

    # Use batch_size=5 to test batching
    results = calculate_user_metrics(
        db_session,
        reference_date=reference_date,
        batch_size=5
    )

    # Should have 15 users
    assert len(results) == 15

    # Verify all users are present
    user_ids = {u.user_id for u in results}
    expected_ids = {f"user_{i:03d}" for i in range(15)}
    assert user_ids == expected_ids


def test_calculate_user_metrics_updated_timestamp(db_session: Session, sample_events: date):
    """Test that updated_at timestamp is set correctly."""
    before_time = datetime.now()
    results = calculate_user_metrics(db_session, reference_date=sample_events)
    after_time = datetime.now()

    # All records should have updated_at between before_time and after_time
    for user_metrics in results:
        assert before_time <= user_metrics.updated_at <= after_time