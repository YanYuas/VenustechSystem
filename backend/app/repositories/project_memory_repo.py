# ============================================================
# 项目记忆 Repository（二期 M10）
# 继承 BaseRepository，扩展模块特定查询
# ============================================================
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.asset import ProjectMemory


class ProjectMemoryRepository(BaseRepository[ProjectMemory]):
    """项目记忆 数据访问层"""
    model = ProjectMemory

    def list_by_user(self, user_id: str, skip: int = 0, limit: int = 100) -> list[ProjectMemory]:
        return self.list(skip=skip, limit=limit, user_id=user_id)

    def count_by_user(self, user_id: str) -> int:
        return self.count(user_id=user_id)

    def list_by_project(self, project_id: str) -> list[ProjectMemory]:
        return self.list(project_id=project_id)

