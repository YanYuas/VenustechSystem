# ============================================================
# 资源中心 API（二期 M7）
# 对齐一期风格：Depends(get_db) + Depends(get_current_user) + success()
# Service层已接入，P0功能待实现
# ============================================================
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.response import success
from app.models.user import User
from app.services.resource_service import ResourceService

router = APIRouter(prefix="/resource", tags=["资源中心"])


def _svc(db: Session) -> ResourceService:
    return ResourceService(db)

@router.get("/inbox", summary="收集箱列表")
async def list_inbox(
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).list_inbox(user.id, status))


@router.post("/inbox", summary="创建收集箱条目")
async def create_inbox_item(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # TODO: P0 接入 CreateInboxItemRequest body
    return success({"module": "资源中心", "endpoint": "create_inbox_item", "status": "skeleton"})


@router.get("/templates", summary="模板列表")
async def list_templates(
    category: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).list_templates(user.id, category))


@router.post("/templates", summary="创建模板")
async def create_template(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success({"module": "资源中心", "endpoint": "create_template", "status": "skeleton"})


@router.get("/domains", summary="领域列表")
async def list_domains(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).list_domains(user.id))

