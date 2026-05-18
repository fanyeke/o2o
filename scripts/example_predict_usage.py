"""Example: How to use PredictService for coupon redemption prediction.

This script demonstrates the integration between:
- PredictService (ML inference)
- Domain models (CouponReceiptEvent, UserMetrics, MerchantMetrics, CouponMetrics)

Usage:
    python scripts/example_predict_usage.py

Note: This requires a trained model at app/ml/artifacts/redeem_predictor.joblib
"""
from datetime import date
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.ml.inference.predict_service import PredictService
from app.domain.staging.coupon_receipt_event import CouponReceiptEvent
from app.domain.feature.user_metrics import UserMetrics
from app.domain.feature.merchant_metrics import MerchantMetrics
from app.domain.feature.coupon_metrics import CouponMetrics


def main():
    """Demonstrate PredictService usage with domain models."""
    print("=" * 60)
    print("PredictService Usage Example")
    print("=" * 60)

    # Create sample receipt event
    receipt_event = CouponReceiptEvent(
        id=1,
        user_id="user_001",
        merchant_id="merchant_001",
        coupon_id="coupon_001",
        discount_rate="200:50",  # Spend 200, save 50
        distance=2.5,  # Distance in 500m increments
        date_received=date(2016, 5, 15),
        is_redeemed=False,
    )

    # Create user metrics
    user_metrics = UserMetrics(
        user_id="user_001",
        total_receipts_30d=10,  # User received 10 coupons in last 30 days
        redeemed_count_30d=3,   # User redeemed 3 coupons
        redeemed_rate_30d=0.3,  # User's redemption rate: 30%
        avg_distance=2.0,       # User's average distance preference
        last_receipt_date=date(2016, 5, 10),
    )

    # Create merchant metrics
    merchant_metrics = MerchantMetrics(
        merchant_id="merchant_001",
        total_receipts_7d=500,  # Merchant issued 500 coupons in last 7 days
        redeemed_count_7d=225,  # 225 redeemed
        redeemed_rate_7d=0.45,  # 7-day redemption rate: 45%
        total_receipts_30d=2000,  # Merchant issued 2000 coupons in last 30 days
        redeemed_count_30d=1300,  # 1300 redeemed
        redeemed_rate_30d=0.65,   # 30-day redemption rate: 65%
        redeemed_rate_change=-0.30,  # Rate dropped 30% (concerning!)
        avg_discount_depth=0.25,     # Average discount: 25%
    )

    # Create coupon metrics (optional)
    coupon_metrics = CouponMetrics(
        coupon_id="coupon_001",
        merchant_id="merchant_001",
        discount_type="满减",
        discount_rate="200:50",
        discount_value=0.25,  # 50/200 = 0.25
        threshold_amount=200.0,
        discount_amount=50.0,
        total_receipts=1000,  # This coupon issued 1000 times
        redeemed_count=100,   # Only 100 redeemed
        redeemed_rate=0.10,   # Coupon redemption rate: 10% (low!)
        avg_redeem_days=5.0,  # Average redemption time: 5 days
    )

    print("\nInput Data:")
    print(f"  User ID: {receipt_event.user_id}")
    print(f"  Merchant ID: {receipt_event.merchant_id}")
    print(f"  Coupon ID: {receipt_event.coupon_id}")
    print(f"  Discount: {receipt_event.discount_rate}")
    print(f"  Distance: {receipt_event.distance}")
    print(f"  User Redemption Rate: {user_metrics.redeemed_rate_30d:.1%}")
    print(f"  Merchant 7d Redemption Rate: {merchant_metrics.redeemed_rate_7d:.1%}")
    print(f"  Merchant 30d Redemption Rate: {merchant_metrics.redeemed_rate_30d:.1%}")
    print(f"  Coupon Redemption Rate: {coupon_metrics.redeemed_rate:.1%}")

    # Create PredictService instance
    try:
        service = PredictService()
        print("\n✓ Model loaded successfully")

        # Predict redemption probability
        probability = service.predict_redeem_probability(
            receipt_event=receipt_event,
            user_metrics=user_metrics,
            merchant_metrics=merchant_metrics,
            coupon_metrics=coupon_metrics,
        )

        print("\nPrediction Result:")
        print(f"  Redemption Probability: {probability:.2%}")
        print(f"  Interpretation: {'Likely to redeem' if probability > 0.5 else 'Unlikely to redeem'}")

        # Store prediction in ORM model
        receipt_event.predicted_probability = probability
        print(f"\n✓ Prediction stored in receipt_event.predicted_probability = {probability:.4f}")

    except FileNotFoundError as e:
        print(f"\n✗ Error: {e}")
        print("\nNote: You need to train the model first using:")
        print("  python scripts/train_model.py")
        return 1

    print("\n" + "=" * 60)
    print("Example completed successfully!")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())