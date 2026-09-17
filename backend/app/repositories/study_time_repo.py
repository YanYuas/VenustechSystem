# ============================================================
# 学习时长 Repository（二期 M8）
# 继承 BaseRepository，扩展模块特定查询
# ============================================================
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.learning import StudyTimeLog


class StudyTimeRepository(BaseRepository[StudyTimeLog]):
    """学习时长 数据访问层"""
    model = StudyTimeLog

    def list_by_user(self, user_id: str, skip: int = 0, limit: int = 100) -> list[StudyTimeLog]:
        return self.list(skip=skip, limit=limit, user_id=user_id)

    def count_by_user(self, user_id: str) -> int:
        return self.count(user_id=user_id)

    def list_by_date_range(self, user_id: str, start_date, end_date) -> list[StudyTimeLog]:
        q = select(StudyTimeLog).where(
            StudyTimeLog.user_id == user_id,
            StudyTimeLog.logged_date >= start_date,
            StudyTimeLog.logged_date <= end_date,
        ).order_by(StudyTimeLog.logged_date)
        return list(self.db.scalars(q))

