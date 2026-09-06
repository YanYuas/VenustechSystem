# ============================================================
# 学习成长模型（二期 M8）：学习计划 / 知识卡片 / 学习时长
# ============================================================
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, Index, Float
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.types import JSONType


class StudyPlan(UUIDMixin, TimestampMixin, Base):
    """学习计划"""
    __tablename__ = "study_plans"
    __table_args__ = (
        Index("idx_study_plans_user_status", "user_id", "status"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    estimated_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active/paused/completed/archived
    config: Mapped[dict] = mapped_column(JSONType, default=dict)


class Flashcard(UUIDMixin, TimestampMixin, Base):
    """知识卡片（SM-2间隔重复）"""
    __tablename__ = "flashcards"
    __table_args__ = (
        Index("idx_flashcards_user_next_review", "user_id", "next_review"),
        Index("idx_flashcards_user_category", "user_id", "category"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    plan_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("study_plans.id", ondelete="SET NULL"), nullable=True
    )
    front: Mapped[str] = mapped_column(Text, nullable=False)  # 正面（问题）
    back: Mapped[str] = mapped_column(Text, nullable=False)  # 背面（答案）
    card_type: Mapped[str] = mapped_column(String(20), default="qa")  # qa/concept/cloze/list
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tags: Mapped[list] = mapped_column(JSONType, default=list)
    difficulty: Mapped[int] = mapped_column(Integer, default=3)  # 1-5
    # SM-2参数
    ef: Mapped[float] = mapped_column(Float, default=2.5)
    interval: Mapped[int] = mapped_column(Integer, default=0)
    repetition: Mapped[int] = mapped_column(Integer, default=0)
    next_review: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_count: Mapped[int] = mapped_column(Integer, default=0)


class StudyTimeLog(UUIDMixin, Base):
    """学习时长记录"""
    __tablename__ = "study_time_logs"
    __table_args__ = (
        Index("idx_study_time_user_date", "user_id", "logged_date"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    plan_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("study_plans.id", ondelete="SET NULL"), nullable=True
    )
    subject: Mapped[str | None] = mapped_column(String(200), nullable=True)
    duration: Mapped[int] = mapped_column(Integer, nullable=False)  # 分钟
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)  # manual/pomodoro/auto
    logged_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
