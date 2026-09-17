# ============================================================
# 身份路由（三期 B 阶段 · 横切标签）
#
# GET    /api/v1/identities          列表（含归档）
# POST   /api/v1/identities          创建
# GET    /api/v1/identities/{id}     详情
# PATCH  /api/v1/identities/{id}     更新（slug 不可改）
# DELETE /api/v1/identities/{id}     软删除
# ============================================================
from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.response import success
from app.schemas.identity import CreateIdentityRequest, UpdateIdentityRequest
from app.services.identity_service import IdentityService

if TYPE_CHECKING:
    from app.models.user import User

router = APIRouter(prefix="/identities", tags=["identities"])


def _svc(db: Session, user: User) -> IdentityService:
    return IdentityService(db, user.id)


@router.get("", summary="身份列表")
def list_identities(
    include_archived: bool = True,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db, user).list(include_archived=include_archived))


@router.post("", summary="创建身份")
def create_identity(
    data: CreateIdentityRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db, user).create(data))


@router.get("/{identity_id}", summary="身份详情")
def get_identity(
    identity_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db, user).get(identity_id))


@router.patch("/{identity_id}", summary="更新身份（slug 不可改）")
def update_identity(
    identity_id: str,
    data: UpdateIdentityRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db, user).update(identity_id, data))


@router.delete("/{identity_id}", summary="删除身份（软删除）")
def delete_identity(
    identity_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db, user).delete(identity_id))
