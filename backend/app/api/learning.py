# ============================================================
# 学习成长 API（二期 M8）
# 对齐一期风格：Depends(get_db) + Depends(get_current_user) + success()
# Service层已接入，P0功能待实现
# ============================================================
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.response import success
from app.models.user import User
from app.services.learning_service import LearningService

router = APIRouter(prefix="/learning", tags=["学习成长"])


def _svc(db: Session) -> LearningService:
    return LearningService(db)

@router.get("/plans", summary="学习计划列表")
async def list_plans(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).list_plans(user.id))


@router.post("/plans", summary="创建学习计划")
async def create_plan(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success({"module": "学习成长", "endpoint": "create_plan", "status": "skeleton"})


@router.get("/cards", summary="知识卡片列表")
async def list_cards(
    plan_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).list_cards(user.id, plan_id))


@router.post("/cards", summary="创建知识卡片")
async def create_card(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success({"module": "学习成长", "endpoint": "create_card", "status": "skeleton"})


@router.get("/review/today", summary="今日复习队列")
async def today_review(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).get_today_review(user.id))


@router.get("/time/stats", summary="学习时长统计")
async def time_stats(
    days: int = 30,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).get_time_stats(user.id, days))

