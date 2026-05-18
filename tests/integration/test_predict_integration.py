"""Integration tests to verify PredictService works with domain models."""
from datetime import date
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

import pytest
import numpy as np

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
def mock_model_with_features():
    """Mock model file with realistic feature list."""
    mock_model = Mock()
    mock_model.predict = Mock(return_value=np.array([0.75]))

    # Realistic feature list based on training
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


@pytest.mark.skip(reason="需要PostgreSQL数据库环境")
def test_predict_with_all_domain_models(mock_model_with_features):
    """Test PredictService with complete domain model data."""
    # Create realistic domain model instances
    receipt_event = CouponReceiptEvent(
        id=1,
        user_id="user_001",
        merchant_id="merchant_001",
        coupon_id="coupon_001",
        discount_rate="200:50",  # Full reduction
        distance=2.5,
        date_received=date(2016, 5, 15),  # Sunday (weekday=6)
        is_redeemed=False,
    )

    user_metrics = UserMetrics(
        user_id="user_001",
        total_receipts_30d=10,
        redeemed_count_30d=3,
        redeemed_rate_30d=0.3,
        avg_distance=2.0,
        last_receipt_date=date(2016, 5, 10),
    )

    merchant_metrics = MerchantMetrics(
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

    coupon_metrics = CouponMetrics(
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

    # Create PredictService instance
    service = PredictService()

    # Predict redemption probability
    probability = service.predict_redeem_probability(
        receipt_event=receipt_event,
        user_metrics=user_metrics,
        merchant_metrics=merchant_metrics,
        coupon_metrics=coupon_metrics,
    )

    # Verify result
    assert isinstance(probability, float)
    assert 0.0 <= probability <= 1.0
    assert probability == pytest.approx(0.75)


@pytest.mark.skip(reason="需要PostgreSQL数据库环境")
def test_feature_extraction_correctness(mock_model_with_features):
    """Test that features are extracted correctly from domain models."""
    receipt_event = CouponReceiptEvent(
        id=1,
        user_id="user_001",
        merchant_id="merchant_001",
        coupon_id="coupon_001",
        discount_rate="0.9",  # 10% off
        distance=5.0,
        date_received=date(2016, 5, 18),  # Wednesday (weekday=2)
        is_redeemed=False,
    )

    user_metrics = UserMetrics(
        user_id="user_001",
        total_receipts_30d=20,
        redeemed_count_30d=5,
        redeemed_rate_30d=0.25,
        avg_distance=3.5,
    )

    merchant_metrics = MerchantMetrics(
        merchant_id="merchant_001",
        total_receipts_7d=100,
        redeemed_count_7d=40,
        redeemed_rate_7d=0.40,
        total_receipts_30d=400,
        redeemed_count_30d=160,
        redeemed_rate_30d=0.40,
        redeemed_rate_change=0.0,
        avg_discount_depth=0.15,
    )

    service = PredictService()

    # Build feature vector
    feature_vector = service._build_features(
        receipt_event=receipt_event,
        user_metrics=user_metrics,
        merchant_metrics=merchant_metrics,
        coupon_metrics=None,
    )

    # Verify specific features
    assert feature_vector[0] == 5.0  # distance
    assert feature_vector[1] == pytest.approx(0.1)  # discount_value (1 - 0.9)
    assert feature_vector[2] == 2.0  # day_of_week (Wednesday)
    assert feature_vector[3] == 5.0  # month (May)
    assert feature_vector[4] == 20.0  # user_total_receipts_30d
    assert feature_vector[5] == 5.0  # user_redeemed_count_30d
    assert feature_vector[6] == pytest.approx(0.25)  # user_redeemed_rate_30d
    assert feature_vector[7] == 3.5  # user_avg_distance


@pytest.mark.skip(reason="需要PostgreSQL数据库环境")
def test_predict_with_partial_domain_data(mock_model_with_features):
    """Test prediction when some domain models have missing optional fields."""
    receipt_event = CouponReceiptEvent(
        id=1,
        user_id="user_002",
        merchant_id="merchant_002",
        coupon_id="coupon_002",
        discount_rate=None,  # Missing discount
        distance=None,  # Missing distance
        date_received=date(2016, 6, 1),
        is_redeemed=False,
    )

    # User with minimal data
    user_metrics = UserMetrics(
        user_id="user_002",
        total_receipts_30d=None,
        redeemed_count_30d=None,
        redeemed_rate_30d=None,
        avg_distance=None,
    )

    # Merchant with complete data
    merchant_metrics = MerchantMetrics(
        merchant_id="merchant_002",
        total_receipts_7d=200,
        redeemed_count_7d=80,
        redeemed_rate_7d=0.40,
        total_receipts_30d=800,
        redeemed_count_30d=320,
        redeemed_rate_30d=0.40,
        redeemed_rate_change=0.0,
        avg_discount_depth=0.20,
    )

    service = PredictService()

    # Should still work with missing optional data
    probability = service.predict_redeem_probability(
        receipt_event=receipt_event,
        user_metrics=user_metrics,
        merchant_metrics=merchant_metrics,
        coupon_metrics=None,
    )

    assert isinstance(probability, float)
    assert 0.0 <= probability <= 1.0


@pytest.mark.skip(reason="需要PostgreSQL数据库环境")
def test_orm_model_field_exists():
    """Verify that CouponReceiptEvent has predicted_probability field."""
    # Create a mock receipt event
    receipt_event = CouponReceiptEvent(
        id=1,
        user_id="test_user",
        merchant_id="test_merchant",
        coupon_id="test_coupon",
        date_received=date(2016, 1, 1),
    )

    # Verify field exists and can be set
    receipt_event.predicted_probability = 0.75
    assert receipt_event.predicted_probability == 0.75

    # Verify field can be None (nullable=True)
    receipt_event.predicted_probability = None
    assert receipt_event.predicted_probability is None