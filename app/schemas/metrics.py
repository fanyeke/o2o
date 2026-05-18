"""
Metrics schemas for API request/response validation.

Task: T018
Phase: 2 - API & Integration Layer
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class MerchantMetricsData(BaseModel):
    """单个商户指标数据"""

    merchant_id: str = Field(..., description="商户ID")
    total_receipts_7d: int = Field(..., ge=0, description="近7天发券总量")
    redeemed_rate_7d: float = Field(..., ge=0.0, le=1.0, description="近7天核销率")
    total_receipts_30d: Optional[int] = Field(None, ge=0, description="近30天发券总量")
    redeemed_rate_30d: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="近30天核销率"
    )
    redeemed_rate_change: float = Field(
        ..., description="核销率变化（7d vs 30d，负数表示下降）"
    )
    avg_discount_depth: float = Field(..., ge=0.0, le=1.0, description="平均折扣深度")
    activity_health_score: float = Field(
        ..., ge=0.0, le=1.0, description="活动健康度评分"
    )
    updated_at: datetime = Field(..., description="更新时间")


class MerchantMetricsResponse(BaseModel):
    """商户指标查询响应"""

    total: int = Field(..., ge=0, description="总记录数")
    limit: int = Field(default=100, ge=1, le=1000, description="返回数量限制")
    offset: int = Field(default=0, ge=0, description="分页偏移")
    data: list[MerchantMetricsData] = Field(..., description="商户指标列表")


class UserMetricsData(BaseModel):
    """单个用户指标数据"""

    user_id: str = Field(..., description="用户ID")
    total_receipts_30d: int = Field(..., ge=0, description="近30天领券总量")
    redeemed_count_30d: int = Field(..., ge=0, description="近30天核销数量")
    redeemed_rate_30d: float = Field(..., ge=0.0, le=1.0, description="近30天核销率")
    avg_distance: float = Field(..., ge=0.0, description="平均领券距离（公里）")
    last_receipt_date: str = Field(..., description="最后领券日期（YYYY-MM-DD）")
    updated_at: datetime = Field(..., description="更新时间")


class UserMetricsResponse(BaseModel):
    """用户指标查询响应"""

    total: int = Field(..., ge=0, description="总记录数")
    limit: int = Field(default=100, ge=1, le=1000, description="返回数量限制")
    offset: int = Field(default=0, ge=0, description="分页偏移")
    data: list[UserMetricsData] = Field(..., description="用户指标列表")


class CouponMetricsData(BaseModel):
    """单个优惠券指标数据"""

    coupon_id: str = Field(..., description="优惠券ID")
    merchant_id: str = Field(..., description="商户ID")
    discount_type: str = Field(..., description="券类型（满减/折扣）")
    discount_rate: str = Field(..., description="折扣率（如 '200:50'）")
    discount_value: float = Field(..., ge=0.0, le=1.0, description="折扣值")
    total_receipts: int = Field(..., ge=0, description="发券总量")
    redeemed_count: int = Field(..., ge=0, description="核销数量")
    redeemed_rate: float = Field(..., ge=0.0, le=1.0, description="核销率")
    avg_redeem_days: float = Field(..., ge=0.0, description="平均核销天数")
    updated_at: datetime = Field(..., description="更新时间")


class CouponMetricsResponse(BaseModel):
    """优惠券指标查询响应"""

    total: int = Field(..., ge=0, description="总记录数")
    data: list[CouponMetricsData] = Field(..., description="优惠券指标列表")