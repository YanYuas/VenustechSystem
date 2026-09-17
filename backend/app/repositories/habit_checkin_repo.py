# ============================================================
# 习惯打卡 Repository（二期 M9）
# 继承 BaseRepository，扩展模块特定查询
# ============================================================
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.life import HabitCheckin


class HabitCheckinRepository(BaseRepository[HabitCheckin]):
    """习惯打卡 数据访问层"""
    model = HabitCheckin

    def list_by_user(self, user_id: str, skip: int = 0, limit: int = 100) -> list[HabitCheckin]:
        return self.list(skip=skip, limit=limit, user_id=user_id)

    def count_by_user(self, user_id: str) -> int:
        return self.count(user_id=user_id)

    def list_by_habit(self, habit_id: str) -> list[HabitCheckin]:
        return self.list(habit_id=habit_id)

    def get_by_date(self, habit_id: str, checkin_date) -> HabitCheckin | None:
        q = select(HabitCheckin).where(
            HabitCheckin.habit_id == habit_id,
            HabitCheckin.checkin_date == checkin_date,
        )
        return self.db.scalar(q)

