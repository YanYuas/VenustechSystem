# ============================================================
# 项目记忆 Repository（二期 M10）
# 继承 BaseRepository，扩展模块特定查询
# ============================================================
from __future__ import annotations

from sqlalchemy import func, select

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

    # ---------- D-06 收口新增 ----------

    def identity_counts(self, user_id: str) -> dict[str, int]:
        """按身份分组计数（跳过未归类）。"""
        q = (
            select(ProjectMemory.identity_id, func.count())
            .where(
                ProjectMemory.user_id == user_id,
                ProjectMemory.identity_id.is_not(None),
            )
            .group_by(ProjectMemory.identity_id)
        )
        return {rid: int(count) for rid, count in self.db.execute(q).all()}

    def count_identity_unassigned(self, user_id: str) -> int:
        q = select(func.count()).select_from(ProjectMemory).where(
            ProjectMemory.user_id == user_id,
            ProjectMemory.identity_id.is_(None),
        )
        return int(self.db.scalar(q) or 0)

    def clear_identity(self, identity_id: str) -> None:
        """把某身份的引用清回「未归类」（身份软删除时用；只 flush）。"""
        self.nullify("identity_id", identity_id=identity_id)

