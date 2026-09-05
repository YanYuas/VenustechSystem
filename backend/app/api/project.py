# ============================================================
# 项目管理路由
# ============================================================
from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.response import success
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.services.project_service import ProjectService

if TYPE_CHECKING:
    from app.models.user import User

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("")
def list_projects(
    include_archived: bool = Query(default=False),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(ProjectService(db).list(user.id, include_archived))


@router.post("")
def create_project(
    data: ProjectCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(ProjectService(db).create(user.id, data))


@router.get("/{project_id}")
def get_project(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    p = ProjectService(db).get(user.id, project_id)
    if not p:
        from app.core.exceptions import AppException
        raise AppException(404, "项目不存在", http_status=404)
    return success(p)


@router.patch("/{project_id}")
def update_project(
    project_id: str,
    data: ProjectUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    p = ProjectService(db).update(user.id, project_id, data)
    if not p:
        from app.core.exceptions import AppException
        raise AppException(404, "项目不存在", http_status=404)
    return success(p)


@router.delete("/{project_id}")
def delete_project(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ok = ProjectService(db).delete(user.id, project_id)
    if not ok:
        from app.core.exceptions import AppException
        raise AppException(404, "项目不存在", http_status=404)
    return success()
