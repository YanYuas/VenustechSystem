# ============================================================
# 资源中心 API（二期骨架）
# 对齐一期风格：Depends(get_db) + Depends(get_current_user) + success()
# ============================================================
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.response import success
from app.models.user import User

router = APIRouter(prefix="/resource", tags=["资源中心"])

@router.get("/inbox", summary="收集箱列表")
async def list_inbox(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success({"module": "资源中心", "endpoint": "list_inbox", "status": "skeleton", "user": user.id})

@router.get("/templates", summary="模板列表")
async def list_templates(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success({"module": "资源中心", "endpoint": "list_templates", "status": "skeleton", "user": user.id})

@router.get("/domains", summary="领域列表")
async def list_domains(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success({"module": "资源中心", "endpoint": "list_domains", "status": "skeleton", "user": user.id})

