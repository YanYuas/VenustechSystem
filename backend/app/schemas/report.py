# ============================================================
# 人生报告 Schema（S6-5 · 三轴合一）
#
# 三轴（总路线）：身份 × 成长 × 档案。前端把这份 JSON 渲染成
# 单文件 HTML（内联样式、零外部依赖）供下载留存。
# ============================================================
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class IdentityStat(BaseModel):
    id: str
    name: str
    slug: str
    color_token: str
    icon: str
    is_archived: bool
    tasks_open: int = 0
    tasks_completed: int = 0
    documents: int = 0
    diaries: int = 0
    reviews: int = 0
    memories: int = 0  # 分身记忆 + 项目记忆


class UnassignedStat(BaseModel):
    tasks_open: int = 0
    documents: int = 0
    diaries: int = 0
    reviews: int = 0
    memories: int = 0


class IdentityAxis(BaseModel):
    identities: list[IdentityStat] = Field(default_factory=list)
    unassigned: UnassignedStat = Field(default_factory=UnassignedStat)


class SkillStatOut(BaseModel):
    name: str
    count: int


class GrowthAxis(BaseModel):
    level: int = 1
    exp: int = 0
    percent: int = 0
    skills: list[SkillStatOut] = Field(default_factory=list)
    tasks_completed_total: int = 0
    diaries_total: int = 0
    reviews_total: int = 0


class WorkspaceRootStat(BaseModel):
    path: str
    label: str | None = None
    file_count: int = 0
    total_size: int = 0


class ArchiveAxis(BaseModel):
    workspace_enabled: bool = False
    roots: list[WorkspaceRootStat] = Field(default_factory=list)
    documents_total: int = 0
    sops_total: int = 0
    prompts_total: int = 0
    skills_total: int = 0
    project_memories_total: int = 0
    avatar_memories_total: int = 0


class ExperienceRecentItem(BaseModel):
    source: Literal["diary", "review", "avatar_memory", "project_memory"]
    source_label: str
    title: str
    identity_name: str | None = None
    occurred_at: datetime


class ReportOut(BaseModel):
    generated_at: datetime
    nickname: str
    identity_axis: IdentityAxis
    growth_axis: GrowthAxis
    archive_axis: ArchiveAxis
    recent_experience: list[ExperienceRecentItem] = Field(default_factory=list)
