"""Recent receipts query tool for Agent decision-making.

This tool queries recent coupon receipt events for a specific merchant or user
from the staging layer and returns JSON-serializable output.

Output format:
{
  "merchant_id": "xxx" or "user_id": "yyy",
  "receipts": [
    {
      "date_received": "2016-06-30",
      "coupon_id": "coupon_001",
      "user_id": "user_001",
      "merchant_id": "merchant_001",
      "is_redeemed": true,
      "distance": 2,
      "discount_rate": "满100:减20"
    },
    ...
  ],
  "total_count": 10
}
"""

from typing import Dict, Any, Optional, List
from datetime import date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.domain.staging.coupon_receipt_event import CouponReceiptEvent


def get_recent_receipts(
    db: Session,
    merchant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    days: int = 7,
    limit: int = 20
) -> Dict[str, Any]:
    """Query recent receipt events and return JSON-formatted data.

    Args:
        db: Database session
        merchant_id: Filter by merchant (optional)
        user_id: Filter by user (optional)
        days: Number of recent days to query (default: 7)
        limit: Maximum number of receipts to return (default: 20)

    Returns:
        JSON-serializable dict with recent receipts list.

    Example:
        >>> result = get_recent_receipts(db, merchant_id="merchant_001", days=7)
        >>> assert "receipts" in result
        >>> assert len(result["receipts"]) <= 20
    """
    # Build base query
    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    query = db.query(CouponReceiptEvent).filter(
        CouponReceiptEvent.date_received >= start_date,
        CouponReceiptEvent.date_received <= end_date
    )

    # Apply filters
    if merchant_id:
        query = query.filter(CouponReceiptEvent.merchant_id == merchant_id)

    if user_id:
        query = query.filter(CouponReceiptEvent.user_id == user_id)

    # Order by date descending and limit
    query = query.order_by(CouponReceiptEvent.date_received.desc()).limit(limit)

    receipts = query.all()

    # Build receipts list
    receipts_list = []
    for r in receipts:
        receipts_list.append({
            "date_received": str(r.date_received),
            "coupon_id": r.coupon_id,
            "user_id": r.user_id,
            "merchant_id": r.merchant_id,
            "is_redeemed": r.is_redeemed or False,
            "distance": r.distance or 0,
            "discount_rate": r.discount_rate or ""
        })

    # Return result
    result = {
        "total_count": len(receipts_list),
        "days": days,
        "start_date": str(start_date),
        "end_date": str(end_date),
        "receipts": receipts_list
    }

    if merchant_id:
        result["merchant_id"] = merchant_id

    if user_id:
        result["user_id"] = user_id

    return result