# ============================================================
# 桌宠 API（二期 P1）
# 配置 + 形象管理 + 状态感知
# ============================================================
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.response import success
from app.models.user import User
from app.schemas.pet import UpdatePetConfigRequest, CreatePetAvatarRequest
from app.services.pet_service import PetService

router = APIRouter(prefix="/pet", tags=["桌宠"])


def _svc(db: Session) -> PetService:
    return PetService(db)


# ==================== 配置 ====================

@router.get("/config", summary="获取桌宠配置")
async def get_config(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(_svc(db).get_config(user.id))


@router.patch("/config", summary="更新桌宠配置")
async def update_config(
    data: UpdatePetConfigRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).update_config(user.id, data))


# ==================== 形象管理 ====================

@router.get("/avatars", summary="形象列表")
async def list_avatars(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(_svc(db).list_avatars(user.id))


@router.post("/avatars", summary="创建形象")
async def create_avatar(
    data: CreatePetAvatarRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).create_avatar(user.id, data))


@router.patch("/avatars/{avatar_id}", summary="更新形象")
async def update_avatar(
    avatar_id: str,
    data: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).update_avatar(avatar_id, data))


@router.delete("/avatars/{avatar_id}", summary="删除形象")
async def delete_avatar(avatar_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _svc(db).delete_avatar(avatar_id)
    return success(None)


@router.post("/avatars/{avatar_id}/activate", summary="设为当前形象")
async def activate_avatar(
    avatar_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).set_active_avatar(user.id, avatar_id))


# ==================== 状态感知 ====================

@router.get("/state", summary="获取桌宠当前状态（状态感知）")
async def get_state(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(_svc(db).get_current_state(user.id))
