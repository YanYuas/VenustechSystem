# ============================================================
# 模板库 Repository（二期 M7）
# 继承 BaseRepository，扩展模块特定查询
# ============================================================
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.resource import Template


class TemplateRepository(BaseRepository[Template]):
    """模板库 数据访问层"""
    model = Template

    def list_by_user(self, user_id: str, skip: int = 0, limit: int = 100) -> list[Template]:
        return self.list(skip=skip, limit=limit, user_id=user_id)

    def count_by_user(self, user_id: str) -> int:
        return self.count(user_id=user_id)

    def list_by_category(self, user_id: str, category: str) -> list[Template]:
        return self.list(user_id=user_id, category=category)

    def list_builtin(self) -> list[Template]:
        return self.list(is_builtin=True)

