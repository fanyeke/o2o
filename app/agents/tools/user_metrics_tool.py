"""User metrics query tool for Agent decision-making.

This tool queries user-level metrics from the feature layer and returns
JSON-serializable output suitable for LLM Tool Calling.

Output format:
{
  "user_id": "xxx",
  "total_receipts_30d": 10,
  "redeemed_count_30d": 5,
  "redeemed_rate_30d": 0.50,
  "avg_distance": 2.5,
  "last_receipt_date": "2016-06-30",
  "evidence": [
    {"type": "engagement", "content": "..."},
    {"type": "conversion", "content": "..."}
  ]
}
"""

from typing import Dict, Any
from sqlalchemy.orm import Session
from app.domain.feature.user_metrics import UserMetrics


def get_user_metrics(db: Session, user_id: str) -> Dict[str, Any]:
    """Query user-level metrics and return JSON-formatted evidence.

    Args:
        db: Database session
        user_id: User ID to query

    Returns:
        JSON-serializable dict with user metrics and evidence.

    Example:
        >>> result = get_user_metrics(db, user_id="user_001")
        >>> assert "user_id" in result
        >>> assert len(result["evidence"]) >= 2
    """
    user = db.query(UserMetrics).filter(
        UserMetrics.user_id == user_id
    ).first()

    # Handle missing user
    if not user:
        return {
            "error": f"User '{user_id}' not found in feature metrics",
            "user_id": user_id
        }

    # Build metrics dict
    metrics = {
        "user_id": user.user_id,
        "total_receipts_30d": user.total_receipts_30d or 0,
        "redeemed_count_30d": user.redeemed_count_30d or 0,
        "redeemed_rate_30d": user.redeemed_rate_30d or 0.0,
        "avg_distance": user.avg_distance or 0.0,
        "last_receipt_date": str(user.last_receipt_date) if user.last_receipt_date else None,
        "updated_at": str(user.updated_at) if user.updated_at else None
    }

    # Build evidence list (at least 2 items)
    evidence = []

    # Evidence 1: Engagement level
    if metrics["total_receipts_30d"] > 5:
        evidence.append({
            "type": "engagement",
            "content": f"用户活跃度较高: 近30日领券{metrics['total_receipts_30d']}张"
        })
    else:
        evidence.append({
            "type": "engagement",
            "content": f"用户活跃度一般: 近30日领券{metrics['total_receipts_30d']}张"
        })

    # Evidence 2: Conversion performance
    evidence.append({
        "type": "conversion",
        "content": f"核销率: {metrics['redeemed_rate_30d']:.2%} (已核销{metrics['redeemed_count_30d']}/{metrics['total_receipts_30d']}张)"
    })

    # Evidence 3: Distance preference (optional)
    if metrics["avg_distance"] > 0:
        evidence.append({
            "type": "distance_preference",
            "content": f"平均距离档位: {metrics['avg_distance']:.1f}档"
        })

    return {
        **metrics,
        "evidence": evidence
    }