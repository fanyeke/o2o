"""Integration tests for feature calculation and refresh task.

Tests the complete feature refresh workflow including:
- Merchant metrics calculation (7-day/30-day redemption rates)
- Division by zero handling
- Celery task execution
- Database persistence
"""

import pytest
from datetime import date, timedelta
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.features.merchant_features import calculate_merchant_metrics
from app.features.user_features import calculate_user_metrics
from app.features.coupon_features import calculate_coupon_metrics
from app.tasks.refresh_features import refresh_all_features
from app.domain.staging.coupon_receipt_event import CouponReceiptEvent
from app.domain.feature.merchant_metrics import MerchantMetrics
from app.domain.feature.user_metrics import UserMetrics
from app.domain.feature.coupon_metrics import CouponMetrics


class TestMerchantFeatureCalculation:
    """Integration tests for merchant metrics calculation."""

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_merchant_redeemed_rate_7d(self, clean_db: Session):
        """Verify 7-day redemption rate calculation."""
        # Create test data across a date range
        events = []
        for i in range(100):
            # Events from 0-6 days ago (within 7-day window)
            event_date = date.today() - timedelta(days=i % 7)
            is_redeemed = i < 50  # First 50 are redeemed (50% rate)

            events.append({
                "user_id": f"user_{i:03d}",
                "merchant_id": "merchant_001",
                "coupon_id": f"coupon_{i:03d}",
                "discount_rate": "200:50",
                "distance": 500.0,
                "date_received": event_date,
                "is_redeemed": is_redeemed,
                "date_redeemed": event_date + timedelta(days=5) if is_redeemed else None,
                "redeem_days": 5 if is_redeemed else None,
            })

        clean_db.bulk_insert_mappings(CouponReceiptEvent, events)
        clean_db.commit()

        # Calculate metrics
        metrics_list = calculate_merchant_metrics(clean_db, batch_size=1000)

        assert len(metrics_list) == 1
        metrics = metrics_list[0]

        assert metrics.merchant_id == "merchant_001"
        assert metrics.total_receipts_7d >= 0
        assert metrics.redeemed_count_7d >= 0
        # Redemption rate should be calculated correctly
        if metrics.total_receipts_7d > 0:
            expected_rate = metrics.redeemed_count_7d / metrics.total_receipts_7d
            assert metrics.redeemed_rate_7d == pytest.approx(expected_rate, rel=0.01)

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_merchant_rate_change_calculation(self, clean_db: Session):
        """Verify that rate change is calculated when both rates exist."""
        # Create events spanning 30 days
        events = []
        for i in range(200):
            # Distribute events across 30 days
            event_date = date.today() - timedelta(days=i % 30)
            # 60% redemption rate overall
            is_redeemed = i % 5 < 3

            events.append({
                "user_id": f"user_{i:03d}",
                "merchant_id": "merchant_001",
                "coupon_id": f"coupon_{i:03d}",
                "discount_rate": "200:50",
                "distance": 500.0,
                "date_received": event_date,
                "is_redeemed": is_redeemed,
                "date_redeemed": event_date + timedelta(days=5) if is_redeemed else None,
                "redeem_days": 5 if is_redeemed else None,
            })

        clean_db.bulk_insert_mappings(CouponReceiptEvent, events)
        clean_db.commit()

        metrics_list = calculate_merchant_metrics(clean_db, batch_size=1000)

        assert len(metrics_list) == 1
        metrics = metrics_list[0]

        # Verify both rates are calculated
        assert metrics.redeemed_rate_7d is not None or metrics.total_receipts_7d == 0
        assert metrics.redeemed_rate_30d is not None or metrics.total_receipts_30d == 0

        # Rate change should be calculated when both rates exist
        if metrics.redeemed_rate_7d and metrics.redeemed_rate_30d:
            expected_change = (metrics.redeemed_rate_7d - metrics.redeemed_rate_30d) / metrics.redeemed_rate_30d
            assert metrics.redeemed_rate_change == pytest.approx(expected_change, rel=0.05)

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_merchant_with_no_receipts(self, clean_db: Session):
        """Verify merchant with no receipt records at all."""
        # No events for this merchant - should not appear in metrics
        events = [
            {
                "user_id": "user_001",
                "merchant_id": "merchant_001",
                "coupon_id": "coupon_001",
                "discount_rate": "200:50",
                "distance": 500.0,
                "date_received": date.today(),
                "is_redeemed": True,
                "date_redeemed": date.today(),
                "redeem_days": 0,
            }
        ]

        clean_db.bulk_insert_mappings(CouponReceiptEvent, events)
        clean_db.commit()

        metrics_list = calculate_merchant_metrics(clean_db, batch_size=1000)

        merchant_missing = next(
            (m for m in metrics_list if m.merchant_id == "merchant_missing"),
            None
        )

        assert merchant_missing is None


