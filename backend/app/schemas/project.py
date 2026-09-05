# ============================================================
# Project Schema
# ============================================================
from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class ProjectBase(BaseModel):
    name: str = Field(..., max_length=200)
    description: Optional[str] = None
    color: str = Field(default="#7c5cff", max_length=20)
    status: str = Field(default="active", max_length=20)
    due_date: Optional[date] = None


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    color: Optional[str] = Field(None, max_length=20)
    status: Optional[str] = Field(None, max_length=20)
    due_date: Optional[date] = None
    sort_order: Optional[int] = None


class ProjectOut(ProjectBase):
    id: str
    user_id: str
    sort_order: int
    task_count: int = 0
    completed_count: int = 0
    progress: int = 0
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


# ---------- 里程碑（M06 F03） ----------

class MilestoneCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    target_date: Optional[date] = None
    task_ids: list[str] = []
    sort_order: int = 0


class MilestoneUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    target_date: Optional[date] = None
    completed: Optional[bool] = None
    task_ids: Optional[list[str]] = None
    sort_order: Optional[int] = None


class MilestoneOut(BaseModel):
    id: str
    project_id: str
    name: str
    description: Optional[str] = None
    target_date: Optional[date] = None
    completed: bool = False
    completed_at: Optional[str] = None
    task_ids: list[str] = []
    sort_order: int = 0
    created_at: str
    updated_at: str


# ---------- 项目统计（M06 F02） ----------

class ProjectStatsOut(BaseModel):
    """项目进度统计：完成率 + 状态分布 + 近7天趋势 + 逾期 + 健康度。"""

    task_count: int = 0
    completed_count: int = 0
    progress: int = 0
    status_distribution: dict[str, int] = {}
    weekly_trend: list[dict] = []  # [{date, completed}]
    overdue_count: int = 0
    milestone_count: int = 0
    milestone_completed: int = 0
    health: str = "good"  # good / warning / risk
