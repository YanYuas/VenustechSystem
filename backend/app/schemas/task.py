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
    # 身份轴（三期 B）：可空 = 未归类
    identity_id: str | None = None
    due_date: date | None = None
    is_focus: bool = False
    progress: int = 0
    subtasks_count: int = 0
    subtasks_completed: int = 0
    completed_at: datetime | None = None
    # ---------- M02 深度开发 ----------
    reminder_time: datetime | None = None
    recurrence: dict | None = None
    focus_duration: int = 0
    # ---------- S6-1 领域规则引擎（迁移 0012）----------
    # 由学习计划生成的任务会带上这两项：预估时长用于日程排布，
    # 达标标准用于「做完没做完」之外的第二层验收
    estimated_minutes: int | None = None
    acceptance_criteria: str | None = None
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
    # 身份轴（三期 B）：可空 = 未归类
    identity_id: str | None = None
    due_date: date | None = None
    reminder_time: datetime | None = None
    recurrence: dict | None = None


class UpdateTaskRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    priority: str | None = None
    status: str | None = None
    project_tag: str | None = None
    project_id: str | None = None
    # 身份轴（三期 B）：可空 = 未归类
    identity_id: str | None = None
    due_date: date | None = None
    reminder_time: datetime | None = None
    recurrence: dict | None = None
    # S6-1：计划生成的任务带这两项，允许用户后续自行微调
    estimated_minutes: int | None = Field(default=None, ge=0, le=100000)
    acceptance_criteria: str | None = None


class CreateSubtaskRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)


class UpdateSubtaskRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    completed: bool | None = None
    sort_order: int | None = None


# ---------- 批量操作（M02 F07） ----------

class BatchTaskRequest(BaseModel):
    """批量操作：action 决定语义，其余字段按 action 可选。"""

    task_ids: list[str] = Field(min_length=1)
    action: str = Field(pattern="^(complete|delete|move_project|set_priority)$")
    project_id: str | None = None      # move_project
    priority: str | None = None        # set_priority


class BatchTaskResult(BaseModel):
    affected: int = 0
    failed: int = 0


# ---------- 番茄钟（M02 F08） ----------

class FocusSessionOut(BaseModel):
    id: str
    task_id: str | None = None
    start_time: datetime
    end_time: datetime | None = None
    duration: int = 0
    note: str | None = None
    created_at: datetime


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
