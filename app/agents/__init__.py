"""Agent Decision System.

This module provides intelligent decision-making capabilities
for coupon operations using LLM-powered agents.
"""

# Note: decision_service is imported lazily to avoid dependency issues
# during testing. Import directly when needed:
# from app.agents.decision_service import AgentDecisionService, generate_recommendation

# Tools are safe to import without heavy dependencies
from app.agents.tools import get_merchant_metrics, get_coupon_conversion

__all__ = [
    "get_merchant_metrics",
    "get_coupon_conversion",
]