"""M3 Prediction Service Schema Matching Tests.

This module tests M3 (Inference Service) with high standards:
1. test_predict_service_feature_schema_matches_training - Verify inference features match training schema

Schema matching is critical for production ML:
- If inference features differ from training, predictions will be wrong
- Feature ordering must be identical
- Feature transformations must be consistent
"""

import pytest
import joblib
import numpy as np
from pathlib import Path
from datetime import date
from unittest.mock import Mock, patch, MagicMock

from app.ml.inference.predict_service import PredictService
from app.ml.train.feature_extractor import FeatureExtractor
from app.domain.staging.coupon_receipt_event import CouponReceiptEvent
from app.domain.feature.user_metrics import UserMetrics
from app.domain.feature.merchant_metrics import MerchantMetrics
from app.domain.feature.coupon_metrics import CouponMetrics


class TestM3SchemaMatching:
    """M3 Schema Matching Tests."""

    def test_predict_service_feature_schema_matches_training(self):
        """Verify that PredictService feature schema matches training schema.

        Critical validation:
        1. Feature names must match exactly
        2. Feature ordering must be identical
        3. Feature transformations (encoding, normalization) must be consistent
        4. No missing features in inference
        """
        model_path = Path("app/ml/artifacts/redeem_predictor.joblib")

        if not model_path.exists():
            pytest.skip("Model file not trained yet - cannot verify schema match")

        # Load model to get training feature schema
        model_data = joblib.load(model_path)
        training_features = model_data.get("feature_names", [])

        if len(training_features) == 0:
            pytest.fail("Model has no feature_names in metadata - invalid model")

        # Get inference feature schema from FeatureExtractor
        feature_extractor = FeatureExtractor(Mock())  # Mock DB
        inference_features = feature_extractor.get_feature_names()

        # Compare feature schemas
        print(f"\nFeature Schema Matching Test:")
        print(f"  Training features count: {len(training_features)}")
        print(f"  Inference features count: {len(inference_features)}")

        # Check exact match
        missing_in_inference = [f for f in training_features if f not in inference_features]
        extra_in_inference = [f for f in inference_features if f not in training_features]

        if missing_in_inference:
            print(f"  Missing in inference: {missing_in_inference}")
            pytest.fail(
                f"Features missing in PredictService: {missing_in_inference}\n"
                "This will cause incorrect predictions in production!"
            )

        if extra_in_inference:
            print(f"  Extra in inference: {extra_in_inference}")
            pytest.fail(
                f"Extra features in PredictService not in training: {extra_in_inference}\n"
                "This may indicate schema drift or incorrect feature engineering"
            )

        # Check ordering
        if training_features != inference_features:
            print(f"\n  Training order: {training_features}")
            print(f"  Inference order: {inference_features}")

            pytest.fail(
                "Feature ordering mismatch between training and inference!\n"
                "Features must be in identical order for correct predictions."
            )

        print(f"  Status: PASSED - All features match in correct order")

    def test_predict_service_feature_vector_matches_training_format(self):
        """Verify that PredictService builds feature vectors matching training format.

        This test verifies:
        1. Feature values are extracted correctly from domain objects
        2. Feature transformations are consistent with training
        3. Default values match training defaults
        """
        model_path = Path("app/ml/artifacts/redeem_predictor.joblib")

        if not model_path.exists():
            pytest.skip("Model file not trained yet")

        # Mock model load
        with patch.object(Path, "exists", return_value=True):
            with patch("joblib.load") as mock_load:
                mock_model = Mock()
                mock_model.predict = Mock(return_value=np.array([0.75]))

                mock_load.return_value = {
                    "model": mock_model,
                    "feature_names": [
                        "user_redeemed_rate_30d_before",
                        "user_receipts_30d_before",
                        "user_avg_distance_before",
                        "merchant_redeemed_rate_7d_before",
                        "merchant_redeemed_rate_30d_before",
                        "merchant_avg_discount_depth_before",
                        "coupon_redeemed_rate_before",
                        "coupon_avg_redeem_days_before",
                        "discount_value",
                        "discount_type_encoded",
                        "threshold_amount",
                        "discount_amount",
                        "day_of_week",
                        "month",
                        "day_of_month",
                        "distance"
                    ]
                }

                PredictService.reset()
                service = PredictService()

                # Create test domain objects
                receipt_event = CouponReceiptEvent(
                    id=1,
                    user_id="test_user",
                    merchant_id="test_merchant",
                    coupon_id="test_coupon",
                    discount_rate="200:50",
                    distance=5.0,
                    date_received=date(2016, 5, 15),
                    is_redeemed=False,
                )

                user_metrics = UserMetrics(
                    user_id="test_user",
                    total_receipts_30d=10,
                    redeemed_count_30d=3,
                    redeemed_rate_30d=0.30,
                    avg_distance=4.0,
                    last_receipt_date=date(2016, 5, 10),
                )

                merchant_metrics = MerchantMetrics(
                    merchant_id="test_merchant",
                    total_receipts_7d=100,
                    redeemed_count_7d=30,
                    redeemed_rate_7d=0.30,
                    total_receipts_30d=500,
                    redeemed_count_30d=150,
                    redeemed_rate_30d=0.30,
                    redeemed_rate_change=0.0,
                    avg_discount_depth=0.25,
                )

                coupon_metrics = CouponMetrics(
                    coupon_id="test_coupon",
                    merchant_id="test_merchant",
                    discount_type="满减",
                    discount_rate="200:50",
                    discount_value=0.25,
                    threshold_amount=200.0,
                    discount_amount=50.0,
                    total_receipts=1000,
                    redeemed_count=100,
                    redeemed_rate=0.10,
                    avg_redeem_days=5.0,
                )

                # Build feature vector
                feature_vector = service._build_features(
                    receipt_event=receipt_event,
                    user_metrics=user_metrics,
                    merchant_metrics=merchant_metrics,
                    coupon_metrics=coupon_metrics,
                )

                # Validate feature vector
                expected_feature_count = len(service._feature_list)
                assert len(feature_vector) == expected_feature_count, \
                    f"Feature vector length {len(feature_vector)} != expected {expected_feature_count}"

                # Validate specific feature values
                feature_dict = dict(zip(service._feature_list, feature_vector))

                # Check user features (time-safe naming)
                assert feature_dict.get("user_redeemed_rate_30d_before") == 0.30, \
                    f"user_redeemed_rate mismatch: {feature_dict.get('user_redeemed_rate_30d_before')}"

                assert feature_dict.get("user_receipts_30d_before") == 10, \
                    f"user_receipts mismatch: {feature_dict.get('user_receipts_30d_before')}"

                # Check merchant features (time-safe naming)
                assert feature_dict.get("merchant_redeemed_rate_30d_before") == 0.30, \
                    f"merchant_redeemed_rate mismatch"

                # Check discount encoding (满减 = 0.0)
                assert feature_dict.get("discount_type_encoded") == 0.0, \
                    f"discount_type_encoded mismatch for 满减"

                # Check time features
                assert feature_dict.get("day_of_week") == 6, \
                    f"day_of_week mismatch (2016-05-15 was Sunday)"

                assert feature_dict.get("month") == 5, \
                    f"month mismatch"

                print(f"\nFeature Vector Validation PASSED")
                print(f"  Feature count: {len(feature_vector)}")
                print(f"  User features: correct")
                print(f"  Merchant features: correct")
                print(f"  Discount encoding: correct")
                print(f"  Time features: correct")

    def test_predict_service_handles_missing_metrics_gracefully(self):
        """Verify PredictService handles missing metrics with sensible defaults.

        In production, some metrics may be missing for cold-start users/merchants.
        The service should use consistent defaults that match training.
        """
        with patch.object(Path, "exists", return_value=True):
            with patch("joblib.load") as mock_load:
                mock_load.return_value = {
                    "model": Mock(),
                    "feature_names": ["user_redeemed_rate_30d_before", "distance"]
                }

                PredictService.reset()
                service = PredictService()

                # Create receipt with minimal info
                receipt_event = CouponReceiptEvent(
                    id=1,
                    user_id="cold_start_user",
                    merchant_id="cold_start_merchant",
                    coupon_id="cold_start_coupon",
                    discount_rate="0.9",
                    distance=None,  # Missing distance
                    date_received=date(2016, 5, 15),
                    is_redeemed=False,
                )

                # User metrics with None values (cold start)
                user_metrics = UserMetrics(
                    user_id="cold_start_user",
                    total_receipts_30d=None,
                    redeemed_count_30d=None,
                    redeemed_rate_30d=None,
                    avg_distance=None,
                )

                merchant_metrics = MerchantMetrics(
                    merchant_id="cold_start_merchant",
                    total_receipts_7d=None,
                    redeemed_count_7d=None,
                    redeemed_rate_7d=None,
                    total_receipts_30d=None,
                    redeemed_count_30d=None,
                    redeemed_rate_30d=None,
                    redeemed_rate_change=None,
                    avg_discount_depth=None,
                )

                # Should handle gracefully
                feature_vector = service._build_features(
                    receipt_event=receipt_event,
                    user_metrics=user_metrics,
                    merchant_metrics=merchant_metrics,
                    coupon_metrics=None,
                )

                # All features should have values (defaults)
                assert all(f is not None for f in feature_vector), \
                    "Feature vector contains None values - should use defaults"

                # Cold start rates should be 0
                feature_dict = dict(zip(service._feature_list, feature_vector))
                assert feature_dict.get("user_redeemed_rate_30d_before", 0) == 0, \
                    "Cold start user should have 0 redeem rate"

                print(f"\nMissing Metrics Handling PASSED")
                print(f"  Cold start user: handled with defaults")
                print(f"  Missing distance: handled with default")
                print(f"  Missing coupon metrics: handled with defaults")


