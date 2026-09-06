# ============================================================
# 长期资产库 schema（二期 M10）
# ============================================================
from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class SOPOut(BaseModel):
    id: str
    name: str
    category: str | None = None
    description: str | None = None
    steps: list = []
    checklist: list = []
    tags: list = []
    use_count: int = 0
    version: int = 1
    created_at: datetime
    updated_at: datetime


class CreateSOPRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    category: str | None = None
    description: str | None = None
    steps: list = []
    checklist: list = []
    tags: list = []


class PromptTemplateOut(BaseModel):
    id: str
    name: str
    category: str | None = None
    description: str | None = None
    role_setting: str | None = None
    task_description: str | None = None
    constraints: str | None = None
    output_format: str | None = None
    variables: list = []
    use_count: int = 0
    rating: float | None = None
    created_at: datetime
    updated_at: datetime


class CreatePromptTemplateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    category: str | None = None
    description: str | None = None
    role_setting: str | None = None
    task_description: str | None = None
    constraints: str | None = None
    output_format: str | None = None
    variables: list = []


class SkillOut(BaseModel):
    id: str
    name: str
    category: str | None = None
    description: str | None = None
    methodology: str | None = None
    proficiency: str = "beginner"
    tags: list = []
    use_count: int = 0
    created_at: datetime
    updated_at: datetime


class CreateSkillRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    category: str | None = None
    description: str | None = None
    methodology: str | None = None
    proficiency: str = "beginner"
    tags: list = []


class ProjectMemoryOut(BaseModel):
    id: str
    project_id: str | None = None
    name: str
    summary: str | None = None
    successes: str | None = None
    failures: str | None = None
    extracted_assets: list = []
    key_metrics: dict = {}
    tags: list = []
    created_at: datetime
    updated_at: datetime


class CreateProjectMemoryRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    project_id: str | None = None
    summary: str | None = None
    successes: str | None = None
    failures: str | None = None
    tags: list = []
