"""Feature extraction for ML model training."""

from datetime import date
from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.domain.staging.coupon_receipt_event import CouponReceiptEvent
from app.domain.feature.user_metrics import UserMetrics
from app.domain.feature.merchant_metrics import MerchantMetrics
from app.domain.feature.coupon_metrics import CouponMetrics


class FeatureExtractor:
    """Extract features for coupon redemption prediction model."""

    def __init__(self, db: Session):
        """Initialize feature extractor.

        Args:
            db: SQLAlchemy session for database queries
        """
        self.db = db

    def extract_training_features(
        self,
        start_date: date,
        end_date: date
    ) -> pd.DataFrame:
        """Extract training features from staging and feature tables.

        Args:
            start_date: Start date for feature extraction
            end_date: End date for feature extraction

        Returns:
            DataFrame with features and labels
        """
        # Query coupon receipt events with feature joins
        query = text("""
            SELECT
                cre.user_id,
                cre.merchant_id,
                cre.coupon_id,
                cre.date_received,
                cre.is_redeemed,
                cre.distance,
                cre.discount_rate,
                -- User features
                um.total_receipts_30d as user_total_receipts_30d,
                um.redeemed_rate_30d as user_redeemed_rate_30d,
                um.avg_distance as user_avg_distance,
                -- Merchant features
                mm.redeemed_rate_7d as merchant_redeemed_rate_7d,
                mm.redeemed_rate_30d as merchant_redeemed_rate_30d,
                mm.redeemed_rate_change as merchant_redeemed_rate_change,
                mm.avg_discount_depth as merchant_avg_discount_depth,
                -- Coupon features
                cm.discount_type,
                cm.discount_value,
                cm.threshold_amount,
                cm.discount_amount,
                cm.redeemed_rate as coupon_redeemed_rate,
                cm.avg_redeem_days as coupon_avg_redeem_days
            FROM staging.coupon_receipt_event cre
            LEFT JOIN feature.user_metrics um ON cre.user_id = um.user_id
            LEFT JOIN feature.merchant_metrics mm ON cre.merchant_id = mm.merchant_id
            LEFT JOIN feature.coupon_metrics cm ON cre.coupon_id = cm.coupon_id
            WHERE cre.date_received BETWEEN :start_date AND :end_date
        """)

        result = self.db.execute(
            query,
            {"start_date": start_date, "end_date": end_date}
        )

        # Convert to DataFrame
        df = pd.DataFrame(result.fetchall(), columns=result.keys())

        if df.empty:
            return df

        # Engineer additional features
        df = self._engineer_features(df)

        return df

    def _engineer_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Engineer additional features from raw data.

        Args:
            df: DataFrame with raw features

        Returns:
            DataFrame with engineered features
        """
        # Extract date features
        df['day_of_week'] = pd.to_datetime(df['date_received']).dt.dayofweek
        df['month'] = pd.to_datetime(df['date_received']).dt.month
        df['day_of_month'] = pd.to_datetime(df['date_received']).dt.day

        # Parse discount_rate to extract discount value
        df['parsed_discount_value'] = df['discount_rate'].apply(self._parse_discount_rate)

        # Encode discount_type (categorical)
        df['discount_type_encoded'] = df['discount_type'].map({
            '满减': 0,
            '折扣': 1
        }).fillna(-1)  # -1 for unknown

        # Fill missing values with sensible defaults
        df = self._fill_missing_values(df)

        # Select final feature columns
        feature_columns = [
            # Date column for time split (not used as training feature)
            'date_received',
            # User features
            'user_redeemed_rate_30d',
            'user_total_receipts_30d',
            'user_avg_distance',
            # Merchant features
            'merchant_redeemed_rate_7d',
            'merchant_redeemed_rate_change',
            'merchant_avg_discount_depth',
            # Coupon features
            'discount_value',
            'discount_type_encoded',
            # Time features
            'day_of_week',
            'month',
            'day_of_month',
            # Distance feature
            'distance',
            # Target
            'is_redeemed',
            # Group column for AUC calculation
            'coupon_id'
        ]

        # Only include columns that exist
        available_columns = [col for col in feature_columns if col in df.columns]
        df = df[available_columns].copy()

        return df

    def _parse_discount_rate(self, discount_rate: Optional[str]) -> float:
        """Parse discount rate string to numeric value.

        Args:
            discount_rate: Discount rate string (e.g., "200:50", "0.9")

        Returns:
            Numeric discount value
        """
        if pd.isna(discount_rate):
            return 0.0

        try:
            # Format: "threshold:discount" for 满减券
            if ':' in discount_rate:
                parts = discount_rate.split(':')
                threshold = float(parts[0])
                discount = float(parts[1])
                return discount / threshold if threshold > 0 else 0.0

            # Format: "0.9" for 折扣券
            value = float(discount_rate)
            return 1.0 - value  # Convert to discount depth
        except (ValueError, AttributeError):
            return 0.0

    def _fill_missing_values(self, df: pd.DataFrame) -> pd.DataFrame:
        """Fill missing values with sensible defaults.

        Args:
            df: DataFrame with potential missing values

        Returns:
            DataFrame with filled missing values
        """
        # User features - fill with 0 for missing
        df['user_redeemed_rate_30d'] = df['user_redeemed_rate_30d'].fillna(0.0)
        df['user_total_receipts_30d'] = df['user_total_receipts_30d'].fillna(0)
        df['user_avg_distance'] = df['user_avg_distance'].fillna(df['distance'].median())

        # Merchant features
        df['merchant_redeemed_rate_7d'] = df['merchant_redeemed_rate_7d'].fillna(0.0)
        df['merchant_redeemed_rate_change'] = df['merchant_redeemed_rate_change'].fillna(0.0)
        df['merchant_avg_discount_depth'] = df['merchant_avg_discount_depth'].fillna(0.0)

        # Coupon features
        df['discount_value'] = df['discount_value'].fillna(df['parsed_discount_value'])
        df['avg_redeem_days'] = df.get('coupon_avg_redeem_days', pd.Series([0.0] * len(df)))

        # Distance - fill with median
        df['distance'] = df['distance'].fillna(df['distance'].median())

        return df

    def get_feature_names(self) -> List[str]:
        """Get list of feature names used in model training.

        Returns:
            List of feature column names
        """
        return [
            'user_redeemed_rate_30d',
            'user_total_receipts_30d',
            'user_avg_distance',
            'merchant_redeemed_rate_7d',
            'merchant_redeemed_rate_change',
            'merchant_avg_discount_depth',
            'discount_value',
            'discount_type_encoded',
            'day_of_week',
            'month',
            'day_of_month',
            'distance'
        ]