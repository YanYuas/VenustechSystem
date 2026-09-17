# ============================================================
# 生活记录 API（二期 M9 P0）
# 习惯打卡 + 心情记录 + 日记
# ============================================================
from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.response import success
from app.schemas.life import CreateHabitRequest, CreateMoodLogRequest, CreateDiaryRequest
from app.services.life_service import LifeService

if TYPE_CHECKING:
    # 仅用于 user 参数的类型标注（依赖注入由 deps.get_current_user 提供），运行期不需要该名字。
    from app.models.user import User

router = APIRouter(prefix="/life", tags=["生活记录"])


def _svc(db: Session) -> LifeService:
    return LifeService(db)


# ==================== 习惯追踪 ====================

@router.get("/habits", summary="习惯列表（含今日打卡状态+连续天数）")
async def list_habits(
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).list_habits(user.id, page, page_size))


@router.post("/habits", summary="创建习惯")
async def create_habit(
    data: CreateHabitRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).create_habit(user.id, data))


@router.patch("/habits/{habit_id}", summary="更新习惯")
async def update_habit(
    habit_id: str,
    data: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).update_habit(habit_id, data))


@router.delete("/habits/{habit_id}", summary="删除习惯")
async def delete_habit(
    habit_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _svc(db).delete_habit(habit_id)
    return success(None)


@router.post("/habits/{habit_id}/checkin", summary="习惯打卡（幂等）")
async def checkin_habit(
    habit_id: str,
    checkin_date: date | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).checkin_habit(habit_id, checkin_date))


@router.delete("/habits/{habit_id}/checkin", summary="取消打卡")
async def uncheck_habit(
    habit_id: str,
    checkin_date: date | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _svc(db).uncheck_habit(habit_id, checkin_date)
    return success(None)


@router.get("/habits/{habit_id}/calendar", summary="习惯打卡日历")
async def habit_calendar(
    habit_id: str,
    year: int = Query(default_factory=lambda: date.today().year),
    month: int = Query(default_factory=lambda: date.today().month),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).get_habit_calendar(habit_id, year, month))


# ==================== 心情记录 ====================

@router.get("/moods", summary="心情记录列表")
async def list_moods(
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).list_moods(user.id, page, page_size))


@router.post("/moods", summary="记录心情")
async def create_mood(
    data: CreateMoodLogRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).create_mood(user.id, data))


@router.delete("/moods/{mood_id}", summary="删除心情记录")
async def delete_mood(
    mood_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _svc(db).delete_mood(mood_id)
    return success(None)


@router.get("/moods/stats", summary="心情统计")
async def mood_stats(
    days: int = 30,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).get_mood_stats(user.id, days))


# ==================== 日记 ====================

@router.get("/diaries", summary="日记列表")
async def list_diaries(
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).list_diaries(user.id, page, page_size))


@router.get("/diaries/{diary_id}", summary="日记详情")
async def get_diary(
    diary_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).get_diary(diary_id))


@router.post("/diaries", summary="创建日记")
async def create_diary(
    data: CreateDiaryRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).create_diary(user.id, data))


@router.patch("/diaries/{diary_id}", summary="更新日记")
async def update_diary(
    diary_id: str,
    data: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).update_diary(diary_id, data))


@router.delete("/diaries/{diary_id}", summary="删除日记")
async def delete_diary(
    diary_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _svc(db).delete_diary(diary_id)
    return success(None)
