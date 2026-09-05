# ============================================================
# quick_todos + reminders（左侧信息面板）
# 对应参考UI左侧面板：待办事项 + 系统提醒
# ============================================================
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class QuickTodo(UUIDMixin, TimestampMixin, Base):
    """左侧面板快速待办（轻量级，区别于 tasks 模块的完整任务）"""
    __tablename__ = "quick_todos"
    __table_args__ = (
        Index("idx_quick_todos_user", "user_id"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Reminder(UUIDMixin, TimestampMixin, Base):
    """系统提醒（左侧面板展示，带时间）"""
    __tablename__ = "reminders"
    __table_args__ = (
        Index("idx_reminders_user_time", "user_id", "remind_at"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    remind_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # 类型：meeting / study / health / custom
    type: Mapped[str] = mapped_column(String(20), nullable=False, default="custom")
    # 是否已读/已完成
    dismissed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # 重复规则：none / daily / weekly
    repeat: Mapped[str] = mapped_column(String(20), nullable=False, default="none")
