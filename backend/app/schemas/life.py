# ============================================================
# 生活记录 schema（二期 M9）
# ============================================================
from __future__ import annotations

from datetime import date, datetime, time
from pydantic import BaseModel, Field


class HabitOut(BaseModel):
    id: str
    name: str
    icon: str | None = None
    color: str | None = None
    frequency: str = "daily"
    target_per_week: int = 7
    reminder_time: time | None = None
    goal_days: int | None = None
    status: str = "active"
    created_at: datetime
    updated_at: datetime


class CreateHabitRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    icon: str | None = None
    color: str | None = None
    frequency: str = "daily"
    target_per_week: int = 7
    reminder_time: time | None = None
    goal_days: int | None = None


class HabitCheckinOut(BaseModel):
    id: str
    habit_id: str
    checkin_date: date
    note: str | None = None
    created_at: datetime


class MoodLogOut(BaseModel):
    id: str
    score: int
    tags: list = []
    content: str | None = None
    logged_date: date
    created_at: datetime


class CreateMoodLogRequest(BaseModel):
    score: int = Field(ge=1, le=5)
    tags: list = []
    content: str | None = None
    logged_date: date | None = None


class DiaryOut(BaseModel):
    id: str
    dimension: str | None = None
    title: str | None = None
    content: str | None = None
    diary_date: date
    tags: list = []
    # 身份轴（三期 B）
    identity_id: str | None = None
    created_at: datetime
    updated_at: datetime


class CreateDiaryRequest(BaseModel):
    dimension: str | None = None
    title: str | None = None
    content: str | None = None
    tags: list = []
    # 身份轴（三期 B）：可空 = 未归类
    identity_id: str | None = None
    diary_date: date | None = None
