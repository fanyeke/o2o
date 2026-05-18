"""Repository for UserMetrics entity.

Task: T054
Phase: 3 - US2 Metrics Query API

Features:
- Filtering by user_id, redeemed_rate range, receipts range, date range
- Sorting by any valid field (asc/desc)
- Pagination (limit/offset)
- Optimized SQL queries
"""

from typing import Optional, List
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, asc
from app.domain.feature.user_metrics import UserMetrics


# Valid sort fields for user metrics
VALID_SORT_FIELDS = {
    "user_id",
    "total_receipts_30d",
    "redeemed_count_30d",
    "redeemed_rate_30d",
    "avg_distance",
    "last_receipt_date",
    "updated_at",
}


class UserMetricsRepository:
    """Repository for user metrics data access.

    Provides methods for querying user metrics with filtering,
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
        user_id: Optional[str] = None,
        min_redeemed_rate: Optional[float] = None,
        max_redeemed_rate: Optional[float] = None,
        min_receipts: Optional[int] = None,
        receipt_start_date: Optional[date] = None,
        receipt_end_date: Optional[date] = None,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = "desc",
        limit: Optional[int] = 100,
        offset: Optional[int] = 0,
    ) -> tuple[List[UserMetrics], int]:
        """Find user metrics with filtering, sorting, and pagination.

        Args:
            user_id: Filter by specific user ID (exact match)
            min_redeemed_rate: Minimum redeemed_rate_30d (inclusive)
            max_redeemed_rate: Maximum redeemed_rate_30d (inclusive)
            min_receipts: Minimum total_receipts_30d (inclusive)
            receipt_start_date: Minimum last_receipt_date (inclusive)
            receipt_end_date: Maximum last_receipt_date (inclusive)
            sort_by: Field to sort by (must be in VALID_SORT_FIELDS)
            sort_order: Sort order ("asc" or "desc")
            limit: Maximum number of results to return
            offset: Number of results to skip (for pagination)

        Returns:
            Tuple of (list of UserMetrics, total count)

        Raises:
            ValueError: If sort_by or sort_order is invalid

        Example:
            >>> repo.find_all_with_filters(
                min_redeemed_rate=0.5,
                sort_by="total_receipts_30d",
                sort_order="desc",
                limit=20,
                offset=0
            )
        """
        # Validate sort order first
        if sort_order not in ("asc", "desc"):
            raise ValueError(
                f"Invalid sort order: {sort_order}. Must be 'asc' or 'desc'"
            )

        # Build base query
        query = self.db.query(UserMetrics)

        # Apply user_id filter (exact match)
        if user_id:
            query = query.filter(UserMetrics.user_id == user_id)

        # Apply redeemed_rate_30d range filter
        if min_redeemed_rate is not None:
            query = query.filter(
                UserMetrics.redeemed_rate_30d >= min_redeemed_rate
            )

        if max_redeemed_rate is not None:
            query = query.filter(
                UserMetrics.redeemed_rate_30d <= max_redeemed_rate
            )

        # Apply receipts filter (total_receipts_30d)
        if min_receipts is not None:
            query = query.filter(
                UserMetrics.total_receipts_30d >= min_receipts
            )

        # Apply date range filter (last_receipt_date)
        if receipt_start_date is not None:
            query = query.filter(
                UserMetrics.last_receipt_date >= receipt_start_date
            )

        if receipt_end_date is not None:
            query = query.filter(
                UserMetrics.last_receipt_date <= receipt_end_date
            )

        # Get total count BEFORE pagination
        total = query.count()

        # Apply sorting
        if sort_by:
            # Validate sort field
            if sort_by not in VALID_SORT_FIELDS:
                raise ValueError(
                    f"Invalid sort field: {sort_by}. "
                    f"Valid fields: {sorted(VALID_SORT_FIELDS)}"
                )

            # Get sort column
            sort_column = getattr(UserMetrics, sort_by)

            # Apply order
            if sort_order == "asc":
                query = query.order_by(asc(sort_column))
            else:
                query = query.order_by(desc(sort_column))

        # Apply pagination
        if limit is not None:
            query = query.limit(limit)

        if offset is not None:
            query = query.offset(offset)

        # Execute query
        results = query.all()

        return results, total

    def find_by_id(self, user_id: str) -> Optional[UserMetrics]:
        """Find a single user metric by user_id.

        Args:
            user_id: User ID (primary key)

        Returns:
            UserMetrics if found, None otherwise

        Example:
            >>> metric = repo.find_by_id("user_001")
            >>> if metric:
                print(metric.redeemed_rate_30d)
        """
        query = self.db.query(UserMetrics)
        query = query.filter(UserMetrics.user_id == user_id)
        return query.first()

    def count_all_with_filters(
        self,
        user_id: Optional[str] = None,
        min_redeemed_rate: Optional[float] = None,
        max_redeemed_rate: Optional[float] = None,
        min_receipts: Optional[int] = None,
        receipt_start_date: Optional[date] = None,
        receipt_end_date: Optional[date] = None,
    ) -> int:
        """Count total user metrics matching filters.

        Used for pagination to calculate total pages.

        Args:
            user_id: Filter by specific user ID
            min_redeemed_rate: Minimum redeemed_rate_30d
            max_redeemed_rate: Maximum redeemed_rate_30d
            min_receipts: Minimum total_receipts_30d
            receipt_start_date: Minimum last_receipt_date
            receipt_end_date: Maximum last_receipt_date

        Returns:
            Total count of matching records

        Example:
            >>> total = repo.count_all_with_filters(min_redeemed_rate=0.5)
            >>> pages = (total + limit - 1) // limit
        """
        # Build base query
        query = self.db.query(UserMetrics)

        # Apply same filters as find_all_with_filters
        if user_id:
            query = query.filter(UserMetrics.user_id == user_id)

        if min_redeemed_rate is not None:
            query = query.filter(
                UserMetrics.redeemed_rate_30d >= min_redeemed_rate
            )

        if max_redeemed_rate is not None:
            query = query.filter(
                UserMetrics.redeemed_rate_30d <= max_redeemed_rate
            )

        if min_receipts is not None:
            query = query.filter(
                UserMetrics.total_receipts_30d >= min_receipts
            )

        if receipt_start_date is not None:
            query = query.filter(
                UserMetrics.last_receipt_date >= receipt_start_date
            )

        if receipt_end_date is not None:
            query = query.filter(
                UserMetrics.last_receipt_date <= receipt_end_date
            )

        # Return count
        return query.count()

    # Legacy method for backward compatibility
    def find_by_user_id(self, user_id: str) -> Optional[UserMetrics]:
        """Find user metrics by user ID (legacy method).

        Args:
            user_id: User ID

        Returns:
            UserMetrics or None

        Note:
            This method is deprecated. Use find_by_id instead.
        """
        return self.find_by_id(user_id)