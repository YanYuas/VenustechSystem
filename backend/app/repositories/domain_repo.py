# ============================================================
# 领域库 Repository（二期 M7）
# 继承 BaseRepository，扩展模块特定查询
# ============================================================
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.resource import Domain


class DomainRepository(BaseRepository[Domain]):
    """领域库 数据访问层"""
    model = Domain

    def list_by_user(self, user_id: str, skip: int = 0, limit: int = 100) -> list[Domain]:
        return self.list(skip=skip, limit=limit, user_id=user_id)

    def count_by_user(self, user_id: str) -> int:
        return self.count(user_id=user_id)

    def list_ordered(self, user_id: str) -> list[Domain]:
        q = select(Domain).where(Domain.user_id == user_id).order_by(Domain.sort_order)
        return list(self.db.scalars(q))