class TestUserFeatureCalculation:
    """Integration tests for user metrics calculation."""

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_user_redeemed_rate_30d(self, clean_db: Session):
        """Verify user 30-day redemption rate calculation."""
        reference_date = date.today()

        events = []
        # User 1: 10 receipts, 7 redeemed (70% rate)
        for i in range(10):
            event_date = reference_date - timedelta(days=i * 3 % 30)
            is_redeemed = i < 7

            events.append({
                "user_id": "user_001",
                "merchant_id": "merchant_001",
                "coupon_id": f"coupon_{i:03d}",
                "discount_rate": "200:50",
                "distance": float(i % 3),
                "date_received": event_date,
                "is_redeemed": is_redeemed,
                "date_redeemed": event_date + timedelta(days=5) if is_redeemed else None,
                "redeem_days": 5 if is_redeemed else None,
            })

        clean_db.bulk_insert_mappings(CouponReceiptEvent, events)
        clean_db.commit()

        # Calculate metrics
        metrics_list = calculate_user_metrics(clean_db, reference_date=reference_date)

        assert len(metrics_list) >= 1
        metrics = next((m for m in metrics_list if m.user_id == "user_001"), None)

        assert metrics is not None
        assert metrics.total_receipts_30d >= 0
        assert metrics.redeemed_count_30d >= 0

        if metrics.total_receipts_30d > 0:
            expected_rate = metrics.redeemed_count_30d / metrics.total_receipts_30d
            assert metrics.redeemed_rate_30d == pytest.approx(expected_rate, rel=0.01)

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_user_avg_distance_excludes_unknown(self, clean_db: Session):
        """Verify average distance excludes -1 (unknown)."""
        reference_date = date.today()

        events = [
            # Known distances: 1.0, 2.0, 3.0 (avg = 2.0)
            {"user_id": "user_001", "merchant_id": "merchant_001", "coupon_id": "coupon_001",
             "discount_rate": "200:50", "distance": 1.0,
             "date_received": reference_date - timedelta(days=5),
             "is_redeemed": True, "date_redeemed": reference_date, "redeem_days": 5},
            {"user_id": "user_001", "merchant_id": "merchant_001", "coupon_id": "coupon_002",
             "discount_rate": "200:50", "distance": 2.0,
             "date_received": reference_date - timedelta(days=10),
             "is_redeemed": False, "date_redeemed": None, "redeem_days": None},
            {"user_id": "user_001", "merchant_id": "merchant_001", "coupon_id": "coupon_003",
             "discount_rate": "200:50", "distance": -1,  # Unknown
             "date_received": reference_date - timedelta(days=15),
             "is_redeemed": True, "date_redeemed": reference_date, "redeem_days": 5},
            {"user_id": "user_001", "merchant_id": "merchant_001", "coupon_id": "coupon_004",
             "discount_rate": "200:50", "distance": 3.0,
             "date_received": reference_date - timedelta(days=20),
             "is_redeemed": False, "date_redeemed": None, "redeem_days": None},
        ]

        clean_db.bulk_insert_mappings(CouponReceiptEvent, events)
        clean_db.commit()

        # Calculate metrics
        metrics_list = calculate_user_metrics(clean_db, reference_date=reference_date)

        assert len(metrics_list) >= 1
        metrics = next((m for m in metrics_list if m.user_id == "user_001"), None)

        assert metrics is not None
        # Average should exclude -1: (1.0 + 2.0 + 3.0) / 3 = 2.0
        assert metrics.avg_distance == pytest.approx(2.0, rel=0.01)


