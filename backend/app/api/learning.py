# ============================================================
# 学习成长 API（二期骨架）
# 对齐一期风格：Depends(get_db) + Depends(get_current_user) + success()
# ============================================================
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.response import success
from app.models.user import User

router = APIRouter(prefix="/learning", tags=["学习成长"])

@router.get("/plans", summary="学习计划列表")
async def list_plans(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success({"module": "学习成长", "endpoint": "list_plans", "status": "skeleton", "user": user.id})

@router.get("/cards", summary="知识卡片列表")
async def list_cards(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success({"module": "学习成长", "endpoint": "list_cards", "status": "skeleton", "user": user.id})

@router.get("/review/today", summary="今日复习队列")
async def today_review(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success({"module": "学习成长", "endpoint": "today_review", "status": "skeleton", "user": user.id})

@router.get("/time/stats", summary="学习时长统计")
async def time_stats(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success({"module": "学习成长", "endpoint": "time_stats", "status": "skeleton", "user": user.id})

