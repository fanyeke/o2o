import pytest
"""Integration tests for metrics API endpoints.

Task: T056
Phase: 3 - US2 Metrics Query API
"""

from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.domain.feature.merchant_metrics import MerchantMetrics
from app.domain.feature.user_metrics import UserMetrics
from app.domain.feature.coupon_metrics import CouponMetrics

client = TestClient(app)


class TestMerchantMetricsAPI:
    """Tests for GET /api/v1/metrics/merchants endpoint."""

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_get_merchant_metrics_success(self, db_session: Session):
        """Test successful retrieval of merchant metrics."""
        # Setup: Insert test data
        test_data = [
            MerchantMetrics(
                merchant_id="merchant_001",
                total_receipts_7d=500,
                redeemed_count_7d=225,
                redeemed_rate_7d=0.45,
                total_receipts_30d=2000,
                redeemed_count_30d=1300,
                redeemed_rate_30d=0.65,
                redeemed_rate_change=-0.30,
                avg_discount_depth=0.25,
                activity_health_score=0.72,
                last_activity_date=datetime(2016, 6, 15).date(),
                updated_at=datetime(2016, 6, 15, 0, 0, 0),
            ),
            MerchantMetrics(
                merchant_id="merchant_002",
                total_receipts_7d=300,
                redeemed_count_7d=150,
                redeemed_rate_7d=0.50,
                total_receipts_30d=1200,
                redeemed_count_30d=600,
                redeemed_rate_30d=0.50,
                redeemed_rate_change=0.0,
                avg_discount_depth=0.30,
                activity_health_score=0.80,
                last_activity_date=datetime(2016, 6, 14).date(),
                updated_at=datetime(2016, 6, 14, 0, 0, 0),
            ),
        ]
        db_session.add_all(test_data)
        db_session.commit()

        # Execute: Call the API
        response = client.get("/api/v1/metrics/merchants")

        # Verify: Check response
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert data["limit"] == 100
        assert data["offset"] == 0
        assert len(data["data"]) == 2

        # Verify first merchant
        merchant_1 = data["data"][0]
        assert merchant_1["merchant_id"] == "merchant_001"
        assert merchant_1["total_receipts_7d"] == 500
        assert merchant_1["redeemed_rate_7d"] == 0.45
        assert merchant_1["total_receipts_30d"] == 2000
        assert merchant_1["redeemed_rate_30d"] == 0.65
        assert merchant_1["redeemed_rate_change"] == -0.30
        assert merchant_1["avg_discount_depth"] == 0.25
        assert merchant_1["activity_health_score"] == 0.72

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_get_merchant_metrics_with_filter(self, db_session: Session):
        """Test merchant metrics filtering by merchant_id."""
        # Setup
        test_data = [
            MerchantMetrics(
                merchant_id="merchant_001",
                total_receipts_7d=100,
                redeemed_rate_7d=0.40,
                redeemed_rate_change=-0.10,
                avg_discount_depth=0.20,
                activity_health_score=0.70,
                updated_at=datetime(2016, 6, 15, 0, 0, 0),
            ),
            MerchantMetrics(
                merchant_id="merchant_002",
                total_receipts_7d=200,
                redeemed_rate_7d=0.50,
                redeemed_rate_change=0.05,
                avg_discount_depth=0.30,
                activity_health_score=0.80,
                updated_at=datetime(2016, 6, 15, 0, 0, 0),
            ),
        ]
        db_session.add_all(test_data)
        db_session.commit()

        # Execute: Filter by merchant_id
        response = client.get(
            "/api/v1/metrics/merchants", params={"merchant_id": "merchant_001"}
        )

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["data"][0]["merchant_id"] == "merchant_001"

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_get_merchant_metrics_with_sorting(self, db_session: Session):
        """Test merchant metrics sorting by redeemed_rate_change."""
        # Setup
        test_data = [
            MerchantMetrics(
                merchant_id="merchant_001",
                total_receipts_7d=100,
                redeemed_rate_7d=0.40,
                redeemed_rate_change=-0.20,
                avg_discount_depth=0.20,
                activity_health_score=0.70,
                updated_at=datetime(2016, 6, 15, 0, 0, 0),
            ),
            MerchantMetrics(
                merchant_id="merchant_002",
                total_receipts_7d=200,
                redeemed_rate_7d=0.50,
                redeemed_rate_change=-0.10,
                avg_discount_depth=0.30,
                activity_health_score=0.80,
                updated_at=datetime(2016, 6, 15, 0, 0, 0),
            ),
        ]
        db_session.add_all(test_data)
        db_session.commit()

        # Execute: Sort by redeemed_rate_change ascending
        response = client.get(
            "/api/v1/metrics/merchants",
            params={"sort_by": "redeemed_rate_change", "order": "asc"},
        )

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        # Most negative change should come first
        assert data["data"][0]["merchant_id"] == "merchant_001"
        assert data["data"][0]["redeemed_rate_change"] == -0.20

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_get_merchant_metrics_with_pagination(self, db_session: Session):
        """Test merchant metrics pagination."""
        # Setup: Insert 150 merchants
        test_data = []
        for i in range(150):
            test_data.append(
                MerchantMetrics(
                    merchant_id=f"merchant_{i:03d}",
                    total_receipts_7d=100,
                    redeemed_rate_7d=0.40,
                    redeemed_rate_change=-0.10,
                    avg_discount_depth=0.20,
                    activity_health_score=0.70,
                    updated_at=datetime(2016, 6, 15, 0, 0, 0),
                )
            )
        db_session.add_all(test_data)
        db_session.commit()

        # Execute: Get first page
        response = client.get(
            "/api/v1/metrics/merchants", params={"limit": 50, "offset": 0}
        )

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 150
        assert len(data["data"]) == 50

        # Execute: Get second page
        response = client.get(
            "/api/v1/metrics/merchants", params={"limit": 50, "offset": 50}
        )

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 150
        assert len(data["data"]) == 50

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_get_merchant_metrics_empty_result(self, db_session: Session):
        """Test merchant metrics with no data."""
        # Execute: Query empty table
        response = client.get("/api/v1/metrics/merchants")

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert len(data["data"]) == 0

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_get_merchant_metrics_invalid_param(self, db_session: Session):
        """Test merchant metrics with invalid parameter."""
        # Execute: Invalid limit parameter
        response = client.get(
            "/api/v1/metrics/merchants", params={"limit": -1}
        )

        # Verify: Should return 400 Bad Request
        assert response.status_code == 422  # FastAPI validation error


