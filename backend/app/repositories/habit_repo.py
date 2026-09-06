# ============================================================
# 习惯 Repository（二期 M9）
# 继承 BaseRepository，扩展模块特定查询
# ============================================================
from __future__ import annotations

from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.life import Habit


class HabitRepository(BaseRepository[Habit]):
    """习惯 数据访问层"""
    model = Habit

    def list_by_user(self, user_id: str, skip: int = 0, limit: int = 100) -> list[Habit]:
        return self.list(skip=skip, limit=limit, user_id=user_id)

    def count_by_user(self, user_id: str) -> int:
        return self.count(user_id=user_id)

    def list_active(self, user_id: str) -> list[Habit]:
        return self.list(user_id=user_id, status="active")

