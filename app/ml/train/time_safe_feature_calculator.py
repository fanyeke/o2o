"""Time-leakage-safe feature calculator for ML training.

This module computes features for ML model training where ALL historical
features are computed using only data BEFORE each receipt's date_received.

Time leakage prevention is critical for ML model integrity:
- If we use future data (receipts after training sample date) in features,
  the model learns patterns that won't exist in production
- Production predictions only have historical data available
- Time leakage leads to inflated training metrics but poor production performance

This calculator ensures:
1. All receipt counts use WHERE date_received < current receipt's date_received
2. All redeemed counts use WHERE is_redeemed=false OR date_redeemed < current receipt's date_received
3. No features can access information from the current receipt or future receipts
"""

from datetime import date, timedelta
from typing import List
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.domain.feature.receipt_training_features import ReceiptTrainingFeatures


class TimeSafeFeatureCalculator:
    """Calculator for time-leakage-safe training features."""

    def __init__(self, db: Session):
        """Initialize calculator with database session.

        Args:
            db: SQLAlchemy session for database operations
        """
        self.db = db

    def compute_all_training_features(
        self,
        start_date: date,
        end_date: date,
        batch_size: int = 1000
    ) -> int:
        """Compute time-safe features for all receipts in date range.

        Args:
            start_date: Start date for receipts to compute features for
            end_date: End date for receipts to compute features for
            batch_size: Number of receipts to process in each batch

        Returns:
            Total number of receipt features computed
        """
        # Get all receipts in date range
        receipts_query = text("""
            SELECT
                id as receipt_db_id,
                user_id || '_' || merchant_id || '_' || coupon_id || '_' || to_char(date_received, 'YYYYMMDD') || '_' || id as receipt_id,
                user_id,
                merchant_id,
                coupon_id,
                date_received,
                is_redeemed,
                distance,
                discount_rate,
                date_redeemed
            FROM staging.coupon_receipt_event
            WHERE date_received BETWEEN :start_date AND :end_date
            ORDER BY date_received, user_id, merchant_id
        """)

        result = self.db.execute(receipts_query, {"start_date": start_date, "end_date": end_date})
        receipts = result.fetchall()

        if not receipts:
            return 0

        # Process in batches
        total_computed = 0
        for i in range(0, len(receipts), batch_size):
            batch = receipts[i:i + batch_size]
            features_list = []

            for receipt in batch:
                features = self._compute_single_receipt_features(receipt)
                if features:
                    features_list.append(features)

            # Bulk save batch
            if features_list:
                self.db.bulk_save_objects(features_list)
                self.db.commit()
                total_computed += len(features_list)

        return total_computed

    def _compute_single_receipt_features(self, receipt) -> ReceiptTrainingFeatures:
        """Compute time-safe features for a single receipt.

        Args:
            receipt: Receipt row from database (user_id, merchant_id, coupon_id, date_received, etc.)

        Returns:
            ReceiptTrainingFeatures ORM object with time-safe features
        """
        receipt_id = receipt.receipt_id
        user_id = receipt.user_id
        merchant_id = receipt.merchant_id
        coupon_id = receipt.coupon_id
        as_of_date = receipt.date_received
        is_redeemed = receipt.is_redeemed or False
        distance = receipt.distance or 0
        discount_rate = receipt.discount_rate or ""
        date_redeemed = receipt.date_redeemed

        # Compute user features (as-of as_of_date)
        user_features = self._compute_user_features_as_of(user_id, as_of_date)

        # Compute merchant features (as-of as_of_date)
        merchant_features = self._compute_merchant_features_as_of(merchant_id, as_of_date)

        # Compute coupon features (as-of as_of_date)
        coupon_features = self._compute_coupon_features_as_of(coupon_id, as_of_date)

        # Parse discount rate
        discount_type, discount_value, threshold_amount, discount_amount = self._parse_discount(discount_rate)

        # Compute time features
        day_of_week = as_of_date.weekday()
        month = as_of_date.month
        day_of_month = as_of_date.day

        # Build receipt training features object
        features = ReceiptTrainingFeatures(
            receipt_id=receipt_id,
            user_id=user_id,
            merchant_id=merchant_id,
            coupon_id=coupon_id,
            as_of_date=as_of_date,

            # User features
            user_receipts_30d_before=user_features.get('receipts_30d', 0),
            user_redeemed_count_30d_before=user_features.get('redeemed_count_30d', 0),
            user_redeemed_rate_30d_before=user_features.get('redeemed_rate_30d', 0.0),
            user_avg_distance_before=user_features.get('avg_distance', 0.0),

            # Merchant features
            merchant_receipts_7d_before=merchant_features.get('receipts_7d', 0),
            merchant_redeemed_count_7d_before=merchant_features.get('redeemed_count_7d', 0),
            merchant_redeemed_rate_7d_before=merchant_features.get('redeemed_rate_7d', 0.0),
            merchant_receipts_30d_before=merchant_features.get('receipts_30d', 0),
            merchant_redeemed_count_30d_before=merchant_features.get('redeemed_count_30d', 0),
            merchant_redeemed_rate_30d_before=merchant_features.get('redeemed_rate_30d', 0.0),
            merchant_avg_discount_depth_before=merchant_features.get('avg_discount_depth', 0.0),

            # Coupon features
            coupon_total_receipts_before=coupon_features.get('total_receipts', 0),
            coupon_redeemed_count_before=coupon_features.get('redeemed_count', 0),
            coupon_redeemed_rate_before=coupon_features.get('redeemed_rate', 0.0),
            coupon_avg_redeem_days_before=coupon_features.get('avg_redeem_days', 0.0),

            # Static features
            discount_type=discount_type,
            discount_value=discount_value,
            threshold_amount=threshold_amount,
            discount_amount=discount_amount,
            distance=distance,

            # Time features
            day_of_week=day_of_week,
            month=month,
            day_of_month=day_of_month,

            # Target label
            label_is_redeemed=is_redeemed,

            feature_version='v1_time_safe'
        )

        return features

    def _compute_user_features_as_of(self, user_id: str, as_of_date: date) -> dict:
        """Compute user historical features as-of a specific date.

        CRITICAL: Only uses receipts WHERE date_received < as_of_date
        For redeemed counts: WHERE is_redeemed=false OR date_redeemed < as_of_date

        Args:
            user_id: User ID
            as_of_date: Date to compute features as-of

        Returns:
            Dict with user features (receipts_30d, redeemed_count_30d, redeemed_rate_30d, avg_distance)
        """
        window_30d_start = as_of_date - timedelta(days=30)

        query = text("""
            SELECT
                COUNT(*) as receipts_30d,
                COUNT(CASE WHEN is_redeemed = true AND date_redeemed < :as_of_date THEN 1 END) as redeemed_count_30d,
                AVG(distance) as avg_distance
            FROM staging.coupon_receipt_event
            WHERE user_id = :user_id
                AND date_received < :as_of_date
                AND date_received >= :window_30d_start
        """)

        result = self.db.execute(query, {
            "user_id": user_id,
            "as_of_date": as_of_date,
            "window_30d_start": window_30d_start
        }).first()

        if not result:
            return {"receipts_30d": 0, "redeemed_count_30d": 0, "redeemed_rate_30d": 0.0, "avg_distance": 0.0}

        receipts_30d = result.receipts_30d or 0
        redeemed_count_30d = result.redeemed_count_30d or 0
        redeemed_rate_30d = redeemed_count_30d / receipts_30d if receipts_30d > 0 else 0.0
        avg_distance = result.avg_distance or 0.0

        return {
            "receipts_30d": receipts_30d,
            "redeemed_count_30d": redeemed_count_30d,
            "redeemed_rate_30d": redeemed_rate_30d,
            "avg_distance": avg_distance
        }

    def _compute_merchant_features_as_of(self, merchant_id: str, as_of_date: date) -> dict:
        """Compute merchant historical features as-of a specific date.

        CRITICAL: Only uses receipts WHERE date_received < as_of_date
        For redeemed counts: WHERE is_redeemed=false OR date_redeemed < as_of_date

        Args:
            merchant_id: Merchant ID
            as_of_date: Date to compute features as-of

        Returns:
            Dict with merchant features (receipts_7d/30d, redeemed rates, avg_discount_depth)
        """
        window_7d_start = as_of_date - timedelta(days=7)
        window_30d_start = as_of_date - timedelta(days=30)

        query = text("""
            SELECT
                COUNT(CASE WHEN date_received >= :window_7d_start THEN 1 END) as receipts_7d,
                COUNT(CASE WHEN date_received >= :window_7d_start AND is_redeemed = true AND date_redeemed < :as_of_date THEN 1 END) as redeemed_count_7d,
                COUNT(CASE WHEN date_received >= :window_30d_start THEN 1 END) as receipts_30d,
                COUNT(CASE WHEN date_received >= :window_30d_start AND is_redeemed = true AND date_redeemed < :as_of_date THEN 1 END) as redeemed_count_30d,
                AVG(CASE
                    WHEN discount_rate LIKE '%:%' THEN
                        CAST(SPLIT_PART(discount_rate, ':', 2) AS FLOAT) /
                        CAST(SPLIT_PART(discount_rate, ':', 1) AS FLOAT)
                    WHEN discount_rate ~ '^[0-9.]+$' THEN
                        1.0 - CAST(discount_rate AS FLOAT)
                    ELSE NULL
                END) as avg_discount_depth
            FROM staging.coupon_receipt_event
            WHERE merchant_id = :merchant_id
                AND date_received < :as_of_date
        """)

        result = self.db.execute(query, {
            "merchant_id": merchant_id,
            "as_of_date": as_of_date,
            "window_7d_start": window_7d_start,
            "window_30d_start": window_30d_start
        }).first()

        if not result:
            return {
                "receipts_7d": 0, "redeemed_count_7d": 0, "redeemed_rate_7d": 0.0,
                "receipts_30d": 0, "redeemed_count_30d": 0, "redeemed_rate_30d": 0.0,
                "avg_discount_depth": 0.0
            }

        receipts_7d = result.receipts_7d or 0
        redeemed_count_7d = result.redeemed_count_7d or 0
        redeemed_rate_7d = redeemed_count_7d / receipts_7d if receipts_7d > 0 else 0.0

        receipts_30d = result.receipts_30d or 0
        redeemed_count_30d = result.redeemed_count_30d or 0
        redeemed_rate_30d = redeemed_count_30d / receipts_30d if receipts_30d > 0 else 0.0

        avg_discount_depth = result.avg_discount_depth or 0.0

        return {
            "receipts_7d": receipts_7d,
            "redeemed_count_7d": redeemed_count_7d,
            "redeemed_rate_7d": redeemed_rate_7d,
            "receipts_30d": receipts_30d,
            "redeemed_count_30d": redeemed_count_30d,
            "redeemed_rate_30d": redeemed_rate_30d,
            "avg_discount_depth": avg_discount_depth
        }

    def _compute_coupon_features_as_of(self, coupon_id: str, as_of_date: date) -> dict:
        """Compute coupon historical features as-of a specific date.

        CRITICAL: Only uses receipts WHERE date_received < as_of_date
        For redeemed counts: WHERE is_redeemed=false OR date_redeemed < as_of_date

        Args:
            coupon_id: Coupon ID
            as_of_date: Date to compute features as-of

        Returns:
            Dict with coupon features (total_receipts, redeemed_count, redeemed_rate, avg_redeem_days)
        """
        query = text("""
            SELECT
                COUNT(*) as total_receipts,
                COUNT(CASE WHEN is_redeemed = true AND date_redeemed < :as_of_date THEN 1 END) as redeemed_count,
                AVG(CASE WHEN is_redeemed = true AND date_redeemed < :as_of_date THEN date_redeemed - date_received END) as avg_redeem_days
            FROM staging.coupon_receipt_event
            WHERE coupon_id = :coupon_id
                AND date_received < :as_of_date
        """)

        result = self.db.execute(query, {
            "coupon_id": coupon_id,
            "as_of_date": as_of_date
        }).first()

        if not result:
            return {"total_receipts": 0, "redeemed_count": 0, "redeemed_rate": 0.0, "avg_redeem_days": 0.0}

        total_receipts = result.total_receipts or 0
        redeemed_count = result.redeemed_count or 0
        redeemed_rate = redeemed_count / total_receipts if total_receipts > 0 else 0.0
        avg_redeem_days = result.avg_redeem_days or 0.0

        return {
            "total_receipts": total_receipts,
            "redeemed_count": redeemed_count,
            "redeemed_rate": redeemed_rate,
            "avg_redeem_days": avg_redeem_days
        }

    def _parse_discount(self, discount_rate: str) -> tuple:
        """Parse discount rate string into structured fields.

        Args:
            discount_rate: Discount rate string (e.g., "200:50", "0.9")

        Returns:
            Tuple of (discount_type, discount_value, threshold_amount, discount_amount)
        """
        if not discount_rate:
            return ("未知", 0.0, 0.0, 0.0)

        try:
            # Format: "threshold:discount" for 满减券
            if ':' in discount_rate:
                parts = discount_rate.split(':')
                threshold = float(parts[0])
                discount = float(parts[1])
                discount_value = discount / threshold if threshold > 0 else 0.0
                return ("满减", discount_value, threshold, discount)

            # Format: "0.9" for 折扣券
            value = float(discount_rate)
            discount_value = 1.0 - value
            return ("折扣", discount_value, 0.0, 0.0)
        except (ValueError, AttributeError):
            return ("未知", 0.0, 0.0, 0.0)