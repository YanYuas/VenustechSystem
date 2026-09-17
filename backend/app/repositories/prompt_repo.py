# ============================================================
# Prompt模板 Repository（二期 M10）
# 继承 BaseRepository，扩展模块特定查询
# ============================================================
from __future__ import annotations

from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.asset import PromptTemplate


class PromptRepository(BaseRepository[PromptTemplate]):
    """Prompt模板 数据访问层"""
    model = PromptTemplate

    def list_by_user(self, user_id: str, skip: int = 0, limit: int = 100) -> list[PromptTemplate]:
        return self.list(skip=skip, limit=limit, user_id=user_id)

    def count_by_user(self, user_id: str) -> int:
        return self.count(user_id=user_id)

    def list_by_category(self, user_id: str, category: str) -> list[PromptTemplate]:
        return self.list(user_id=user_id, category=category)

