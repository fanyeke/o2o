"""Coupon conversion query tool for Agent decision-making.

This tool queries coupon conversion metrics from the feature layer and returns
JSON-serializable output suitable for LLM Tool Calling.

Output format:
{
  "coupon_id": "xxx",
  "merchant_id": "yyy",
  "conversion_metrics": {
    "discount_type": "满减",
    "redeemed_rate": 0.50,
    ...
  },
  "evidence": [
    {"type": "conversion", "content": "..."},
    {"type": "timing", "content": "..."},
    {"type": "discount", "content": "..."}
  ]
}

When querying by merchant_id, returns list of all coupons for that merchant:
{
  "merchant_id": "yyy",
  "coupons": [
    { "coupon_id": "...", "conversion_metrics": {...}, "evidence": [...] },
    ...
  ]
}
"""

from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from app.domain.feature.coupon_metrics import CouponMetrics


def get_coupon_conversion(
    db: Session,
    coupon_id: Optional[str] = None,
    merchant_id: Optional[str] = None
) -> Dict[str, Any]:
    """Query coupon conversion metrics and return JSON-formatted evidence.

    Args:
        db: Database session
        coupon_id: Specific coupon ID to query (optional)
        merchant_id: Merchant ID to query all coupons for (optional)

    Returns:
        JSON-serializable dict with coupon conversion metrics and evidence.
        If querying by coupon_id and not found, returns error JSON.
        If querying by merchant_id, returns list of coupons.

    Example:
        >>> result = get_coupon_conversion(db, coupon_id="coupon_001")
        >>> assert "coupon_id" in result
        >>> assert len(result["evidence"]) >= 3

        >>> result = get_coupon_conversion(db, merchant_id="merchant_001")
        >>> assert "coupons" in result
        >>> assert len(result["coupons"]) >= 1
    """
    # Query by coupon_id (single coupon)
    if coupon_id:
        return _get_single_coupon(db, coupon_id)

    # Query by merchant_id (multiple coupons)
    if merchant_id:
        return _get_merchant_coupons(db, merchant_id)

    # No parameters provided
    return {
        "error": "Must provide either coupon_id or merchant_id parameter",
        "coupon_id": None,
        "merchant_id": None
    }


def _get_single_coupon(db: Session, coupon_id: str) -> Dict[str, Any]:
    """Query a single coupon by ID.

    Args:
        db: Database session
        coupon_id: Coupon ID to query

    Returns:
        JSON dict with coupon metrics and evidence, or error dict if not found.
    """
    coupon = db.query(CouponMetrics).filter(
        CouponMetrics.coupon_id == coupon_id
    ).first()

    # Handle missing coupon
    if not coupon:
        return {
            "error": f"Coupon '{coupon_id}' not found in feature metrics",
            "coupon_id": coupon_id
        }

    # Build conversion metrics dict
    conversion_metrics = {
        "discount_type": coupon.discount_type or "未知",
        "discount_rate": coupon.discount_rate or "",
        "discount_value": coupon.discount_value or 0.0,
        "threshold_amount": coupon.threshold_amount or 0.0,
        "discount_amount": coupon.discount_amount or 0.0,
        "total_receipts": coupon.total_receipts or 0,
        "redeemed_count": coupon.redeemed_count or 0,
        "redeemed_rate": coupon.redeemed_rate or 0.0,
        "avg_redeem_days": coupon.avg_redeem_days or 0.0,
        "updated_at": str(coupon.updated_at) if coupon.updated_at else None
    }

    # Build evidence list (at least 3 items)
    evidence = []

    # Evidence 1: Conversion rate performance
    evidence.append({
        "type": "conversion_rate",
        "content": f"券转化率: {conversion_metrics['redeemed_rate']:.2%} (已核销 {conversion_metrics['redeemed_count']}/{conversion_metrics['total_receipts']})"
    })

    # Evidence 2: Time to redeem analysis
    evidence.append({
        "type": "redeem_timing",
        "content": f"平均核销时间: {conversion_metrics['avg_redeem_days']:.1f} 天"
    })

    # Evidence 3: Discount effectiveness
    discount_desc = ""
    if conversion_metrics["discount_type"] == "满减":
        discount_desc = f"满{conversion_metrics['threshold_amount']:.0f}减{conversion_metrics['discount_amount']:.0f}"
    elif conversion_metrics["discount_type"] == "折扣":
        discount_desc = f"{conversion_metrics['discount_rate']}折扣"
    else:
        discount_desc = f"{conversion_metrics['discount_type']}"

    evidence.append({
        "type": "discount_strategy",
        "content": f"折扣策略: {discount_desc}, 折扣深度 {conversion_metrics['discount_value']:.2%}"
    })

    # Evidence 4: Receipt volume (optional)
    if conversion_metrics["total_receipts"] > 100:
        evidence.append({
            "type": "distribution_scale",
            "content": f"发券规模较大: 共发放 {conversion_metrics['total_receipts']} 张券"
        })

    # Return result
    return {
        "coupon_id": coupon_id,
        "merchant_id": coupon.merchant_id,
        "conversion_metrics": conversion_metrics,
        "evidence": evidence
    }


def _get_merchant_coupons(db: Session, merchant_id: str) -> Dict[str, Any]:
    """Query all coupons for a specific merchant.

    Args:
        db: Database session
        merchant_id: Merchant ID to query

    Returns:
        JSON dict with list of coupons, each with metrics and evidence.
    """
    coupons = db.query(CouponMetrics).filter(
        CouponMetrics.merchant_id == merchant_id
    ).all()

    # Handle merchant with no coupons
    if not coupons:
        return {
            "error": f"No coupons found for merchant '{merchant_id}'",
            "merchant_id": merchant_id,
            "coupons": []
        }

    # Build list of coupon results
    coupons_list = []
    for coupon in coupons:
        coupon_result = _get_single_coupon(db, coupon.coupon_id)
        coupons_list.append(coupon_result)

    # Return result
    return {
        "merchant_id": merchant_id,
        "coupons": coupons_list,
        "total_coupons": len(coupons_list)
    }