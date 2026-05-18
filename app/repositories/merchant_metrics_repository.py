"""Repository for MerchantMetrics entity.

Task: T052-T053
Phase: 3 - US2 Metrics Query API

Features:
- Filtering by merchant_id, redeemed_rate range, receipts range, date range
- Sorting by any valid field (asc/desc)
- Pagination (limit/offset)
- Optimized SQL queries with proper indexing
"""

from typing import Optional, List
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, asc
from app.domain.feature.merchant_metrics import MerchantMetrics


# Valid sort fields for merchant metrics
VALID_SORT_FIELDS = {
    "merchant_id",
    "total_receipts_7d",
    "redeemed_count_7d",
    "redeemed_rate_7d",
    "total_receipts_30d",
    "redeemed_count_30d",
    "redeemed_rate_30d",
    "redeemed_rate_change",
    "avg_discount_depth",
    "activity_health_score",
    "last_activity_date",
    "updated_at",
}


class MerchantMetricsRepository:
    """Repository for merchant metrics data access.

    Provides methods for querying merchant metrics with filtering,
    sorting, and pagination capabilities.
    """

    def __init__(self, db: Session):
        """Initialize repository with database session.

        Args:
            db: SQLAlchemy session for database operations
        """
        self.db = db

    def find_all_with_filters(
        self,
        merchant_id: Optional[str] = None,
        min_redeemed_rate: Optional[float] = None,
        max_redeemed_rate: Optional[float] = None,
        min_receipts: Optional[int] = None,
        activity_start_date: Optional[date] = None,
        activity_end_date: Optional[date] = None,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = "desc",
        limit: Optional[int] = 100,
        offset: Optional[int] = 0,
    ) -> tuple[List[MerchantMetrics], int]:
        """Find merchant metrics with filtering, sorting, and pagination.

        This method supports multiple filter conditions and returns
        a paginated list of merchant metrics sorted by specified field.

        Args:
            merchant_id: Filter by specific merchant ID (exact match)
            min_redeemed_rate: Minimum redeemed_rate_7d (inclusive)
            max_redeemed_rate: Maximum redeemed_rate_7d (inclusive)
            min_receipts: Minimum total_receipts_7d (inclusive)
            activity_start_date: Minimum last_activity_date (inclusive)
            activity_end_date: Maximum last_activity_date (inclusive)
            sort_by: Field to sort by (must be in VALID_SORT_FIELDS)
            sort_order: Sort order ("asc" or "desc")
            limit: Maximum number of results to return
            offset: Number of results to skip (for pagination)

        Returns:
            Tuple of (list of MerchantMetrics, total count)

        Raises:
            ValueError: If sort_by or sort_order is invalid

        Example:
            >>> repo.find_all_with_filters(
                min_redeemed_rate=0.5,
                sort_by="total_receipts_7d",
                sort_order="desc",
                limit=20,
                offset=0
            )
        """
        # Build base query
        query = self.db.query(MerchantMetrics)

        # Apply merchant_id filter (exact match)
        if merchant_id:
            query = query.filter(MerchantMetrics.merchant_id == merchant_id)

        # Apply redeemed_rate_7d range filter
        if min_redeemed_rate is not None:
            query = query.filter(
                MerchantMetrics.redeemed_rate_7d >= min_redeemed_rate
            )

        if max_redeemed_rate is not None:
            query = query.filter(
                MerchantMetrics.redeemed_rate_7d <= max_redeemed_rate
            )

        # Apply receipts filter (total_receipts_7d)
        if min_receipts is not None:
            query = query.filter(
                MerchantMetrics.total_receipts_7d >= min_receipts
            )

        # Apply date range filter (last_activity_date)
        if activity_start_date is not None:
            query = query.filter(
                MerchantMetrics.last_activity_date >= activity_start_date
            )

        if activity_end_date is not None:
            query = query.filter(
                MerchantMetrics.last_activity_date <= activity_end_date
            )

        # Validate sort order (even if sort_by is not provided)
        if sort_order not in ("asc", "desc"):
            raise ValueError(
                f"Invalid sort order: {sort_order}. Must be 'asc' or 'desc'"
            )

        # Apply sorting
        if sort_by:
            # Validate sort field
            if sort_by not in VALID_SORT_FIELDS:
                raise ValueError(
                    f"Invalid sort field: {sort_by}. "
                    f"Valid fields: {sorted(VALID_SORT_FIELDS)}"
                )

            # Get sort column
            sort_column = getattr(MerchantMetrics, sort_by)

            # Apply order
            if sort_order == "asc":
                query = query.order_by(asc(sort_column))
            else:
                query = query.order_by(desc(sort_column))

        # Get total count BEFORE pagination
        total = query.count()

        # Apply pagination
        if limit is not None:
            query = query.limit(limit)

        if offset is not None:
            query = query.offset(offset)

        # Execute query
        results = query.all()

        return results, total

    def find_by_id(self, merchant_id: str) -> Optional[MerchantMetrics]:
        """Find a single merchant metric by merchant_id.

        Args:
            merchant_id: Merchant ID (primary key)

        Returns:
            MerchantMetrics if found, None otherwise

        Example:
            >>> metric = repo.find_by_id("merchant_001")
            >>> if metric:
                print(metric.redeemed_rate_7d)
        """
        query = self.db.query(MerchantMetrics)
        query = query.filter(MerchantMetrics.merchant_id == merchant_id)
        return query.first()

    def count_all_with_filters(
        self,
        merchant_id: Optional[str] = None,
        min_redeemed_rate: Optional[float] = None,
        max_redeemed_rate: Optional[float] = None,
        min_receipts: Optional[int] = None,
        activity_start_date: Optional[date] = None,
        activity_end_date: Optional[date] = None,
    ) -> int:
        """Count total merchant metrics matching filters.

        Used for pagination to calculate total pages.

        Args:
            merchant_id: Filter by specific merchant ID
            min_redeemed_rate: Minimum redeemed_rate_7d
            max_redeemed_rate: Maximum redeemed_rate_7d
            min_receipts: Minimum total_receipts_7d
            activity_start_date: Minimum last_activity_date
            activity_end_date: Maximum last_activity_date

        Returns:
            Total count of matching records

        Example:
            >>> total = repo.count_all_with_filters(min_redeemed_rate=0.5)
            >>> pages = (total + limit - 1) // limit
        """
        # Build base query
        query = self.db.query(MerchantMetrics)

        # Apply same filters as find_all_with_filters (but no pagination)
        if merchant_id:
            query = query.filter(MerchantMetrics.merchant_id == merchant_id)

        if min_redeemed_rate is not None:
            query = query.filter(
                MerchantMetrics.redeemed_rate_7d >= min_redeemed_rate
            )

        if max_redeemed_rate is not None:
            query = query.filter(
                MerchantMetrics.redeemed_rate_7d <= max_redeemed_rate
            )

        if min_receipts is not None:
            query = query.filter(
                MerchantMetrics.total_receipts_7d >= min_receipts
            )

        if activity_start_date is not None:
            query = query.filter(
                MerchantMetrics.last_activity_date >= activity_start_date
            )

        if activity_end_date is not None:
            query = query.filter(
                MerchantMetrics.last_activity_date <= activity_end_date
            )

        # Return count
        return query.count()

    # Legacy method for backward compatibility
    def find_by_merchant_id(self, merchant_id: str) -> Optional[MerchantMetrics]:
        """Find merchant metrics by merchant ID (legacy method).

        Args:
            merchant_id: Merchant ID

        Returns:
            MerchantMetrics or None

        Note:
            This method is deprecated. Use find_by_id instead.
        """
        return self.find_by_id(merchant_id)