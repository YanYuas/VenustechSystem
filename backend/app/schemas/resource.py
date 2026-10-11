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


class BatchProcessRequest(BaseModel):
    """批量处理收集箱条目的请求体。

    为什么要有这个模型（而不是把 item_ids/action 写成裸参数）：
      FastAPI 对 `item_ids: list[str]` 这类非标量、非路径参数会推定它是 **body**，
      且因它是唯一 body 参数而不做 embed —— 于是后端期望的请求体是裸数组
      `["id1","id2"]`，而 `action: str` 被推定为 **query**。
      但前端发的是 `{item_ids: [...], action: "..."}`（见 frontend/src/api/resource.ts），
      两者对不上 → 批量处理端点恒定返回「参数错误」。用显式模型收口后
      前后端一致，且 item_ids/action 都能得到校验。
    """

    item_ids: list[str] = Field(min_length=1, max_length=200)
    action: str = Field(min_length=1, max_length=32)


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
