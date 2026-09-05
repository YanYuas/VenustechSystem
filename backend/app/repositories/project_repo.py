# ============================================================
# Project Repository
# ============================================================
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.task import Task
from app.repositories.base import BaseRepository


class ProjectRepository(BaseRepository[Project]):
    model = Project

    def list_by_user(self, user_id: str, include_archived: bool = False) -> list[Project]:
        stmt = select(Project).where(Project.user_id == user_id)
        if not include_archived:
            stmt = stmt.where(Project.status != "archived")
        stmt = stmt.order_by(Project.sort_order, Project.created_at.desc())
        return list(self.db.execute(stmt).scalars().all())

    def get_by_id(self, user_id: str, project_id: str) -> Project | None:
        stmt = select(Project).where(Project.id == project_id, Project.user_id == user_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_task_stats(self, project_id: str) -> dict:
        """获取项目的任务统计"""
        total = self.db.execute(
            select(func.count(Task.id)).where(Task.project_id == project_id)
        ).scalar() or 0
        completed = self.db.execute(
            select(func.count(Task.id)).where(
                Task.project_id == project_id, Task.status == "completed"
            )
        ).scalar() or 0
        progress = round((completed / total) * 100) if total > 0 else 0
        return {"task_count": total, "completed_count": completed, "progress": progress}
