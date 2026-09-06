# ============================================================
# 学习成长 schema（二期 M8）
# ============================================================
from __future__ import annotations

from datetime import date, datetime
from pydantic import BaseModel, Field


class StudyPlanOut(BaseModel):
    id: str
    name: str
    description: str | None = None
    target_date: date | None = None
    estimated_hours: int | None = None
    progress: int = 0
    status: str = "active"
    config: dict = {}
    created_at: datetime
    updated_at: datetime


class CreateStudyPlanRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    target_date: date | None = None
    estimated_hours: int | None = None


class FlashcardOut(BaseModel):
    id: str
    plan_id: str | None = None
    front: str
    back: str
    card_type: str = "qa"
    category: str | None = None
    tags: list = []
    difficulty: int = 3
    ef: float = 2.5
    interval: int = 0
    repetition: int = 0
    next_review: date | None = None
    last_reviewed_at: datetime | None = None
    review_count: int = 0
    created_at: datetime
    updated_at: datetime


class CreateFlashcardRequest(BaseModel):
    front: str = Field(min_length=1)
    back: str = Field(min_length=1)
    plan_id: str | None = None
    card_type: str = "qa"
    category: str | None = None
    tags: list = []
    difficulty: int = 3


class ReviewSubmitRequest(BaseModel):
    quality: int = Field(ge=0, le=5)


class StudyTimeLogOut(BaseModel):
    id: str
    plan_id: str | None = None
    subject: str | None = None
    duration: int
    note: str | None = None
    source: str | None = None
    logged_date: date
    created_at: datetime


class CreateStudyTimeLogRequest(BaseModel):
    duration: int = Field(gt=0)
    subject: str | None = None
    plan_id: str | None = None
    note: str | None = None
    source: str = "manual"
    logged_date: date | None = None
