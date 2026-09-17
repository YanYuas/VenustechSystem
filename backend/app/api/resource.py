# ============================================================
# 资源中心 API（二期 M7 P0）
# 收集箱 + 模板库 + 领域库 完整CRUD
# ============================================================
from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.response import success
from app.schemas.resource import CreateInboxItemRequest, UpdateInboxItemRequest, CreateTemplateRequest, CreateDomainRequest
from app.services.resource_service import ResourceService

if TYPE_CHECKING:
    # 仅用于 user 参数的类型标注（依赖注入由 deps.get_current_user 提供），运行期不需要该名字。
    from app.models.user import User

router = APIRouter(prefix="/resource", tags=["资源中心"])


def _svc(db: Session) -> ResourceService:
    return ResourceService(db)


# ==================== 收集箱 ====================

@router.get("/inbox", summary="收集箱列表（分页）")
async def list_inbox(
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).list_inbox(user.id, status, page, page_size))


@router.get("/inbox/{item_id}", summary="收集箱条目详情")
async def get_inbox_item(
    item_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).get_inbox_item(item_id))


@router.post("/inbox", summary="创建收集箱条目")
async def create_inbox_item(
    data: CreateInboxItemRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).create_inbox_item(user.id, data))


@router.patch("/inbox/{item_id}", summary="更新收集箱条目")
async def update_inbox_item(
    item_id: str,
    data: UpdateInboxItemRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).update_inbox_item(item_id, data))


@router.delete("/inbox/{item_id}", summary="删除收集箱条目")
async def delete_inbox_item(
    item_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _svc(db).delete_inbox_item(item_id)
    return success(None)


@router.post("/inbox/{item_id}/process", summary="处理收集箱条目")
async def process_inbox_item(
    item_id: str,
    action: str,
    target_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).process_inbox_item(item_id, action, target_id))


@router.post("/inbox/batch-process", summary="批量处理收集箱条目")
async def batch_process_inbox(
    item_ids: list[str],
    action: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).batch_process(user.id, item_ids, action))


# ==================== 模板库 ====================

@router.get("/templates", summary="模板列表（分页）")
async def list_templates(
    category: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).list_templates(user.id, category, page, page_size))


@router.post("/templates", summary="创建模板")
async def create_template(
    data: CreateTemplateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).create_template(user.id, data))


@router.patch("/templates/{template_id}", summary="更新模板")
async def update_template(
    template_id: str,
    data: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).update_template(template_id, data))


@router.delete("/templates/{template_id}", summary="删除模板")
async def delete_template(
    template_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _svc(db).delete_template(template_id)
    return success(None)


@router.post("/templates/{template_id}/apply", summary="应用模板（变量替换）")
async def apply_template(
    template_id: str,
    variables: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).apply_template(template_id, variables))


# ==================== 领域库 ====================

@router.get("/domains", summary="领域列表")
async def list_domains(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).list_domains(user.id))


@router.post("/domains", summary="创建领域")
async def create_domain(
    data: CreateDomainRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).create_domain(user.id, data))


@router.patch("/domains/{domain_id}", summary="更新领域")
async def update_domain(
    domain_id: str,
    data: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).update_domain(domain_id, data))


@router.delete("/domains/{domain_id}", summary="删除领域")
async def delete_domain(
    domain_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _svc(db).delete_domain(domain_id)
    return success(None)
