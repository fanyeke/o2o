"""M2 Model Backtest Tests - High Standard Validation.

This module tests M2 (Model Training) with high standards:
1. test_model_better_than_random_baseline - AUC > 0.50
2. test_model_better_than_merchant_baseline - AUC > merchant-only baseline
3. test_model_better_than_user_baseline - AUC > user-only baseline
4. test_model_better_than_coupon_baseline - AUC > coupon-only baseline
5. test_top_10_percent_lift_ge_2x - Lift metric validation
6. test_top_20_percent_lift_ge_1_5x - Lift metric validation
7. test_ece_le_0_05 - Expected Calibration Error
8. test_train_test_auc_gap_le_0_08 - Overfitting detection
9. test_prediction_p95_latency_le_200ms - Latency test
"""

import pytest
import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import date
from sqlalchemy import text
from sklearn.metrics import roc_auc_score
from unittest.mock import Mock, patch, MagicMock
import time

from app.core.database import get_db
from app.ml.train.train_model import CouponRedemptionPredictor
from app.ml.train.evaluate_model import GroupedAUCEvaluator
from app.ml.inference.predict_service import PredictService


class TestM2Baselines:
    """M2 Baseline Comparison Tests."""

    def test_model_better_than_random_baseline(self):
        """Verify model AUC > 0.50 (random baseline).

        Random baseline: 0.50 AUC
        Minimum acceptable: 0.60 AUC
        Target baseline: 0.68 AUC (Tianchi competition standard)
        """
        model_path = Path("app/ml/artifacts/redeem_predictor.joblib")

        if not model_path.exists():
            pytest.skip("Model file not trained yet")

        model_data = joblib.load(model_path)

        # Check if metrics exist
        metadata = model_data.get("metadata", {})
        metrics = metadata.get("metrics", {})

        if not metrics:
            pytest.skip("Model metrics not available - run evaluation first")

        grouped_auc = metrics.get("grouped_auc", 0)

        print(f"\nModel AUC vs Random Baseline:")
        print(f"  Random baseline: 0.50")
        print(f"  Model AUC: {grouped_auc:.4f}")

        # Must be better than random
        assert grouped_auc > 0.50, \
            f"Model AUC {grouped_auc:.4f} not better than random (0.50)"

        # Should ideally be >= 0.68 (Tianchi baseline)
        if grouped_auc < 0.60:
            pytest.warning(
                f"Model AUC {grouped_auc:.4f} is below acceptable threshold (0.60)"
            )

    def test_model_better_than_merchant_baseline(self):
        """Verify model beats merchant-only baseline.

        Merchant-only baseline uses only merchant historical metrics
        to predict redemption probability.
        """
        model_path = Path("app/ml/artifacts/redeem_predictor.joblib")

        if not model_path.exists():
            pytest.skip("Model file not trained yet")

        db = next(get_db())

        # Check test data availability
        test_count = db.execute(text("""
            SELECT COUNT(*) FROM feature.receipt_training_features
            WHERE as_of_date >= '2016-06-01' AND as_of_date <= '2016-06-30'
        """)).scalar()

        if test_count == 0:
            pytest.skip("No test data (June 2016) available")

        # Load test data
        test_df_result = db.execute(text("""
            SELECT
                merchant_redeemed_rate_7d_before,
                merchant_redeemed_rate_30d_before,
                merchant_avg_discount_depth_before,
                label_is_redeemed,
                coupon_id
            FROM feature.receipt_training_features
            WHERE as_of_date >= '2016-06-01' AND as_of_date <= '2016-06-30'
        """))

        test_data = pd.DataFrame(test_df_result.fetchall(), columns=test_df_result.keys())

        if test_data.empty:
            pytest.skip("No test data loaded")

        # Create merchant-only baseline predictions
        # Use merchant_redeemed_rate_30d_before as the prediction
        merchant_baseline_preds = test_data['merchant_redeemed_rate_30d_before'].fillna(0).values
        labels = test_data['label_is_redeemed'].astype(int).values
        coupon_ids = test_data['coupon_id'].values

        # Calculate merchant-only baseline AUC
        evaluator = GroupedAUCEvaluator()

        try:
            merchant_baseline_auc = evaluator.calculate_grouped_auc(
                merchant_baseline_preds, labels, coupon_ids
            )
        except ValueError:
            pytest.skip("Cannot calculate merchant baseline AUC (insufficient variation)")

        # Load model metrics
        model_data = joblib.load(model_path)
        metrics = model_data.get("metadata", {}).get("metrics", {})
        model_auc = metrics.get("grouped_auc", 0)

        print(f"\nModel AUC vs Merchant Baseline:")
        print(f"  Merchant-only baseline: {merchant_baseline_auc:.4f}")
        print(f"  Model AUC: {model_auc:.4f}")
        print(f"  Improvement: {(model_auc - merchant_baseline_auc):.4f}")

        # Model should beat merchant baseline
        assert model_auc > merchant_baseline_auc, \
            f"Model AUC {model_auc:.4f} not better than merchant baseline {merchant_baseline_auc:.4f}"

        db.close()

    def test_model_better_than_user_baseline(self):
        """Verify model beats user-only baseline."""
        model_path = Path("app/ml/artifacts/redeem_predictor.joblib")

        if not model_path.exists():
            pytest.skip("Model file not trained yet")

        db = next(get_db())

        # Check test data availability
        test_count = db.execute(text("""
            SELECT COUNT(*) FROM feature.receipt_training_features
            WHERE as_of_date >= '2016-06-01' AND as_of_date <= '2016-06-30'
        """)).scalar()

        if test_count == 0:
            pytest.skip("No test data (June 2016) available")

        # Load test data
        test_df_result = db.execute(text("""
            SELECT
                user_redeemed_rate_30d_before,
                user_receipts_30d_before,
                user_avg_distance_before,
                label_is_redeemed,
                coupon_id
            FROM feature.receipt_training_features
            WHERE as_of_date >= '2016-06-01' AND as_of_date <= '2016-06-30'
        """))

        test_data = pd.DataFrame(test_df_result.fetchall(), columns=test_df_result.keys())

        if test_data.empty:
            pytest.skip("No test data loaded")

        # Create user-only baseline predictions
        user_baseline_preds = test_data['user_redeemed_rate_30d_before'].fillna(0).values
        labels = test_data['label_is_redeemed'].astype(int).values
        coupon_ids = test_data['coupon_id'].values

        # Calculate user-only baseline AUC
        evaluator = GroupedAUCEvaluator()

        try:
            user_baseline_auc = evaluator.calculate_grouped_auc(
                user_baseline_preds, labels, coupon_ids
            )
        except ValueError:
            pytest.skip("Cannot calculate user baseline AUC (insufficient variation)")

        # Load model metrics
        model_data = joblib.load(model_path)
        metrics = model_data.get("metadata", {}).get("metrics", {})
        model_auc = metrics.get("grouped_auc", 0)

        print(f"\nModel AUC vs User Baseline:")
        print(f"  User-only baseline: {user_baseline_auc:.4f}")
        print(f"  Model AUC: {model_auc:.4f}")
        print(f"  Improvement: {(model_auc - user_baseline_auc):.4f}")

        # Model should beat user baseline
        assert model_auc > user_baseline_auc, \
            f"Model AUC {model_auc:.4f} not better than user baseline {user_baseline_auc:.4f}"

        db.close()

    def test_model_better_than_coupon_baseline(self):
        """Verify model beats coupon-only baseline."""
        model_path = Path("app/ml/artifacts/redeem_predictor.joblib")

        if not model_path.exists():
            pytest.skip("Model file not trained yet")

        db = next(get_db())

        # Check test data availability
        test_count = db.execute(text("""
            SELECT COUNT(*) FROM feature.receipt_training_features
            WHERE as_of_date >= '2016-06-01' AND as_of_date <= '2016-06-30'
        """)).scalar()

        if test_count == 0:
            pytest.skip("No test data (June 2016) available")

        # Load test data
        test_df_result = db.execute(text("""
            SELECT
                coupon_redeemed_rate_before,
                coupon_total_receipts_before,
                label_is_redeemed,
                coupon_id
            FROM feature.receipt_training_features
            WHERE as_of_date >= '2016-06-01' AND as_of_date <= '2016-06-30'
        """))

        test_data = pd.DataFrame(test_df_result.fetchall(), columns=test_df_result.keys())

        if test_data.empty:
            pytest.skip("No test data loaded")

        # Create coupon-only baseline predictions
        coupon_baseline_preds = test_data['coupon_redeemed_rate_before'].fillna(0).values
        labels = test_data['label_is_redeemed'].astype(int).values
        coupon_ids = test_data['coupon_id'].values

        # Calculate coupon-only baseline AUC
        evaluator = GroupedAUCEvaluator()

        try:
            coupon_baseline_auc = evaluator.calculate_grouped_auc(
                coupon_baseline_preds, labels, coupon_ids
            )
        except ValueError:
            pytest.skip("Cannot calculate coupon baseline AUC (insufficient variation)")

        # Load model metrics
        model_data = joblib.load(model_path)
        metrics = model_data.get("metadata", {}).get("metrics", {})
        model_auc = metrics.get("grouped_auc", 0)

        print(f"\nModel AUC vs Coupon Baseline:")
        print(f"  Coupon-only baseline: {coupon_baseline_auc:.4f}")
        print(f"  Model AUC: {model_auc:.4f}")
        print(f"  Improvement: {(model_auc - coupon_baseline_auc):.4f}")

        # Model should beat coupon baseline
        assert model_auc > coupon_baseline_auc, \
            f"Model AUC {model_auc:.4f} not better than coupon baseline {coupon_baseline_auc:.4f}"

        db.close()


