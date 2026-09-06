# ============================================================
# 生活记录 API（二期骨架）
# 对齐一期风格：Depends(get_db) + Depends(get_current_user) + success()
# ============================================================
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.response import success
from app.models.user import User

router = APIRouter(prefix="/life", tags=["生活记录"])

@router.get("/habits", summary="习惯列表")
async def list_habits(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success({"module": "生活记录", "endpoint": "list_habits", "status": "skeleton", "user": user.id})

@router.get("/moods", summary="心情记录列表")
async def list_moods(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success({"module": "生活记录", "endpoint": "list_moods", "status": "skeleton", "user": user.id})

@router.get("/diaries", summary="日记列表")
async def list_diaries(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success({"module": "生活记录", "endpoint": "list_diaries", "status": "skeleton", "user": user.id})

