"""Merchant metrics query tool for Agent decision-making.

This tool queries merchant metrics from the feature layer and returns
JSON-serializable output suitable for LLM Tool Calling.

Output format:
{
  "merchant_id": "xxx",
  "metrics": {
    "total_receipts_7d": 100,
    "redeemed_rate_7d": 0.45,
    ...
  },
  "evidence": [
    {"type": "metric", "content": "..."},
    {"type": "trend", "content": "..."},
    {"type": "health", "content": "..."}
  ]
}
"""

from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.domain.feature.merchant_metrics import MerchantMetrics


def get_merchant_metrics(
    db: Session,
    merchant_id: str
) -> Dict[str, Any]:
    """Query merchant metrics and return JSON-formatted evidence.

    Args:
        db: Database session
        merchant_id: Merchant ID to query

    Returns:
        JSON-serializable dict with merchant metrics and evidence items.
        If merchant not found, returns error JSON.

    Example:
        >>> result = get_merchant_metrics(db, "merchant_001")
        >>> assert "merchant_id" in result
        >>> assert len(result["evidence"]) >= 3
    """
    # Query merchant metrics
    merchant = db.query(MerchantMetrics).filter(
        MerchantMetrics.merchant_id == merchant_id
    ).first()

    # Handle missing merchant
    if not merchant:
        return {
            "error": f"Merchant '{merchant_id}' not found in feature metrics",
            "merchant_id": merchant_id
        }

    # Build metrics dict
    metrics = {
        "total_receipts_7d": merchant.total_receipts_7d or 0,
        "redeemed_count_7d": merchant.redeemed_count_7d or 0,
        "redeemed_rate_7d": merchant.redeemed_rate_7d or 0.0,
        "total_receipts_30d": merchant.total_receipts_30d or 0,
        "redeemed_count_30d": merchant.redeemed_count_30d or 0,
        "redeemed_rate_30d": merchant.redeemed_rate_30d or 0.0,
        "redeemed_rate_change": merchant.redeemed_rate_change or 0.0,
        "avg_discount_depth": merchant.avg_discount_depth or 0.0,
        "activity_health_score": merchant.activity_health_score or 0.0,
        "last_activity_date": str(merchant.last_activity_date) if merchant.last_activity_date else None,
        "updated_at": str(merchant.updated_at) if merchant.updated_at else None
    }

    # Build evidence list (at least 3 items)
    evidence = []

    # Evidence 1: Metric anomaly (redeemed rate change)
    if metrics["redeemed_rate_change"] != 0.0:
        change_pct = metrics["redeemed_rate_change"] * 100
        evidence.append({
            "type": "metric_anomaly",
            "content": f"核销率变化: 近7日核销率较30日基线变化 {change_pct:.1f}%"
        })

    # Evidence 2: Receipt volume trend
    evidence.append({
        "type": "receipt_volume",
        "content": f"发券量趋势: 近7日发券 {metrics['total_receipts_7d']} 张, 近30日发券 {metrics['total_receipts_30d']} 张"
    })

    # Evidence 3: Redemption performance
    evidence.append({
        "type": "redemption_performance",
        "content": f"核销表现: 近7日核销率 {metrics['redeemed_rate_7d']:.2%}, 近30日核销率 {metrics['redeemed_rate_30d']:.2%}"
    })

    # Evidence 4: Discount depth (optional, if available)
    if metrics["avg_discount_depth"] > 0:
        evidence.append({
            "type": "discount_strategy",
            "content": f"平均折扣深度: {metrics['avg_discount_depth']:.2%}"
        })

    # Evidence 5: Activity health (optional)
    if metrics["activity_health_score"] > 0:
        health_level = "健康" if metrics["activity_health_score"] > 0.7 else "警告" if metrics["activity_health_score"] > 0.5 else "异常"
        evidence.append({
            "type": "health_status",
            "content": f"活动健康分: {metrics['activity_health_score']:.2f} ({health_level})"
        })

    # Return result
    return {
        "merchant_id": merchant_id,
        "metrics": metrics,
        "evidence": evidence
    }