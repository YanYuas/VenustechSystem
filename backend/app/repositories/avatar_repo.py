# ============================================================
# 第二分身 Repository（二期 P1）
# ============================================================
from __future__ import annotations

from app.repositories.base import BaseRepository
from app.models.avatar import AvatarMemory, AvatarInspiration, AvatarConfig


class AvatarMemoryRepository(BaseRepository[AvatarMemory]):
    """第二分身记忆 数据访问层"""
    model = AvatarMemory

    def list_by_type(self, user_id: str, memory_type: str) -> list[AvatarMemory]:
        return self.list(user_id=user_id, memory_type=memory_type)


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
