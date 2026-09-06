# ============================================================
# Project Repository（含里程碑）
# ============================================================
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.project import Project, ProjectMilestone
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

    def stats_by_project(self, user_id: str, project_ids: list[str]) -> dict[str, dict]:
        """一次 GROUP BY 拿到所有项目的任务统计（列表页避免 N+2 条 COUNT）"""
        result = {
            pid: {"task_count": 0, "completed_count": 0, "progress": 0}
            for pid in project_ids
        }
        if not project_ids:
            return result
        rows = self.db.execute(
            select(Task.project_id, Task.status).where(Task.project_id.in_(project_ids))
        ).all()
        for pid, status in rows:
            stats = result[pid]
            stats["task_count"] += 1
            if status == "completed":
                stats["completed_count"] += 1
        for stats in result.values():
            if stats["task_count"] > 0:
                stats["progress"] = round(
                    stats["completed_count"] / stats["task_count"] * 100
                )
        return result

    def tasks_by_status(self, project_id: str) -> dict[str, int]:
        """项目内任务按状态分布（一条 GROUP BY）"""
        rows = self.db.execute(
            select(Task.status, func.count(Task.id))
            .where(Task.project_id == project_id)
            .group_by(Task.status)
        ).all()
        return {status: int(count) for status, count in rows}

    def completions_by_day(self, project_id: str, day_bounds: list) -> dict:
        """项目任务完成时间分布（内存按日分桶，避免 SQLite 按日函数差异）。

        day_bounds: [(date_str, start_utc, end_utc), ...]
        返回 {date_str: completed_count}
        """
        rows = self.db.execute(
            select(Task.completed_at).where(
                Task.project_id == project_id,
                Task.status == "completed",
                Task.completed_at.is_not(None),
            )
        ).scalars().all()
        result = {d[0]: 0 for d in day_bounds}
        for completed_at in rows:
            for date_str, start, end in day_bounds:
                if start <= completed_at < end:
                    result[date_str] += 1
                    break
        return result

    def count_overdue(self, project_id: str, today) -> int:
        from datetime import date as _date
        return int(
            self.db.execute(
                select(func.count(Task.id)).where(
                    Task.project_id == project_id,
                    Task.status != "completed",
                    Task.due_date.is_not(None),
                    Task.due_date < today,
                )
            ).scalar() or 0
        )


class MilestoneRepository(BaseRepository[ProjectMilestone]):
    model = ProjectMilestone

    def list_by_project(self, project_id: str) -> list[ProjectMilestone]:
        q = (
            select(ProjectMilestone)
            .where(ProjectMilestone.project_id == project_id)
            .order_by(ProjectMilestone.sort_order, ProjectMilestone.created_at)
        )
        return list(self.db.scalars(q))
