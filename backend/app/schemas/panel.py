# ============================================================
# 左侧信息面板 schema（快速待办 + 系统提醒）
# 对应参考UI左侧面板
# ============================================================
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


# ---------- 快速待办 ----------
class QuickTodoOut(BaseModel):
    id: str
    title: str
    completed: bool
    sort_order: int
    created_at: datetime
    completed_at: datetime | None = None


class CreateQuickTodoRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class UpdateQuickTodoRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    completed: bool | None = None


# ---------- 系统提醒 ----------
class ReminderOut(BaseModel):
    id: str
    title: str
    description: str | None = None
    remind_at: datetime
    type: str
    dismissed: bool
    repeat: str
    created_at: datetime


class CreateReminderRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    remind_at: datetime
    type: str = "custom"
    repeat: str = "none"


class UpdateReminderRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    remind_at: datetime | None = None
    type: str | None = None
    dismissed: bool | None = None
    repeat: str | None = None


# ---------- 左侧面板聚合数据 ----------
class LeftPanelStats(BaseModel):
    """今日状态（5项，对齐参考UI）"""
    focus_task: int = 0       # 今日最重要
    must_do: int = 0          # 必须完成
    in_progress: int = 0      # 进行中项目
    waiting: int = 0          # 等待处理
    completed_today: int = 0  # 今日完成


class LeftPanelData(BaseModel):
    """左侧信息面板完整数据"""
    greeting: str
    date_str: str
    weekday: str
    stats: LeftPanelStats
    quick_todos: list[QuickTodoOut] = Field(default_factory=list)
    reminders: list[ReminderOut] = Field(default_factory=list)
