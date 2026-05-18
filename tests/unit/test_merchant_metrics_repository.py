"""Unit tests for MerchantMetricsRepository.

Tests filtering, sorting, and pagination logic.
"""

import pytest
from datetime import date, datetime, timedelta
from unittest.mock import Mock, MagicMock, patch
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.repositories.merchant_metrics_repository import MerchantMetricsRepository
from app.domain.feature.merchant_metrics import MerchantMetrics


class TestMerchantMetricsRepository:
    """Test suite for MerchantMetricsRepository."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return Mock(spec=Session)

    @pytest.fixture
    def repository(self, mock_db):
        """Create repository instance with mock database."""
        return MerchantMetricsRepository(mock_db)

    def test_init_with_db_session(self, mock_db):
        """Test repository initialization with database session."""
        repo = MerchantMetricsRepository(mock_db)
        assert repo.db == mock_db

    def test_find_all_with_filters_no_filters(self, repository, mock_db):
        """Test find_all_without any filters returns all metrics."""
        # Mock query result
        mock_metrics = [
            MerchantMetrics(
                merchant_id="merchant_001",
                total_receipts_7d=100,
                redeemed_count_7d=50,
                redeemed_rate_7d=0.5,
                total_receipts_30d=300,
                redeemed_count_30d=150,
                redeemed_rate_30d=0.5,
                redeemed_rate_change=0.0,
                avg_discount_depth=0.2,
                activity_health_score=0.7,
                last_activity_date=date(2016, 6, 30),
                updated_at=datetime.now(),
            )
        ]

        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.all.return_value = mock_metrics
        mock_query.count.return_value = len(mock_metrics)  # Add count mock

        mock_db.query.return_value = mock_query

        # Call repository method
        result, count = repository.find_all_with_filters()

        # Verify
        assert result == mock_metrics
        assert count == len(mock_metrics)
        mock_db.query.assert_called_once_with(MerchantMetrics)

    def test_find_all_with_filters_by_merchant_id(self, repository, mock_db):
        """Test filtering by merchant_id."""
        merchant_id = "merchant_001"
        mock_metrics = [
            MerchantMetrics(merchant_id=merchant_id, total_receipts_7d=100)
        ]

        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.all.return_value = mock_metrics

        mock_db.query.return_value = mock_query

        # Call with filter
        result, total = repository.find_all_with_filters(merchant_id=merchant_id)

        # Verify
        assert result == mock_metrics
        mock_db.query.assert_called_once_with(MerchantMetrics)
        # Verify filter was called (should filter by merchant_id)
        mock_query.filter.assert_called()

    def test_find_all_with_filters_by_min_redeemed_rate(self, repository, mock_db):
        """Test filtering by minimum redeemed_rate_7d."""
        min_rate = 0.5
        mock_metrics = [
            MerchantMetrics(merchant_id="merchant_001", redeemed_rate_7d=0.7)
        ]

        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.all.return_value = mock_metrics

        mock_db.query.return_value = mock_query

        # Call with min_redeemed_rate filter
        result, total = repository.find_all_with_filters(min_redeemed_rate=min_rate)

        # Verify
        assert result == mock_metrics
        mock_query.filter.assert_called()

    def test_find_all_with_filters_by_max_redeemed_rate(self, repository, mock_db):
        """Test filtering by maximum redeemed_rate_7d."""
        max_rate = 0.3
        mock_metrics = [
            MerchantMetrics(merchant_id="merchant_001", redeemed_rate_7d=0.2)
        ]

        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.all.return_value = mock_metrics

        mock_db.query.return_value = mock_query

        # Call with max_redeemed_rate filter
        result, total = repository.find_all_with_filters(max_redeemed_rate=max_rate)

        # Verify
        assert result == mock_metrics
        mock_query.filter.assert_called()

    def test_find_all_with_filters_sorting_desc(self, repository, mock_db):
        """Test sorting by redeemed_rate_7d descending."""
        mock_metrics = [
            MerchantMetrics(merchant_id="merchant_001", redeemed_rate_7d=0.8),
            MerchantMetrics(merchant_id="merchant_002", redeemed_rate_7d=0.6),
        ]

        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.all.return_value = mock_metrics

        mock_db.query.return_value = mock_query

        # Call with sorting
        result, total = repository.find_all_with_filters(
            sort_by="redeemed_rate_7d", sort_order="desc"
        )

        # Verify
        assert result == mock_metrics
        mock_query.order_by.assert_called()

    def test_find_all_with_filters_sorting_asc(self, repository, mock_db):
        """Test sorting by total_receipts_7d ascending."""
        mock_metrics = [
            MerchantMetrics(merchant_id="merchant_001", total_receipts_7d=100),
            MerchantMetrics(merchant_id="merchant_002", total_receipts_7d=200),
        ]

        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.all.return_value = mock_metrics

        mock_db.query.return_value = mock_query

        # Call with sorting
        result, total = repository.find_all_with_filters(
            sort_by="total_receipts_7d", sort_order="asc"
        )

        # Verify
        assert result == mock_metrics
        mock_query.order_by.assert_called()

    def test_find_all_with_filters_pagination(self, repository, mock_db):
        """Test pagination with limit and offset."""
        mock_metrics_page2 = [
            MerchantMetrics(merchant_id="merchant_011", total_receipts_7d=100),
        ]

        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.all.return_value = mock_metrics_page2

        mock_db.query.return_value = mock_query

        # Call with pagination (page 2, limit 10)
        result, total = repository.find_all_with_filters(limit=10, offset=10)

        # Verify
        assert result == mock_metrics_page2
        mock_query.limit.assert_called_once_with(10)
        mock_query.offset.assert_called_once_with(10)

    def test_find_all_with_filters_combined(self, repository, mock_db):
        """Test combined filters, sorting, and pagination."""
        mock_metrics = [
            MerchantMetrics(
                merchant_id="merchant_001",
                redeemed_rate_7d=0.7,
                total_receipts_7d=150,
            )
        ]

        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.all.return_value = mock_metrics

        mock_db.query.return_value = mock_query

        # Call with all filters
        result, total = repository.find_all_with_filters(
            min_redeemed_rate=0.5,
            max_redeemed_rate=0.9,
            sort_by="total_receipts_7d",
            sort_order="desc",
            limit=20,
            offset=0,
        )

        # Verify
        assert result == mock_metrics
        # Should have multiple filter calls
        assert mock_query.filter.call_count >= 1
        mock_query.order_by.assert_called_once()
        mock_query.limit.assert_called_once_with(20)
        mock_query.offset.assert_called_once_with(0)

    def test_find_by_id_exists(self, repository, mock_db):
        """Test finding a merchant metric by ID when it exists."""
        merchant_id = "merchant_001"
        mock_metric = MerchantMetrics(
            merchant_id=merchant_id,
            total_receipts_7d=100,
            redeemed_count_7d=50,
        )

        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_metric

        mock_db.query.return_value = mock_query

        # Call repository method
        result = repository.find_by_id(merchant_id)

        # Verify
        assert result == mock_metric
        assert result.merchant_id == merchant_id
        mock_db.query.assert_called_once_with(MerchantMetrics)

    def test_find_by_id_not_found(self, repository, mock_db):
        """Test finding a merchant metric by ID when it doesn't exist."""
        merchant_id = "merchant_999"

        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        mock_db.query.return_value = mock_query

        # Call repository method
        result = repository.find_by_id(merchant_id)

        # Verify
        assert result is None
        mock_db.query.assert_called_once_with(MerchantMetrics)

    def test_find_all_with_filters_invalid_sort_field(self, repository, mock_db):
        """Test that invalid sort field raises ValueError."""
        with pytest.raises(ValueError, match="Invalid sort field"):
            repository.find_all_with_filters(sort_by="invalid_field")

    def test_find_all_with_filters_invalid_sort_order(self, repository, mock_db):
        """Test that invalid sort order raises ValueError."""
        with pytest.raises(ValueError, match="Invalid sort order"):
            repository.find_all_with_filters(sort_order="invalid_order")

    def test_count_all_with_filters(self, repository, mock_db):
        """Test counting total records with filters."""
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 42

        mock_db.query.return_value = mock_query

        # Call count
        result = repository.count_all_with_filters(min_redeemed_rate=0.5)

        # Verify
        assert result == 42
        mock_db.query.assert_called_once_with(MerchantMetrics)

    def test_count_all_without_filters(self, repository, mock_db):
        """Test counting all records without filters."""
        mock_query = Mock()
        mock_query.count.return_value = 100

        mock_db.query.return_value = mock_query

        # Call count
        result = repository.count_all_with_filters()

        # Verify
        assert result == 100
        mock_db.query.assert_called_once_with(MerchantMetrics)

    def test_find_all_with_filters_by_min_receipts(self, repository, mock_db):
        """Test filtering by minimum total_receipts_7d."""
        min_receipts = 100
        mock_metrics = [
            MerchantMetrics(merchant_id="merchant_001", total_receipts_7d=150)
        ]

        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.all.return_value = mock_metrics

        mock_db.query.return_value = mock_query

        # Call with min_receipts filter
        result, total = repository.find_all_with_filters(min_receipts=min_receipts)

        # Verify
        assert result == mock_metrics
        mock_query.filter.assert_called()

    def test_find_all_with_filters_by_date_range(self, repository, mock_db):
        """Test filtering by last_activity_date range."""
        start_date = date(2016, 6, 1)
        end_date = date(2016, 6, 30)
        mock_metrics = [
            MerchantMetrics(
                merchant_id="merchant_001",
                last_activity_date=date(2016, 6, 15),
            )
        ]

        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.all.return_value = mock_metrics

        mock_db.query.return_value = mock_query

        # Call with date range filter
        result, total = repository.find_all_with_filters(
            activity_start_date=start_date, activity_end_date=end_date
        )

        # Verify
        assert result == mock_metrics
        mock_query.filter.assert_called()