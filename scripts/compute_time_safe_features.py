"""Compute time-safe features for ML model training.

This script computes time-leakage-safe features where ALL historical
features use only data BEFORE each receipt's date_received.

Usage:
    python scripts/compute_time_safe_features.py --start 2016-01-01 --end 2016-05-31
    python scripts/compute_time_safe_features.py --full-range
    python scripts/compute_time_safe_features.py --dry-run

Time leakage prevention rules:
- User stats: WHERE date_received < as_of_date
- Merchant stats: WHERE date_received < as_of_date
- Redeemed stats: WHERE (is_redeemed=false OR date_redeemed < as_of_date)
- No current or future receipt data allowed

Performance optimization:
- Batch processing: 1000 receipts per batch
- Parallel processing: optional (future enhancement)
- Progress tracking: log every 1000 receipts
"""

import argparse
import sys
import logging
from pathlib import Path
from datetime import date

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import get_db
from app.ml.train.time_safe_feature_calculator import TimeSafeFeatureCalculator
from sqlalchemy import text

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_full_date_range(db) -> tuple:
    """获取数据集完整日期范围."""

    result = db.execute(text("""
        SELECT
            MIN(date_received) as min_date,
            MAX(date_received) as max_date,
            COUNT(*) as total_receipts
        FROM staging.coupon_receipt_event
    """)).first()

    if result and result.min_date and result.max_date:
        logger.info(f"Dataset date range: {result.min_date} to {result.max_date}")
        logger.info(f"Total receipts: {result.total_receipts}")
        return (result.min_date, result.max_date)

    logger.warning("No receipts found in staging layer")
    return (date(2016, 1, 1), date(2016, 6, 30))  # Default range


def clear_existing_features(db):
    """清空已有的time-safe特征（重新计算）."""

    logger.info("Clearing existing time-safe features...")

    db.execute(text("TRUNCATE TABLE feature.receipt_training_features"))
    db.commit()

    logger.info("✓ Existing features cleared")


def compute_features_batch(start_date: date, end_date: date, batch_size: int = 1000):
    """批量计算time-safe特征."""

    db = next(get_db())
    calculator = TimeSafeFeatureCalculator(db)

    logger.info("=" * 60)
    logger.info(f"Computing time-safe features: {start_date} to {end_date}")
    logger.info("=" * 60)

    # Clear existing features
    clear_existing_features(db)

    # Compute features
    total_computed = calculator.compute_all_training_features(
        start_date=start_date,
        end_date=end_date,
        batch_size=batch_size
    )

    logger.info("=" * 60)
    logger.info(f"✓ Time-safe features computed: {total_computed} receipts")
    logger.info("=" * 60)

    # Verify result
    result = db.execute(text("""
        SELECT COUNT(*) as count,
               MIN(as_of_date) as min_date,
               MAX(as_of_date) as max_date,
               COUNT(DISTINCT user_id) as unique_users,
               COUNT(DISTINCT merchant_id) as unique_merchants,
               COUNT(DISTINCT coupon_id) as unique_coupons
        FROM feature.receipt_training_features
    """)).first()

    logger.info("\nFeature statistics:")
    logger.info(f"  - Total receipts: {result.count}")
    logger.info(f"  - Date range: {result.min_date} to {result.max_date}")
    logger.info(f"  - Unique users: {result.unique_users}")
    logger.info(f"  - Unique merchants: {result.unique_merchants}")
    logger.info(f"  - Unique coupons: {result.unique_coupons}")

    # Check feature coverage
    coverage_result = db.execute(text("""
        SELECT
            COUNT(CASE WHEN user_receipts_30d_before IS NOT NULL THEN 1 END) as user_covered,
            COUNT(CASE WHEN merchant_receipts_30d_before IS NOT NULL THEN 1 END) as merchant_covered,
            COUNT(CASE WHEN coupon_total_receipts_before IS NOT NULL THEN 1 END) as coupon_covered,
            COUNT(*) as total
        FROM feature.receipt_training_features
    """)).first()

    total = coverage_result.total or 0

    if total > 0:
        user_coverage = coverage_result.user_covered / total
        merchant_coverage = coverage_result.merchant_covered / total
        coupon_coverage = coverage_result.coupon_covered / total

        logger.info(f"\nFeature coverage:")
        logger.info(f"  - User features: {user_coverage:.2%}")
        logger.info(f"  - Merchant features: {merchant_coverage:.2%}")
        logger.info(f"  - Coupon features: {coupon_coverage:.2%}")

        # Warning if coverage low
        if user_coverage < 0.95:
            logger.warning("⚠️  User feature coverage < 95% (cold start issue)")

        if merchant_coverage < 0.95:
            logger.warning("⚠️  Merchant feature coverage < 95%")

        if coupon_coverage < 0.95:
            logger.warning("⚠️  Coupon feature coverage < 95%")

    db.close()

    return total_computed


