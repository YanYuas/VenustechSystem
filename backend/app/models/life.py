# ============================================================
# 生活记录模型（二期 M9）：习惯 / 心情 / 日记
# ============================================================
from __future__ import annotations

from datetime import date, datetime, time

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, Time, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin, utcnow
from app.models.types import JSONType


class Habit(UUIDMixin, TimestampMixin, Base):
    """习惯"""
    __tablename__ = "habits"
    __table_args__ = (
        Index("idx_habits_user_status", "user_id", "status"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)
    color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    frequency: Mapped[str] = mapped_column(String(20), default="daily")  # daily/weekly
    target_per_week: Mapped[int] = mapped_column(Integer, default=7)
    reminder_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    goal_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active/archived


class HabitCheckin(UUIDMixin, Base):
    """习惯打卡记录"""
    __tablename__ = "habit_checkins"
    __table_args__ = (
        UniqueConstraint("habit_id", "checkin_date", name="uq_habit_checkin"),
        Index("idx_habit_checkins_user_date", "user_id", "checkin_date"),
    )

    habit_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("habits.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    checkin_date: Mapped[date] = mapped_column(Date, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MoodLog(UUIDMixin, Base):
    """心情记录"""
    __tablename__ = "mood_logs"
    __table_args__ = (
        Index("idx_mood_logs_user_date", "user_id", "logged_date"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    score: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-5
    tags: Mapped[list] = mapped_column(JSONType, default=list)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    logged_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Diary(UUIDMixin, TimestampMixin, Base):
    """四维日记"""
    __tablename__ = "diaries"
    __table_args__ = (
        Index("idx_diaries_user_date", "user_id", "diary_date"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    dimension: Mapped[str | None] = mapped_column(String(20), nullable=True)  # family/health/energy/growth
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    diary_date: Mapped[date] = mapped_column(Date, nullable=False)
    tags: Mapped[list] = mapped_column(JSONType, default=list)
