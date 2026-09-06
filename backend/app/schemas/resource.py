# ============================================================
# 资源中心 schema（二期 M7）
# ============================================================
from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class InboxItemOut(BaseModel):
    id: str
    content_type: str
    content: str | None = None
    title: str | None = None
    preview_url: str | None = None
    file_path: str | None = None
    source: str | None = None
    tags: list = []
    status: str = "pending"
    processed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class CreateInboxItemRequest(BaseModel):
    content_type: str = Field(min_length=1, max_length=20)
    content: str | None = None
    title: str | None = None
    source: str | None = None
    tags: list = []


class UpdateInboxItemRequest(BaseModel):
    status: str | None = None
    title: str | None = None
    tags: list | None = None


class TemplateOut(BaseModel):
    id: str
    name: str
    category: str
    description: str | None = None
    content: str
    variables: list = []
    tags: list = []
    is_builtin: bool = False
    use_count: int = 0
    created_at: datetime
    updated_at: datetime


class CreateTemplateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=50)
    content: str
    description: str | None = None
    variables: list = []
    tags: list = []


class DomainOut(BaseModel):
    id: str
    name: str
    description: str | None = None
    icon: str | None = None
    color: str | None = None
    sort_order: int = 0
    created_at: datetime
    updated_at: datetime


class CreateDomainRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    icon: str | None = None
    color: str | None = None
