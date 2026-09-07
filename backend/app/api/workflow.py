# ============================================================
# 工作流 API（二期 P1）
# ============================================================
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.response import success
from app.models.user import User
from app.schemas.workflow import CreateWorkflowRequest, ApplyWorkflowRequest
from app.services.workflow_service import WorkflowService

router = APIRouter(prefix="/workflows", tags=["工作流"])


def _svc(db: Session) -> WorkflowService:
    return WorkflowService(db)


@router.get("/presets", summary="预设工作流列表")
async def list_presets(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(_svc(db).list_presets())


@router.get("", summary="工作流列表（分页+分类筛选）")
async def list_workflows(
    category: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).list_workflows(category, page, page_size))


@router.get("/{workflow_id}", summary="工作流详情")
async def get_workflow(workflow_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(_svc(db).get_workflow(workflow_id))


@router.post("", summary="创建自定义工作流")
async def create_workflow(
    data: CreateWorkflowRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).create_workflow(user.id, data))


@router.patch("/{workflow_id}", summary="更新工作流")
async def update_workflow(
    workflow_id: str,
    data: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).update_workflow(workflow_id, data))


@router.delete("/{workflow_id}", summary="删除工作流")
async def delete_workflow(workflow_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _svc(db).delete_workflow(workflow_id)
    return success(None)


@router.post("/{workflow_id}/apply", summary="一键应用工作流")
async def apply_workflow(
    workflow_id: str,
    data: ApplyWorkflowRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).apply_workflow(user.id, workflow_id, data))


@router.get("/applications/history", summary="工作流应用历史")
async def list_applications(
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).list_applications(user.id, page, page_size))
