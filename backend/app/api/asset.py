# ============================================================
# 长期资产库 API（二期 M10）
# 对齐一期风格：Depends(get_db) + Depends(get_current_user) + success()
# Service层已接入，P0功能待实现
# ============================================================
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.response import success
from app.models.user import User
from app.services.asset_service import AssetService

router = APIRouter(prefix="/asset", tags=["长期资产库"])


def _svc(db: Session) -> AssetService:
    return AssetService(db)

@router.get("/sops", summary="SOP列表")
async def list_sops(
    category: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).list_sops(user.id, category))


@router.post("/sops", summary="创建SOP")
async def create_sop(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success({"module": "长期资产库", "endpoint": "create_sop", "status": "skeleton"})


@router.get("/prompts", summary="Prompt模板列表")
async def list_prompts(
    category: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).list_prompts(user.id, category))


@router.post("/prompts", summary="创建Prompt模板")
async def create_prompt(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success({"module": "长期资产库", "endpoint": "create_prompt", "status": "skeleton"})


@router.get("/skills", summary="Skill列表")
async def list_skills(
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).list_skills(user.id))


@router.get("/memories", summary="项目记忆列表")
async def list_memories(
    project_id: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).list_memories(user.id, project_id))

