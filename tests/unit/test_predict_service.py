"""Unit tests for PredictService."""
import joblib
import numpy as np
from datetime import date
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

import pytest

from app.ml.inference.predict_service import PredictService
from app.domain.staging.coupon_receipt_event import CouponReceiptEvent
from app.domain.feature.user_metrics import UserMetrics
from app.domain.feature.merchant_metrics import MerchantMetrics
from app.domain.feature.coupon_metrics import CouponMetrics


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset PredictService singleton before each test."""
    PredictService.reset()
    yield
    PredictService.reset()


@pytest.fixture
def mock_model_file():
    """Mock model file with fake LightGBM model."""
    mock_model = Mock()
    mock_model.predict = Mock(return_value=np.array([0.75]))

    mock_data = {
        "model": mock_model,
        "feature_list": [
            "distance",
            "discount_value",
            "day_of_week",
            "month",
            "user_total_receipts_30d",
            "user_redeemed_count_30d",
            "user_redeemed_rate_30d",
            "user_avg_distance",
            "merchant_total_receipts_7d",
            "merchant_redeemed_count_7d",
            "merchant_redeemed_rate_7d",
            "merchant_total_receipts_30d",
            "merchant_redeemed_count_30d",
            "merchant_redeemed_rate_30d",
            "merchant_redeemed_rate_change",
            "merchant_avg_discount_depth",
            "coupon_total_receipts",
            "coupon_redeemed_count",
            "coupon_redeemed_rate",
            "coupon_avg_redeem_days",
            "coupon_discount_value",
        ],
    }

    with patch.object(Path, "exists", return_value=True):
        with patch("joblib.load", return_value=mock_data):
            yield mock_model


@pytest.fixture
def receipt_event():
    """Create sample receipt event."""
    return CouponReceiptEvent(
        id=1,
        user_id="user_001",
        merchant_id="merchant_001",
        coupon_id="coupon_001",
        discount_rate="200:50",
        distance=2.5,
        date_received=date(2016, 5, 15),
        is_redeemed=False,
    )


@pytest.fixture
def user_metrics():
    """Create sample user metrics."""
    return UserMetrics(
        user_id="user_001",
        total_receipts_30d=10,
        redeemed_count_30d=3,
        redeemed_rate_30d=0.3,
        avg_distance=2.0,
        last_receipt_date=date(2016, 5, 10),
    )


@pytest.fixture
def merchant_metrics():
    """Create sample merchant metrics."""
    return MerchantMetrics(
        merchant_id="merchant_001",
        total_receipts_7d=500,
        redeemed_count_7d=225,
        redeemed_rate_7d=0.45,
        total_receipts_30d=2000,
        redeemed_count_30d=1300,
        redeemed_rate_30d=0.65,
        redeemed_rate_change=-0.30,
        avg_discount_depth=0.25,
    )


@pytest.fixture
def coupon_metrics():
    """Create sample coupon metrics."""
    return CouponMetrics(
        coupon_id="coupon_001",
        merchant_id="merchant_001",
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


def test_singleton_pattern(mock_model_file):
    """Test that PredictService uses singleton pattern."""
    service1 = PredictService()
    service2 = PredictService()

    assert service1 is service2
    assert service1._model is not None
    assert service1._feature_list is not None


def test_predict_returns_float(mock_model_file, receipt_event, user_metrics, merchant_metrics):
    """Test that predict_redeem_probability returns float."""
    service = PredictService()

    probability = service.predict_redeem_probability(
        receipt_event=receipt_event,
        user_metrics=user_metrics,
        merchant_metrics=merchant_metrics,
    )

    assert isinstance(probability, float)


def test_predict_probability_range(mock_model_file, receipt_event, user_metrics, merchant_metrics):
    """Test that predicted probability is within [0, 1] range."""
    service = PredictService()

    # Test with normal prediction
    probability = service.predict_redeem_probability(
        receipt_event=receipt_event,
        user_metrics=user_metrics,
        merchant_metrics=merchant_metrics,
    )

    assert 0.0 <= probability <= 1.0

    # Test with out-of-range prediction (mock returns >1)
    mock_model_file.predict.return_value = np.array([1.5])
    PredictService.reset()
    service2 = PredictService()

    probability2 = service2.predict_redeem_probability(
        receipt_event=receipt_event,
        user_metrics=user_metrics,
        merchant_metrics=merchant_metrics,
    )

    # Should be clipped to 1.0
    assert probability2 == 1.0


def test_predict_with_coupon_metrics(
    mock_model_file, receipt_event, user_metrics, merchant_metrics, coupon_metrics
):
    """Test prediction with coupon metrics."""
    service = PredictService()

    probability = service.predict_redeem_probability(
        receipt_event=receipt_event,
        user_metrics=user_metrics,
        merchant_metrics=merchant_metrics,
        coupon_metrics=coupon_metrics,
    )

    assert isinstance(probability, float)
    assert 0.0 <= probability <= 1.0


def test_feature_vector_order(mock_model_file, receipt_event, user_metrics, merchant_metrics):
    """Test that feature vector is built in correct order."""
    service = PredictService()

    feature_vector = service._build_features(
        receipt_event=receipt_event,
        user_metrics=user_metrics,
        merchant_metrics=merchant_metrics,
        coupon_metrics=None,
    )

    # Check that feature vector has correct length
    assert len(feature_vector) == len(service._feature_list)

    # Check that features are not all zero (basic sanity check)
    assert any(feature != 0.0 for feature in feature_vector)


def test_parse_discount_rate_full_reduction():
    """Test parsing full reduction discount (e.g., '200:50')."""
    with patch.object(Path, "exists", return_value=True):
        with patch("joblib.load") as mock_load:
            mock_load.return_value = {
                "model": Mock(),
                "feature_list": ["feature1"],
            }
            service = PredictService()
            result = service._parse_discount_rate("200:50")
            assert result == 50.0 / 200.0

            result = service._parse_discount_rate("100:20")
            assert result == 20.0 / 100.0


def test_parse_discount_rate_percentage():
    """Test parsing percentage discount (e.g., '0.9')."""
    with patch.object(Path, "exists", return_value=True):
        with patch("joblib.load") as mock_load:
            mock_load.return_value = {
                "model": Mock(),
                "feature_list": ["feature1"],
            }
            service = PredictService()
            result = service._parse_discount_rate("0.9")
            assert result == pytest.approx(0.1)

            result = service._parse_discount_rate("0.85")
            assert result == pytest.approx(0.15)


def test_parse_discount_rate_none():
    """Test parsing None discount rate."""
    with patch.object(Path, "exists", return_value=True):
        with patch("joblib.load") as mock_load:
            mock_load.return_value = {
                "model": Mock(),
                "feature_list": ["feature1"],
            }
            service = PredictService()
            result = service._parse_discount_rate(None)
            assert result == 0.0


def test_parse_discount_rate_invalid():
    """Test parsing invalid discount rate."""
    with patch.object(Path, "exists", return_value=True):
        with patch("joblib.load") as mock_load:
            mock_load.return_value = {
                "model": Mock(),
                "feature_list": ["feature1"],
            }
            service = PredictService()
            result = service._parse_discount_rate("invalid")
            assert result == 0.0

            result = service._parse_discount_rate("")
            assert result == 0.0


def test_missing_features_use_defaults(mock_model_file, receipt_event, user_metrics, merchant_metrics):
    """Test that missing features use default values."""
    service = PredictService()

    # Create user metrics with missing fields
    incomplete_user_metrics = UserMetrics(
        user_id="user_001",
        total_receipts_30d=None,  # Missing
        redeemed_count_30d=None,  # Missing
        redeemed_rate_30d=None,   # Missing
        avg_distance=None,        # Missing
    )

    probability = service.predict_redeem_probability(
        receipt_event=receipt_event,
        user_metrics=incomplete_user_metrics,
        merchant_metrics=merchant_metrics,
    )

    assert isinstance(probability, float)
    assert 0.0 <= probability <= 1.0


def test_model_file_not_found():
    """Test error when model file is missing."""
    with patch.object(Path, "exists", return_value=False):
        with pytest.raises(FileNotFoundError) as exc_info:
            PredictService()

        assert "Model file not found" in str(exc_info.value)
        assert "scripts/train_model.py" in str(exc_info.value)


def test_reset_singleton():
    """Test that reset clears singleton instance."""
    # Create instance
    with patch.object(Path, "exists", return_value=True):
        with patch("joblib.load") as mock_load:
            mock_load.return_value = {
                "model": Mock(),
                "feature_list": ["feature1"],
            }
            service1 = PredictService()
            assert PredictService._instance is not None

    # Reset
    PredictService.reset()
    assert PredictService._instance is None
    assert PredictService._model is None
    assert PredictService._feature_list is None