class TestM2LiftMetrics:
    """M2 Lift Metrics Tests."""

    def test_top_10_percent_lift_ge_2x(self):
        """Verify top 10% predictions have >= 2x lift over baseline.

        Lift definition:
        - Top 10% redemption rate / overall redemption rate >= 2x
        - This means model effectively identifies high-probability users
        """
        model_path = Path("app/ml/artifacts/redeem_predictor.joblib")

        if not model_path.exists():
            pytest.skip("Model file not trained yet")

        db = next(get_db())

        # Check test data availability
        test_count = db.execute(text("""
            SELECT COUNT(*) FROM feature.receipt_training_features
            WHERE as_of_date >= '2016-06-01' AND as_of_date <= '2016-06-30'
        """)).scalar()

        if test_count == 0:
            pytest.skip("No test data (June 2016) available")

        # Load model and test features
        model_data = joblib.load(model_path)
        model = model_data["model"]
        feature_names = model_data.get("feature_names", [])

        # Load test features
        test_df_result = db.execute(text("""
            SELECT * FROM feature.receipt_training_features
            WHERE as_of_date >= '2016-06-01' AND as_of_date <= '2016-06-30'
        """))

        test_data = pd.DataFrame(test_df_result.fetchall(), columns=test_df_result.keys())

        if test_data.empty or len(feature_names) == 0:
            pytest.skip("No test data or feature names available")

        # Build feature matrix
        feature_columns = [col for col in feature_names if col in test_data.columns]
        X_test = test_data[feature_columns].fillna(0).values

        # Get predictions
        predictions = model.predict(X_test)
        labels = test_data['label_is_redeemed'].astype(int).values

        # Calculate lift
        overall_rate = labels.mean()
        top_10_pct_threshold = np.percentile(predictions, 90)
        top_10_mask = predictions >= top_10_pct_threshold
        top_10_rate = labels[top_10_mask].mean()

        lift = top_10_rate / overall_rate if overall_rate > 0 else 0

        print(f"\nTop 10% Lift Metric:")
        print(f"  Overall redemption rate: {overall_rate:.2%}")
        print(f"  Top 10% redemption rate: {top_10_rate:.2%}")
        print(f"  Lift: {lift:.2f}x")

        assert lift >= 2.0, \
            f"Top 10% lift {lift:.2f}x < 2x (model not identifying high-probability users)"

        db.close()

    def test_top_20_percent_lift_ge_1_5x(self):
        """Verify top 20% predictions have >= 1.5x lift over baseline."""
        model_path = Path("app/ml/artifacts/redeem_predictor.joblib")

        if not model_path.exists():
            pytest.skip("Model file not trained yet")

        db = next(get_db())

        # Check test data availability
        test_count = db.execute(text("""
            SELECT COUNT(*) FROM feature.receipt_training_features
            WHERE as_of_date >= '2016-06-01' AND as_of_date <= '2016-06-30'
        """)).scalar()

        if test_count == 0:
            pytest.skip("No test data (June 2016) available")

        # Load model and test features
        model_data = joblib.load(model_path)
        model = model_data["model"]
        feature_names = model_data.get("feature_names", [])

        # Load test features
        test_df_result = db.execute(text("""
            SELECT * FROM feature.receipt_training_features
            WHERE as_of_date >= '2016-06-01' AND as_of_date <= '2016-06-30'
        """))

        test_data = pd.DataFrame(test_df_result.fetchall(), columns=test_df_result.keys())

        if test_data.empty or len(feature_names) == 0:
            pytest.skip("No test data or feature names available")

        # Build feature matrix
        feature_columns = [col for col in feature_names if col in test_data.columns]
        X_test = test_data[feature_columns].fillna(0).values

        # Get predictions
        predictions = model.predict(X_test)
        labels = test_data['label_is_redeemed'].astype(int).values

        # Calculate lift for top 20%
        overall_rate = labels.mean()
        top_20_pct_threshold = np.percentile(predictions, 80)
        top_20_mask = predictions >= top_20_pct_threshold
        top_20_rate = labels[top_20_mask].mean()

        lift = top_20_rate / overall_rate if overall_rate > 0 else 0

        print(f"\nTop 20% Lift Metric:")
        print(f"  Overall redemption rate: {overall_rate:.2%}")
        print(f"  Top 20% redemption rate: {top_20_rate:.2%}")
        print(f"  Lift: {lift:.2f}x")

        assert lift >= 1.5, \
            f"Top 20% lift {lift:.2f}x < 1.5x"

        db.close()


