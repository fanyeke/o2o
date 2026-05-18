"""
Rule scanning schemas for API request/response validation.

Task: T021
Phase: 2 - API & Integration Layer
"""

from typing import Optional

from pydantic import BaseModel, Field


class RuleScanRequest(BaseModel):
    """规则扫描请求"""

    rule_ids: Optional[list[str]] = Field(
        None, description="规则ID列表（可选，默认扫描所有规则）"
    )
    dry_run: bool = Field(
        default=False, description="试运行模式（为true时不创建案例仅返回匹配结果）"
    )


class RuleScanResponse(BaseModel):
    """规则扫描响应"""

    status: str = Field(..., description="状态（accepted）")
    message: str = Field(..., description="消息（包含任务ID）")
    task_id: str = Field(..., description="Celery任务ID")