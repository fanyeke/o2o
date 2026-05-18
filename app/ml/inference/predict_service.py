"""Prediction service for ML model inference."""
import joblib
import numpy as np
from pathlib import Path
from typing import Optional

from app.domain.staging.coupon_receipt_event import CouponReceiptEvent
from app.domain.feature.user_metrics import UserMetrics
from app.domain.feature.merchant_metrics import MerchantMetrics
from app.domain.feature.coupon_metrics import CouponMetrics


class PredictService:
    """Singleton service for predicting coupon redemption probability.

    Uses LightGBM model trained on historical coupon data.
    Implements singleton pattern to avoid repeated model loading.
    """

    _instance: Optional["PredictService"] = None
    _model: Optional[object] = None
    _feature_list: Optional[list[str]] = None

    def __new__(cls) -> "PredictService":
        """Create singleton instance and load model."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_model()
        return cls._instance

    def _load_model(self) -> None:
        """Load trained model and feature list from disk."""
        model_path = Path("app/ml/artifacts/redeem_predictor.joblib")

        if not model_path.exists():
            raise FileNotFoundError(
                f"Model file not found at {model_path}. "
                "Please train the model first using scripts/train_model.py"
            )

        data = joblib.load(model_path)
        self._model = data["model"]
        # Support both 'feature_names' (new) and 'feature_list' (legacy) keys
        self._feature_list = data.get("feature_names") or data.get("feature_list")

    def predict_redeem_probability(
        self,
        receipt_event: CouponReceiptEvent,
        user_metrics: UserMetrics,
        merchant_metrics: MerchantMetrics,
        coupon_metrics: Optional[CouponMetrics] = None,
    ) -> float:
        """Predict probability that a coupon will be redeemed.

        Args:
            receipt_event: Coupon receipt event with user/merchant/coupon info
            user_metrics: User's historical metrics (receipts, redeem rate, etc.)
            merchant_metrics: Merchant's historical metrics (redeem rate, etc.)
            coupon_metrics: Optional coupon-specific metrics (redeem rate, discount, etc.)

        Returns:
            Predicted redemption probability (0.0 to 1.0)

        Raises:
            ValueError: If model is not loaded or feature extraction fails
        """
        if self._model is None or self._feature_list is None:
            raise ValueError("Model not loaded. Call _load_model() first.")

        # Build feature vector in the same order as training
        feature_vector = self._build_features(
            receipt_event=receipt_event,
            user_metrics=user_metrics,
            merchant_metrics=merchant_metrics,
            coupon_metrics=coupon_metrics,
        )

        # Reshape for single prediction
        feature_vector = np.array(feature_vector).reshape(1, -1)

        # Predict using LightGBM model
        probability = self._model.predict(feature_vector)[0]

        # Ensure probability is within valid range
        probability = float(np.clip(probability, 0.0, 1.0))

        return probability

    def _build_features(
        self,
        receipt_event: CouponReceiptEvent,
        user_metrics: UserMetrics,
        merchant_metrics: MerchantMetrics,
        coupon_metrics: Optional[CouponMetrics] = None,
    ) -> list[float]:
        """Build feature vector in the same order as training features.

        Args:
            receipt_event: Coupon receipt event
            user_metrics: User metrics
            merchant_metrics: Merchant metrics
            coupon_metrics: Optional coupon metrics

        Returns:
            Feature vector with all features in correct order

        Raises:
            ValueError: If required feature cannot be extracted
        """
        features: dict[str, float] = {}

        # Receipt event features
        features["distance"] = float(receipt_event.distance) if receipt_event.distance else 0.0

        # Parse discount_rate (e.g., "200:50" or "0.9")
        discount_value = self._parse_discount_rate(receipt_event.discount_rate)
        features["discount_value"] = discount_value

        # Discount type encoding (满减=0, 折扣=1, unknown=-1)
        if coupon_metrics and coupon_metrics.discount_type:
            features["discount_type_encoded"] = 0.0 if coupon_metrics.discount_type == "满减" else 1.0
        else:
            # Infer from discount_rate format
            if receipt_event.discount_rate and ":" in receipt_event.discount_rate:
                features["discount_type_encoded"] = 0.0  # 满减
            elif receipt_event.discount_rate:
                features["discount_type_encoded"] = 1.0  # 折扣
            else:
                features["discount_type_encoded"] = -1.0  # unknown

        # Date features (day of week, month, day of month)
        features["day_of_week"] = float(receipt_event.date_received.weekday())
        features["month"] = float(receipt_event.date_received.month)
        features["day_of_month"] = float(receipt_event.date_received.day)

        # User metrics
        features["user_total_receipts_30d"] = float(user_metrics.total_receipts_30d or 0)
        features["user_redeemed_count_30d"] = float(user_metrics.redeemed_count_30d or 0)
        features["user_redeemed_rate_30d"] = float(user_metrics.redeemed_rate_30d or 0.0)
        features["user_avg_distance"] = float(user_metrics.avg_distance or 0.0)

        # Merchant metrics
        features["merchant_total_receipts_7d"] = float(merchant_metrics.total_receipts_7d or 0)
        features["merchant_redeemed_count_7d"] = float(merchant_metrics.redeemed_count_7d or 0)
        features["merchant_redeemed_rate_7d"] = float(merchant_metrics.redeemed_rate_7d or 0.0)
        features["merchant_total_receipts_30d"] = float(merchant_metrics.total_receipts_30d or 0)
        features["merchant_redeemed_count_30d"] = float(merchant_metrics.redeemed_count_30d or 0)
        features["merchant_redeemed_rate_30d"] = float(merchant_metrics.redeemed_rate_30d or 0.0)
        features["merchant_redeemed_rate_change"] = float(merchant_metrics.redeemed_rate_change or 0.0)
        features["merchant_avg_discount_depth"] = float(merchant_metrics.avg_discount_depth or 0.0)

        # Coupon metrics (optional)
        if coupon_metrics:
            features["coupon_total_receipts"] = float(coupon_metrics.total_receipts or 0)
            features["coupon_redeemed_count"] = float(coupon_metrics.redeemed_count or 0)
            features["coupon_redeemed_rate"] = float(coupon_metrics.redeemed_rate or 0.0)
            features["coupon_avg_redeem_days"] = float(coupon_metrics.avg_redeem_days or 0.0)
            features["coupon_discount_value"] = float(coupon_metrics.discount_value or 0.0)
        else:
            # Use default values for missing coupon metrics
            features["coupon_total_receipts"] = 0.0
            features["coupon_redeemed_count"] = 0.0
            features["coupon_redeemed_rate"] = 0.0
            features["coupon_avg_redeem_days"] = 0.0
            features["coupon_discount_value"] = 0.0

        # Build feature vector in the same order as training
        feature_vector: list[float] = []
        for feature_name in self._feature_list:
            if feature_name in features:
                feature_vector.append(features[feature_name])
            else:
                # Use default value for missing features
                feature_vector.append(0.0)

        return feature_vector

    def _parse_discount_rate(self, discount_rate: Optional[str]) -> float:
        """Parse discount_rate string to numeric value.

        Args:
            discount_rate: Discount string (e.g., "200:50" for "spend 200 save 50", or "0.9" for 10% off)

        Returns:
            Discount value (discount_amount / threshold_amount for full reduction, or 1 - discount_rate for percentage)
        """
        if not discount_rate:
            return 0.0

        try:
            if ":" in discount_rate:
                # Full reduction: "200:50" means "spend 200 save 50"
                threshold_str, discount_str = discount_rate.split(":")
                threshold = float(threshold_str)
                discount = float(discount_str)
                return discount / threshold if threshold > 0 else 0.0
            else:
                # Percentage discount: "0.9" means 10% off
                rate = float(discount_rate)
                return 1.0 - rate
        except (ValueError, ZeroDivisionError):
            return 0.0

    @classmethod
    def reset(cls) -> None:
        """Reset singleton instance (for testing purposes)."""
        cls._instance = None
        cls._model = None
        cls._feature_list = None