from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import joinedload, selectinload

from app.core.utils import local_day_bounds_utc
from app.models.task import Subtask, Task
from app.repositories.base import BaseRepository

# 允许排序的字段白名单（防注入）
_SORT_COLUMNS = {
    "created_at": Task.created_at,
    "updated_at": Task.updated_at,
    "due_date": Task.due_date,
    "priority": Task.priority,
    "status": Task.status,
    "title": Task.title,
    "sort_order": Task.sort_order,
}


class TaskRepository(BaseRepository[Task]):
    model = Task

    def list_user_tasks(
        self,
        user_id: str,
        status: str | None = None,
        priority: str | None = None,
        project_tag: str | None = None,
        project_id: str | None = None,
        due_date: date | None = None,
    ) -> list[Task]:
        """全量查询（用于内存分组/统计，数据量小时使用）。"""
        q = select(Task).where(Task.user_id == user_id)
        if status:
            q = q.where(Task.status == status)
        if priority:
            q = q.where(Task.priority == priority)
        if project_tag:
            q = q.where(Task.project_tag == project_tag)
        if due_date:
            q = q.where(Task.due_date == due_date)
        return list(self.db.scalars(q))

    def list_paginated(
        self,
        user_id: str,
        status: str | None = None,
        priority: str | None = None,
        project_tag: str | None = None,
        project_id: str | None = None,
        due_date: date | None = None,
        sort: str = "-created_at",
        skip: int = 0,
        limit: int = 20,
    ) -> list[Task]:
        """SQL 层排序+分页（列表页专用，性能优先）。"""
        # 预加载 subtasks/project：序列化要访问这两个关系，懒加载会造成每行 2 条 SQL 的 N+1
        q = (
            select(Task)
            .options(selectinload(Task.subtasks), joinedload(Task.project))
            .where(Task.user_id == user_id)
        )
        if status:
            q = q.where(Task.status == status)
        if priority:
            q = q.where(Task.priority == priority)
        if project_tag:
            q = q.where(Task.project_tag == project_tag)
        if due_date:
            q = q.where(Task.due_date == due_date)
        # 排序：-前缀=降序
        asc = not sort.startswith("-")
        col = _SORT_COLUMNS.get(sort.lstrip("-"), Task.created_at)
        q = q.order_by(col.asc() if asc else col.desc())
        q = q.offset(skip).limit(limit)
        return list(self.db.scalars(q))

    def count_by_status(self, user_id: str, status: str) -> int:
        return self.count(user_id=user_id, status=status)

    def count_due_today_open(self, user_id: str, today: date) -> int:
        q = (
            select(func.count())
            .select_from(Task)
            .where(
                Task.user_id == user_id,
                Task.due_date == today,
                Task.status != "completed",
            )
        )
        return int(self.db.scalar(q))

    def count_completed_on(self, user_id: str, day: date) -> int:
        # completed_at 存 naive UTC，本地日期边界须换算成 UTC 再比较（否则错位一个时区）
        start, end = local_day_bounds_utc(day)
        q = (
            select(func.count())
            .select_from(Task)
            .where(
                Task.user_id == user_id,
                Task.status == "completed",
                Task.completed_at >= start,
                Task.completed_at < end,
            )
        )
        return int(self.db.scalar(q))

    def get_focus(self, user_id: str) -> Task | None:
        return self.db.scalar(
            select(Task).where(Task.user_id == user_id, Task.is_focus.is_(True))
        )


class SubtaskRepository(BaseRepository[Subtask]):
    model = Subtask
