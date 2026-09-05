# ============================================================
# 第二分身 schema（对齐前端 types/conversation.ts）
# ============================================================
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ConversationOut(BaseModel):
    id: str
    title: str | None = None
    scene: str = "general"
    created_at: datetime
    updated_at: datetime


class CreateConversationRequest(BaseModel):
    title: str | None = None


class MessageOut(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    tokens: int | None = None
    referenced_doc_ids: list[str] = []
    created_at: datetime


class SendMessageRequest(BaseModel):
    content: str = Field(min_length=1)
    referenced_doc_ids: list[str] = []
    mode: str = "normal"  # normal | deep | creative | critical | brainstorm


class SseEvent(BaseModel):
    type: str  # content | done | error
    content: str | None = None
    tokens: int | None = None
    error: str | None = None


class AiSummaryResult(BaseModel):
    summary: str


class AiTagsResult(BaseModel):
    tags: list[str]


class AiInspirationResult(BaseModel):
    inspiration: str
    direction: list[str] = []
    prompt: str = ""


class ReflectionQuestion(BaseModel):
    question: str
    answer: str | None = None


class SummarizeRequest(BaseModel):
    document_id: str


class SuggestTagsRequest(BaseModel):
    document_id: str


class InspirationRequest(BaseModel):
    document_id: str


class ReflectionQuestionsRequest(BaseModel):
    review_type: str = "daily"
    date: str = ""
    data: dict = {}
