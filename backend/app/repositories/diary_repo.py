# ============================================================
# 日记 Repository（二期 M9）
# 继承 BaseRepository，扩展模块特定查询
# ============================================================
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.life import Diary


class DiaryRepository(BaseRepository[Diary]):
    """日记 数据访问层"""
    model = Diary

    def list_by_user(self, user_id: str, skip: int = 0, limit: int = 100) -> list[Diary]:
        return self.list(skip=skip, limit=limit, user_id=user_id)

    def count_by_user(self, user_id: str) -> int:
        return self.count(user_id=user_id)

    def list_by_dimension(self, user_id: str, dimension: str) -> list[Diary]:
        return self.list(user_id=user_id, dimension=dimension)

    def get_by_date(self, user_id: str, diary_date) -> Diary | None:
        q = select(Diary).where(
            Diary.user_id == user_id,
            Diary.diary_date == diary_date,
        )
        return self.db.scalar(q)

