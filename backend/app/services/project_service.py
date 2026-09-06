# ============================================================
# Project Service（M06 深度开发：CRUD + 归档恢复 + 统计 + 里程碑 + 详情聚合）
# ============================================================
from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundException, ValidationException
from app.core.utils import local_day_bounds_utc
from app.models.base import utcnow
from app.models.conversation import Conversation
from app.models.document import Document
from app.models.project import Project, ProjectMilestone
from app.models.review import Review
from app.models.task import Task
from app.repositories.project_repo import MilestoneRepository, ProjectRepository
from app.schemas.project import (
    MilestoneCreate,
    MilestoneOut,
    MilestoneUpdate,
    ProjectCreate,
    ProjectStatsOut,
    ProjectUpdate,
)

_VALID_STATUS = {"active", "archived", "completed"}


class ProjectService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = ProjectRepository(db)
        self.milestone_repo = MilestoneRepository(db)

    # ---------- 基础 CRUD ----------

    def list(self, user_id: str, include_archived: bool = False) -> list[dict]:
        projects = self.repo.list_by_user(user_id, include_archived)
        # 一次 GROUP BY 批量取统计（避免每项目 2 条 COUNT 的 N+1）
        stats_map = self.repo.stats_by_project(user_id, [p.id for p in projects])
        return [
            self._to_dict(p, stats_map.get(p.id, {"task_count": 0, "completed_count": 0, "progress": 0}))
            for p in projects
        ]

    def get(self, user_id: str, project_id: str) -> dict | None:
        p = self._owned(user_id, project_id)
        stats = self.repo.get_task_stats(p.id)
        return self._to_dict(p, stats)

    def create(self, user_id: str, data: ProjectCreate) -> dict:
        if data.status and data.status not in _VALID_STATUS:
            raise ValidationException(f"无效的项目状态: {data.status}")
        p = Project(user_id=user_id, **data.model_dump())
        self.db.add(p)
        self.db.commit()
        self.db.refresh(p)
        return self._to_dict(p, {"task_count": 0, "completed_count": 0, "progress": 0})

    def update(self, user_id: str, project_id: str, data: ProjectUpdate) -> dict | None:
        p = self._owned(user_id, project_id)
        update_data = data.model_dump(exclude_unset=True)
        if "status" in update_data and update_data["status"] not in _VALID_STATUS:
            raise ValidationException(f"无效的项目状态: {update_data['status']}")
        for k, v in update_data.items():
            setattr(p, k, v)
        self.db.commit()
        self.db.refresh(p)
        stats = self.repo.get_task_stats(p.id)
        return self._to_dict(p, stats)

    def delete(self, user_id: str, project_id: str) -> bool:
        p = self._owned(user_id, project_id)
        # 解除任务/文档/对话/复盘关联（不删除内容）
        from sqlalchemy import update as sa_update
        for model in (Task, Document, Conversation, Review):
            self.db.execute(
                sa_update(model).where(model.project_id == project_id).values(project_id=None)
            )
        self.db.delete(p)
        self.db.commit()
        return True

    # ---------- 归档 / 恢复（M06 F04） ----------

    def archive(self, user_id: str, project_id: str) -> dict:
        return self._set_status(user_id, project_id, "archived")

    def restore(self, user_id: str, project_id: str) -> dict:
        return self._set_status(user_id, project_id, "active")

    def _set_status(self, user_id: str, project_id: str, status: str) -> dict:
        p = self._owned(user_id, project_id)
        p.status = status
        self.db.commit()
        self.db.refresh(p)
        return self._to_dict(p, self.repo.get_task_stats(p.id))

    # ---------- 项目统计（M06 F02） ----------

    def stats(self, user_id: str, project_id: str) -> ProjectStatsOut:
        p = self._owned(user_id, project_id)
        today = date.today()

        # 基础统计
        base = self.repo.get_task_stats(p.id)
        distribution = self.repo.tasks_by_status(p.id)
        overdue = self.repo.count_overdue(p.id, today)

        # 近7天完成趋势（completed_at 为 UTC，本地日边界换算）
        day_bounds = []
        for offset in range(6, -1, -1):
            d = today - timedelta(days=offset)
            start, end = local_day_bounds_utc(d)
            day_bounds.append((d.isoformat(), start, end))
        by_day = self.repo.completions_by_day(p.id, day_bounds)
        weekly_trend = [{"date": d, "completed": by_day[d]} for d, _, _ in day_bounds]

        # 里程碑统计
        milestones = self.milestone_repo.list_by_project(p.id)
        milestone_completed = sum(1 for m in milestones if m.completed)

        # 健康度：逾期>0 → risk；进度落后于时间 → warning；否则 good
        health = "good"
        if overdue > 0:
            health = "risk"
        elif p.due_date and p.due_date >= today:
            total_days = (p.due_date - p.created_at.date()).days or 1
            elapsed = (today - p.created_at.date()).days
            expected = elapsed / total_days
            if base["progress"] / 100 < expected * 0.6:
                health = "warning"

        return ProjectStatsOut(
            task_count=base["task_count"],
            completed_count=base["completed_count"],
            progress=base["progress"],
            status_distribution=distribution,
            weekly_trend=weekly_trend,
            overdue_count=overdue,
            milestone_count=len(milestones),
            milestone_completed=milestone_completed,
            health=health,
        )

    # ---------- 项目详情聚合（M06 F01） ----------

    def detail(self, user_id: str, project_id: str) -> dict:
        """项目详情：基础信息 + 统计 + 任务/文档/对话/复盘/里程碑列表（各取前50）。"""
        p = self._owned(user_id, project_id)
        result = self.get(user_id, project_id)

        def _iso(v):
            return v.isoformat() if v else None

        # 任务（按状态→优先级排序）
        tasks = self.db.scalars(
            select(Task)
            .where(Task.project_id == project_id)
            .order_by(Task.status, Task.priority.desc(), Task.created_at.desc())
            .limit(100)
        ).all()
        result["tasks"] = [
            {
                "id": t.id, "title": t.title, "status": t.status, "priority": t.priority,
                "due_date": _iso(t.due_date), "is_focus": t.is_focus,
                "completed_at": _iso(t.completed_at), "created_at": _iso(t.created_at),
            }
            for t in tasks
        ]

        # 文档（列表卡片字段，不拉 content 大字段）
        docs = self.db.execute(
            select(Document.id, Document.title, Document.updated_at, Document.tags, Document.word_count)
            .where(Document.project_id == project_id)
            .order_by(Document.updated_at.desc())
            .limit(50)
        ).all()
        result["documents"] = [
            {
                "id": d.id, "title": d.title, "updated_at": _iso(d.updated_at),
                "tags": d.tags or [], "word_count": d.word_count,
            }
            for d in docs
        ]

        # 对话
        convs = self.db.scalars(
            select(Conversation)
            .where(Conversation.project_id == project_id)
            .order_by(Conversation.updated_at.desc())
            .limit(50)
        ).all()
        result["conversations"] = [
            {"id": c.id, "title": c.title or "未命名对话", "updated_at": _iso(c.updated_at)}
            for c in convs
        ]

        # 复盘
        reviews = self.db.scalars(
            select(Review)
            .where(Review.project_id == project_id)
            .order_by(Review.review_date.desc())
            .limit(50)
        ).all()
        result["reviews"] = [
            {
                "id": r.id, "type": r.type, "review_date": r.review_date.isoformat(),
                "mood": (r.data or {}).get("mood"), "summary": (r.data or {}).get("gains", "")[:80],
            }
            for r in reviews
        ]

        # 里程碑
        result["milestones"] = [
            self._milestone_to_dict(m) for m in self.milestone_repo.list_by_project(project_id)
        ]
        return result

    # ---------- 里程碑 CRUD（M06 F03） ----------

    def list_milestones(self, user_id: str, project_id: str) -> list[dict]:
        self._owned(user_id, project_id)
        return [
            self._milestone_to_dict(m)
            for m in self.milestone_repo.list_by_project(project_id)
        ]

    def create_milestone(self, user_id: str, project_id: str, data: MilestoneCreate) -> dict:
        self._owned(user_id, project_id)
        m = ProjectMilestone(project_id=project_id, **data.model_dump())
        self.db.add(m)
        self.db.commit()
        self.db.refresh(m)
        return self._milestone_to_dict(m)

    def update_milestone(self, user_id: str, milestone_id: str, data: MilestoneUpdate) -> dict:
        m = self._owned_milestone(user_id, milestone_id)
        payload = data.model_dump(exclude_unset=True)
        # 勾选完成时补 completed_at
        if payload.get("completed") is True and not m.completed:
            m.completed_at = utcnow()
        elif payload.get("completed") is False:
            m.completed_at = None
        for k, v in payload.items():
            setattr(m, k, v)
        self.db.commit()
        self.db.refresh(m)
        return self._milestone_to_dict(m)

    def delete_milestone(self, user_id: str, milestone_id: str) -> None:
        m = self._owned_milestone(user_id, milestone_id)
        self.db.delete(m)
        self.db.commit()

    # ---------- 内部 ----------

    def _owned(self, user_id: str, project_id: str) -> Project:
        p = self.repo.get_by_id(user_id, project_id)
        if not p:
            raise NotFoundException("项目不存在")
        return p

    def _owned_milestone(self, user_id: str, milestone_id: str) -> ProjectMilestone:
        m = self.milestone_repo.get(milestone_id)
        if m is None:
            raise NotFoundException("里程碑不存在")
        # 校验归属：里程碑 → 项目 → 用户
        project = self.repo.get_by_id(user_id, m.project_id)
        if project is None:
            raise NotFoundException("里程碑不存在")
        return m

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

    def _milestone_to_dict(self, m: ProjectMilestone) -> dict:
        return {
            "id": m.id,
            "project_id": m.project_id,
            "name": m.name,
            "description": m.description,
            "target_date": m.target_date.isoformat() if m.target_date else None,
            "completed": m.completed,
            "completed_at": m.completed_at.isoformat() if m.completed_at else None,
            "task_ids": m.task_ids or [],
            "sort_order": m.sort_order,
            "created_at": m.created_at.isoformat() if m.created_at else "",
            "updated_at": m.updated_at.isoformat() if m.updated_at else "",
        }
