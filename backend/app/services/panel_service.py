# ============================================================
# 左侧信息面板 Service（快速待办 + 系统提醒 + 聚合）
# ============================================================
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundException
from app.core.utils import WEEKDAYS, format_date_cn, greeting_by_hour
from app.models.panel import QuickTodo, Reminder
from app.models.user import User
from app.repositories import QuickTodoRepository, ReminderRepository, TaskRepository
from app.schemas.panel import (
    CreateQuickTodoRequest,
    CreateReminderRequest,
    LeftPanelData,
    LeftPanelStats,
    QuickTodoOut,
    ReminderOut,
    UpdateQuickTodoRequest,
    UpdateReminderRequest,
)


class PanelService:
    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user
        self.todo_repo = QuickTodoRepository(db)
        self.reminder_repo = ReminderRepository(db)
        self.task_repo = TaskRepository(db)

    # ---------- 左侧面板聚合 ----------
    def get_left_panel(self) -> LeftPanelData:
        now = datetime.now()
        stats = self._build_stats()
        todos = [self._todo_out(t) for t in self.todo_repo.list_active(self.user.id)]
        reminders = [self._reminder_out(r) for r in self.reminder_repo.list_upcoming(self.user.id)]
        return LeftPanelData(
            greeting=greeting_by_hour(now.hour),
            date_str=format_date_cn(now),
            weekday=WEEKDAYS[now.weekday()],
            stats=stats,
            quick_todos=todos,
            reminders=reminders,
        )

    def _build_stats(self) -> LeftPanelStats:
        today = datetime.now().date()
        return LeftPanelStats(
            focus_task=1 if self.task_repo.get_focus(self.user.id) else 0,
            must_do=self.task_repo.count_due_today_open(self.user.id, today),
            in_progress=self.task_repo.count_by_status(self.user.id, "in_progress"),
            waiting=self.task_repo.count_by_status(self.user.id, "waiting"),
            completed_today=self.task_repo.count_completed_on(self.user.id, today),
        )

    # ---------- 快速待办 CRUD ----------
    def list_todos(self) -> list[QuickTodoOut]:
        return [self._todo_out(t) for t in self.todo_repo.list_user_todos(self.user.id)]

    def create_todo(self, data: CreateQuickTodoRequest) -> QuickTodoOut:
        max_order = max(
            (t.sort_order for t in self.todo_repo.list_user_todos(self.user.id, limit=100)),
            default=-1,
        )
        todo = self.todo_repo.create(
            user_id=self.user.id, title=data.title, sort_order=max_order + 1
        )
        return self._todo_out(todo)

    def update_todo(self, todo_id: str, data: UpdateQuickTodoRequest) -> QuickTodoOut:
        todo = self._get_todo(todo_id)
        payload = data.model_dump(exclude_unset=True)
        if "completed" in payload:
            todo.completed = payload["completed"]
            todo.completed_at = datetime.utcnow() if payload["completed"] else None
        if "title" in payload:
            todo.title = payload["title"]
        self.db.commit()
        self.db.refresh(todo)
        return self._todo_out(todo)

    def delete_todo(self, todo_id: str) -> None:
        todo = self._get_todo(todo_id)
        self.todo_repo.delete(todo)

    def _get_todo(self, todo_id: str) -> QuickTodo:
        todo = self.todo_repo.get(todo_id)
        if todo is None or todo.user_id != self.user.id:
            raise NotFoundException("待办不存在")
        return todo

    @staticmethod
    def _todo_out(todo: QuickTodo) -> QuickTodoOut:
        return QuickTodoOut(
            id=todo.id,
            title=todo.title,
            completed=todo.completed,
            sort_order=todo.sort_order,
            created_at=todo.created_at,
            completed_at=todo.completed_at,
        )

    # ---------- 系统提醒 CRUD ----------
    def list_reminders(self) -> list[ReminderOut]:
        return [self._reminder_out(r) for r in self.reminder_repo.list_user(self.user.id)]

    def create_reminder(self, data: CreateReminderRequest) -> ReminderOut:
        reminder = self.reminder_repo.create(
            user_id=self.user.id,
            title=data.title,
            description=data.description,
            remind_at=data.remind_at,
            type=data.type,
            repeat=data.repeat,
        )
        return self._reminder_out(reminder)

    def update_reminder(self, reminder_id: str, data: UpdateReminderRequest) -> ReminderOut:
        reminder = self._get_reminder(reminder_id)
        payload = data.model_dump(exclude_unset=True)
        for key, value in payload.items():
            setattr(reminder, key, value)
        self.db.commit()
        self.db.refresh(reminder)
        return self._reminder_out(reminder)

    def delete_reminder(self, reminder_id: str) -> None:
        reminder = self._get_reminder(reminder_id)
        self.reminder_repo.delete(reminder)

    def _get_reminder(self, reminder_id: str) -> Reminder:
        reminder = self.reminder_repo.get(reminder_id)
        if reminder is None or reminder.user_id != self.user.id:
            raise NotFoundException("提醒不存在")
        return reminder

    @staticmethod
    def _reminder_out(reminder: Reminder) -> ReminderOut:
        return ReminderOut(
            id=reminder.id,
            title=reminder.title,
            description=reminder.description,
            remind_at=reminder.remind_at,
            type=reminder.type,
            dismissed=reminder.dismissed,
            repeat=reminder.repeat,
            created_at=reminder.created_at,
        )
