"""Feature extraction for ML model training - TIME-SAFE VERSION.

IMPORTANT: This version uses ONLY time-leakage-safe features from
feature.receipt_training_features table.

All historical features are computed using data BEFORE as_of_date,
ensuring no future data leaks into training features.

Time leakage prevention:
- No direct joins to feature.user_metrics, merchant_metrics, coupon_metrics
- All features come from pre-computed receipt_training_features
- Feature version must be 'v1_time_safe'
"""

from datetime import date
from typing import List
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import text


class FeatureExtractor:
    """Extract TIME-SAFE features for coupon redemption prediction model.

    This extractor ONLY uses feature.receipt_training_features table,
    which contains features computed using data BEFORE as_of_date.

    NO direct joins to feature.user_metrics, merchant_metrics, coupon_metrics.
    """

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
        """Extract TIME-SAFE training features from receipt_training_features table.

        Args:
            start_date: Start date for feature extraction (as_of_date range)
            end_date: End date for feature extraction

        Returns:
            DataFrame with time-safe features and labels

        IMPORTANT: All features are computed BEFORE as_of_date, preventing time leakage.
        """
        # Query time-safe features directly from receipt_training_features
        query = text("""
            SELECT
                -- Identifiers
                receipt_id,
                user_id,
                merchant_id,
                coupon_id,
                as_of_date as date_received,

                -- User historical features (BEFORE as_of_date)
                user_receipts_30d_before,
                user_redeemed_count_30d_before,
                user_redeemed_rate_30d_before,
                user_avg_distance_before,

                -- Merchant historical features (BEFORE as_of_date)
                merchant_receipts_7d_before,
                merchant_redeemed_count_7d_before,
                merchant_redeemed_rate_7d_before,
                merchant_receipts_30d_before,
                merchant_redeemed_count_30d_before,
                merchant_redeemed_rate_30d_before,
                merchant_avg_discount_depth_before,

                -- Coupon historical features (BEFORE as_of_date)
                coupon_total_receipts_before,
                coupon_redeemed_count_before,
                coupon_redeemed_rate_before,
                coupon_avg_redeem_days_before,

                -- Static features
                discount_type,
                discount_value,
                threshold_amount,
                discount_amount,
                distance,

                -- Time features
                day_of_week,
                month,
                day_of_month,

                -- Target label
                label_is_redeemed as is_redeemed,

                -- Metadata
                feature_version

            FROM feature.receipt_training_features
            WHERE as_of_date BETWEEN :start_date AND :end_date
              AND feature_version = 'v1_time_safe'
        """)

        result = self.db.execute(
            query,
            {"start_date": start_date, "end_date": end_date}
        )

        # Convert to DataFrame
        df = pd.DataFrame(result.fetchall(), columns=result.keys())

        if df.empty:
            return df

        # Verify feature version
        if not all(df['feature_version'] == 'v1_time_safe'):
            raise ValueError(
                "Feature version mismatch: expected 'v1_time_safe', "
                f"found versions: {df['feature_version'].unique()}"
            )

        # Engineer additional features (if needed)
        df = self._engineer_features(df)

        return df

    def _engineer_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Engineer additional features from time-safe base features.

        Args:
            df: DataFrame with time-safe features from receipt_training_features

        Returns:
            DataFrame with engineered features
        """
        # Encode discount_type (categorical)
        df['discount_type_encoded'] = df['discount_type'].map({
            '满减': 0,
            '折扣': 1
        }).fillna(-1)  # -1 for unknown

        # Fill missing values with sensible defaults (should be minimal with time-safe features)
        df = self._fill_missing_values(df)

        # Select final feature columns (using time-safe feature names)
        feature_columns = [
            # Date column for time split (not used as training feature)
            'date_received',
            # User time-safe features
            'user_redeemed_rate_30d_before',
            'user_receipts_30d_before',
            'user_avg_distance_before',
            # Merchant time-safe features
            'merchant_redeemed_rate_7d_before',
            'merchant_redeemed_rate_30d_before',
            'merchant_avg_discount_depth_before',
            # Coupon time-safe features
            'coupon_redeemed_rate_before',
            'coupon_avg_redeem_days_before',
            # Static features
            'discount_value',
            'discount_type_encoded',
            'threshold_amount',
            'discount_amount',
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

    def _fill_missing_values(self, df: pd.DataFrame) -> pd.DataFrame:
        """Fill missing values with sensible defaults for time-safe features.

        Args:
            df: DataFrame with potential missing values

        Returns:
            DataFrame with filled missing values
        """
        # User time-safe features - fill with 0 for missing
        df['user_redeemed_rate_30d_before'] = df['user_redeemed_rate_30d_before'].fillna(0.0)
        df['user_receipts_30d_before'] = df['user_receipts_30d_before'].fillna(0)
        df['user_avg_distance_before'] = df['user_avg_distance_before'].fillna(df['distance'].median())

        # Merchant time-safe features
        df['merchant_redeemed_rate_7d_before'] = df['merchant_redeemed_rate_7d_before'].fillna(0.0)
        df['merchant_redeemed_rate_30d_before'] = df['merchant_redeemed_rate_30d_before'].fillna(0.0)
        df['merchant_avg_discount_depth_before'] = df['merchant_avg_discount_depth_before'].fillna(0.0)

        # Coupon time-safe features
        df['coupon_redeemed_rate_before'] = df['coupon_redeemed_rate_before'].fillna(0.0)
        df['coupon_avg_redeem_days_before'] = df['coupon_avg_redeem_days_before'].fillna(0.0)

        # Static features
        df['discount_value'] = df['discount_value'].fillna(0.0)
        df['threshold_amount'] = df['threshold_amount'].fillna(0.0)
        df['discount_amount'] = df['discount_amount'].fillna(0.0)

        # Distance - fill with median
        df['distance'] = df['distance'].fillna(df['distance'].median())

        return df

    def get_feature_names(self) -> List[str]:
        """Get list of TIME-SAFE feature names used in model training.

        Returns:
            List of time-safe feature column names
        """
        return [
            'user_redeemed_rate_30d_before',
            'user_receipts_30d_before',
            'user_avg_distance_before',
            'merchant_redeemed_rate_7d_before',
            'merchant_redeemed_rate_30d_before',
            'merchant_avg_discount_depth_before',
            'coupon_redeemed_rate_before',
            'coupon_avg_redeem_days_before',
            'discount_value',
            'discount_type_encoded',
            'threshold_amount',
            'discount_amount',
            'day_of_week',
            'month',
            'day_of_month',
            'distance'
        ]