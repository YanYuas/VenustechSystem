from __future__ import annotations

from datetime import date

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import joinedload, selectinload

from app.core.utils import local_day_bounds_utc
from app.models.task import FocusSession, Subtask, Task
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
        if project_id:
            q = q.where(Task.project_id == project_id)
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
        identity_id: str | None = None,
        identity_unassigned: bool = False,
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
        q = self._apply_filters(
            q, status=status, priority=priority, project_tag=project_tag,
            project_id=project_id, due_date=due_date,
            identity_id=identity_id, identity_unassigned=identity_unassigned,
        )
        # 排序：-前缀=降序
        asc = not sort.startswith("-")
        col = _SORT_COLUMNS.get(sort.lstrip("-"), Task.created_at)
        q = q.order_by(col.asc() if asc else col.desc())
        q = q.offset(skip).limit(limit)
        return list(self.db.scalars(q))

    def count_paginated(
        self,
        user_id: str,
        status: str | None = None,
        priority: str | None = None,
        project_tag: str | None = None,
        project_id: str | None = None,
        due_date: date | None = None,
        identity_id: str | None = None,
        identity_unassigned: bool = False,
    ) -> int:
        """与 list_paginated 完全同源的计数（同一 _apply_filters，口径不会漂移）。"""
        q = select(func.count()).select_from(Task).where(Task.user_id == user_id)
        q = self._apply_filters(
            q, status=status, priority=priority, project_tag=project_tag,
            project_id=project_id, due_date=due_date,
            identity_id=identity_id, identity_unassigned=identity_unassigned,
        )
        return int(self.db.scalar(q))

    @staticmethod
    def _apply_filters(
        q,
        *,
        status: str | None,
        priority: str | None,
        project_tag: str | None,
        project_id: str | None,
        due_date: date | None,
        identity_id: str | None,
        identity_unassigned: bool,
    ):
        """列表/计数共用的过滤条件（身份轴过滤也在这里，三期 B）。"""
        if status:
            q = q.where(Task.status == status)
        if priority:
            q = q.where(Task.priority == priority)
        if project_tag:
            q = q.where(Task.project_tag == project_tag)
        if project_id:
            q = q.where(Task.project_id == project_id)
        if due_date:
            q = q.where(Task.due_date == due_date)
        # 身份轴（三期 B）：按身份过滤 / 只看未归类
        if identity_id:
            q = q.where(Task.identity_id == identity_id)
        if identity_unassigned:
            q = q.where(Task.identity_id.is_(None))
        return q

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

    # ---------- D-06 收口新增：供 service 用的语义化查询 ----------

    def count_user(self, user_id: str, **filters) -> int:
        """按用户计数（可带等值过滤，如 status="completed"）。"""
        return self.count(user_id=user_id, **filters)

    def list_by_project(self, project_id: str, limit: int = 100) -> list[Task]:
        """项目详情用任务列表：按状态→优先级→创建时间排序。"""
        q = (
            select(Task)
            .where(Task.project_id == project_id)
            .order_by(Task.status, Task.priority.desc(), Task.created_at.desc())
            .limit(limit)
        )
        return list(self.db.scalars(q))

    def list_all_by_project(self, project_id: str) -> list[Task]:
        """项目导出用：全量任务（不排序、不分页）。"""
        return list(self.db.scalars(select(Task).where(Task.project_id == project_id)))

    def list_completed_by_project(self, project_id: str, limit: int = 20) -> list[Task]:
        """项目时间线用：最近完成的任务（completed_at 降序，NULL 靠后）。"""
        q = (
            select(Task)
            .where(Task.project_id == project_id, Task.status == "completed")
            .order_by(Task.completed_at.desc().nullslast())
            .limit(limit)
        )
        return list(self.db.scalars(q))

    def search_by_title(self, user_id: str, keyword: str, limit: int = 10) -> list[Task]:
        """全局搜索：标题包含关键字。"""
        like = f"%{keyword}%"
        q = (
            select(Task)
            .where(Task.user_id == user_id, Task.title.like(like))
            .limit(limit)
        )
        return list(self.db.scalars(q))

    def list_recurring_templates(self, user_id: str) -> list[Task]:
        """重复任务模板（recurrence 非空）—— 惰性生成到期实例的数据源。"""
        q = select(Task).where(
            Task.user_id == user_id,
            Task.recurrence.is_not(None),
        )
        return list(self.db.scalars(q))

    def exists_instance(self, user_id: str, title: str, due_date) -> bool:
        """幂等判重：同模板同目标日是否已生成过实例（按 title + due_date 粗粒度）。"""
        q = select(func.count()).select_from(Task).where(
            Task.user_id == user_id,
            Task.title == title,
            Task.due_date == due_date,
        )
        return bool(self.db.scalar(q))

    def list_autofill_candidates(self, user_id: str, day_start, day_end, today) -> list[Task]:
        """每日复盘自动填充：今天完成的任务 + 今天到期的未完成任务。"""
        q = select(Task).where(
            Task.user_id == user_id,
            or_(
                and_(
                    Task.status == "completed",
                    Task.completed_at >= day_start,
                    Task.completed_at < day_end,
                ),
                and_(Task.status != "completed", Task.due_date == today),
            ),
        )
        return list(self.db.scalars(q))

    def count_overdue_for_user(self, user_id: str, today) -> int:
        """用户级逾期任务数（未完成且 due_date 早于今天）。"""
        q = select(func.count()).select_from(Task).where(
            Task.user_id == user_id,
            Task.status != "completed",
            Task.due_date < today,
        )
        return int(self.db.scalar(q) or 0)

    def identity_counts(self, user_id: str, completed: bool | None = None) -> dict[str, int]:
        """按身份分组计数（跳过未归类）；completed 可进一步按完成态过滤。"""
        q = select(Task.identity_id, func.count()).where(
            Task.user_id == user_id,
            Task.identity_id.is_not(None),
        )
        if completed is True:
            q = q.where(Task.status == "completed")
        elif completed is False:
            q = q.where(Task.status != "completed")
        return {
            rid: int(count)
            for rid, count in self.db.execute(q.group_by(Task.identity_id)).all()
        }

    def count_identity_unassigned(
        self, user_id: str, completed: bool | None = None
    ) -> int:
        """未归类任务数（报告「未归类」统计用）。"""
        q = select(func.count()).select_from(Task).where(
            Task.user_id == user_id,
            Task.identity_id.is_(None),
        )
        if completed is True:
            q = q.where(Task.status == "completed")
        elif completed is False:
            q = q.where(Task.status != "completed")
        return int(self.db.scalar(q) or 0)

    def clear_identity(self, identity_id: str) -> None:
        """把某身份的引用清回「未归类」（身份软删除时用；只 flush）。"""
        self.nullify("identity_id", identity_id=identity_id)

    def clear_project(self, project_id: str) -> None:
        """解除任务与项目的关联（项目删除时用；只 flush）。"""
        self.nullify("project_id", project_id=project_id)


class SubtaskRepository(BaseRepository[Subtask]):
    model = Subtask


class FocusSessionRepository(BaseRepository[FocusSession]):
    """番茄钟会话（M02 F08）。"""

    model = FocusSession

    def list_by_task(self, task_id: str, limit: int = 50) -> list[FocusSession]:
        """某任务的专注会话（新的在前）。"""
        q = (
            select(FocusSession)
            .where(FocusSession.task_id == task_id)
            .order_by(FocusSession.start_time.desc())
            .limit(limit)
        )
        return list(self.db.scalars(q))
