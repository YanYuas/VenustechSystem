# ============================================================
# 第二分身 Repository（二期 P1）
# ============================================================
from __future__ import annotations

from sqlalchemy import func, select

from app.repositories.base import BaseRepository
from app.models.avatar import AvatarMemory, AvatarInspiration, AvatarConfig


class AvatarMemoryRepository(BaseRepository[AvatarMemory]):
    """第二分身记忆 数据访问层"""
    model = AvatarMemory

    def list_by_type(self, user_id: str, memory_type: str) -> list[AvatarMemory]:
        return self.list(user_id=user_id, memory_type=memory_type)

    # ---------- D-06 收口新增（经历视图 / 报告 / 身份引用清理） ----------

    def list_by_user(self, user_id: str, limit: int = 100) -> list[AvatarMemory]:
        return self.list(user_id=user_id, limit=limit)

    def count_by_user(self, user_id: str) -> int:
        return self.count(user_id=user_id)

    def identity_counts(self, user_id: str) -> dict[str, int]:
        """按身份分组计数（跳过未归类）。"""
        q = (
            select(AvatarMemory.identity_id, func.count())
            .where(
                AvatarMemory.user_id == user_id,
                AvatarMemory.identity_id.is_not(None),
            )
            .group_by(AvatarMemory.identity_id)
        )
        return {rid: int(count) for rid, count in self.db.execute(q).all()}

    def count_identity_unassigned(self, user_id: str) -> int:
        q = select(func.count()).select_from(AvatarMemory).where(
            AvatarMemory.user_id == user_id,
            AvatarMemory.identity_id.is_(None),
        )
        return int(self.db.scalar(q) or 0)

    def clear_identity(self, identity_id: str) -> None:
        """把某身份的引用清回「未归类」（身份软删除时用；只 flush）。"""
        self.nullify("identity_id", identity_id=identity_id)


class AvatarInspirationRepository(BaseRepository[AvatarInspiration]):
    """第二分身灵感 数据访问层"""
    model = AvatarInspiration

    def list_by_batch(self, batch_id: str) -> list[AvatarInspiration]:
        return self.list(batch_id=batch_id)


class AvatarConfigRepository(BaseRepository[AvatarConfig]):
    """第二分身配置 数据访问层"""
    model = AvatarConfig

    def get_by_user(self, user_id: str) -> AvatarConfig | None:
        results = self.list(user_id=user_id, limit=1)
        return results[0] if results else None
