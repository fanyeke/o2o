"""
Pydantic schemas for API request/response validation.

Phase 2 - API & Integration Layer
"""

from app.schemas.approvals import (
    ApprovalCallbackRequest,
    ApprovalCallbackResponse,
)
from app.schemas.cases import (
    ActionExecutionItem,
    ApprovalLogItem,
    DecisionCaseDetailResponse,
    DecisionCaseListResponse,
    DecisionCaseResponse,
    EvidenceItem,
    RecommendationResponse,
    SuggestedAction,
)
from app.schemas.metrics import (
    CouponMetricsData,
    CouponMetricsResponse,
    MerchantMetricsData,
    MerchantMetricsResponse,
    UserMetricsData,
    UserMetricsResponse,
)
from app.schemas.rules import RuleScanRequest, RuleScanResponse

__all__ = [
    # Metrics schemas
    "MerchantMetricsData",
    "MerchantMetricsResponse",
    "UserMetricsData",
    "UserMetricsResponse",
    "CouponMetricsData",
    "CouponMetricsResponse",
    # Cases schemas
    "DecisionCaseResponse",
    "DecisionCaseListResponse",
    "DecisionCaseDetailResponse",
    "EvidenceItem",
    "SuggestedAction",
    "RecommendationResponse",
    "ApprovalLogItem",
    "ActionExecutionItem",
    # Approvals schemas
    "ApprovalCallbackRequest",
    "ApprovalCallbackResponse",
    # Rules schemas
    "RuleScanRequest",
    "RuleScanResponse",
]