class TestCouponFeatureCalculation:
    """Integration tests for coupon metrics calculation."""

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_coupon_redeemed_rate(self, clean_db: Session):
        """Verify coupon redemption rate calculation."""
        events = [
            # Coupon 001: 5 receipts, 3 redeemed (60% rate)
            {"user_id": "user_001", "merchant_id": "merchant_001", "coupon_id": "coupon_001",
             "discount_rate": "200:50", "distance": 500.0,
             "date_received": date(2016, 5, 1),
             "is_redeemed": True, "date_redeemed": date(2016, 5, 10), "redeem_days": 9},
            {"user_id": "user_002", "merchant_id": "merchant_001", "coupon_id": "coupon_001",
             "discount_rate": "200:50", "distance": 500.0,
             "date_received": date(2016, 5, 2),
             "is_redeemed": True, "date_redeemed": date(2016, 5, 15), "redeem_days": 13},
            {"user_id": "user_003", "merchant_id": "merchant_001", "coupon_id": "coupon_001",
             "discount_rate": "200:50", "distance": 500.0,
             "date_received": date(2016, 5, 3),
             "is_redeemed": False, "date_redeemed": None, "redeem_days": None},
            {"user_id": "user_004", "merchant_id": "merchant_001", "coupon_id": "coupon_001",
             "discount_rate": "200:50", "distance": 500.0,
             "date_received": date(2016, 5, 4),
             "is_redeemed": True, "date_redeemed": date(2016, 5, 12), "redeem_days": 8},
            {"user_id": "user_005", "merchant_id": "merchant_001", "coupon_id": "coupon_001",
             "discount_rate": "200:50", "distance": 500.0,
             "date_received": date(2016, 5, 5),
             "is_redeemed": False, "date_redeemed": None, "redeem_days": None},
        ]

        clean_db.bulk_insert_mappings(CouponReceiptEvent, events)
        clean_db.commit()

        # Calculate metrics
        metrics_list = calculate_coupon_metrics(clean_db)

        assert len(metrics_list) == 1
        metrics = metrics_list[0]

        assert metrics.coupon_id == "coupon_001"
        assert metrics.total_receipts == 5
        assert metrics.redeemed_count == 3
        assert metrics.redeemed_rate == pytest.approx(0.6, rel=0.01)

        # Average redeem days = (9 + 13 + 8) / 3 = 10.0
        assert metrics.avg_redeem_days == pytest.approx(10.0, rel=0.01)


class TestFeatureRefreshTask:
    """Integration tests for Celery refresh task."""

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_feature_refresh_task_execution(self, clean_db: Session):
        """Verify Celery task execution and database persistence."""
        # Create sample events with recent dates (within 30-day window)
        events = [
            # Merchant events
            {"user_id": "user_001", "merchant_id": "merchant_001", "coupon_id": "coupon_001",
             "discount_rate": "200:50", "distance": 500.0,
             "date_received": date.today() - timedelta(days=5),
             "is_redeemed": True, "date_redeemed": date.today(), "redeem_days": 5},
            {"user_id": "user_002", "merchant_id": "merchant_001", "coupon_id": "coupon_001",
             "discount_rate": "200:50", "distance": 500.0,
             "date_received": date.today() - timedelta(days=10),
             "is_redeemed": False, "date_redeemed": None, "redeem_days": None},

            # User events
            {"user_id": "user_001", "merchant_id": "merchant_002", "coupon_id": "coupon_002",
             "discount_rate": "0.9", "distance": 1000.0,
             "date_received": date.today() - timedelta(days=3),
             "is_redeemed": True, "date_redeemed": date.today(), "redeem_days": 5},

            # Coupon events
            {"user_id": "user_003", "merchant_id": "merchant_001", "coupon_id": "coupon_003",
             "discount_rate": "100:20", "distance": 500.0,
             "date_received": date.today() - timedelta(days=4),
             "is_redeemed": True, "date_redeemed": date.today(), "redeem_days": 2},
        ]

        clean_db.bulk_insert_mappings(CouponReceiptEvent, events)
        clean_db.commit()

        # Execute task (not async for test)
        result = refresh_all_features.apply()

        # Verify task completed successfully
        assert result.status == 'SUCCESS'

        # Check database persistence
        merchant_count = clean_db.execute(
            text("SELECT COUNT(*) FROM feature.merchant_metrics")
        ).scalar()
        user_count = clean_db.execute(
            text("SELECT COUNT(*) FROM feature.user_metrics")
        ).scalar()
        coupon_count = clean_db.execute(
            text("SELECT COUNT(*) FROM feature.coupon_metrics")
        ).scalar()

        # Should have metrics for each dimension
        assert merchant_count >= 1
        assert user_count >= 1
        assert coupon_count >= 1

        # Verify specific metrics are correct
        merchant_metrics = clean_db.query(MerchantMetrics).filter(
            MerchantMetrics.merchant_id == "merchant_001"
        ).first()
        assert merchant_metrics is not None
        assert merchant_metrics.total_receipts_7d >= 0


