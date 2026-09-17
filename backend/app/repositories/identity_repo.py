from __future__ import annotations

from sqlalchemy import select

from app.models.identity import Identity
from app.repositories.base import BaseRepository


class IdentityRepository(BaseRepository[Identity]):
    model = Identity

    def list_user(self, user_id: str, include_archived: bool = True) -> list[Identity]:
        """按 sort_order 排序返回用户的身份列表。

        软删除的行**一律排除**（deleted_at 过滤）——否则删除的身份仍会
        出现在列表/筛选器里，甚至被「按身份生成目录骨架」建出文件夹。
        默认包含归档身份（is_active=False）：归档不是删除，历史数据
        仍挂在其上，筛选器需要展示完整的身份集合（归档的灰显）。
        """
        q = (
            select(Identity)
            .where(
                Identity.user_id == user_id,
                Identity.deleted_at.is_(None),
            )
            .order_by(Identity.sort_order, Identity.created_at)
        )
        if not include_archived:
            q = q.where(Identity.is_active.is_(True))
        return list(self.db.scalars(q))

    def get_by_slug(self, user_id: str, slug: str) -> Identity | None:
        return self.db.scalar(
            select(Identity).where(
                Identity.user_id == user_id,
                Identity.slug == slug,
                Identity.deleted_at.is_(None),
            )
        )

    def count_user(self, user_id: str) -> int:
        from sqlalchemy import func
        return int(
            self.db.scalar(
                select(func.count()).select_from(Identity).where(
                    Identity.user_id == user_id,
                    Identity.deleted_at.is_(None),
                )
            )
            or 0
        )
