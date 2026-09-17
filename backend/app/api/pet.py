# ============================================================
# 桌宠 API（二期 P1）
# 配置 + 形象管理 + 状态感知
# ============================================================
from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.response import success
from app.schemas.pet import (
    CreatePetAvatarRequest, UpdatePetConfigRequest, UpdatePetStatsRequest,
)
from app.services.pet_service import PetService

if TYPE_CHECKING:
    # 仅用于 user 参数的类型标注（依赖注入由 deps.get_current_user 提供），运行期不需要该名字。
    from app.models.user import User

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


# ==================== 四维陪伴数值（S6-2）====================
# 这两个端点让桌宠数值从 localStorage 迁入数据库 —— 之后备份能带上、
# 换设备不归零。注意必须在 /pet/{...} 之类的通配路由之前定义（目前没有，
# 但保持顺序以防后续新增）。

@router.get("/stats", summary="获取四维陪伴数值（含按时间的惰性衰减）")
async def get_stats(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(_svc(db).get_stats(user.id))


@router.put("/stats", summary="按增量更新四维陪伴数值（互动时调用）")
async def update_stats(
    data: UpdatePetStatsRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).update_stats(user.id, data))
