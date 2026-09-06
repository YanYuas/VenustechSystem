# ============================================================
# 知识卡片 Repository（二期 M8）
# 继承 BaseRepository，扩展模块特定查询
# ============================================================
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.learning import Flashcard


class FlashcardRepository(BaseRepository[Flashcard]):
    """知识卡片 数据访问层"""
    model = Flashcard

    def list_by_user(self, user_id: str, skip: int = 0, limit: int = 100) -> list[Flashcard]:
        return self.list(skip=skip, limit=limit, user_id=user_id)

    def count_by_user(self, user_id: str) -> int:
        return self.count(user_id=user_id)

    def list_due_today(self, user_id: str, today) -> list[Flashcard]:
        q = select(Flashcard).where(
            Flashcard.user_id == user_id,
            Flashcard.next_review <= today,
        ).order_by(Flashcard.next_review)
        return list(self.db.scalars(q))

    def count_due_today(self, user_id: str, today) -> int:
        from sqlalchemy import func
        q = select(func.count()).select_from(Flashcard).where(
            Flashcard.user_id == user_id,
            Flashcard.next_review <= today,
        )
        return int(self.db.scalar(q))

