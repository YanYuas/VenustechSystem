# ============================================================
# AI 行程助理路由（移动端方案 M2）
#
# GET  /api/v1/assistant/status   Key 是否已配置
# PUT  /api/v1/assistant/config   配置 DeepSeek Key（加密落库，永不回显）
# POST /api/v1/assistant/parse    语音文字 → 结构化建议（只建议，不落库）
# POST /api/v1/assistant/apply    用户确认后的条目 → 白名单落库
# ============================================================
from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.response import success
from app.services.assistant_service import ApplyItem, AssistantService

if TYPE_CHECKING:
    from app.models.user import User

router = APIRouter(prefix="/assistant", tags=["assistant"])


def _svc(db: Session, user: User) -> AssistantService:
    return AssistantService(db, user.id)


class ConfigRequest(BaseModel):
    api_key: str = Field(..., min_length=8, max_length=200)


class ParseRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)


class ApplyRequest(BaseModel):
    items: list[ApplyItem]


@router.get("/status", summary="助理状态（Key 是否已配置）")
def status(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(_svc(db, user).status())


@router.put("/config", summary="配置 DeepSeek API Key（加密落库）")
def configure(data: ConfigRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(_svc(db, user).configure(data.api_key))


@router.post("/parse", summary="口语文字 → 结构化待办建议（AI 只建议，不落库）")
async def parse(data: ParseRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(await _svc(db, user).parse(data.text))


@router.post("/apply", summary="确认后的条目 → 白名单落库（任务/提醒/收集箱）")
def apply(data: ApplyRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(_svc(db, user).apply([i.model_dump() for i in data.items]))
