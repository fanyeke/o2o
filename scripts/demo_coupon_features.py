"""Demo script for coupon metrics calculation.

This script demonstrates how to use the coupon feature engineering module.
"""

from app.core.database import SessionLocal
from app.features.coupon_features import CouponFeatureCalculator, calculate_coupon_metrics


def demo_coupon_metrics():
    """Demonstrate coupon metrics calculation."""
    db = SessionLocal()

    try:
        # Method 1: Using convenience function
        print("=== Method 1: Using calculate_coupon_metrics() ===")
        metrics_list = calculate_coupon_metrics(db)

        print(f"Total coupons: {len(metrics_list)}")

        if metrics_list:
            print("\nFirst coupon metrics:")
            first = metrics_list[0]
            print(f"  Coupon ID: {first.coupon_id}")
            print(f"  Merchant ID: {first.merchant_id}")
            print(f"  Discount Type: {first.discount_type}")
            print(f"  Total Receipts: {first.total_receipts}")
            print(f"  Redeemed Count: {first.redeemed_count}")
            print(f"  Redeemed Rate: {first.redeemed_rate:.2%}")
            print(f"  Avg Redeem Days: {first.avg_redeem_days}")

        # Method 2: Using Calculator class
        print("\n=== Method 2: Using CouponFeatureCalculator ===")
        calculator = CouponFeatureCalculator(db)

        # Calculate for specific coupons
        if metrics_list:
            specific_ids = [metrics_list[0].coupon_id]
            specific_metrics = list(calculator.calculate_coupon_metrics(coupon_ids=specific_ids))
            print(f"Calculated metrics for {len(specific_metrics)} specific coupon(s)")

        # Method 3: Batch processing with yield
        print("\n=== Method 3: Batch processing ===")
        batch_count = 0
        total_coupons = 0

        for batch in calculator.calculate_coupon_metrics(batch_size=100):
            batch_count += 1
            total_coupons += len(batch)
            print(f"Batch {batch_count}: {len(batch)} coupons")

        print(f"\nTotal coupons processed: {total_coupons}")

        # Method 4: Save to database
        print("\n=== Method 4: Save metrics to database ===")
        result = calculator.save_coupon_metrics()
        print(f"Saved {result['coupons_processed']} coupon metrics to feature layer")

    finally:
        db.close()


if __name__ == "__main__":
    demo_coupon_metrics()