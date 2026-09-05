# ============================================================
# 知识资源 schema（对齐前端 types/document.ts）
# ============================================================
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class DocumentOut(BaseModel):
    id: str
    title: str
    content: str | None = None
    folder_id: str | None = None
    folder_name: str = "收集箱"
    tags: list[str] = []
    summary: str | None = None
    ai_suggested_tags: list[str] = []
    version: int = 1
    word_count: int = 0
    created_at: datetime
    updated_at: datetime


class CreateDocumentRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    folder_id: str | None = None
    content: str | None = None


class UpdateDocumentRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    content: str | None = None
    tags: list[str] | None = None
    folder_id: str | None = None


class DocumentVersionOut(BaseModel):
    id: str
    document_id: str
    content: str
    version: int
    word_count: int
    created_at: datetime


class BacklinkOut(BaseModel):
    id: str
    source_doc_id: str
    target_doc_id: str | None = None
    target_title: str | None = None
    created_at: datetime


class BacklinkSourceOut(BaseModel):
    source_doc_id: str
    source_title: str


class SearchTaskHit(BaseModel):
    id: str
    title: str
    type: str = "task"
    status: str = ""


class SearchDocumentHit(BaseModel):
    id: str
    title: str
    snippet: str = ""
    updated_at: datetime
    type: str = "document"


class SearchConversationHit(BaseModel):
    id: str
    title: str
    updated_at: datetime
    type: str = "conversation"


class SearchActionHit(BaseModel):
    id: str
    name: str
    type: str = "action"


class SearchResultOut(BaseModel):
    tasks: list[SearchTaskHit] = []
    documents: list[SearchDocumentHit] = []
    conversations: list[SearchConversationHit] = []
    actions: list[SearchActionHit] = []
