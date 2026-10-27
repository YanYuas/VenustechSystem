# ============================================================
# 保险箱 Repository（三期 D · D-06 收口）
#
# 两张表：
#   vault_config —— 主密码 salt + 校验器（每用户一条）
#   vault_items  —— 凭据条目（secret 只存 Fernet 密文）
#
# 事务语义：只 flush，不 commit。
# ============================================================
from __future__ import annotations

from sqlalchemy import func, select

from app.models.vault import VaultConfig, VaultItem
from app.repositories.base import BaseRepository


class VaultConfigRepository(BaseRepository[VaultConfig]):
    """保险箱配置（主密码校验器）。"""

    model = VaultConfig

    def get_by_user(self, user_id: str) -> VaultConfig | None:
        """取用户保险箱配置；未初始化返回 None。"""
        return self.db.scalar(
            select(VaultConfig).where(VaultConfig.user_id == user_id)
        )


class VaultItemRepository(BaseRepository[VaultItem]):
    """凭据条目。"""

    model = VaultItem

    def list_by_user(self, user_id: str) -> list[VaultItem]:
        """列表中元数据（按分类 + 名称排序，与展示顺序一致）。"""
        q = (
            select(VaultItem)
            .where(VaultItem.user_id == user_id)
            .order_by(VaultItem.category, VaultItem.name)
        )
        return list(self.db.scalars(q))

    def list_with_secret(self, user_id: str) -> list[VaultItem]:
        """主密码轮换用：只取真正存了密文的条目。"""
        q = (
            select(VaultItem)
            .where(
                VaultItem.user_id == user_id,
                VaultItem.secret_encrypted.is_not(None),
            )
        )
        return list(self.db.scalars(q))

    def count_by_user(self, user_id: str) -> int:
        return int(
            self.db.scalar(
                select(func.count())
                .select_from(VaultItem)
                .where(VaultItem.user_id == user_id)
            )
            or 0
        )

    def clear_identity(self, identity_id: str) -> None:
        """把某身份的引用清回「未归类」（身份软删除时用；只 flush）。"""
        self.nullify("identity_id", identity_id=identity_id)
