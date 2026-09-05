# ============================================================
# 左侧信息面板路由（快速待办 + 系统提醒 + 聚合）
# 对应参考UI左侧信息面板
# ============================================================
from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.response import success
from app.schemas.panel import (
    CreateQuickTodoRequest,
    CreateReminderRequest,
    UpdateQuickTodoRequest,
    UpdateReminderRequest,
)
from app.services.panel_service import PanelService


if TYPE_CHECKING:
    from app.models.user import User

router = APIRouter(prefix="/panel", tags=["panel"])
todo_router = APIRouter(prefix="/quick-todos", tags=["panel"])
reminder_router = APIRouter(prefix="/reminders", tags=["panel"])


def _svc(db: Session, user: User) -> PanelService:
    return PanelService(db, user)


# ---------- 左侧面板聚合 ----------
@router.get("")
def left_panel(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(_svc(db, user).get_left_panel())


# ---------- 快速待办 ----------
@todo_router.get("")
def list_todos(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(_svc(db, user).list_todos())


@todo_router.post("")
def create_todo(
    data: CreateQuickTodoRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db, user).create_todo(data))


@todo_router.patch("/{todo_id}")
def update_todo(
    todo_id: str,
    data: UpdateQuickTodoRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db, user).update_todo(todo_id, data))


@todo_router.delete("/{todo_id}")
def delete_todo(
    todo_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _svc(db, user).delete_todo(todo_id)
    return success()


# ---------- 系统提醒 ----------
@reminder_router.get("")
def list_reminders(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(_svc(db, user).list_reminders())


@reminder_router.post("")
def create_reminder(
    data: CreateReminderRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db, user).create_reminder(data))


@reminder_router.patch("/{reminder_id}")
def update_reminder(
    reminder_id: str,
    data: UpdateReminderRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db, user).update_reminder(reminder_id, data))


@reminder_router.delete("/{reminder_id}")
def delete_reminder(
    reminder_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _svc(db, user).delete_reminder(reminder_id)
    return success()
