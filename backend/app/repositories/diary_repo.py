# ============================================================
# 日记 Repository（二期 M9）
# 继承 BaseRepository，扩展模块特定查询
# ============================================================
from __future__ import annotations

from sqlalchemy import func, select

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

    # ---------- D-06 收口新增（报告 / 身份引用清理） ----------

    def identity_counts(self, user_id: str) -> dict[str, int]:
        """按身份分组计数（跳过未归类）。"""
        q = (
            select(Diary.identity_id, func.count())
            .where(Diary.user_id == user_id, Diary.identity_id.is_not(None))
            .group_by(Diary.identity_id)
        )
        return {rid: int(count) for rid, count in self.db.execute(q).all()}

    def count_identity_unassigned(self, user_id: str) -> int:
        q = select(func.count()).select_from(Diary).where(
            Diary.user_id == user_id,
            Diary.identity_id.is_(None),
        )
        return int(self.db.scalar(q) or 0)

    def clear_identity(self, identity_id: str) -> None:
        """把某身份的引用清回「未归类」（身份软删除时用；只 flush）。"""
        self.nullify("identity_id", identity_id=identity_id)

