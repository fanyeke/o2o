"""Metrics API endpoints.

Task: T047-T050
Phase: 3 - US2 Metrics Query API
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.merchant_metrics_repository import MerchantMetricsRepository
from app.repositories.user_metrics_repository import UserMetricsRepository
from app.repositories.coupon_metrics_repository import CouponMetricsRepository
from app.schemas.metrics import (
    MerchantMetricsResponse,
    MerchantMetricsData,
    UserMetricsResponse,
    UserMetricsData,
    CouponMetricsResponse,
    CouponMetricsData,
)

router = APIRouter()


@router.get("/merchants", response_model=MerchantMetricsResponse)
async def get_merchant_metrics(
    merchant_id: Optional[str] = Query(None, description="Filter by merchant ID"),
    min_receipts: Optional[int] = Query(None, ge=0, description="Minimum receipts filter"),
    redeemed_rate_range: Optional[str] = Query(
        None, description="Redeemed rate range (format: 'min,max')"
    ),
    sort_by: Optional[str] = Query(
        None, description="Sort field (e.g., 'redeemed_rate_change')"
    ),
    order: Optional[str] = Query("desc", description="Sort order ('asc' or 'desc')"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    db: Session = Depends(get_db),
):
    """Get merchant metrics with filtering, sorting, and pagination.

    Args:
        merchant_id: Filter by specific merchant ID
        min_receipts: Filter by minimum receipts
        redeemed_rate_range: Filter by redeemed rate range (format: 'min,max')
        sort_by: Sort field
        order: Sort order ('asc' or 'desc')
        limit: Maximum results to return
        offset: Number of results to skip
        db: Database session

    Returns:
        MerchantMetricsResponse with total count and data list

    Raises:
        HTTPException: If validation fails
    """
    # Create repository
    repo = MerchantMetricsRepository(db)

    # Validate order parameter
    if order not in ["asc", "desc"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid order parameter: {order}. Must be 'asc' or 'desc'",
        )

    # Validate sort_by parameter
    valid_sort_fields = [
        "redeemed_rate_change",
        "total_receipts_7d",
        "redeemed_rate_7d",
        "activity_health_score",
        "avg_discount_depth",
    ]
    if sort_by and sort_by not in valid_sort_fields:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid sort_by field: {sort_by}. Valid fields: {valid_sort_fields}",
        )

    # Query data
    # Parse redeemed_rate_range into min/max
    min_redeemed_rate = None
    max_redeemed_rate = None
    if redeemed_rate_range:
        try:
            parts = redeemed_rate_range.split(',')
            if len(parts) == 2:
                min_redeemed_rate = float(parts[0])
                max_redeemed_rate = float(parts[1])
        except (ValueError, AttributeError):
            raise HTTPException(
                status_code=400,
                detail="Invalid redeemed_rate_range format. Expected: 'min,max'"
            )

    # Call repository with correct parameter names
    metrics_list, total = repo.find_all_with_filters(
        merchant_id=merchant_id,
        min_receipts=min_receipts,
        min_redeemed_rate=min_redeemed_rate,
        max_redeemed_rate=max_redeemed_rate,
        sort_by=sort_by,
        sort_order=order,  # Repository uses sort_order, not order
        limit=limit,
        offset=offset
    )

    # Convert to response format
    data = [
        MerchantMetricsData(
            merchant_id=m.merchant_id,
            total_receipts_7d=m.total_receipts_7d or 0,
            redeemed_rate_7d=m.redeemed_rate_7d or 0.0,
            total_receipts_30d=m.total_receipts_30d,
            redeemed_rate_30d=m.redeemed_rate_30d,
            redeemed_rate_change=m.redeemed_rate_change or 0.0,
            avg_discount_depth=m.avg_discount_depth or 0.0,
            activity_health_score=m.activity_health_score or 0.0,
            updated_at=m.updated_at,
        )
        for m in metrics_list
    ]

    return MerchantMetricsResponse(
        total=total,
        limit=limit,
        offset=offset,
        data=data,
    )


@router.get("/users", response_model=UserMetricsResponse)
async def get_user_metrics(
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    min_receipts: Optional[int] = Query(None, ge=0, description="Minimum receipts filter"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    db: Session = Depends(get_db),
):
    """Get user metrics with filtering and pagination.

    Args:
        user_id: Filter by specific user ID
        min_receipts: Filter by minimum receipts (30d)
        limit: Maximum results to return
        offset: Number of results to skip
        db: Database session

    Returns:
        UserMetricsResponse with total count and data list
    """
    # Create repository
    repo = UserMetricsRepository(db)

    # Query data
    metrics_list, total = repo.find_all_with_filters(
        user_id=user_id,
        min_receipts=min_receipts,
        limit=limit,
        offset=offset,
    )

    # Convert to response format
    data = [
        UserMetricsData(
            user_id=u.user_id,
            total_receipts_30d=u.total_receipts_30d or 0,
            redeemed_count_30d=u.redeemed_count_30d or 0,
            redeemed_rate_30d=u.redeemed_rate_30d or 0.0,
            avg_distance=u.avg_distance or 0.0,
            last_receipt_date=str(u.last_receipt_date) if u.last_receipt_date else "",
            updated_at=u.updated_at,
        )
        for u in metrics_list
    ]

    return UserMetricsResponse(
        total=total,
        limit=limit,
        offset=offset,
        data=data,
    )


@router.get("/coupons", response_model=CouponMetricsResponse)
async def get_coupon_metrics(
    coupon_id: Optional[str] = Query(None, description="Filter by coupon ID"),
    merchant_id: Optional[str] = Query(None, description="Filter by merchant ID"),
    discount_type: Optional[str] = Query(None, description="Filter by discount type"),
    min_redeemed_rate: Optional[float] = Query(
        None, ge=0.0, le=1.0, description="Minimum redeemed rate filter"
    ),
    db: Session = Depends(get_db),
):
    """Get coupon metrics with filtering.

    Args:
        coupon_id: Filter by specific coupon ID
        merchant_id: Filter by merchant ID
        discount_type: Filter by discount type (e.g., '满减', '折扣')
        min_redeemed_rate: Filter by minimum redeemed rate
        db: Database session

    Returns:
        CouponMetricsResponse with total count and data list
    """
    # Create repository
    repo = CouponMetricsRepository(db)

    # Query data
    metrics_list, total = repo.find_all_with_filters(
        coupon_id=coupon_id,
        merchant_id=merchant_id,
        discount_type=discount_type,
        min_redeemed_rate=min_redeemed_rate,
    )

    # Convert to response format
    data = [
        CouponMetricsData(
            coupon_id=c.coupon_id,
            merchant_id=c.merchant_id,
            discount_type=c.discount_type or "",
            discount_rate=c.discount_rate or "",
            discount_value=c.discount_value or 0.0,
            total_receipts=c.total_receipts or 0,
            redeemed_count=c.redeemed_count or 0,
            redeemed_rate=c.redeemed_rate or 0.0,
            avg_redeem_days=c.avg_redeem_days or 0.0,
            updated_at=c.updated_at,
        )
        for c in metrics_list
    ]

    return CouponMetricsResponse(
        total=total,
        data=data,
    )