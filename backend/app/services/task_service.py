# ============================================================
# 任务服务（CRUD + 状态机 + 今日最重要互斥 + 子任务 + 统计）
# 对齐 PRD §8 / 架构 v2.0 §8.1 状态机
# ============================================================
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.event_bus import EVENT_TASK_COMPLETED, EVENT_TASK_CREATED, event_bus
from app.core.exceptions import NotFoundException, TaskStateException
from app.models.base import utcnow
from app.models.task import FocusSession, Task
from app.repositories import SubtaskRepository, TaskRepository
from app.schemas.common import PaginatedData
from app.schemas.task import (
    BatchTaskRequest,
    BatchTaskResult,
    CreateSubtaskRequest,
    CreateTaskRequest,
    FocusSessionOut,
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
            reminder_time=task.reminder_time,
            recurrence=task.recurrence,
            focus_duration=task.focus_duration or 0,
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
    def _ensure_project_active(task: Task) -> None:
        """归档项目的任务只读（M06 F04）：修改/完成前校验所属项目状态。"""
        if task.project_id is None:
            return
        project = task.project  # relationship（expire_on_commit=False 下可用）
        if project is not None and project.status == "archived":
            raise TaskStateException("所属项目已归档，任务为只读。请先恢复项目")

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
            reminder_time=data.reminder_time,
            recurrence=data.recurrence,
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
    _UPDATABLE_FIELDS = {
        "title", "description", "priority", "project_tag", "project_id",
        "due_date", "sort_order", "reminder_time", "recurrence",
    }

    def update(self, user_id: str, task_id: str, data: UpdateTaskRequest) -> TaskOut:
        task = self._owned(task_id, user_id)
        self._ensure_project_active(task)
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

    # ---------- 批量操作（M02 F07） ----------

    def batch(self, user_id: str, data: BatchTaskRequest) -> BatchTaskResult:
        affected = 0
        failed = 0
        for task_id in data.task_ids:
            try:
                task = self.repo.get(task_id)
                if task is None or task.user_id != user_id:
                    failed += 1
                    continue
                if data.action == "complete":
                    self._ensure_project_active(task)
                    if task.status != "completed":
                        self._apply_status(task, "completed")
                elif data.action == "delete":
                    self.db.delete(task)
                elif data.action == "move_project":
                    self._ensure_project_active(task)
                    task.project_id = data.project_id
                elif data.action == "set_priority":
                    if data.priority not in VALID_PRIORITIES:
                        raise TaskStateException(f"无效优先级: {data.priority}")
                    task.priority = data.priority
                affected += 1
            except Exception:
                failed += 1
        self.db.commit()
        return BatchTaskResult(affected=affected, failed=failed)

    # ---------- 番茄钟（M02 F08） ----------

    def focus_start(self, user_id: str, task_id: str) -> FocusSessionOut:
        task = self._owned(task_id, user_id)
        session = FocusSession(
            task_id=task.id, user_id=user_id, start_time=utcnow()
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return self._focus_session_out(session)

    def focus_stop(self, user_id: str, session_id: str) -> FocusSessionOut:
        session = self.db.get(FocusSession, session_id)
        if session is None or session.user_id != user_id:
            raise NotFoundException("专注会话不存在")
        if session.end_time is not None:
            raise TaskStateException("该专注会话已结束")
        session.end_time = utcnow()
        session.duration = max(
            0, int((session.end_time - session.start_time).total_seconds())
        )
        # 累计到任务总专注时长
        if session.task_id:
            task = self.repo.get(session.task_id)
            if task is not None:
                task.focus_duration = (task.focus_duration or 0) + session.duration
        self.db.commit()
        self.db.refresh(session)
        return self._focus_session_out(session)

    def focus_sessions(self, user_id: str, task_id: str) -> list[FocusSessionOut]:
        task = self._owned(task_id, user_id)
        from sqlalchemy import select as sa_select
        rows = self.db.scalars(
            sa_select(FocusSession)
            .where(FocusSession.task_id == task.id)
            .order_by(FocusSession.start_time.desc())
            .limit(50)
        )
        return [self._focus_session_out(s) for s in rows]

    @staticmethod
    def _focus_session_out(s: FocusSession) -> FocusSessionOut:
        return FocusSessionOut(
            id=s.id, task_id=s.task_id, start_time=s.start_time,
            end_time=s.end_time, duration=s.duration, note=s.note,
            created_at=s.created_at,
        )

    # ---------- 重复任务（M02 F05）：惰性生成到期实例 ----------

    def generate_recurring_instances(self, user_id: str) -> int:
        """为重复任务生成到期实例（启动/每日触发，幂等：已有当日实例不重复生成）。"""
        from sqlalchemy import select as sa_select
        today = date.today()
        templates = list(
            self.db.scalars(
                sa_select(Task).where(
                    Task.user_id == user_id,
                    Task.recurrence.is_not(None),
                )
            )
        )
        created = 0
        for t in templates:
            rule = t.recurrence or {}
            rtype = rule.get("type")
            if not rtype:
                continue
            # 目标日期：模板 due_date 或今天
            base_date = t.due_date or today
            target = self._next_occurrence(base_date, today, rtype, rule)
            if target is None:
                continue
            # 幂等：同模板同目标日已存在实例则跳过（按 title+due_date 粗粒度判重）
            exists = self.db.scalar(
                sa_select(func.count()).select_from(Task).where(
                    Task.user_id == user_id,
                    Task.title == t.title,
                    Task.due_date == target,
                )
            )
            if exists:
                continue
            self.db.add(Task(
                user_id=user_id,
                title=t.title,
                description=t.description,
                status="pending",
                priority=t.priority,
                project_tag=t.project_tag,
                project_id=t.project_id,
                due_date=target,
                recurrence=t.recurrence,
            ))
            created += 1
        if created:
            self.db.commit()
        return created

    @staticmethod
    def _next_occurrence(base_date: date, today: date, rtype: str, rule: dict) -> date | None:
        """从 base_date 推进到 ≥today 的下一次出现日；已过期的周期跳到当前周期。"""
        interval = max(1, int(rule.get("interval", 1)))
        if rtype == "daily":
            delta = (today - base_date).days
            if delta < 0:
                return base_date
            step = ((delta + interval - 1) // interval) * interval
            return base_date + timedelta(days=step)
        if rtype == "weekly":
            days = rule.get("days") or []
            # 未指定星期几则按 base_date 的星期
            weekdays = sorted({int(d) for d in days}) if days else [base_date.weekday()]
            for offset in range(0, 60):
                d = today + timedelta(days=offset)
                if d.weekday() in weekdays and d >= base_date and d >= today:
                    return d
            return None
        if rtype == "monthly":
            # 月份推进
            d = base_date
            while d < today:
                month = d.month + interval
                year = d.year + (month - 1) // 12
                month = (month - 1) % 12 + 1
                try:
                    d = date(year, month, min(base_date.day, 28))
                except ValueError:
                    d = date(year, month, 28)
            return d if d >= today else None
        return None
