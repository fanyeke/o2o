"""Agent tools package.

This package contains data query tools used by the Agent system
to gather evidence for decision-making. Each tool returns JSON-serializable
output suitable for LLM Tool Calling.
"""

from app.agents.tools.merchant_metrics_tool import get_merchant_metrics
from app.agents.tools.coupon_conversion_tool import get_coupon_conversion

__all__ = [
    "get_merchant_metrics",
    "get_coupon_conversion",
]