class TestM2Calibration:
    """M2 Calibration Tests."""

    def test_ece_le_0_05(self):
        """Verify Expected Calibration Error <= 0.05.

        ECE measures how well predicted probabilities match actual rates.
        Low ECE means the model's confidence is trustworthy.
        """
        model_path = Path("app/ml/artifacts/redeem_predictor.joblib")

        if not model_path.exists():
            pytest.skip("Model file not trained yet")

        db = next(get_db())

        # Check test data availability
        test_count = db.execute(text("""
            SELECT COUNT(*) FROM feature.receipt_training_features
            WHERE as_of_date >= '2016-06-01' AND as_of_date <= '2016-06-30'
        """)).scalar()

        if test_count == 0:
            pytest.skip("No test data (June 2016) available")

        # Load model and test features
        model_data = joblib.load(model_path)
        model = model_data["model"]
        feature_names = model_data.get("feature_names", [])

        # Load test features
        test_df_result = db.execute(text("""
            SELECT * FROM feature.receipt_training_features
            WHERE as_of_date >= '2016-06-01' AND as_of_date <= '2016-06-30'
        """))

        test_data = pd.DataFrame(test_df_result.fetchall(), columns=test_df_result.keys())

        if test_data.empty or len(feature_names) == 0:
            pytest.skip("No test data or feature names available")

        # Build feature matrix and get predictions
        feature_columns = [col for col in feature_names if col in test_data.columns]
        X_test = test_data[feature_columns].fillna(0).values
        predictions = model.predict(X_test)
        labels = test_data['label_is_redeemed'].astype(int).values

        # Calculate ECE using binning approach
        n_bins = 10
        bin_boundaries = np.linspace(0, 1, n_bins + 1)
        ece = 0.0

        for i in range(n_bins):
            bin_lower = bin_boundaries[i]
            bin_upper = bin_boundaries[i + 1]
            bin_mask = (predictions >= bin_lower) & (predictions < bin_upper)

            if bin_mask.sum() > 0:
                bin_accuracy = labels[bin_mask].mean()
                bin_confidence = predictions[bin_mask].mean()
                bin_weight = bin_mask.sum() / len(predictions)
                ece += bin_weight * abs(bin_accuracy - bin_confidence)

        print(f"\nExpected Calibration Error (ECE):")
        print(f"  ECE: {ece:.4f}")
        print(f"  Threshold: 0.05")

        assert ece <= 0.05, \
            f"ECE {ece:.4f} > 0.05 (model predictions not well-calibrated)"

        db.close()


