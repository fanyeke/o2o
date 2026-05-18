"""User feature engineering module.

计算用户维度聚合指标，包括近30日领券总数、核销数量、核销率等。
"""
from datetime import datetime, timedelta, date
from typing import List
from sqlalchemy import func, case, and_, text
from sqlalchemy.orm import Session

from app.domain.staging.coupon_receipt_event import CouponReceiptEvent
from app.domain.feature.user_metrics import UserMetrics


def calculate_user_metrics(
    db: Session,
    reference_date: date = None,
    batch_size: int = 1000
) -> List[UserMetrics]:
    """Calculate user-level aggregated metrics from coupon receipt events.

    Args:
        db: SQLAlchemy database session
        reference_date: Reference date for 30-day window (defaults to latest date in data)
        batch_size: Number of users to process per batch (default: 1000)

    Returns:
        List of UserMetrics ORM objects

    Calculation Logic:
        - Query staging.coupon_receipt_event
        - Group by user_id
        - Calculate 30-day window metrics
        - Handle division by zero: if total_receipts=0, rate=NULL
        - avg_distance: exclude -1 (unknown distance) before averaging
        - Use SQL aggregation functions (AVG, COUNT)
    """
    # Determine reference date (latest activity date in data)
    if reference_date is None:
        result = db.execute(
            text("SELECT MAX(date_received) as max_date FROM staging.coupon_receipt_event")
        ).first()
        reference_date = result.max_date if result and result.max_date else date.today()

    # Calculate the start date for 30-day window (inclusive)
    window_start = reference_date - timedelta(days=29)  # 29 days ago + today = 30 days

    # Build aggregation query
    # Group by user_id and calculate metrics for the 30-day window
    query = (
        db.query(
            CouponReceiptEvent.user_id,
            # Total receipts in 30-day window
            func.count(CouponReceiptEvent.id).label('total_receipts_30d'),
            # Redeemed count in 30-day window
            func.sum(
                case(
                    (CouponReceiptEvent.is_redeemed == True, 1),
                    else_=0
                )
            ).label('redeemed_count_30d'),
            # Average distance (exclude -1 which means unknown)
            func.avg(
                case(
                    (CouponReceiptEvent.distance == -1, None),
                    else_=CouponReceiptEvent.distance
                )
            ).label('avg_distance'),
            # Last receipt date
            func.max(CouponReceiptEvent.date_received).label('last_receipt_date')
        )
        .filter(
            and_(
                CouponReceiptEvent.date_received >= window_start,
                CouponReceiptEvent.date_received <= reference_date
            )
        )
        .group_by(CouponReceiptEvent.user_id)
        .order_by(CouponReceiptEvent.user_id)
    )

    # Execute query and collect results
    results = query.all()

    # Process results in batches
    user_metrics_list: List[UserMetrics] = []
    current_time = datetime.now()

    for row in results:
        user_id = row.user_id
        total_receipts = row.total_receipts_30d or 0
        redeemed_count = row.redeemed_count_30d or 0
        avg_distance = row.avg_distance  # Can be None if all distances are -1
        last_receipt_date = row.last_receipt_date

        # Calculate redeemed rate with division by zero handling
        if total_receipts > 0:
            redeemed_rate = redeemed_count / total_receipts
        else:
            redeemed_rate = None  # NULL when no receipts

        # Create UserMetrics object
        user_metrics = UserMetrics(
            user_id=user_id,
            total_receipts_30d=total_receipts,
            redeemed_count_30d=redeemed_count,
            redeemed_rate_30d=redeemed_rate,
            avg_distance=avg_distance,
            last_receipt_date=last_receipt_date,
            updated_at=current_time
        )
        user_metrics_list.append(user_metrics)

    # Return list of UserMetrics objects (not persisted)
    # Caller is responsible for saving to database
    return user_metrics_list