class TestUserMetricsAPI:
    """Tests for GET /api/v1/metrics/users endpoint."""

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_get_user_metrics_success(self, db_session: Session):
        """Test successful retrieval of user metrics."""
        # Setup
        test_data = [
            UserMetrics(
                user_id="user_001",
                total_receipts_30d=15,
                redeemed_count_30d=8,
                redeemed_rate_30d=0.53,
                avg_distance=2.5,
                last_receipt_date=datetime(2016, 6, 20).date(),
                updated_at=datetime(2016, 6, 20, 0, 0, 0),
            ),
            UserMetrics(
                user_id="user_002",
                total_receipts_30d=20,
                redeemed_count_30d=15,
                redeemed_rate_30d=0.75,
                avg_distance=1.8,
                last_receipt_date=datetime(2016, 6, 19).date(),
                updated_at=datetime(2016, 6, 19, 0, 0, 0),
            ),
        ]
        db_session.add_all(test_data)
        db_session.commit()

        # Execute
        response = client.get("/api/v1/metrics/users")

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["data"]) == 2

        # Verify first user
        user_1 = data["data"][0]
        assert user_1["user_id"] == "user_001"
        assert user_1["total_receipts_30d"] == 15
        assert user_1["redeemed_count_30d"] == 8
        assert user_1["redeemed_rate_30d"] == 0.53
        assert user_1["avg_distance"] == 2.5
        assert user_1["last_receipt_date"] == "2016-06-20"

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_get_user_metrics_with_filter(self, db_session: Session):
        """Test user metrics filtering by user_id."""
        # Setup
        test_data = [
            UserMetrics(
                user_id="user_001",
                total_receipts_30d=10,
                redeemed_count_30d=5,
                redeemed_rate_30d=0.50,
                avg_distance=1.0,
                last_receipt_date=datetime(2016, 6, 15).date(),
                updated_at=datetime(2016, 6, 15, 0, 0, 0),
            ),
            UserMetrics(
                user_id="user_002",
                total_receipts_30d=20,
                redeemed_count_30d=15,
                redeemed_rate_30d=0.75,
                avg_distance=2.0,
                last_receipt_date=datetime(2016, 6, 16).date(),
                updated_at=datetime(2016, 6, 16, 0, 0, 0),
            ),
        ]
        db_session.add_all(test_data)
        db_session.commit()

        # Execute
        response = client.get(
            "/api/v1/metrics/users", params={"user_id": "user_001"}
        )

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["data"][0]["user_id"] == "user_001"

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_get_user_metrics_with_min_receipts(self, db_session: Session):
        """Test user metrics filtering by minimum receipts."""
        # Setup
        test_data = [
            UserMetrics(
                user_id="user_001",
                total_receipts_30d=5,
                redeemed_count_30d=2,
                redeemed_rate_30d=0.40,
                avg_distance=1.0,
                last_receipt_date=datetime(2016, 6, 15).date(),
                updated_at=datetime(2016, 6, 15, 0, 0, 0),
            ),
            UserMetrics(
                user_id="user_002",
                total_receipts_30d=15,
                redeemed_count_30d=10,
                redeemed_rate_30d=0.67,
                avg_distance=2.0,
                last_receipt_date=datetime(2016, 6, 16).date(),
                updated_at=datetime(2016, 6, 16, 0, 0, 0),
            ),
        ]
        db_session.add_all(test_data)
        db_session.commit()

        # Execute: Filter users with at least 10 receipts
        response = client.get(
            "/api/v1/metrics/users", params={"min_receipts": 10}
        )

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["data"][0]["user_id"] == "user_002"

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_get_user_metrics_with_pagination(self, db_session: Session):
        """Test user metrics pagination."""
        # Setup: Insert 150 users
        test_data = []
        for i in range(150):
            test_data.append(
                UserMetrics(
                    user_id=f"user_{i:03d}",
                    total_receipts_30d=10,
                    redeemed_count_30d=5,
                    redeemed_rate_30d=0.50,
                    avg_distance=1.5,
                    last_receipt_date=datetime(2016, 6, 15).date(),
                    updated_at=datetime(2016, 6, 15, 0, 0, 0),
                )
            )
        db_session.add_all(test_data)
        db_session.commit()

        # Execute
        response = client.get(
            "/api/v1/metrics/users", params={"limit": 100, "offset": 0}
        )

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 150
        assert len(data["data"]) == 100


