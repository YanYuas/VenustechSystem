# ============================================================
# 桌宠 Repository（二期 P1）
# ============================================================
from __future__ import annotations

from app.repositories.base import BaseRepository
from app.models.pet import PetConfig, PetAvatar


class PetConfigRepository(BaseRepository[PetConfig]):
    """桌宠配置 数据访问层"""
    model = PetConfig

    def get_by_user(self, user_id: str) -> PetConfig | None:
        results = self.list(user_id=user_id, limit=1)
        return results[0] if results else None


class PetAvatarRepository(BaseRepository[PetAvatar]):
    """桌宠形象 数据访问层"""
    model = PetAvatar

    def list_by_user(self, user_id: str) -> list[PetAvatar]:
        return self.list(user_id=user_id)

    def get_active(self, user_id: str) -> PetAvatar | None:
        results = self.list(user_id=user_id, is_active=True, limit=1)
        return results[0] if results else None
