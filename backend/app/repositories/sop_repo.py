# ============================================================
# SOP Repository（二期 M10）
# 继承 BaseRepository，扩展模块特定查询
# ============================================================
from __future__ import annotations

from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.asset import SOP


class SOPRepository(BaseRepository[SOP]):
    """SOP 数据访问层"""
    model = SOP

    def list_by_user(self, user_id: str, skip: int = 0, limit: int = 100) -> list[SOP]:
        return self.list(skip=skip, limit=limit, user_id=user_id)

    def count_by_user(self, user_id: str) -> int:
        return self.count(user_id=user_id)

    def list_by_category(self, user_id: str, category: str) -> list[SOP]:
        return self.list(user_id=user_id, category=category)

