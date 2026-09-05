# ============================================================
# 左侧信息面板 Repository（快速待办 + 系统提醒）
# ============================================================
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select

from app.models.panel import QuickTodo, Reminder
from app.repositories.base import BaseRepository


class QuickTodoRepository(BaseRepository[QuickTodo]):
    model = QuickTodo

    def list_user_todos(self, user_id: str, limit: int = 20) -> list[QuickTodo]:
        q = (
            select(QuickTodo)
            .where(QuickTodo.user_id == user_id)
            .order_by(QuickTodo.sort_order.asc(), QuickTodo.created_at.asc())
            .limit(limit)
        )
        return list(self.db.scalars(q))

    def list_active(self, user_id: str, limit: int = 10) -> list[QuickTodo]:
        """未完成的待办（左侧面板展示）"""
        q = (
            select(QuickTodo)
            .where(QuickTodo.user_id == user_id, QuickTodo.completed.is_(False))
            .order_by(QuickTodo.sort_order.asc(), QuickTodo.created_at.asc())
            .limit(limit)
        )
        return list(self.db.scalars(q))


class ReminderRepository(BaseRepository[Reminder]):
    model = Reminder

    def list_upcoming(self, user_id: str, limit: int = 10) -> list[Reminder]:
        """未来7天内的提醒（左侧面板展示）"""
        now = datetime.utcnow()
        end = now + timedelta(days=7)
        q = (
            select(Reminder)
            .where(
                Reminder.user_id == user_id,
                Reminder.dismissed.is_(False),
                Reminder.remind_at <= end,
            )
            .order_by(Reminder.remind_at.asc())
            .limit(limit)
        )
        return list(self.db.scalars(q))

    def list_user(self, user_id: str, limit: int = 50) -> list[Reminder]:
        q = (
            select(Reminder)
            .where(Reminder.user_id == user_id)
            .order_by(Reminder.remind_at.asc())
            .limit(limit)
        )
        return list(self.db.scalars(q))