def run_time_leakage_audit():
    """运行时间泄漏审计（验证计算结果）."""

    logger.info("\n" + "=" * 60)
    logger.info("Running time leakage audit...")
    logger.info("=" * 60)

    # Import audit test
    try:
        # Run audit checks
        db = next(get_db())

        # Check user receipts leakage
        violations = db.execute(text("""
            SELECT COUNT(*) as violations
            FROM feature.receipt_training_features rtf
            JOIN staging.coupon_receipt_event cre ON
                cre.user_id = rtf.user_id
                AND cre.date_received >= rtf.as_of_date
            WHERE rtf.user_receipts_30d_before > 0
        """)).first()

        user_violations = violations.violations or 0

        # Check redeemed leakage
        redeem_violations = db.execute(text("""
            SELECT COUNT(*) as violations
            FROM feature.receipt_training_features rtf
            JOIN staging.coupon_receipt_event cre ON
                cre.user_id = rtf.user_id
                AND cre.is_redeemed = true
                AND cre.date_redeemed >= rtf.as_of_date
            WHERE rtf.user_redeemed_count_30d_before > 0
        """)).first()

        redeem_violations_count = redeem_violations.violations or 0

        logger.info("\nAudit results:")
        logger.info(f"  - User receipts violations: {user_violations}")
        logger.info(f"  - Redeemed data violations: {redeem_violations_count}")

        if user_violations == 0 and redeem_violations_count == 0:
            logger.info("✓ Time leakage audit PASSED - No violations detected")
            return True
        else:
            logger.error("✗ Time leakage audit FAILED - Violations detected!")
            logger.error("  This indicates features use future data!")
            logger.error("  Model training will have inflated metrics!")
            return False

    except Exception as e:
        logger.error(f"Audit failed with error: {e}")
        return False
    finally:
        db.close()


def main():
    """Main entry point."""

    parser = argparse.ArgumentParser(
        description="Compute time-safe features for ML model training"
    )

    parser.add_argument(
        "--start",
        type=str,
        help="Start date (YYYY-MM-DD format)"
    )

    parser.add_argument(
        "--end",
        type=str,
        help="End date (YYYY-MM-DD format)"
    )

    parser.add_argument(
        "--full-range",
        action="store_true",
        help="Compute features for full dataset date range"
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Batch size for processing (default: 1000)"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show date range and count, don't compute"
    )

    parser.add_argument(
        "--skip-audit",
        action="store_true",
        help="Skip time leakage audit after computation"
    )

    args = parser.parse_args()

    # Determine date range
    if args.full_range:
        db = next(get_db())
        start_date, end_date = get_full_date_range(db)
        db.close()
    elif args.start and args.end:
        start_date = date.fromisoformat(args.start)
        end_date = date.fromisoformat(args.end)
    else:
        logger.error("Must specify --start/--end or --full-range")
        return 1

    logger.info(f"Date range: {start_date} to {end_date}")

    # Dry run mode
    if args.dry_run:
        db = next(get_db())

        count = db.execute(text("""
            SELECT COUNT(*) as count
            FROM staging.coupon_receipt_event
            WHERE date_received BETWEEN :start AND :end
        """), {"start": start_date, "end": end_date}).first()[0]

        logger.info(f"Would process {count} receipts")

        db.close()
        return 0

    # Compute features
    try:
        total_computed = compute_features_batch(
            start_date=start_date,
            end_date=end_date,
            batch_size=args.batch_size
        )

        if total_computed == 0:
            logger.warning("No features computed - check data availability")
            return 1

        # Run audit
        if not args.skip_audit:
            audit_passed = run_time_leakage_audit()

            if not audit_passed:
                logger.error("\n⚠️  CRITICAL: Time leakage detected!")
                logger.error("Model training will have invalid features!")
                logger.error("Fix time-safe feature calculator before training!")
                return 1

        logger.info("\n" + "=" * 60)
        logger.info("✓ Time-safe features ready for model training")
        logger.info("=" * 60)

        logger.info("\nNext steps:")
        logger.info("  1. Verify features: pytest tests/validation/test_time_leakage_audit.py -v")
        logger.info("  2. Train model: python scripts/train_model.py")
        logger.info("  3. Check AUC: should be realistic (0.65-0.68) without leakage")

        return 0

    except Exception as e:
        logger.error(f"Feature computation failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())