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


class GeneratePlanRequest(BaseModel):
    """从自然语言目标生成学习计划（S6-1 · **离线可用**）。

    走内置领域知识库（13 领域 / 52 能力单元 / 90 条带达标标准的任务）；
    未命中领域时退化为「入门准备 → 基础操作 → 核心练习 → 实战产出」
    四阶段通用拆解。**全程不依赖任何模型，也不需要 API Key。**
    """

    goal: str = Field(min_length=1, max_length=200, description="学习目标，如「我想学雅思」")
    total_days: int = Field(default=30, ge=1, le=730, description="计划周期（天）")
    minutes_per_day: int = Field(default=45, ge=10, le=600, description="每天可投入分钟数")


class ApplyPlanRequest(GeneratePlanRequest):
    """生成计划并落成任务（写入 Task 表，可参与日程与统计）。"""

    plan_name: str | None = Field(default=None, max_length=200, description="学习计划名称")
    project_id: str | None = Field(default=None, description="将生成的任务归入该项目")
    start_date: date | None = Field(default=None, description="起始日期，默认今天")


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