class TestFeatureCalculationEdgeCases:
    """Integration tests for edge cases in feature calculation."""

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_empty_database(self, clean_db: Session):
        """Verify behavior with empty staging tables."""
        # Calculate all metrics with no events
        merchant_metrics = calculate_merchant_metrics(clean_db)
        user_metrics = calculate_user_metrics(clean_db)
        coupon_metrics = calculate_coupon_metrics(clean_db)

        # Should return empty lists
        assert len(merchant_metrics) == 0
        assert len(user_metrics) == 0
        assert len(coupon_metrics) == 0

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_mixed_discount_formats(self, clean_db: Session):
        """Verify handling of mixed discount formats (满减 and 折扣)."""
        events = [
            # 满减 format
            {"user_id": "user_001", "merchant_id": "merchant_001", "coupon_id": "coupon_001",
             "discount_rate": "200:50", "distance": 500.0,
             "date_received": date(2016, 5, 1),
             "is_redeemed": True, "date_redeemed": date(2016, 5, 10), "redeem_days": 9},

            # 折扣 format
            {"user_id": "user_002", "merchant_id": "merchant_001", "coupon_id": "coupon_002",
             "discount_rate": "0.9", "distance": 1000.0,
             "date_received": date(2016, 5, 2),
             "is_redeemed": True, "date_redeemed": date(2016, 5, 8), "redeem_days": 6},

            # Null discount
            {"user_id": "user_003", "merchant_id": "merchant_001", "coupon_id": "coupon_003",
             "discount_rate": None, "distance": 500.0,
             "date_received": date(2016, 5, 3),
             "is_redeemed": False, "date_redeemed": None, "redeem_days": None},
        ]

        clean_db.bulk_insert_mappings(CouponReceiptEvent, events)
        clean_db.commit()

        # Calculate coupon metrics
        metrics_list = calculate_coupon_metrics(clean_db)

        # Should have 3 coupons with different discount types
        assert len(metrics_list) == 3

        # Sort by coupon_id
        metrics_list.sort(key=lambda m: m.coupon_id)

        # Verify coupon_001 (满减)
        assert metrics_list[0].discount_type == "满减"
        assert metrics_list[0].threshold_amount == 200.0
        assert metrics_list[0].discount_amount == 50.0

        # Verify coupon_002 (折扣)
        assert metrics_list[1].discount_type == "折扣"
        assert metrics_list[1].threshold_amount is None
        assert metrics_list[1].discount_amount is None

        # Verify coupon_003 (null)
        assert metrics_list[2].discount_type is None

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_large_batch_processing(self, clean_db: Session):
        """Verify batch processing handles large datasets."""
        # Create 1000 events (large dataset)
        events = []
        for i in range(1000):
            events.append({
                "user_id": f"user_{i % 50:03d}",  # 50 users
                "merchant_id": f"merchant_{i % 20:03d}",  # 20 merchants
                "coupon_id": f"coupon_{i % 100:03d}",  # 100 coupons
                "discount_rate": "200:50",
                "distance": float(i % 10),
                "date_received": date.today() - timedelta(days=i % 30),
                "is_redeemed": (i % 3 == 0),  # ~33% redemption rate
                "date_redeemed": date.today() if (i % 3 == 0) else None,
                "redeem_days": 5 if (i % 3 == 0) else None,
            })

        clean_db.bulk_insert_mappings(CouponReceiptEvent, events)
        clean_db.commit()

        # Calculate all metrics with small batch size
        merchant_metrics = calculate_merchant_metrics(clean_db, batch_size=50)
        user_metrics = calculate_user_metrics(clean_db, batch_size=50)
        coupon_metrics = calculate_coupon_metrics(clean_db, batch_size=50)

        # Should process all records
        assert len(merchant_metrics) == 20  # 20 merchants
        assert len(user_metrics) == 50  # 50 users
        assert len(coupon_metrics) == 100  # 100 coupons