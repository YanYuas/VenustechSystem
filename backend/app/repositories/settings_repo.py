# ============================================================
# settings 键值配置 Repository（PRD §15.11）
# ------------------------------------------------------------
# 为什么单独建这个 repo：
#   settings 表是 (user_id, key) 唯一的键值表，写入语义是 upsert 而非
#   insert。BaseRepository.create() 每次都直接 INSERT，重复保存同一个
#   开关会撞 UniqueConstraint。因此把「存在即更新、不存在才插入」收敛
#   在 Repository 层，Service 只管业务语义（默认值 / 白名单 / 类型转换）。
# ============================================================
from __future__ import annotations

from sqlalchemy import select

from app.models.settings import Setting
from app.repositories.base import BaseRepository


class SettingRepository(BaseRepository[Setting]):
    model = Setting

    def list_user(self, user_id: str) -> list[Setting]:
        """列出用户全部配置行。

        显式过滤 deleted_at：W3 已为 settings 补上软删除字段，虽然软删除语义
        尚未全局启用，但这里提前过滤可避免「删掉的开关被重新读出来」。
        """
        q = (
            select(Setting)
            .where(Setting.user_id == user_id, Setting.deleted_at.is_(None))
            .order_by(Setting.key)
        )
        return list(self.db.scalars(q))

    def get_by_key(self, user_id: str, key: str) -> Setting | None:
        q = select(Setting).where(
            Setting.user_id == user_id,
            Setting.key == key,
            Setting.deleted_at.is_(None),
        )
        return self.db.scalar(q)

    def upsert(self, user_id: str, key: str, value: str | None) -> Setting:
        """写入一条配置（存在则更新，不存在则插入，软删除则复活）。

        注意：查询时不带 deleted_at 过滤，是为了能命中「同名但已软删除」的
        历史行并把它复活，否则会因唯一约束冲突直接报错。
        """
        row = self.db.scalar(
            select(Setting).where(Setting.user_id == user_id, Setting.key == key)
        )
        if row is None:
            return self.create(user_id=user_id, key=key, value=value)
        row.value = value
        if row.deleted_at is not None:
            row.deleted_at = None
        self.db.commit()
        self.db.refresh(row)
        return row
