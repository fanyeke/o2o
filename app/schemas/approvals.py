"""
Approval callback schemas for API request/response validation.

Task: T020
Phase: 2 - API & Integration Layer
"""

from typing import Any, Optional

from pydantic import BaseModel, Field


class ApprovalCallbackRequest(BaseModel):
    """飞书审批回调请求"""

    challenge: Optional[str] = Field(None, description="首次验证挑战码")
    type: str = Field(..., description="回调类型（card_action）")
    action: dict[str, Any] = Field(
        ...,
        description="审批动作详情（包含 value 字段，内含 case_id, action_type, operator_id, comment）",
    )
    token: str = Field(..., description="飞书 verification token")
    timestamp: int = Field(..., description="时间戳（秒级）")
    sign: str = Field(..., description="飞书签名（HMAC-SHA256）")

    # 提取 action.value 中的字段作为便捷访问属性
    @property
    def case_id(self) -> int:
        """获取案例ID"""
        return self.action.get("value", {}).get("case_id")

    @property
    def action_type(self) -> str:
        """获取审批动作类型（approve/reject）"""
        return self.action.get("value", {}).get("action_type")

    @property
    def operator_id(self) -> str:
        """获取飞书用户ID"""
        return self.action.get("value", {}).get("operator_id")

    @property
    def comment(self) -> Optional[str]:
        """获取审批意见"""
        return self.action.get("value", {}).get("comment")


class ApprovalCallbackResponse(BaseModel):
    """飞书审批回调响应"""

    status: str = Field(..., description="状态（success/error）")
    message: str = Field(..., description="消息")
    case_id: Optional[int] = Field(None, description="案例ID")
    new_status: Optional[str] = Field(None, description="新案例状态")