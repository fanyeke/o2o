"""Repository for CouponMetrics entity.

Task: T055
Phase: 3 - US2 Metrics Query API

Features:
- Filtering by coupon_id, merchant_id, discount_type, redeemed_rate range
- Sorting by any valid field (asc/desc)
- Pagination (limit/offset)
- Optimized SQL queries
"""

from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, asc
from app.domain.feature.coupon_metrics import CouponMetrics


# Valid sort fields for coupon metrics
VALID_SORT_FIELDS = {
    "coupon_id",
    "merchant_id",
    "discount_type",
    "discount_rate",
    "discount_value",
    "threshold_amount",
    "discount_amount",
    "total_receipts",
    "redeemed_count",
    "redeemed_rate",
    "avg_redeem_days",
    "updated_at",
}


class CouponMetricsRepository:
    """Repository for coupon metrics data access.

    Provides methods for querying coupon metrics with filtering,
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
        coupon_id: Optional[str] = None,
        merchant_id: Optional[str] = None,
        discount_type: Optional[str] = None,
        min_redeemed_rate: Optional[float] = None,
        max_redeemed_rate: Optional[float] = None,
        min_receipts: Optional[int] = None,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = "desc",
        limit: Optional[int] = 100,
        offset: Optional[int] = 0,
    ) -> tuple[List[CouponMetrics], int]:
        """Find coupon metrics with filtering, sorting, and pagination.

        Args:
            coupon_id: Filter by specific coupon ID (exact match)
            merchant_id: Filter by merchant ID (exact match)
            discount_type: Filter by discount type (e.g., "满减", "折扣")
            min_redeemed_rate: Minimum redeemed_rate (inclusive)
            max_redeemed_rate: Maximum redeemed_rate (inclusive)
            min_receipts: Minimum total_receipts (inclusive)
            sort_by: Field to sort by (must be in VALID_SORT_FIELDS)
            sort_order: Sort order ("asc" or "desc")
            limit: Maximum number of results to return
            offset: Number of results to skip (for pagination)

        Returns:
            Tuple of (list of CouponMetrics, total count)

        Raises:
            ValueError: If sort_by or sort_order is invalid

        Example:
            >>> repo.find_all_with_filters(
                merchant_id="merchant_001",
                discount_type="满减",
                sort_by="redeemed_rate",
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
        query = self.db.query(CouponMetrics)

        # Apply coupon_id filter (exact match)
        if coupon_id:
            query = query.filter(CouponMetrics.coupon_id == coupon_id)

        # Apply merchant_id filter (exact match)
        if merchant_id:
            query = query.filter(CouponMetrics.merchant_id == merchant_id)

        # Apply discount_type filter (exact match)
        if discount_type:
            query = query.filter(CouponMetrics.discount_type == discount_type)

        # Apply redeemed_rate range filter
        if min_redeemed_rate is not None:
            query = query.filter(
                CouponMetrics.redeemed_rate >= min_redeemed_rate
            )

        if max_redeemed_rate is not None:
            query = query.filter(
                CouponMetrics.redeemed_rate <= max_redeemed_rate
            )

        # Apply receipts filter (total_receipts)
        if min_receipts is not None:
            query = query.filter(
                CouponMetrics.total_receipts >= min_receipts
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
            sort_column = getattr(CouponMetrics, sort_by)

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

    def find_by_id(self, coupon_id: str) -> Optional[CouponMetrics]:
        """Find a single coupon metric by coupon_id.

        Args:
            coupon_id: Coupon ID (primary key)

        Returns:
            CouponMetrics if found, None otherwise

        Example:
            >>> metric = repo.find_by_id("coupon_001")
            >>> if metric:
                print(metric.redeemed_rate)
        """
        query = self.db.query(CouponMetrics)
        query = query.filter(CouponMetrics.coupon_id == coupon_id)
        return query.first()

    def count_all_with_filters(
        self,
        coupon_id: Optional[str] = None,
        merchant_id: Optional[str] = None,
        discount_type: Optional[str] = None,
        min_redeemed_rate: Optional[float] = None,
        max_redeemed_rate: Optional[float] = None,
        min_receipts: Optional[int] = None,
    ) -> int:
        """Count total coupon metrics matching filters.

        Used for pagination to calculate total pages.

        Args:
            coupon_id: Filter by specific coupon ID
            merchant_id: Filter by merchant ID
            discount_type: Filter by discount type
            min_redeemed_rate: Minimum redeemed_rate
            max_redeemed_rate: Maximum redeemed_rate
            min_receipts: Minimum total_receipts

        Returns:
            Total count of matching records

        Example:
            >>> total = repo.count_all_with_filters(
                merchant_id="merchant_001",
                min_redeemed_rate=0.5
            )
            >>> pages = (total + limit - 1) // limit
        """
        # Build base query
        query = self.db.query(CouponMetrics)

        # Apply same filters as find_all_with_filters
        if coupon_id:
            query = query.filter(CouponMetrics.coupon_id == coupon_id)

        if merchant_id:
            query = query.filter(CouponMetrics.merchant_id == merchant_id)

        if discount_type:
            query = query.filter(CouponMetrics.discount_type == discount_type)

        if min_redeemed_rate is not None:
            query = query.filter(
                CouponMetrics.redeemed_rate >= min_redeemed_rate
            )

        if max_redeemed_rate is not None:
            query = query.filter(
                CouponMetrics.redeemed_rate <= max_redeemed_rate
            )

        if min_receipts is not None:
            query = query.filter(
                CouponMetrics.total_receipts >= min_receipts
            )

        # Return count
        return query.count()

    # Legacy method for backward compatibility
    def find_by_coupon_id(self, coupon_id: str) -> Optional[CouponMetrics]:
        """Find coupon metrics by coupon ID (legacy method).

        Args:
            coupon_id: Coupon ID

        Returns:
            CouponMetrics or None

        Note:
            This method is deprecated. Use find_by_id instead.
        """
        return self.find_by_id(coupon_id)