"""M1 High Standard Validation Tests.

This module tests M1 (Feature Engineering) with high standards:
1. test_feature_coverage_ge_95_percent - Verify >= 95% coverage for core features
2. test_feature_computation_reproducible - Verify features compute consistently
3. test_full_feature_computation_under_15_minutes - Performance test
4. test_core_feature_missing_rate_le_5_percent - Missing rate validation
"""

import pytest
from datetime import date, datetime, timedelta
from sqlalchemy import text
from unittest.mock import Mock, patch, MagicMock
import time
import pandas as pd
import numpy as np

from app.core.database import get_db
from app.ml.train.time_safe_feature_calculator import TimeSafeFeatureCalculator


class TestM1FeatureCoverage:
    """M1 Feature Coverage Tests - Verify >= 95% coverage."""

    def test_feature_coverage_ge_95_percent(self):
        """Verify that feature coverage is >= 95% for all core feature dimensions.

        Coverage requirements:
        - User features: >= 95% (cold start acceptable for new users)
        - Merchant features: >= 95%
        - Coupon features: >= 95%
        - Core static features: >= 99% (discount_value, distance, etc.)
        """
        db = next(get_db())

        # Check if receipt_training_features table exists and has data
        table_exists = db.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'feature'
                AND table_name = 'receipt_training_features'
            )
        """)).scalar()

        if not table_exists:
            pytest.skip("receipt_training_features table not created yet")

        result = db.execute(text("""
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN user_receipts_30d_before IS NOT NULL THEN 1 END) as user_covered,
                COUNT(CASE WHEN merchant_redeemed_rate_30d_before IS NOT NULL THEN 1 END) as merchant_covered,
                COUNT(CASE WHEN coupon_total_receipts_before IS NOT NULL THEN 1 END) as coupon_covered,
                COUNT(CASE WHEN discount_value IS NOT NULL THEN 1 END) as discount_covered,
                COUNT(CASE WHEN distance IS NOT NULL THEN 1 END) as distance_covered
            FROM feature.receipt_training_features
        """)).first()

        total = result.total or 0

        if total == 0:
            pytest.skip("No receipt_training_features data yet")

        # Calculate coverage rates
        user_coverage = result.user_covered / total
        merchant_coverage = result.merchant_covered / total
        coupon_coverage = result.coupon_covered / total
        discount_coverage = result.discount_covered / total
        distance_coverage = result.distance_covered / total

        # Print coverage report
        print(f"\nFeature Coverage Report:")
        print(f"  Total receipts: {total}")
        print(f"  User features: {user_coverage:.2%}")
        print(f"  Merchant features: {merchant_coverage:.2%}")
        print(f"  Coupon features: {coupon_coverage:.2%}")
        print(f"  Discount features: {discount_coverage:.2%}")
        print(f"  Distance features: {distance_coverage:.2%}")

        # Assert coverage >= 95% for core features
        assert user_coverage >= 0.95, \
            f"User feature coverage {user_coverage:.2%} < 95%"

        assert merchant_coverage >= 0.95, \
            f"Merchant feature coverage {merchant_coverage:.2%} < 95%"

        assert coupon_coverage >= 0.95, \
            f"Coupon feature coverage {coupon_coverage:.2%} < 95%"

        # Static features should have even higher coverage
        assert discount_coverage >= 0.99, \
            f"Discount feature coverage {discount_coverage:.2%} < 99%"

        db.close()


class TestM1FeatureReproducibility:
    """M1 Feature Reproducibility Tests."""

    def test_feature_computation_reproducible(self):
        """Verify that features compute consistently (no random variations).

        Test procedure:
        1. Compute features for a sample receipt twice
        2. Verify exact match for all features
        3. Check that historical features are deterministic
        """
        db = next(get_db())

        # Check if staging data exists
        staging_count = db.execute(text("""
            SELECT COUNT(*) FROM staging.coupon_receipt_event
        """)).scalar()

        if staging_count == 0:
            pytest.skip("No staging data available")

        # Get a sample receipt with some history
        sample_receipt = db.execute(text("""
            SELECT
                user_id,
                merchant_id,
                coupon_id,
                date_received,
                distance,
                discount_rate,
                is_redeemed
            FROM staging.coupon_receipt_event
            WHERE date_received > '2016-02-01'
            ORDER BY date_received DESC
            LIMIT 1
        """)).first()

        if not sample_receipt:
            pytest.skip("No sample receipt found")

        # Create calculator
        calculator = TimeSafeFeatureCalculator(db)

        # Compute features twice for the same receipt
        user_id = sample_receipt.user_id
        merchant_id = sample_receipt.merchant_id
        coupon_id = sample_receipt.coupon_id
        as_of_date = sample_receipt.date_received

        # First computation
        user_features_1 = calculator._compute_user_features_as_of(user_id, as_of_date)
        merchant_features_1 = calculator._compute_merchant_features_as_of(merchant_id, as_of_date)
        coupon_features_1 = calculator._compute_coupon_features_as_of(coupon_id, as_of_date)

        # Second computation (should be identical)
        user_features_2 = calculator._compute_user_features_as_of(user_id, as_of_date)
        merchant_features_2 = calculator._compute_merchant_features_as_of(merchant_id, as_of_date)
        coupon_features_2 = calculator._compute_coupon_features_as_of(coupon_id, as_of_date)

        # Verify exact match
        assert user_features_1 == user_features_2, \
            f"User features not reproducible: {user_features_1} != {user_features_2}"

        assert merchant_features_1 == merchant_features_2, \
            f"Merchant features not reproducible: {merchant_features_1} != {merchant_features_2}"

        assert coupon_features_1 == coupon_features_2, \
            f"Coupon features not reproducible: {coupon_features_1} != {coupon_features_2}"

        print(f"\nFeature Reproducibility Test PASSED")
        print(f"  Receipt: {user_id}_{merchant_id}_{coupon_id}_{as_of_date}")
        print(f"  User features: reproducible")
        print(f"  Merchant features: reproducible")
        print(f"  Coupon features: reproducible")

        db.close()


class TestM1Performance:
    """M1 Performance Tests."""

    def test_full_feature_computation_under_15_minutes(self):
        """Verify full feature computation completes in under 15 minutes.

        Performance requirements:
        - 1M+ receipts should compute in < 15 minutes
        - Average per receipt: < 10ms
        - Batch processing should be efficient
        """
        db = next(get_db())

        # Check staging data count
        staging_count = db.execute(text("""
            SELECT COUNT(*) FROM staging.coupon_receipt_event
        """)).scalar()

        if staging_count < 100000:
            pytest.skip(f"Not enough staging data for performance test ({staging_count} < 100k)")

        print(f"\nPerformance Test: {staging_count} receipts")

        # Measure computation time for a batch of receipts
        start_time = time.time()

        calculator = TimeSafeFeatureCalculator(db)

        # Compute features for a 1000-receipt batch
        batch_size = 1000
        sample_receipts = db.execute(text("""
            SELECT
                user_id,
                merchant_id,
                coupon_id,
                date_received
            FROM staging.coupon_receipt_event
            WHERE date_received BETWEEN '2016-01-15' AND '2016-01-20'
            LIMIT :batch_size
        """), {"batch_size": batch_size}).fetchall()

        if len(sample_receipts) < batch_size:
            pytest.skip("Not enough receipts in test date range")

        # Compute features for batch
        for receipt in sample_receipts:
            calculator._compute_user_features_as_of(receipt.user_id, receipt.date_received)
            calculator._compute_merchant_features_as_of(receipt.merchant_id, receipt.date_received)
            calculator._compute_coupon_features_as_of(receipt.coupon_id, receipt.date_received)

        elapsed_time = time.time() - start_time

        # Calculate per-receipt average
        avg_time_per_receipt = elapsed_time / batch_size

        # Extrapolate to full dataset
        estimated_full_time = avg_time_per_receipt * staging_count

        print(f"  Batch size: {batch_size}")
        print(f"  Batch time: {elapsed_time:.2f} seconds")
        print(f"  Avg per receipt: {avg_time_per_receipt*1000:.2f} ms")
        print(f"  Estimated full time: {estimated_full_time/60:.2f} minutes")

        # Assert per-receipt time < 10ms
        assert avg_time_per_receipt < 0.010, \
            f"Per-receipt time {avg_time_per_receipt*1000:.2f}ms exceeds 10ms"

        # Assert estimated full time < 15 minutes
        assert estimated_full_time < 900, \
            f"Estimated full time {estimated_full_time/60:.2f}min exceeds 15min"

        db.close()


class TestM1CoreFeatureMissingRate:
    """M1 Core Feature Missing Rate Tests."""

    def test_core_feature_missing_rate_le_5_percent(self):
        """Verify that core feature missing rate is <= 5%.

        Core features include:
        - discount_value (from discount_rate parsing)
        - distance (user-merchant distance)
        - day_of_week, month, day_of_month (time features)
        - User historical metrics (30d)
        - Merchant historical metrics (7d/30d)
        """
        db = next(get_db())

        # Check if receipt_training_features exists
        table_exists = db.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'feature'
                AND table_name = 'receipt_training_features'
            )
        """)).scalar()

        if not table_exists:
            pytest.skip("receipt_training_features table not created yet")

        result = db.execute(text("""
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN discount_value IS NULL OR discount_value = 0 THEN 1 END) as discount_missing,
                COUNT(CASE WHEN distance IS NULL THEN 1 END) as distance_missing,
                COUNT(CASE WHEN day_of_week IS NULL THEN 1 END) as dow_missing,
                COUNT(CASE WHEN user_receipts_30d_before IS NULL THEN 1 END) as user_history_missing,
                COUNT(CASE WHEN merchant_receipts_30d_before IS NULL THEN 1 END) as merchant_history_missing
            FROM feature.receipt_training_features
        """)).first()

        total = result.total or 0

        if total == 0:
            pytest.skip("No receipt_training_features data yet")

        # Calculate missing rates
        discount_missing_rate = result.discount_missing / total
        distance_missing_rate = result.distance_missing / total
        dow_missing_rate = result.dow_missing / total
        user_history_missing_rate = result.user_history_missing / total
        merchant_history_missing_rate = result.merchant_history_missing / total

        print(f"\nCore Feature Missing Rate Report:")
        print(f"  Total receipts: {total}")
        print(f"  discount_value missing: {discount_missing_rate:.2%}")
        print(f"  distance missing: {distance_missing_rate:.2%}")
        print(f"  day_of_week missing: {dow_missing_rate:.2%}")
        print(f"  user_history missing: {user_history_missing_rate:.2%}")
        print(f"  merchant_history missing: {merchant_history_missing_rate:.2%}")

        # Static features should have near-zero missing rate
        assert discount_missing_rate <= 0.05, \
            f"discount_value missing rate {discount_missing_rate:.2%} > 5%"

        assert distance_missing_rate <= 0.05, \
            f"distance missing rate {distance_missing_rate:.2%} > 5%"

        assert dow_missing_rate <= 0.01, \
            f"day_of_week missing rate {dow_missing_rate:.2%} > 1%"

        # Historical features have cold start, allow 5% missing
        assert user_history_missing_rate <= 0.05, \
            f"user_history missing rate {user_history_missing_rate:.2%} > 5%"

        assert merchant_history_missing_rate <= 0.05, \
            f"merchant_history missing rate {merchant_history_missing_rate:.2%} > 5%"

        db.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])