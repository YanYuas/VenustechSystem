# ============================================================
# 任务服务（CRUD + 状态机 + 今日最重要互斥 + 子任务 + 统计）
# 对齐 PRD §8 / 架构 v2.0 §8.1 状态机
# ============================================================
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from app.core.event_bus import EVENT_TASK_COMPLETED, EVENT_TASK_CREATED, event_bus
from app.core.exceptions import NotFoundException, TaskStateException
from app.models.base import utcnow
from app.models.task import Task
from app.repositories import SubtaskRepository, TaskRepository
from app.schemas.common import PaginatedData
from app.schemas.task import (
    CreateSubtaskRequest,
    CreateTaskRequest,
    FocusTaskOut,
    SubtaskOut,
    TaskDetailOut,
    TaskOut,
    TodayStatsOut,
    UpdateSubtaskRequest,
    UpdateTaskRequest,
)

# 状态流转白名单（PRD §8.4）：key=当前状态 → 允许到达的状态
STATUS_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"in_progress", "waiting", "completed"},
    "in_progress": {"completed", "waiting", "pending"},
    "waiting": {"in_progress", "pending", "completed"},
    "completed": {"pending"},
}

VALID_PRIORITIES = {"low", "medium", "high", "urgent"}

# 状态 → 首页「阶段」展示（PRD FocusTask.stage）
STAGE_LABELS = {
    "pending": "待办",
    "in_progress": "进行中",
    "waiting": "等待中",
    "completed": "已完成",
}

NEXT_STEP_LABELS = {
    "pending": "点击开始任务",
    "in_progress": "继续推进",
    "waiting": "等待外部条件",
    "completed": "任务已完成",
}


