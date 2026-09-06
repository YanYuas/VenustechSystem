# ============================================================
# 长期资产库 API（二期骨架）
# 对齐一期风格：Depends(get_db) + Depends(get_current_user) + success()
# ============================================================
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.response import success
from app.models.user import User

router = APIRouter(prefix="/asset", tags=["长期资产库"])

@router.get("/sops", summary="SOP列表")
async def list_sops(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success({"module": "长期资产库", "endpoint": "list_sops", "status": "skeleton", "user": user.id})

@router.get("/prompts", summary="Prompt模板列表")
async def list_prompts(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success({"module": "长期资产库", "endpoint": "list_prompts", "status": "skeleton", "user": user.id})

@router.get("/skills", summary="Skill列表")
async def list_skills(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success({"module": "长期资产库", "endpoint": "list_skills", "status": "skeleton", "user": user.id})

@router.get("/memories", summary="项目记忆列表")
async def list_memories(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success({"module": "长期资产库", "endpoint": "list_memories", "status": "skeleton", "user": user.id})

