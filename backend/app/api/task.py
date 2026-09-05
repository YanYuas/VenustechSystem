# ============================================================
# 任务模块路由（PRD §13.3）
# 注意：/tasks/focus、/tasks/today/stats 字面路径必须注册在 /tasks/{id} 之前
# ============================================================
from __future__ import annotations

from typing import TYPE_CHECKING

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.response import success
from app.schemas.task import (
    CreateSubtaskRequest,
    CreateTaskRequest,
    UpdateSubtaskRequest,
    UpdateTaskRequest,
)
from app.services.task_service import TaskService


if TYPE_CHECKING:
    from app.models.user import User

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _svc(db: Session) -> TaskService:
    return TaskService(db)


@router.get("")
def list_tasks(
    status: str | None = None,
    priority: str | None = None,
    project_tag: str | None = None,
    project_id: str | None = None,
    due_date: date | None = None,
    page: int = 1,
    page_size: int = 20,
    sort: str = "-created_at",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    data = _svc(db).list(
        user.id, status=status, priority=priority, project_tag=project_tag,
        project_id=project_id, due_date=due_date,
        page=page, page_size=page_size, sort=sort,
    )
    return success(data)


@router.post("")
def create_task(data: CreateTaskRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(_svc(db).create(user.id, data))


@router.get("/focus")
def get_focus(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(_svc(db).focus(user.id))


@router.get("/today/stats")
def today_stats(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(_svc(db).today_stats(user.id))


@router.post("/{task_id}/focus")
def set_focus(task_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(_svc(db).set_focus(user.id, task_id))


@router.delete("/{task_id}/focus")
def cancel_focus(task_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(_svc(db).cancel_focus(user.id, task_id))


@router.get("/{task_id}")
def task_detail(task_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(_svc(db).detail(user.id, task_id))


@router.patch("/{task_id}")
def update_task(
    task_id: str,
    data: UpdateTaskRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).update(user.id, task_id, data))


@router.delete("/{task_id}")
def delete_task(task_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _svc(db).delete(user.id, task_id)
    return success()


@router.post("/{task_id}/subtasks")
def add_subtask(
    task_id: str,
    data: CreateSubtaskRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).add_subtask(user.id, task_id, data))


@router.patch("/{task_id}/subtasks/{sub_id}")
def update_subtask(
    task_id: str,
    sub_id: str,
    data: UpdateSubtaskRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).update_subtask(user.id, task_id, sub_id, data))


@router.delete("/{task_id}/subtasks/{sub_id}")
def delete_subtask(
    task_id: str,
    sub_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _svc(db).delete_subtask(user.id, task_id, sub_id)
    return success()
