"""Repository for decision case data access.

Task: T118, T121 - Repository layer for case search
Phase: 6 - US4 案例检索功能
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import and_
from sqlalchemy.orm import Session
from app.domain.application.decision_case import DecisionCase


class DecisionCaseRepository:
    """决策案例数据访问层"""

    def __init__(self, db: Session):
        """初始化仓储.

        Args:
            db: 数据库会话
        """
        self.db = db

    def list_cases(
        self,
        status: Optional[str] = None,
        case_type: Optional[str] = None,
        merchant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        created_after: Optional[datetime] = None,
        created_before: Optional[datetime] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[DecisionCase], int]:
        """查询案例列表，支持多条件筛选.

        Args:
            status: 案例状态筛选
            case_type: 案例类型筛选
            merchant_id: 商户ID筛选（T118）
            user_id: 用户ID筛选
            created_after: 创建时间起始筛选（T117）
            created_before: 创建时间结束筛选（T117）
            limit: 返回数量限制
            offset: 分页偏移

        Returns:
            案例列表和总数
        """
        query = self.db.query(DecisionCase)

        # 构建筛选条件
        filters = []
        if status:
            filters.append(DecisionCase.status == status)
        if case_type:
            filters.append(DecisionCase.case_type == case_type)
        if merchant_id:
            filters.append(DecisionCase.merchant_id == merchant_id)
        if user_id:
            filters.append(DecisionCase.user_id == user_id)
        if created_after:
            filters.append(DecisionCase.created_at >= created_after)
        if created_before:
            filters.append(DecisionCase.created_at <= created_before)

        if filters:
            query = query.filter(and_(*filters))

        # 获取总数
        total = query.count()

        # 分页和排序
        cases = (
            query.order_by(DecisionCase.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )

        return cases, total

    def get_case_by_id(self, case_id: int) -> Optional[DecisionCase]:
        """根据ID获取案例详情.

        Args:
            case_id: 案例ID

        Returns:
            案例对象，不存在则返回None
        """
        return self.db.query(DecisionCase).filter(DecisionCase.id == case_id).first()

    def search_by_merchant(
        self,
        merchant_id: str,
        status: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[DecisionCase], int]:
        """按商户ID高效检索案例（T118）.

        Args:
            merchant_id: 商户ID
            status: 可选的状态筛选
            limit: 返回数量限制
            offset: 分页偏移

        Returns:
            案例列表和总数

        Note:
            此方法利用 idx_merchant_status 索引优化查询性能
        """
        query = self.db.query(DecisionCase).filter(
            DecisionCase.merchant_id == merchant_id
        )

        if status:
            query = query.filter(DecisionCase.status == status)

        total = query.count()

        # 使用索引 idx_merchant_status 进行优化查询
        cases = (
            query.order_by(DecisionCase.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )

        return cases, total