# ============================================================
# 通知 Schema
# ============================================================
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

NotificationType = Literal["info", "success", "warning", "error"]


class NotificationOut(BaseModel):
    id: str
    type: NotificationType
    title: str
    content: str | None = None
    is_read: bool
    read_at: datetime | None = None
    source_type: str | None = None
    source_id: str | None = None
    created_at: datetime
    updated_at: datetime


class CreateNotificationRequest(BaseModel):
    type: NotificationType = "info"
    title: str = Field(..., max_length=200)
    content: str | None = Field(None, max_length=2000)
    source_type: str | None = Field(None, max_length=30)
    source_id: str | None = Field(None, max_length=36)


class MarkReadRequest(BaseModel):
    read: bool = True


class NotificationStats(BaseModel):
    total: int
    unread: int
