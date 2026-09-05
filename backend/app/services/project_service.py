# ============================================================
# Project Service
# ============================================================
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.project import Project
from app.repositories.project_repo import ProjectRepository
from app.schemas.project import ProjectCreate, ProjectUpdate


class ProjectService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = ProjectRepository(db)

    def list(self, user_id: str, include_archived: bool = False) -> list[dict]:
        projects = self.repo.list_by_user(user_id, include_archived)
        result = []
        for p in projects:
            stats = self.repo.get_task_stats(p.id)
            result.append(self._to_dict(p, stats))
        return result

    def get(self, user_id: str, project_id: str) -> dict | None:
        p = self.repo.get_by_id(user_id, project_id)
        if not p:
            return None
        stats = self.repo.get_task_stats(p.id)
        return self._to_dict(p, stats)

    def create(self, user_id: str, data: ProjectCreate) -> dict:
        p = Project(user_id=user_id, **data.model_dump())
        self.db.add(p)
        self.db.commit()
        self.db.refresh(p)
        return self._to_dict(p, {"task_count": 0, "completed_count": 0, "progress": 0})

    def update(self, user_id: str, project_id: str, data: ProjectUpdate) -> dict | None:
        p = self.repo.get_by_id(user_id, project_id)
        if not p:
            return None
        update_data = data.model_dump(exclude_unset=True)
        for k, v in update_data.items():
            setattr(p, k, v)
        self.db.commit()
        self.db.refresh(p)
        stats = self.repo.get_task_stats(p.id)
        return self._to_dict(p, stats)

    def delete(self, user_id: str, project_id: str) -> bool:
        p = self.repo.get_by_id(user_id, project_id)
        if not p:
            return False
        # 解除任务关联（不删除任务）
        from app.models.task import Task
        from sqlalchemy import update
        self.db.execute(update(Task).where(Task.project_id == project_id).values(project_id=None))
        self.db.delete(p)
        self.db.commit()
        return True

    def _to_dict(self, p: Project, stats: dict) -> dict:
        return {
            "id": p.id,
            "user_id": p.user_id,
            "name": p.name,
            "description": p.description,
            "color": p.color,
            "status": p.status,
            "due_date": p.due_date.isoformat() if p.due_date else None,
            "sort_order": p.sort_order,
            "task_count": stats["task_count"],
            "completed_count": stats["completed_count"],
            "progress": stats["progress"],
            "created_at": p.created_at.isoformat() if p.created_at else "",
            "updated_at": p.updated_at.isoformat() if p.updated_at else "",
        }
