"""
Decision cases schemas for API request/response validation.

Task: T019
Phase: 2 - API & Integration Layer
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class DecisionCaseResponse(BaseModel):
    """决策案例列表响应"""

    id: int = Field(..., ge=1, description="案例ID")
    case_type: str = Field(..., description="案例类型（商户异常/券策略复核/用户召回）")
    severity_level: str = Field(..., description="严重级别（高/中/低）")
    merchant_id: Optional[str] = Field(None, description="商户ID（可选）")
    trigger_rule_id: str = Field(..., description="触发规则ID")
    status: str = Field(
        ...,
        description="案例状态（pending/recommended/approved/rejected/executed）",
    )
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")


class DecisionCaseListResponse(BaseModel):
    """决策案例列表查询响应"""

    total: int = Field(..., ge=0, description="总记录数")
    limit: int = Field(default=20, ge=1, le=1000, description="返回数量限制")
    offset: int = Field(default=0, ge=0, description="分页偏移")
    data: list[DecisionCaseResponse] = Field(..., description="案例列表")


class EvidenceItem(BaseModel):
    """证据项"""

    type: str = Field(..., description="证据类型（指标异常/券策略问题/历史对比）")
    content: str = Field(..., description="证据内容")


class SuggestedAction(BaseModel):
    """建议行动"""

    action_type: str = Field(..., description="行动类型（暂停活动/调整策略/召回用户）")
    params: dict[str, Any] = Field(..., description="行动参数")
    risk_level: str = Field(..., description="风险级别（高/中/低）")


class RecommendationResponse(BaseModel):
    """Agent建议响应"""

    id: int = Field(..., ge=1, description="建议ID")
    summary: str = Field(..., description="建议摘要")
    evidence_list: list[EvidenceItem] = Field(..., description="证据列表")
    suggested_actions: list[SuggestedAction] = Field(..., description="建议行动列表")
    risk_alerts: str = Field(..., description="风险提示")
    confidence_score: float = Field(
        ..., ge=0.0, le=1.0, description="置信度分数（0-1）"
    )
    requires_approval: bool = Field(..., description="是否需要审批")
    created_at: datetime = Field(..., description="创建时间")


class ApprovalLogItem(BaseModel):
    """审批记录项"""

    operator_name: str = Field(..., description="审批人姓名")
    action: str = Field(..., description="审批动作（approve/reject）")
    comment: str = Field(..., description="审批意见")
    created_at: datetime = Field(..., description="审批时间")


class ActionExecutionItem(BaseModel):
    """行动执行记录项"""

    action_type: str = Field(..., description="行动类型")
    execution_status: str = Field(
        ..., description="执行状态（success/failed/pending）"
    )
    executed_at: datetime = Field(..., description="执行时间")


class DecisionCaseDetailResponse(BaseModel):
    """决策案例详情响应"""

    id: int = Field(..., ge=1, description="案例ID")
    case_type: str = Field(..., description="案例类型")
    severity_level: str = Field(..., description="严重级别")
    merchant_id: Optional[str] = Field(None, description="商户ID")
    trigger_rule_id: str = Field(..., description="触发规则ID")
    trigger_metrics_snapshot: dict[str, Any] = Field(
        ..., description="触发时指标快照"
    )
    status: str = Field(..., description="案例状态")
    recommendation: Optional[RecommendationResponse] = Field(
        None, description="Agent建议"
    )
    approval_logs: list[ApprovalLogItem] = Field(
        default_factory=list, description="审批记录"
    )
    action_executions: list[ActionExecutionItem] = Field(
        default_factory=list, description="行动执行记录"
    )
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")


class ApprovalRequest(BaseModel):
    """审批请求"""

    operator_id: str = Field(..., description="审批人ID")
    operator_name: Optional[str] = Field(None, description="审批人姓名")
    comment: Optional[str] = Field(None, description="审批意见")


class ApprovalResponse(BaseModel):
    """审批响应"""

    status: str = Field(..., description="处理状态（success/error）")
    message: str = Field(..., description="处理消息")
    case_id: int = Field(..., ge=1, description="案例ID")
    new_status: str = Field(..., description="新的案例状态")