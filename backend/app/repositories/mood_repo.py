# ============================================================
# 心情记录 Repository（二期 M9）
# 继承 BaseRepository，扩展模块特定查询
# ============================================================
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.life import MoodLog


class MoodRepository(BaseRepository[MoodLog]):
    """心情记录 数据访问层"""
    model = MoodLog

    def list_by_user(self, user_id: str, skip: int = 0, limit: int = 100) -> list[MoodLog]:
        return self.list(skip=skip, limit=limit, user_id=user_id)

    def count_by_user(self, user_id: str) -> int:
        return self.count(user_id=user_id)

    def list_by_date_range(self, user_id: str, start_date, end_date) -> list[MoodLog]:
        q = select(MoodLog).where(
            MoodLog.user_id == user_id,
            MoodLog.logged_date >= start_date,
            MoodLog.logged_date <= end_date,
        ).order_by(MoodLog.logged_date)
        return list(self.db.scalars(q))

