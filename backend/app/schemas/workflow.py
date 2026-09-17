# ============================================================
# 工作流 schema（二期 P1）
# ============================================================
from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class WorkflowOut(BaseModel):
    id: str
    name: str
    description: str | None = None
    icon: str | None = None
    category: str | None = None
    scenario: str | None = None
    config: dict = {}
    is_preset: bool = False
    is_active: bool = True
    use_count: int = 0
    created_at: datetime
    updated_at: datetime


class CreateWorkflowRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    icon: str | None = None
    category: str | None = None
    scenario: str | None = None
    config: dict = {}


class ApplyWorkflowRequest(BaseModel):
    params: dict = {}  # 应用参数（如项目名称、学习科目）


class WorkflowApplicationOut(BaseModel):
    id: str
    workflow_id: str
    user_id: str
    params: dict = {}
    status: str = "completed"
    result_summary: str | None = None
    applied_at: datetime
