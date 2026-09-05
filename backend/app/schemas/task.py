# ============================================================
# 任务 schema（对齐前端 types/task.ts + PRD §13.3）
# ============================================================
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class SubtaskOut(BaseModel):
    id: str
    task_id: str
    title: str
    completed: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime


class TaskOut(BaseModel):
    id: str
    title: str
    description: str | None = None
    status: str
    priority: str
    project_tag: str | None = None
    project_id: str | None = None
    project_name: str | None = None
    due_date: date | None = None
    is_focus: bool = False
    progress: int = 0
    subtasks_count: int = 0
    subtasks_completed: int = 0
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class TaskDetailOut(TaskOut):
    subtasks: list[SubtaskOut] = []


class CreateTaskRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    priority: str | None = "medium"
    status: str | None = "pending"
    project_tag: str | None = None
    project_id: str | None = None
    due_date: date | None = None


class UpdateTaskRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    priority: str | None = None
    status: str | None = None
    project_tag: str | None = None
    project_id: str | None = None
    due_date: date | None = None


class CreateSubtaskRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)


class UpdateSubtaskRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    completed: bool | None = None


class TodayStatsOut(BaseModel):
    must_do: int = 0
    in_progress: int = 0
    waiting: int = 0
    completed_today: int = 0


class FocusTaskOut(BaseModel):
    id: str
    title: str
    project_tag: str | None = None
    project_id: str | None = None
    stage: str = ""
    progress: int = 0
    next_step: str = ""
    status: str