class TestCouponMetricsAPI:
    """Tests for GET /api/v1/metrics/coupons endpoint."""

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_get_coupon_metrics_success(self, db_session: Session):
        """Test successful retrieval of coupon metrics."""
        # Setup
        # First create merchant metrics (foreign key constraint)
        merchant = MerchantMetrics(
            merchant_id="merchant_001",
            total_receipts_7d=500,
            redeemed_rate_7d=0.45,
            redeemed_rate_change=-0.10,
            avg_discount_depth=0.25,
            activity_health_score=0.70,
            updated_at=datetime(2016, 6, 15, 0, 0, 0),
        )
        db_session.add(merchant)
        db_session.commit()

        test_data = [
            CouponMetrics(
                coupon_id="coupon_001",
                merchant_id="merchant_001",
                discount_type="满减",
                discount_rate="200:50",
                discount_value=0.25,
                threshold_amount=200.0,
                discount_amount=50.0,
                total_receipts=500,
                redeemed_count=250,
                redeemed_rate=0.50,
                avg_redeem_days=7.5,
                updated_at=datetime(2016, 6, 15, 0, 0, 0),
            ),
            CouponMetrics(
                coupon_id="coupon_002",
                merchant_id="merchant_001",
                discount_type="折扣",
                discount_rate="0.8",
                discount_value=0.20,
                threshold_amount=None,
                discount_amount=None,
                total_receipts=300,
                redeemed_count=180,
                redeemed_rate=0.60,
                avg_redeem_days=5.0,
                updated_at=datetime(2016, 6, 15, 0, 0, 0),
            ),
        ]
        db_session.add_all(test_data)
        db_session.commit()

        # Execute
        response = client.get("/api/v1/metrics/coupons")

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["data"]) == 2

        # Verify first coupon
        coupon_1 = data["data"][0]
        assert coupon_1["coupon_id"] == "coupon_001"
        assert coupon_1["merchant_id"] == "merchant_001"
        assert coupon_1["discount_type"] == "满减"
        assert coupon_1["discount_rate"] == "200:50"
        assert coupon_1["discount_value"] == 0.25
        assert coupon_1["total_receipts"] == 500
        assert coupon_1["redeemed_count"] == 250
        assert coupon_1["redeemed_rate"] == 0.50
        assert coupon_1["avg_redeem_days"] == 7.5

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_get_coupon_metrics_by_merchant(self, db_session: Session):
        """Test coupon metrics filtering by merchant_id."""
        # Setup
        merchant1 = MerchantMetrics(
            merchant_id="merchant_001",
            total_receipts_7d=500,
            redeemed_rate_7d=0.45,
            redeemed_rate_change=-0.10,
            avg_discount_depth=0.25,
            activity_health_score=0.70,
            updated_at=datetime(2016, 6, 15, 0, 0, 0),
        )
        merchant2 = MerchantMetrics(
            merchant_id="merchant_002",
            total_receipts_7d=300,
            redeemed_rate_7d=0.50,
            redeemed_rate_change=0.0,
            avg_discount_depth=0.30,
            activity_health_score=0.80,
            updated_at=datetime(2016, 6, 15, 0, 0, 0),
        )
        db_session.add_all([merchant1, merchant2])
        db_session.commit()

        test_data = [
            CouponMetrics(
                coupon_id="coupon_001",
                merchant_id="merchant_001",
                discount_type="满减",
                discount_rate="200:50",
                discount_value=0.25,
                total_receipts=500,
                redeemed_count=250,
                redeemed_rate=0.50,
                avg_redeem_days=7.5,
                updated_at=datetime(2016, 6, 15, 0, 0, 0),
            ),
            CouponMetrics(
                coupon_id="coupon_002",
                merchant_id="merchant_002",
                discount_type="折扣",
                discount_rate="0.9",
                discount_value=0.10,
                total_receipts=300,
                redeemed_count=180,
                redeemed_rate=0.60,
                avg_redeem_days=5.0,
                updated_at=datetime(2016, 6, 15, 0, 0, 0),
            ),
        ]
        db_session.add_all(test_data)
        db_session.commit()

        # Execute
        response = client.get(
            "/api/v1/metrics/coupons", params={"merchant_id": "merchant_001"}
        )

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["data"][0]["coupon_id"] == "coupon_001"

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_get_coupon_metrics_by_discount_type(self, db_session: Session):
        """Test coupon metrics filtering by discount_type."""
        # Setup
        merchant = MerchantMetrics(
            merchant_id="merchant_001",
            total_receipts_7d=500,
            redeemed_rate_7d=0.45,
            redeemed_rate_change=-0.10,
            avg_discount_depth=0.25,
            activity_health_score=0.70,
            updated_at=datetime(2016, 6, 15, 0, 0, 0),
        )
        db_session.add(merchant)
        db_session.commit()

        test_data = [
            CouponMetrics(
                coupon_id="coupon_001",
                merchant_id="merchant_001",
                discount_type="满减",
                discount_rate="200:50",
                discount_value=0.25,
                total_receipts=500,
                redeemed_count=250,
                redeemed_rate=0.50,
                avg_redeem_days=7.5,
                updated_at=datetime(2016, 6, 15, 0, 0, 0),
            ),
            CouponMetrics(
                coupon_id="coupon_002",
                merchant_id="merchant_001",
                discount_type="折扣",
                discount_rate="0.9",
                discount_value=0.10,
                total_receipts=300,
                redeemed_count=180,
                redeemed_rate=0.60,
                avg_redeem_days=5.0,
                updated_at=datetime(2016, 6, 15, 0, 0, 0),
            ),
        ]
        db_session.add_all(test_data)
        db_session.commit()

        # Execute
        response = client.get(
            "/api/v1/metrics/coupons", params={"discount_type": "满减"}
        )

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["data"][0]["discount_type"] == "满减"

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_get_coupon_metrics_by_min_redeemed_rate(self, db_session: Session):
        """Test coupon metrics filtering by minimum redeemed_rate."""
        # Setup
        merchant = MerchantMetrics(
            merchant_id="merchant_001",
            total_receipts_7d=500,
            redeemed_rate_7d=0.45,
            redeemed_rate_change=-0.10,
            avg_discount_depth=0.25,
            activity_health_score=0.70,
            updated_at=datetime(2016, 6, 15, 0, 0, 0),
        )
        db_session.add(merchant)
        db_session.commit()

        test_data = [
            CouponMetrics(
                coupon_id="coupon_001",
                merchant_id="merchant_001",
                discount_type="满减",
                discount_rate="200:50",
                discount_value=0.25,
                total_receipts=500,
                redeemed_count=250,
                redeemed_rate=0.50,
                avg_redeem_days=7.5,
                updated_at=datetime(2016, 6, 15, 0, 0, 0),
            ),
            CouponMetrics(
                coupon_id="coupon_002",
                merchant_id="merchant_001",
                discount_type="折扣",
                discount_rate="0.9",
                discount_value=0.10,
                total_receipts=300,
                redeemed_count=180,
                redeemed_rate=0.60,
                avg_redeem_days=5.0,
                updated_at=datetime(2016, 6, 15, 0, 0, 0),
            ),
        ]
        db_session.add_all(test_data)
        db_session.commit()

        # Execute: Filter coupons with redeemed_rate >= 0.55
        response = client.get(
            "/api/v1/metrics/coupons", params={"min_redeemed_rate": 0.55}
        )

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["data"][0]["coupon_id"] == "coupon_002"