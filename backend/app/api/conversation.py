# ============================================================
# 第二分身路由：会话 CRUD + SSE 流式对话 + AI 接口（PRD §13.5）
# ============================================================
from __future__ import annotations

from typing import TYPE_CHECKING

import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.exceptions import AIServiceException, AppException
from app.core.response import success
from app.schemas.conversation import (
    CreateConversationRequest,
    InspirationRequest,
    ReflectionQuestionsRequest,
    SendMessageRequest,
    SummarizeRequest,
    SuggestTagsRequest,
)
from app.services.ai import AIService
from app.services.conversation_service import ConversationService


if TYPE_CHECKING:
    from app.models.user import User

router = APIRouter(prefix="/conversations", tags=["conversations"])
ai_router = APIRouter(prefix="/ai", tags=["ai"])


def _svc(db: Session, user: User) -> ConversationService:
    return ConversationService(db, user)


@router.get("")
def list_conversations(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(_svc(db, user).list())


@router.post("")
def create_conversation(
    data: CreateConversationRequest | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    title = data.title if data else None
    project_id = data.project_id if data else None
    return success(_svc(db, user).create(title, project_id))


@router.get("/{conversation_id}/messages")
def messages(conversation_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(_svc(db, user).messages(conversation_id))


@router.post("/{conversation_id}/messages")
async def send_message(
    conversation_id: str,
    data: SendMessageRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    svc = _svc(db, user)

    async def event_stream():
        try:
            async for event in svc.stream_messages(conversation_id, data):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except AIServiceException as exc:
            yield f"data: {json.dumps({'type': 'error', 'error': exc.message}, ensure_ascii=False)}\n\n"
        except AppException as exc:
            # 会话不存在等业务异常：响应已 200 开头，无法再回 404，
            # 以 error 事件下发给前端，避免连接被无声掐断
            yield f"data: {json.dumps({'type': 'error', 'error': exc.message, 'code': exc.code}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.delete("/{conversation_id}")
def delete_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _svc(db, user).delete(conversation_id)
    return success()


# ---------- AI 接口 ----------
@ai_router.post("/summarize")
async def summarize(data: SummarizeRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(await AIService(db, user).summarize(data.document_id))


@ai_router.post("/suggest-tags")
async def suggest_tags(data: SuggestTagsRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(await AIService(db, user).suggest_tags(data.document_id))


@ai_router.post("/inspiration")
async def inspiration(data: InspirationRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(await AIService(db, user).inspiration(data.document_id))


@ai_router.post("/reflection-questions")
async def reflection_questions(
    data: ReflectionQuestionsRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await AIService(db, user).reflection_questions(data.review_type, data.data)
    return success(result)
