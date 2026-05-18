"""Agent tools package.

This package contains data query tools used by the Agent system
to gather evidence for decision-making. Each tool returns JSON-serializable
output suitable for LLM Tool Calling.
"""

import logging
from typing import Any
from sqlalchemy.orm import Session

from app.agents.tools.merchant_metrics_tool import get_merchant_metrics
from app.agents.tools.coupon_conversion_tool import get_coupon_conversion
from app.agents.tools.user_metrics_tool import get_user_metrics
from app.agents.tools.recent_receipts_tool import get_recent_receipts
from app.agents.tools.prediction_summary_tool import get_prediction_summary
from app.agents.tools.campaign_simulation_tool import simulate_campaign_effect

logger = logging.getLogger(__name__)


# Tool registry for Agent orchestration
AVAILABLE_TOOLS = {
    "get_merchant_metrics": {
        "function": get_merchant_metrics,
        "description": "Get merchant metrics including redeem rates, receipt counts, "
                       "discount depth, and activity health score. Returns structured "
                       "evidence items.",
        "parameters": {
            "merchant_id": "Merchant ID to query (required)",
        },
    },
    "get_coupon_conversion": {
        "function": get_coupon_conversion,
        "description": "Get coupon conversion metrics for a merchant or specific coupon, "
                       "including conversion rates, timing analysis, and discount strategy.",
        "parameters": {
            "coupon_id": "Coupon ID to query (optional)",
            "merchant_id": "Merchant ID to query all coupons (optional)",
        },
    },
    "get_user_metrics": {
        "function": get_user_metrics,
        "description": "Get user engagement metrics including receipt counts, "
                       "redeemed rates, distance preference, and activity level.",
        "parameters": {
            "user_id": "User ID to query (required)",
        },
    },
    "get_recent_receipts": {
        "function": get_recent_receipts,
        "description": "Get recent receipt events for a merchant or user, "
                       "showing recent coupon distribution and redemption status.",
        "parameters": {
            "merchant_id": "Merchant ID to query (optional)",
            "user_id": "User ID to query (optional)",
            "days": "Number of recent days to query (default: 7)",
            "limit": "Maximum receipts to return (default: 20)",
        },
    },
    # M4 High Standard: New tools for enhanced analysis
    "get_prediction_summary": {
        "function": get_prediction_summary,
        "description": "Get ML prediction summary including redeem probability, "
                       "confidence interval, and signal classification. "
                       "Provides structured evidence for Agent decisions.",
        "parameters": {
            "merchant_id": "Merchant ID to query (optional)",
            "user_id": "User ID to query (optional)",
            "coupon_id": "Coupon ID to query (optional)",
        },
    },
    "simulate_campaign_effect": {
        "function": simulate_campaign_effect,
        "description": "Simulate campaign adjustment effects including expected "
                       "redeem rate change, volume impact, and risk assessment. "
                       "Supports discount changes, targeting, distribution adjustments.",
        "parameters": {
            "merchant_id": "Merchant ID to simulate (required)",
            "adjustment_type": "Type of adjustment: change_discount, adjust_target_users, "
                              "pause_distribution, increase_distribution, "
                              "reduce_discount_depth, send_reminder",
            "adjustment_params": "Adjustment parameters as JSON object (optional)",
        },
    },
}


def execute_tool(db: Session, tool_name: str, **kwargs) -> Any:
    """Execute a named tool with given parameters.

    Args:
        db: Database session
        tool_name: Name of the tool to execute
        **kwargs: Tool parameters

    Returns:
        Tool execution result

    Raises:
        ValueError: If tool name is invalid
    """
    if tool_name not in AVAILABLE_TOOLS:
        raise ValueError(f"Unknown tool: {tool_name}")

    tool = AVAILABLE_TOOLS[tool_name]
    function = tool["function"]

    logger.info(f"Executing tool '{tool_name}' with params: {kwargs}")

    return function(db, **kwargs)


__all__ = [
    "get_merchant_metrics",
    "get_coupon_conversion",
    "get_user_metrics",
    "get_recent_receipts",
    "get_prediction_summary",
    "simulate_campaign_effect",
    "execute_tool",
    "AVAILABLE_TOOLS",
]