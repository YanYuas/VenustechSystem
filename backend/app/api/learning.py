# ============================================================
# 学习成长 API（二期 M8 P0）
# 学习计划 + 知识卡片(SM-2) + 学习时长
# ============================================================
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.response import success
from app.models.user import User
from app.schemas.learning import CreateStudyPlanRequest, CreateFlashcardRequest, ReviewSubmitRequest, CreateStudyTimeLogRequest
from app.services.learning_service import LearningService

router = APIRouter(prefix="/learning", tags=["学习成长"])


def _svc(db: Session) -> LearningService:
    return LearningService(db)


# ==================== 学习计划 ====================

@router.get("/plans", summary="学习计划列表（分页）")
async def list_plans(
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).list_plans(user.id, page, page_size))


@router.post("/plans", summary="创建学习计划")
async def create_plan(
    data: CreateStudyPlanRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).create_plan(user.id, data))


@router.patch("/plans/{plan_id}", summary="更新学习计划")
async def update_plan(
    plan_id: str,
    data: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).update_plan(plan_id, data))


@router.delete("/plans/{plan_id}", summary="删除学习计划")
async def delete_plan(
    plan_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _svc(db).delete_plan(plan_id)
    return success(None)


# ==================== 知识卡片 ====================

@router.get("/cards", summary="知识卡片列表（分页）")
async def list_cards(
    plan_id: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).list_cards(user.id, plan_id, page, page_size))


@router.post("/cards", summary="创建知识卡片")
async def create_card(
    data: CreateFlashcardRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).create_card(user.id, data))


@router.patch("/cards/{card_id}", summary="更新知识卡片")
async def update_card(
    card_id: str,
    data: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).update_card(card_id, data))


@router.delete("/cards/{card_id}", summary="删除知识卡片")
async def delete_card(
    card_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _svc(db).delete_card(card_id)
    return success(None)


# ==================== SM-2 复习 ====================

@router.get("/review/today", summary="今日复习队列")
async def today_review(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).get_today_review(user.id))


@router.post("/cards/{card_id}/review", summary="提交复习结果（SM-2）")
async def submit_review(
    card_id: str,
    data: ReviewSubmitRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).submit_review(card_id, data))


# ==================== 学习时长 ====================

@router.post("/time/log", summary="记录学习时长")
async def log_study_time(
    data: CreateStudyTimeLogRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).log_study_time(user.id, data))


@router.get("/time/stats", summary="学习时长统计")
async def time_stats(
    days: int = 30,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).get_time_stats(user.id, days))
