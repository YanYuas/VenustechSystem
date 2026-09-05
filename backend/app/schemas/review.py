# ============================================================
# 复盘 schema（对齐前端 types/review.ts）
# ============================================================
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class ReviewReflection(BaseModel):
    question: str
    answer: str = ""


class ReviewData(BaseModel):
    completed_tasks: str = ""
    unfinished_tasks: str = ""
    gains: str = ""
    reflections: list[ReviewReflection] = []
    tomorrow_plan: str = ""
    mood: int = Field(default=3, ge=1, le=5)
    energy: int = Field(default=3, ge=1, le=5)


class ReviewOut(BaseModel):
    id: str
    type: str
    review_date: date
    project_id: str | None = None
    data: ReviewData
    created_at: datetime
    updated_at: datetime


class UpsertReviewRequest(BaseModel):
    type: str = "daily"
    date: date
    project_id: str | None = None
    data: ReviewData


class ReviewListItem(BaseModel):
    id: str
    type: str
    review_date: date
    mood: int | None = None
    energy: int | None = None
    summary: str = ""
    created_at: datetime
    updated_at: datetime


class AutoFillTask(BaseModel):
    id: str
    title: str
    completed_at: datetime | None = None
    due_date: date | None = None


class AutoFillDoc(BaseModel):
    id: str
    title: str
    created_at: datetime


class AutoFillStats(BaseModel):
    tasks_completed: int = 0
    documents_created: int = 0
    tasks_overdue: int = 0


class AutoFillData(BaseModel):
    completed_tasks: list[AutoFillTask] = []
    unfinished_tasks: list[AutoFillTask] = []
    documents_created: list[AutoFillDoc] = []
    stats: AutoFillStats = Field(default_factory=AutoFillStats)


class ConvertTaskRequest(BaseModel):
    content: str = Field(min_length=1)
    priority: str | None = None
    due_date: date | None = None
