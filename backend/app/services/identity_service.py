# ============================================================
# 身份服务（三期 B 阶段 · 横切标签）
#
# 设计要点（三期规划 §4，勿改方向）：
#   1. 身份上限 12 个 —— 超了说明该合并而不是新建（§4.5）。
#   2. slug 唯一（user 内），创建后**不可改**：它是筛选器/路由的稳定键，
#      改名走 name，slug 变更会打断所有按 slug 的引用。
#   3. color_token 只接受设计令牌名，拒绝 # 开头（设计令牌唯一来源
#      variables.scss；schema 层 pattern + 这里双保险）。
#   4. 归档（is_active=False）而非删除：历史记录仍挂在其上。
#      删除走软删除（SoftDeleteMixin），同样不留悬空引用 —— 悬空
#      identity_id 在读取端表现为「未归类」，可接受。
# ============================================================
from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.core.exceptions import BusinessException, NotFoundException, ValidationException
from app.models.base import utcnow
from app.models.identity import Identity
from app.repositories import IdentityRepository
from app.schemas.identity import CreateIdentityRequest, IdentityOut, UpdateIdentityRequest

MAX_IDENTITIES = 12

# 设计令牌白名单：与 frontend/src/styles/variables.scss 的色板令牌一一对应
# （primary/mint/butter/sky/lilac/strawberry/gold）。新增主题色后在此登记。
ALLOWED_COLOR_TOKENS = {
    "primary", "mint", "butter", "sky", "lilac", "strawberry", "gold",
}

SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class IdentityService:
    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id
        self.repo = IdentityRepository(db)

    # ---------- 读 ----------

    def list(self, include_archived: bool = True) -> list[IdentityOut]:
        rows = self.repo.list_user(self.user_id, include_archived=include_archived)
        return [self._out(r) for r in rows]

    def get(self, identity_id: str) -> IdentityOut:
        return self._out(self._get_owned(identity_id))

    # ---------- 写 ----------

    def create(self, data: CreateIdentityRequest) -> IdentityOut:
        self._validate_color(data.color_token)

        if self.repo.count_user(self.user_id) >= MAX_IDENTITIES:
            raise BusinessException(f"身份数量已达上限（{MAX_IDENTITIES} 个），该合并而不是新建")
        if self.repo.get_by_slug(self.user_id, data.slug) is not None:
            raise BusinessException(f"slug 已存在: {data.slug}")

        row = self.repo.create(
            user_id=self.user_id,
            name=data.name.strip(),
            slug=data.slug,
            color_token=data.color_token,
            icon=data.icon,
            description=data.description,
            sort_order=data.sort_order,
        )
        return self._out(row)

    def update(self, identity_id: str, data: UpdateIdentityRequest) -> IdentityOut:
        row = self._get_owned(identity_id)
        if data.color_token is not None:
            self._validate_color(data.color_token)
            row.color_token = data.color_token
        if data.name is not None:
            row.name = data.name.strip()
        if data.icon is not None:
            row.icon = data.icon
        if data.description is not None:
            row.description = data.description
        if data.sort_order is not None:
            row.sort_order = data.sort_order
        if data.is_active is not None:
            row.is_active = data.is_active
        self.db.commit()
        self.db.refresh(row)
        return self._out(row)

    def delete(self, identity_id: str) -> dict:
        """软删除身份，并把 8 张业务表的引用清回「未归类」。

        为什么清引用：悬空 identity_id 会让记录在「按身份」和「未归类」
        两个视图里都不可见（identity_id 非空但身份已删）——两不靠比
        归错类更糟。文档口径一直是"悬空读作未归类"，那就把数据真的
        变成未归类，读取端无需任何特判。
        """
        from sqlalchemy import update as sa_update

        from app.models.asset import ProjectMemory
        from app.models.avatar import AvatarMemory
        from app.models.document import Document
        from app.models.life import Diary
        from app.models.project import Project
        from app.models.resource import InboxItem
        from app.models.review import Review
        from app.models.task import Task
        from app.models.vault import VaultItem
        from app.models.workspace import WorkspaceRoot

        row = self._get_owned(identity_id)
        # 10 处引用全部清回「未归类」（含保险箱凭据与工作区根 ——
        # 漏掉任何一处，前端就会显示一个查无此身份的悬空标签）
        for model in (
            Task, Project, Document, Diary, Review,
            AvatarMemory, ProjectMemory, InboxItem, VaultItem, WorkspaceRoot,
        ):
            self.db.execute(
                sa_update(model)
                .where(model.identity_id == identity_id)
                .values(identity_id=None)
            )
        row.deleted_at = utcnow()
        self.db.commit()
        return {"deleted": True, "id": identity_id}

    # ---------- 内部 ----------

    def _get_owned(self, identity_id: str) -> Identity:
        row = self.repo.get(identity_id)
        if row is None or row.user_id != self.user_id or row.deleted_at is not None:
            raise NotFoundException("身份不存在")
        return row

    @staticmethod
    def _validate_color(token: str) -> None:
        if token.startswith("#"):
            raise ValidationException("color_token 必须是设计令牌名，不允许 # 色值")
        if not SLUG_PATTERN.match(token):
            raise ValidationException(f"非法的 color_token: {token}")
        if token not in ALLOWED_COLOR_TOKENS:
            raise ValidationException(f"未登记的设计令牌: {token}（先在 ALLOWED_COLOR_TOKENS 登记）")

    @staticmethod
    def _out(r: Identity) -> IdentityOut:
        return IdentityOut(
            id=r.id, name=r.name, slug=r.slug, color_token=r.color_token,
            icon=r.icon, description=r.description, sort_order=r.sort_order,
            is_active=r.is_active, created_at=r.created_at, updated_at=r.updated_at,
        )
