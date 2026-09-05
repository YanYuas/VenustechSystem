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
