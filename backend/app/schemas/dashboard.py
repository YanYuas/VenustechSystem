# ============================================================
# 仪表盘 schema（对齐前端 types/dashboard.ts + 参考UI模块丰富度）
# 一期已实现模块返回真实数据，待开发模块返回占位+status="planned"
# ============================================================
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.task import FocusTaskOut, TodayStatsOut

# ---------- 模块开发状态 ----------
ModuleStatus = Literal["ready", "beta", "planned"]


class ModuleStatusItem(BaseModel):
    """模块开发状态，供前端判断是否灰度显示"""
    id: str
    name: str
    status: ModuleStatus = "planned"
    description: str = ""


# ---------- 今日执行（按状态分组） ----------
class ExecutionGroup(BaseModel):
    status: str
    label: str
    count: int = 0
    tasks: list[dict] = Field(default_factory=list)  # 精简任务列表


class TodayExecution(BaseModel):
    groups: list[ExecutionGroup] = Field(default_factory=list)
    total: int = 0


# ---------- 当前项目（基于 project_tag 聚合） ----------
class ProjectItem(BaseModel):
    id: str  # project_tag 作为标识
    name: str
    progress: int = 0
    task_count: int = 0
    completed_count: int = 0
    status: ModuleStatus = "ready"


class ProjectsSection(BaseModel):
    items: list[ProjectItem] = Field(default_factory=list)
    status: ModuleStatus = "ready"


# ---------- 资源中心（待开发） ----------
class ResourceCategory(BaseModel):
    id: str
    name: str
    count: int = 0
    icon: str = ""


class ResourceCenter(BaseModel):
    categories: list[ResourceCategory] = Field(default_factory=list)
    status: ModuleStatus = "planned"


# ---------- 学习与成长（待开发） ----------
class LearningItem(BaseModel):
    id: str
    title: str
    progress: int = 0
    type: str = ""


class LearningSection(BaseModel):
    today_study: LearningItem | None = None
    plans: list[LearningItem] = Field(default_factory=list)
    cards_count: int = 0
    status: ModuleStatus = "planned"


# ---------- 最近沉淀（已实现） ----------
class RecentDocument(BaseModel):
    id: str
    title: str
    updated_at: datetime
    tags: list[str] = Field(default_factory=list)


# ---------- 生活与自我（待开发） ----------
class LifeCategory(BaseModel):
    id: str
    name: str
    value: str = ""
    icon: str = ""


class LifeSection(BaseModel):
    categories: list[LifeCategory] = Field(default_factory=list)
    status: ModuleStatus = "planned"


# ---------- 快速入口 ----------
class QuickAction(BaseModel):
    id: str
    name: str
    icon: str
    action: str  # 路由或命令
    status: ModuleStatus = "ready"


class QuickActions(BaseModel):
    items: list[QuickAction] = Field(default_factory=list)


# ---------- AI 助手状态 ----------
class AIAssistantStatus(BaseModel):
    enabled: bool = False
    model: str = ""
    status: ModuleStatus = "ready"
    quick_prompts: list[str] = Field(default_factory=list)


# ---------- 长期资产库（待开发） ----------
class AssetCategory(BaseModel):
    id: str
    name: str
    count: int = 0
    icon: str = ""


class AssetsSection(BaseModel):
    categories: list[AssetCategory] = Field(default_factory=list)
    status: ModuleStatus = "planned"


# ---------- 用户信息 ----------
class DashboardUser(BaseModel):
    nickname: str
    greeting: str


# ---------- 完整 Dashboard 数据 ----------
class DashboardDataOut(BaseModel):
    # 已实现
    focus_task: FocusTaskOut | None = None
    today_stats: TodayStatsOut
    recent_documents: list[RecentDocument] = Field(default_factory=list)
    user: DashboardUser

    # 今日执行（已实现，基于任务数据聚合）
    today_execution: TodayExecution = Field(default_factory=TodayExecution)

    # 当前项目（已实现，基于 project_tag 聚合）
    projects: ProjectsSection = Field(default_factory=ProjectsSection)

    # 待开发模块（返回占位数据，前端灰度显示）
    resource_center: ResourceCenter = Field(default_factory=ResourceCenter)
    learning: LearningSection = Field(default_factory=LearningSection)
    life: LifeSection = Field(default_factory=LifeSection)
    assets: AssetsSection = Field(default_factory=AssetsSection)

    # 全局
    quick_actions: QuickActions = Field(default_factory=QuickActions)
    ai_assistant: AIAssistantStatus = Field(default_factory=AIAssistantStatus)
    modules_status: list[ModuleStatusItem] = Field(default_factory=list)
