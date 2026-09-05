# ============================================================
# 项目管理路由（M06 深度开发：CRUD + 归档恢复 + 统计 + 里程碑 + 详情聚合）
# 注意：/projects/milestones/{mid} 字面路径注册在 /projects/{project_id} 之前
# ============================================================
from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.response import success
from app.schemas.project import (
    MilestoneCreate,
    MilestoneUpdate,
    ProjectCreate,
    ProjectUpdate,
)
from app.services.project_service import ProjectService

if TYPE_CHECKING:
    from app.models.user import User

router = APIRouter(prefix="/projects", tags=["projects"])


def _svc(db: Session) -> ProjectService:
    return ProjectService(db)


@router.get("")
def list_projects(
    include_archived: bool = Query(default=False),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).list(user.id, include_archived))


@router.post("")
def create_project(
    data: ProjectCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).create(user.id, data))


# ---------- 里程碑（字面路径，需先于 /{project_id} 注册） ----------

@router.patch("/milestones/{milestone_id}")
def update_milestone(
    milestone_id: str,
    data: MilestoneUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).update_milestone(user.id, milestone_id, data))


@router.delete("/milestones/{milestone_id}")
def delete_milestone(
    milestone_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _svc(db).delete_milestone(user.id, milestone_id)
    return success()


# ---------- 项目详情 / 归档 / 统计 ----------

@router.get("/{project_id}")
def get_project(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # M06 F01：详情聚合（基础信息 + 任务/文档/对话/复盘/里程碑 + 统计）
    return success(_svc(db).detail(user.id, project_id))


@router.patch("/{project_id}")
def update_project(
    project_id: str,
    data: ProjectUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).update(user.id, project_id, data))


@router.delete("/{project_id}")
def delete_project(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _svc(db).delete(user.id, project_id)
    return success()


@router.post("/{project_id}/archive")
def archive_project(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).archive(user.id, project_id))


@router.post("/{project_id}/restore")
def restore_project(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).restore(user.id, project_id))


@router.get("/{project_id}/stats")
def project_stats(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).stats(user.id, project_id))


@router.get("/{project_id}/milestones")
def list_milestones(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).list_milestones(user.id, project_id))


@router.post("/{project_id}/milestones")
def create_milestone(
    project_id: str,
    data: MilestoneCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).create_milestone(user.id, project_id, data))
