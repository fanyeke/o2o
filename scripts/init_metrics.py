"""Initialize metrics pipeline - complete data flow from raw to feature layer.

This script orchestrates the complete data initialization pipeline:
1. Import raw data (offline_train.csv, offline_test.csv)
2. Clean data (raw → staging)
3. Calculate features (staging → feature)
4. Train ML model

Usage:
    python scripts/init_metrics.py [--skip-import] [--skip-clean] [--skip-features] [--skip-model]

Examples:
    # Full pipeline
    python scripts/init_metrics.py

    # Skip import (data already imported)
    python scripts/init_metrics.py --skip-import

    # Only calculate features
    python scripts/init_metrics.py --skip-import --skip-clean --skip-model
"""

import argparse
import sys
import logging
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import get_db
from app.services.data_cleaning_service import DataCleaningService
from app.features.merchant_features import MerchantFeatureCalculator
from app.features.user_features import calculate_user_metrics
from app.features.coupon_features import CouponFeatureCalculator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def step_import_data():
    """Import raw data from CSV files."""
    logger.info("=" * 60)
    logger.info("Step 1: Import raw data")
    logger.info("=" * 60)

    import subprocess

    # Import training data
    train_csv = Path("data/offline_train.csv")
    test_csv = Path("data/offline_test.csv")

    if not train_csv.exists():
        logger.error(f"Training data not found: {train_csv}")
        logger.info("Please download the dataset and place it in data/offline_train.csv")
        return False

    cmd = [sys.executable, "scripts/import_dataset.py"]
    if test_csv.exists():
        cmd.extend(["--train", str(train_csv), "--test", str(test_csv)])
    else:
        cmd.extend(["--train", str(train_csv)])

    try:
        subprocess.run(cmd, check=True)
        logger.info("✓ Data import completed")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Data import failed: {e}")
        return False


def step_clean_data():
    """Clean data from raw to staging layer."""
    logger.info("=" * 60)
    logger.info("Step 2: Clean data (raw → staging)")
    logger.info("=" * 60)

    db = next(get_db())
    try:
        service = DataCleaningService(db)
        result = service.clean_all_data()

        logger.info(f"✓ Data cleaning completed:")
        logger.info(f"  - Coupon receipt events: {result['receipt_events']}")
        logger.info(f"  - Consumption events: {result['consumption_events']}")
        return True
    except Exception as e:
        logger.error(f"Data cleaning failed: {e}")
        return False
    finally:
        db.close()


def step_calculate_features():
    """Calculate features from staging to feature layer."""
    logger.info("=" * 60)
    logger.info("Step 3: Calculate features (staging → feature)")
    logger.info("=" * 60)

    db = next(get_db())
    try:
        from sqlalchemy import text

        # Merchant metrics - use save method
        logger.info("Calculating merchant metrics...")
        merchant_calc = MerchantFeatureCalculator(db)
        merchant_result = merchant_calc.save_merchant_metrics()
        logger.info(f"✓ Merchant metrics: {merchant_result.get('merchants_processed', 0)} merchants")

        # User metrics - calculate and bulk save
        logger.info("Calculating user metrics...")
        user_metrics = calculate_user_metrics(db)
        db.execute(text("TRUNCATE TABLE feature.user_metrics"))
        db.bulk_save_objects(user_metrics)
        logger.info(f"✓ User metrics: {len(user_metrics)} users")

        # Coupon metrics - use save method
        logger.info("Calculating coupon metrics...")
        coupon_calc = CouponFeatureCalculator(db)
        coupon_result = coupon_calc.save_coupon_metrics()
        logger.info(f"✓ Coupon metrics: {coupon_result.get('coupons_processed', 0)} coupons")

        db.commit()
        logger.info("✓ Feature calculation completed")
        return True
    except Exception as e:
        logger.error(f"Feature calculation failed: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        return False
    finally:
        db.close()


def step_train_model():
    """Train ML model for redeem prediction."""
    logger.info("=" * 60)
    logger.info("Step 4: Train ML model")
    logger.info("=" * 60)

    import subprocess

    cmd = [sys.executable, "scripts/train_model.py"]

    try:
        subprocess.run(cmd, check=True)
        logger.info("✓ Model training completed")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Model training failed: {e}")
        return False


def main():
    """Run complete initialization pipeline."""
    parser = argparse.ArgumentParser(
        description="Initialize metrics pipeline from raw data to feature layer"
    )
    parser.add_argument(
        "--skip-import",
        action="store_true",
        help="Skip data import step (data already imported)"
    )
    parser.add_argument(
        "--skip-clean",
        action="store_true",
        help="Skip data cleaning step"
    )
    parser.add_argument(
        "--skip-features",
        action="store_true",
        help="Skip feature calculation step"
    )
    parser.add_argument(
        "--skip-model",
        action="store_true",
        help="Skip model training step"
    )

    args = parser.parse_args()

    logger.info("Starting metrics initialization pipeline...")
    logger.info("")

    results = []

    # Step 1: Import data
    if not args.skip_import:
        results.append(("Import data", step_import_data()))
    else:
        logger.info("Skipping data import (--skip-import)")
        results.append(("Import data", True))

    # Step 2: Clean data
    if not args.skip_clean:
        results.append(("Clean data", step_clean_data()))
    else:
        logger.info("Skipping data cleaning (--skip-clean)")
        results.append(("Clean data", True))

    # Step 3: Calculate features
    if not args.skip_features:
        results.append(("Calculate features", step_calculate_features()))
    else:
        logger.info("Skipping feature calculation (--skip-features)")
        results.append(("Calculate features", True))

    # Step 4: Train model
    if not args.skip_model:
        results.append(("Train model", step_train_model()))
    else:
        logger.info("Skipping model training (--skip-model)")
        results.append(("Train model", True))

    # Summary
    logger.info("")
    logger.info("=" * 60)
    logger.info("Pipeline Summary")
    logger.info("=" * 60)

    all_success = True
    for step_name, success in results:
        status = "✓" if success else "✗"
        logger.info(f"{status} {step_name}")
        if not success:
            all_success = False

    if all_success:
        logger.info("")
        logger.info("✓ All steps completed successfully!")
        logger.info("Metrics initialization pipeline finished.")
        return 0
    else:
        logger.info("")
        logger.error("✗ Pipeline failed. Check logs above for errors.")
        return 1


if __name__ == "__main__":
    sys.exit(main())