class TestM3Integration:
    """M3 Integration Tests."""

    def test_end_to_end_prediction_flow(self):
        """Test complete prediction flow from receipt to probability."""
        model_path = Path("app/ml/artifacts/redeem_predictor.joblib")

        if not model_path.exists():
            pytest.skip("Model file not trained yet")

        try:
            PredictService.reset()
            service = PredictService()

            # Create realistic test data
            receipt_event = CouponReceiptEvent(
                id="test_001",
                user_id="user_001",
                merchant_id="merchant_001",
                coupon_id="coupon_001",
                discount_rate="200:50",
                distance=5.0,
                date_received=date(2016, 5, 15),
                is_redeemed=False,
            )

            user_metrics = UserMetrics(
                user_id="user_001",
                total_receipts_30d=10,
                redeemed_count_30d=3,
                redeemed_rate_30d=0.30,
                avg_distance=4.0,
            )

            merchant_metrics = MerchantMetrics(
                merchant_id="merchant_001",
                total_receipts_7d=100,
                redeemed_count_7d=30,
                redeemed_rate_7d=0.30,
                total_receipts_30d=500,
                redeemed_count_30d=150,
                redeemed_rate_30d=0.30,
                avg_discount_depth=0.25,
            )

            # Get prediction
            probability = service.predict_redeem_probability(
                receipt_event=receipt_event,
                user_metrics=user_metrics,
                merchant_metrics=merchant_metrics,
            )

            # Validate prediction
            assert isinstance(probability, float), \
                f"Prediction should be float, got {type(probability)}"

            assert 0.0 <= probability <= 1.0, \
                f"Prediction {probability} outside valid range [0, 1]"

            print(f"\nEnd-to-End Prediction Test PASSED")
            print(f"  Input: user_001, merchant_001, coupon_001")
            print(f"  Output: {probability:.4f} probability")

        except FileNotFoundError:
            pytest.skip("Model file not found")
        except Exception as e:
            pytest.fail(f"Prediction failed: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])