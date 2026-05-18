"""Repository for approval log data access.

Task: T121 - Get approval history
Phase: 6 - US4 案例检索功能
"""

from typing import List
from sqlalchemy.orm import Session
from app.domain.application.approval_log import ApprovalLog


class ApprovalLogRepository:
    """审批记录数据访问层"""

    def __init__(self, db: Session):
        """初始化仓储.

        Args:
            db: 数据库会话
        """
        self.db = db

    def get_approval_history(self, case_id: int) -> List[ApprovalLog]:
        """获取案例的完整审批记录，按时间排序（T121）.

        Args:
            case_id: 案例ID

        Returns:
            审批记录列表，按创建时间升序排列（最早的在前）

        Note:
            此方法利用 idx_case_created 索引优化查询性能
        """
        return (
            self.db.query(ApprovalLog)
            .filter(ApprovalLog.case_id == case_id)
            .order_by(ApprovalLog.created_at.asc())
            .all()
        )