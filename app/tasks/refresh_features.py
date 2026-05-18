"""Celery task for refreshing feature layer metrics.

This task integrates merchant, user, and coupon feature calculations.
"""

from datetime import date
from typing import Dict, Any

from app.tasks.celery_app import celery_app
from app.features.merchant_features import calculate_merchant_metrics
from app.features.user_features import calculate_user_metrics
from app.features.coupon_features import calculate_coupon_metrics
from app.core.database import SessionLocal
from app.domain.feature.merchant_metrics import MerchantMetrics
from app.domain.feature.user_metrics import UserMetrics
from app.domain.feature.coupon_metrics import CouponMetrics
from sqlalchemy import text


@celery_app.task(bind=True, max_retries=3)
def refresh_all_features(self, reference_date: str = None) -> Dict[str, Any]:
    """Refresh all feature layer metrics.

    This task calculates and persists metrics for:
    - Merchants (7-day and 30-day redemption rates, change, health score)
    - Users (30-day redemption stats, average distance)
    - Coupons (redemption rate, average redeem days)

    Args:
        self: Celery task instance
        reference_date: ISO format date string (YYYY-MM-DD).
                       If None, uses the latest date from data.

    Returns:
        Dictionary with status and counts of processed records

    Raises:
        Exception: On failure, retries up to 3 times with 60-second countdown
    """
    try:
        # Parse reference date if provided
        if reference_date:
            ref_date = date.fromisoformat(reference_date)
        else:
            ref_date = None  # Will use latest date in data

        # Use database session with automatic cleanup
        with SessionLocal() as session:
            # 1. Calculate and save merchant metrics
            merchant_metrics = calculate_merchant_metrics(
                session, batch_size=1000
            )

            # Clear existing merchant metrics
            session.execute(text("TRUNCATE TABLE feature.merchant_metrics"))
            session.commit()

            # Bulk insert merchant metrics
            if merchant_metrics:
                session.bulk_save_objects(merchant_metrics)
                session.commit()

            merchant_count = len(merchant_metrics)

            # 2. Calculate and save user metrics
            user_metrics = calculate_user_metrics(
                session, reference_date=ref_date, batch_size=1000
            )

            # Clear existing user metrics
            session.execute(text("TRUNCATE TABLE feature.user_metrics"))
            session.commit()

            # Bulk insert user metrics
            if user_metrics:
                session.bulk_save_objects(user_metrics)
                session.commit()

            user_count = len(user_metrics)

            # 3. Calculate and save coupon metrics
            coupon_metrics = calculate_coupon_metrics(
                session, batch_size=1000
            )

            # Clear existing coupon metrics
            session.execute(text("TRUNCATE TABLE feature.coupon_metrics"))
            session.commit()

            # Bulk insert coupon metrics
            if coupon_metrics:
                session.bulk_save_objects(coupon_metrics)
                session.commit()

            coupon_count = len(coupon_metrics)

        return {
            'status': 'success',
            'merchant_count': merchant_count,
            'user_count': user_count,
            'coupon_count': coupon_count,
            'reference_date': str(ref_date) if ref_date else 'auto-detected'
        }

    except Exception as exc:
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60)