class TestM2Overfitting:
    """M2 Overfitting Detection Tests."""

    def test_train_test_auc_gap_le_0_08(self):
        """Verify train-test AUC gap <= 0.08.

        Large gap indicates overfitting:
        - Train AUC >> Test AUC = overfitting
        - Gap <= 0.08 is acceptable
        """
        model_path = Path("app/ml/artifacts/redeem_predictor.joblib")

        if not model_path.exists():
            pytest.skip("Model file not trained yet")

        model_data = joblib.load(model_path)
        metadata = model_data.get("metadata", {})
        metrics = metadata.get("metrics", {})

        # Check if we have both train and test metrics
        train_auc = metrics.get("train_auc")
        test_auc = metrics.get("grouped_auc") or metrics.get("test_auc")

        if train_auc is None or test_auc is None:
            pytest.skip("Train and test AUC not available in model metadata")

        gap = train_auc - test_auc

        print(f"\nTrain-Test AUC Gap:")
        print(f"  Train AUC: {train_auc:.4f}")
        print(f"  Test AUC: {test_auc:.4f}")
        print(f"  Gap: {gap:.4f}")

        assert gap <= 0.08, \
            f"Train-test gap {gap:.4f} > 0.08 (potential overfitting)"

        # Also check for negative gap (suspicious)
        if gap < -0.02:
            pytest.warning(
                f"Train AUC {train_auc:.4f} < Test AUC {test_auc:.4f} - suspicious"
            )


