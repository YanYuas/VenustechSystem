# ============================================================
# 生活记录 API（二期 M9）
# 对齐一期风格：Depends(get_db) + Depends(get_current_user) + success()
# Service层已接入，P0功能待实现
# ============================================================
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.response import success
from app.models.user import User
from app.services.life_service import LifeService

router = APIRouter(prefix="/life", tags=["生活记录"])


def _svc(db: Session) -> LifeService:
    return LifeService(db)

@router.get("/habits", summary="习惯列表")
async def list_habits(
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).list_habits(user.id))


@router.post("/habits", summary="创建习惯")
async def create_habit(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success({"module": "生活记录", "endpoint": "create_habit", "status": "skeleton"})


@router.post("/habits/{habit_id}/checkin", summary="习惯打卡")
async def checkin_habit(
    habit_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).checkin_habit(user.id, habit_id))


@router.get("/moods", summary="心情记录列表")
async def list_moods(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success({"module": "生活记录", "endpoint": "list_moods", "status": "skeleton"})


@router.post("/moods", summary="记录心情")
async def create_mood(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success({"module": "生活记录", "endpoint": "create_mood", "status": "skeleton"})


@router.get("/diaries", summary="日记列表")
async def list_diaries(
    dimension: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).list_diaries(user.id, dimension))

