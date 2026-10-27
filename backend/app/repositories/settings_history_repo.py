# ============================================================
# 设置变更历史 Repository（mod-platform P2 · D-06 收口）
#
# 每次 PUT /settings 记一条（key / 旧值 / 新值），保留最近 200 条。
# 敏感值在写入前已由 service 脱敏（mask_value），本层不感知。
# ============================================================
from __future__ import annotations

from sqlalchemy import delete, func, select

from app.models.settings_history import SettingHistory
from app.repositories.base import BaseRepository


class SettingHistoryRepository(BaseRepository[SettingHistory]):
    """设置变更历史。"""

    model = SettingHistory

    def add_entry(
        self,
        *,
        user_id: str,
        key: str,
        old_value: str | None,
        new_value: str | None,
    ) -> SettingHistory:
        """追加一条变更历史（只 flush）。"""
        return self.create(
            user_id=user_id,
            key=key,
            old_value=old_value,
            new_value=new_value,
        )

    def count_user(self, user_id: str) -> int:
        return int(
            self.db.scalar(
                select(func.count())
                .select_from(SettingHistory)
                .where(SettingHistory.user_id == user_id)
            )
            or 0
        )

    def trim(self, user_id: str, keep: int) -> None:
        """只保留最近 keep 条（超出即删最旧）；一条 SQL 删除，只 flush。"""
        total = self.count_user(user_id)
        if total <= keep:
            return
        stale = list(
            self.db.scalars(
                select(SettingHistory.id)
                .where(SettingHistory.user_id == user_id)
                .order_by(SettingHistory.created_at.asc())
                .limit(total - keep)
            )
        )
        if stale:
            self.db.execute(
                delete(SettingHistory).where(SettingHistory.id.in_(stale))
            )
            self.db.flush()

    def list_user(self, user_id: str, limit: int = 50) -> list[SettingHistory]:
        """最近 N 条变更历史（新→旧，排除软删除）。"""
        q = (
            select(SettingHistory)
            .where(
                SettingHistory.user_id == user_id,
                SettingHistory.deleted_at.is_(None),
            )
            .order_by(SettingHistory.created_at.desc())
            .limit(limit)
        )
        return list(self.db.scalars(q))
