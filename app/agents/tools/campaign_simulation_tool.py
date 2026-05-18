"""Campaign effect simulation tool for Agent.

This tool simulates the expected effect of campaign adjustments,
providing structured evidence for Agent decision-making.

M4 High Standard: Required tool for comprehensive analysis grounding.
"""

import logging
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def simulate_campaign_effect(
    db: Session,
    merchant_id: str,
    adjustment_type: str,
    adjustment_params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Simulate campaign adjustment effect for Agent decision-making.

    This tool provides:
    1. Expected redeem rate change
    2. Expected volume impact
    3. Risk assessment
    4. Structured evidence for Agent output

    Args:
        db: Database session
        merchant_id: Merchant ID to simulate
        adjustment_type: Type of adjustment (e.g., 'change_discount', 'adjust_target')
        adjustment_params: Parameters for the adjustment simulation

    Returns:
        Dictionary containing simulation results and evidence
    """
    logger.info(
        f"Simulating campaign effect for merchant={merchant_id}, "
        f"type={adjustment_type}, params={adjustment_params}"
    )

    # Validate adjustment type
    valid_adjustment_types = [
        "change_discount",
        "adjust_target_users",
        "pause_distribution",
        "increase_distribution",
        "reduce_discount_depth",
        "send_reminder",
    ]

    if adjustment_type not in valid_adjustment_types:
        return {
            "error": f"Invalid adjustment_type: {adjustment_type}. "
                    f"Valid types: {valid_adjustment_types}",
            "merchant_id": merchant_id,
            "evidence": [],
        }

    # Get current merchant metrics
    try:
        from app.agents.tools.merchant_metrics_tool import get_merchant_metrics
        current_metrics = get_merchant_metrics(db, merchant_id)
    except Exception as e:
        logger.warning(f"Could not get merchant metrics: {e}, using defaults")
        current_metrics = {
            "metrics": {
                "redeemed_rate_7d": 0.15,
                "redeemed_rate_30d": 0.30,
                "total_receipts_30d": 500,
                "avg_discount_depth": 0.35,
            }
        }

    # Run simulation based on adjustment type
    simulation_result = _run_simulation(
        current_metrics=current_metrics,
        adjustment_type=adjustment_type,
        adjustment_params=adjustment_params or {},
    )

    # Generate evidence
    evidence = _generate_simulation_evidence(
        merchant_id=merchant_id,
        adjustment_type=adjustment_type,
        simulation_result=simulation_result,
        current_metrics=current_metrics,
    )

    return {
        "merchant_id": merchant_id,
        "adjustment_type": adjustment_type,
        "adjustment_params": adjustment_params or {},
        "current_metrics": current_metrics.get("metrics", {}),
        "simulation_result": simulation_result,
        "evidence": evidence,
    }


def _run_simulation(
    current_metrics: Dict[str, Any],
    adjustment_type: str,
    adjustment_params: Dict[str, Any],
) -> Dict[str, Any]:
    """Run simulation based on adjustment type.

    Args:
        current_metrics: Current merchant metrics
        adjustment_type: Type of adjustment
        adjustment_params: Adjustment parameters

    Returns:
        Simulation result dictionary
    """
    metrics = current_metrics.get("metrics", {})
    current_rate = metrics.get("redeemed_rate_7d", 0.15)
    current_volume = metrics.get("total_receipts_30d", 500)
    current_discount = metrics.get("avg_discount_depth", 0.35)

    # Simulation rules based on adjustment type
    if adjustment_type == "change_discount":
        new_discount = adjustment_params.get("new_discount", current_discount * 0.9)
        discount_change = (new_discount - current_discount) / current_discount

        # Discount reduction typically increases redeem rate
        rate_change = -discount_change * 0.5  # 50% pass-through
        expected_rate = current_rate * (1 + rate_change)

        return {
            "expected_redeem_rate": expected_rate,
            "rate_change_percent": rate_change * 100,
            "expected_volume": current_volume,  # Volume unchanged
            "volume_change_percent": 0,
            "risk_level": "medium" if abs(rate_change) > 0.1 else "low",
            "confidence": 0.75,
            "assumptions": ["线性折扣-核销率关系", "发券量不变"],
        }

    elif adjustment_type == "adjust_target_users":
        target_segment = adjustment_params.get("target_segment", "high_value")

        # Targeting high-value users increases redeem rate
        rate_boost = {"high_value": 0.15, "medium_value": 0.05, "new_users": -0.1}
        rate_change = rate_boost.get(target_segment, 0)

        expected_rate = current_rate + rate_change

        return {
            "expected_redeem_rate": expected_rate,
            "rate_change_percent": (expected_rate - current_rate) / current_rate * 100,
            "expected_volume": current_volume * 0.8,  # Narrower targeting
            "volume_change_percent": -20,
            "risk_level": "low",
            "confidence": 0.65,
            "assumptions": ["高价值用户核销率更高", "发券量减少20%"],
        }

    elif adjustment_type == "pause_distribution":
        duration_days = adjustment_params.get("duration", 7)

        return {
            "expected_redeem_rate": current_rate,  # No change
            "rate_change_percent": 0,
            "expected_volume": 0,  # Complete pause
            "volume_change_percent": -100,
            "risk_level": "high",
            "confidence": 0.90,
            "assumptions": ["完全暂停发券", "无新用户获取"],
            "warning": f"暂停{duration_days}天将导致零新发券",
        }

    elif adjustment_type == "increase_distribution":
        increase_percent = adjustment_params.get("increase_percent", 50)

        expected_volume = current_volume * (1 + increase_percent / 100)
        # More distribution typically slightly reduces rate (dilution)
        rate_change = -increase_percent * 0.01
        expected_rate = current_rate * (1 + rate_change)

        return {
            "expected_redeem_rate": expected_rate,
            "rate_change_percent": rate_change * 100,
            "expected_volume": expected_volume,
            "volume_change_percent": increase_percent,
            "risk_level": "medium",
            "confidence": 0.70,
            "assumptions": ["发券量增加", "核销率轻微下降（稀释效应）"],
        }

    elif adjustment_type == "reduce_discount_depth":
        reduction_percent = adjustment_params.get("reduction_percent", 10)

        new_discount = current_discount * (1 - reduction_percent / 100)
        # Less discount increases redeem rate
        rate_boost = reduction_percent * 0.02  # 2% rate boost per 10% discount reduction
        expected_rate = current_rate + rate_boost

        return {
            "expected_redeem_rate": expected_rate,
            "rate_change_percent": (expected_rate - current_rate) / current_rate * 100,
            "expected_volume": current_volume,
            "volume_change_percent": 0,
            "risk_level": "low",
            "confidence": 0.65,
            "assumptions": ["折扣深度降低", "发券量不变"],
        }

    elif adjustment_type == "send_reminder":
        reminder_type = adjustment_params.get("reminder_type", "push")

        # Reminders typically boost redeem rate by 5-15%
        rate_boost_map = {"push": 0.08, "sms": 0.12, "email": 0.05}
        rate_boost = rate_boost_map.get(reminder_type, 0.08)
        expected_rate = current_rate + rate_boost

        return {
            "expected_redeem_rate": expected_rate,
            "rate_change_percent": (expected_rate - current_rate) / current_rate * 100,
            "expected_volume": current_volume,
            "volume_change_percent": 0,
            "risk_level": "low",
            "confidence": 0.80,
            "assumptions": ["用户收到提醒", "核销率提升"],
        }

    else:
        return {
            "error": f"Unknown adjustment type: {adjustment_type}",
            "expected_redeem_rate": current_rate,
            "rate_change_percent": 0,
            "expected_volume": current_volume,
            "volume_change_percent": 0,
            "risk_level": "unknown",
            "confidence": 0.0,
        }


def _generate_simulation_evidence(
    merchant_id: str,
    adjustment_type: str,
    simulation_result: Dict[str, Any],
    current_metrics: Dict[str, Any],
) -> list:
    """Generate evidence from simulation result.

    Args:
        merchant_id: Merchant ID
        adjustment_type: Adjustment type
        simulation_result: Simulation result
        current_metrics: Current metrics

    Returns:
        List of evidence items
    """
    evidence = []

    metrics = current_metrics.get("metrics", {})
    current_rate = metrics.get("redeemed_rate_7d", 0)

    expected_rate = simulation_result.get("expected_redeem_rate", 0)
    rate_change = simulation_result.get("rate_change_percent", 0)
    risk_level = simulation_result.get("risk_level", "unknown")
    confidence = simulation_result.get("confidence", 0)

    # Evidence 1: Expected rate change
    evidence.append({
        "type": "simulation_rate_effect",
        "description": f"模拟核销率变化{rate_change:+.1f}%",
        "content": f"模拟调整'{adjustment_type}'后，预期核销率从{current_rate:.1%}变为{expected_rate:.1%}，变化{rate_change:+.1f}%",
        "severity": "medium" if abs(rate_change) > 10 else "low",
    })

    # Evidence 2: Volume effect
    volume_change = simulation_result.get("volume_change_percent", 0)
    expected_volume = simulation_result.get("expected_volume", 0)
    current_volume = metrics.get("total_receipts_30d", 0)

    evidence.append({
        "type": "simulation_volume_effect",
        "description": f"模拟发券量变化{volume_change:+.1f}%",
        "content": f"模拟调整后，预期发券量从{current_volume}变为{expected_volume:.0f}，变化{volume_change:+.1f}%",
        "severity": "high" if abs(volume_change) > 50 else "medium" if abs(volume_change) > 20 else "low",
    })

    # Evidence 3: Risk assessment
    evidence.append({
        "type": "simulation_risk",
        "description": f"调整风险评估：{risk_level}",
        "content": f"调整'{adjustment_type}'的风险等级评估为{risk_level}，模拟置信度{confidence:.0%}",
        "severity": risk_level if risk_level in ["high", "medium", "low"] else "medium",
    })

    return evidence