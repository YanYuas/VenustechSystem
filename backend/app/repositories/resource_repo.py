# ============================================================
# 资源中心 Repository（二期 M7）
# 继承 BaseRepository，扩展模块特定查询
# ============================================================
from __future__ import annotations

from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.resource import InboxItem, Template, Domain


class InboxItemRepository(BaseRepository[InboxItem]):
    """资源中心 数据访问层"""
    model = InboxItem

    def list_by_user(self, user_id: str, skip: int = 0, limit: int = 100) -> list[InboxItem]:
        return self.list(skip=skip, limit=limit, user_id=user_id)

    def count_by_user(self, user_id: str) -> int:
        return self.count(user_id=user_id)

    def list_pending(self, user_id: str) -> list[InboxItem]:
        return self.list(user_id=user_id, status="pending")

    def list_processed(self, user_id: str) -> list[InboxItem]:
        return self.list(user_id=user_id, status="processed")