class TaskService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = TaskRepository(db)
        self.sub_repo = SubtaskRepository(db)

    # ---------- 内部工具 ----------
    @staticmethod
    def _to_out(task: Task) -> TaskOut:
        subs = list(task.subtasks or [])
        total = len(subs)
        done = sum(1 for s in subs if s.completed)
        progress = round(done / total * 100) if total else (100 if task.status == "completed" else 0)
        return TaskOut(
            id=task.id,
            title=task.title,
            description=task.description,
            status=task.status,
            priority=task.priority,
            project_tag=task.project_tag,
            project_id=task.project_id,
            project_name=task.project.name if task.project else None,
            due_date=task.due_date,
            is_focus=task.is_focus,
            progress=progress,
            subtasks_count=total,
            subtasks_completed=done,
            completed_at=task.completed_at,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )

    @staticmethod
    def _to_focus_out(task: Task) -> FocusTaskOut:
        return FocusTaskOut(
            id=task.id,
            title=task.title,
            project_tag=task.project_tag,
            project_id=task.project_id,
            stage=STAGE_LABELS.get(task.status, task.status),
            progress=TaskService._to_out(task).progress,
            next_step=NEXT_STEP_LABELS.get(task.status, ""),
            status=task.status,
        )

    def _owned(self, task_id: str, user_id: str) -> Task:
        task = self.repo.get(task_id)
        if task is None or task.user_id != user_id:
            raise NotFoundException("任务不存在")
        return task

    @staticmethod
    def _apply_status(task: Task, new_status: str) -> bool:
        """应用状态流转。返回是否刚变为 completed（供提交后发布事件）。"""
        if new_status not in STATUS_TRANSITIONS.get(task.status, set()):
            raise TaskStateException(f"不能从 {task.status} 流转到 {new_status}")
        became_completed = False
        if new_status == "completed":
            task.status = "completed"
            task.completed_at = utcnow()
            became_completed = True
        elif task.status == "completed" and new_status != "completed":
            task.status = new_status
            task.completed_at = None
        else:
            task.status = new_status
        return became_completed
        # 注意：EVENT_TASK_COMPLETED 不在此发布——数据尚未 commit，
        # 事件处理器用独立 Session 会读不到；改由 update() 在 commit 后发布

    # ---------- 任务 CRUD ----------
    def list(
        self,
        user_id: str,
        status: str | None = None,
        priority: str | None = None,
        project_tag: str | None = None,
        project_id: str | None = None,
        due_date: date | None = None,
        page: int = 1,
        page_size: int = 20,
        sort: str = "-created_at",
    ) -> PaginatedData[TaskOut]:
        skip = (page - 1) * page_size
        tasks = self.repo.list_paginated(
            user_id, status=status, priority=priority, project_tag=project_tag,
            project_id=project_id, due_date=due_date, sort=sort, skip=skip, limit=page_size,
        )
        total = self.repo.count(
            user_id=user_id, status=status, priority=priority,
            project_tag=project_tag, project_id=project_id, due_date=due_date,
        )
        items = [self._to_out(t) for t in tasks]
        return PaginatedData(list=items, total=total, page=page, page_size=page_size)

    def create(self, user_id: str, data: CreateTaskRequest) -> TaskOut:
        priority = data.priority if (data.priority and data.priority in VALID_PRIORITIES) else "medium"
        task = self.repo.create(
            user_id=user_id,
            title=data.title,
            description=data.description,
            status=data.status or "pending",
            priority=priority,
            project_tag=data.project_tag,
            project_id=data.project_id,
            due_date=data.due_date,
        )
        event_bus.publish(EVENT_TASK_CREATED, task_id=task.id)
        return self._to_out(task)

    def detail(self, user_id: str, task_id: str) -> TaskDetailOut:
        task = self._owned(task_id, user_id)
        out = self._to_out(task)
        subtasks = [
            SubtaskOut(
                id=s.id, task_id=s.task_id, title=s.title, completed=s.completed,
                sort_order=s.sort_order, created_at=s.created_at, updated_at=s.updated_at,
            )
            for s in (task.subtasks or [])
        ]
        return TaskDetailOut(**out.model_dump(), subtasks=subtasks)

    # 允许更新的字段白名单（防越权修改 user_id / is_focus 等）
    _UPDATABLE_FIELDS = {"title", "description", "priority", "project_tag", "project_id", "due_date", "sort_order"}

    def update(self, user_id: str, task_id: str, data: UpdateTaskRequest) -> TaskOut:
        task = self._owned(task_id, user_id)
        payload = data.model_dump(exclude_unset=True)
        became_completed = False
        if "status" in payload:
            became_completed = self._apply_status(task, payload.pop("status"))
        for key, value in payload.items():
            if key in self._UPDATABLE_FIELDS:
                setattr(task, key, value)
        self.db.commit()
        self.db.refresh(task)
        # 事件在 commit 后发布：处理器用独立 Session，未提交数据读不到
        if became_completed:
            event_bus.publish(EVENT_TASK_COMPLETED, task_id=task.id)
        return self._to_out(task)

    def delete(self, user_id: str, task_id: str) -> None:
        task = self._owned(task_id, user_id)
        self.repo.delete(task)

    # ---------- 今日最重要（互斥） ----------
    def set_focus(self, user_id: str, task_id: str) -> TaskOut:
        task = self._owned(task_id, user_id)
        existing = self.repo.get_focus(user_id)
        if existing and existing.id != task_id:
            existing.is_focus = False
            self.db.flush()  # 先落 UPDATE 旧焦点，满足部分唯一索引后再置新焦点
        task.is_focus = True
        self.db.commit()
        self.db.refresh(task)
        return self._to_out(task)

    def cancel_focus(self, user_id: str, task_id: str) -> TaskOut:
        task = self._owned(task_id, user_id)
        task.is_focus = False
        self.db.commit()
        self.db.refresh(task)
        return self._to_out(task)

    def focus(self, user_id: str) -> FocusTaskOut | None:
        task = self.repo.get_focus(user_id)
        return self._to_focus_out(task) if task else None

    def today_stats(self, user_id: str) -> TodayStatsOut:
        today = date.today()
        return TodayStatsOut(
            must_do=self.repo.count_due_today_open(user_id, today),
            in_progress=self.repo.count_by_status(user_id, "in_progress"),
            waiting=self.repo.count_by_status(user_id, "waiting"),
            completed_today=self.repo.count_completed_on(user_id, today),
        )

    # ---------- 子任务 ----------
    def add_subtask(self, user_id: str, task_id: str, data: CreateSubtaskRequest) -> SubtaskOut:
        task = self._owned(task_id, user_id)
        max_order = max((s.sort_order for s in (task.subtasks or [])), default=-1)
        sub = self.sub_repo.create(
            task_id=task.id, title=data.title, sort_order=max_order + 1
        )
        return self._subtask_out(sub)

    def update_subtask(self, user_id: str, task_id: str, sub_id: str, data: UpdateSubtaskRequest) -> SubtaskOut:
        self._owned(task_id, user_id)
        sub = self.sub_repo.get(sub_id)
        if sub is None or sub.task_id != task_id:
            raise NotFoundException("子任务不存在")
        payload = data.model_dump(exclude_unset=True)
        for key, value in payload.items():
            setattr(sub, key, value)
        self.db.commit()
        self.db.refresh(sub)
        return self._subtask_out(sub)

    def delete_subtask(self, user_id: str, task_id: str, sub_id: str) -> None:
        self._owned(task_id, user_id)
        sub = self.sub_repo.get(sub_id)
        if sub is None or sub.task_id != task_id:
            raise NotFoundException("子任务不存在")
        self.sub_repo.delete(sub)

    @staticmethod
    def _subtask_out(sub) -> SubtaskOut:
        return SubtaskOut(
            id=sub.id, task_id=sub.task_id, title=sub.title, completed=sub.completed,
            sort_order=sub.sort_order, created_at=sub.created_at, updated_at=sub.updated_at,
        )