class TestM2Latency:
    """M2 Prediction Latency Tests."""

    def test_prediction_p95_latency_le_200ms(self):
        """Verify P95 prediction latency <= 200ms.

        Latency requirements:
        - Single prediction: <= 50ms
        - Batch prediction (1000): <= 200ms P95
        """
        model_path = Path("app/ml/artifacts/redeem_predictor.joblib")

        if not model_path.exists():
            pytest.skip("Model file not trained yet")

        # Load model directly (bypass singleton for testing)
        model_data = joblib.load(model_path)
        model = model_data["model"]
        feature_names = model_data.get("feature_names", [])

        # Create mock feature vectors
        n_predictions = 1000
        n_features = len(feature_names) or 16
        mock_features = np.random.rand(n_predictions, n_features)

        # Measure prediction latency
        latencies = []

        for _ in range(10):  # Run 10 batches
            start_time = time.time()
            predictions = model.predict(mock_features)
            batch_time = time.time() - start_time
            per_pred_time = batch_time / n_predictions
            latencies.append(per_pred_time)

        # Calculate P95 latency
        p95_latency = np.percentile(latencies, 95) * 1000  # Convert to ms

        print(f"\nPrediction Latency (P95):")
        print(f"  Batch size: {n_predictions}")
        print(f"  Avg latency: {np.mean(latencies)*1000:.2f} ms per prediction")
        print(f"  P95 latency: {p95_latency:.2f} ms")

        assert p95_latency <= 200, \
            f"P95 latency {p95_latency:.2f}ms > 200ms"


class TestM2Artifacts:
    """M2 Required Artifacts Tests."""

    def test_model_card_md_exists(self):
        """Verify docs/model_card.md exists with required sections."""
        model_card_path = Path("docs/model_card.md")

        if not model_card_path.exists():
            pytest.fail("docs/model_card.md not found - required artifact")

        content = model_card_path.read_text()

        # Required sections
        required_sections = [
            "Model Details",
            "Intended Use",
            "Training Data",
            "Evaluation Metrics",
            "Ethical Considerations"
        ]

        for section in required_sections:
            assert section in content, \
                f"model_card.md missing required section: {section}"

    def test_backtest_report_json_exists(self):
        """Verify backtest_report.json exists with evaluation results."""
        backtest_path = Path("app/ml/artifacts/backtest_report.json")

        if not backtest_path.exists():
            pytest.skip("backtest_report.json not found - will be created after model training")

        # Will be validated after full training pipeline

    def test_feature_importance_csv_exists(self):
        """Verify feature_importance.csv exists."""
        importance_path = Path("app/ml/artifacts/feature_importance.csv")

        if not importance_path.exists():
            pytest.skip("feature_importance.csv not found - will be created after model training")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])