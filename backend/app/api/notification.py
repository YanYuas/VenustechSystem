# ============================================================
# 统一通知路由（PRD §12.4）
# ============================================================
from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.response import success
from app.schemas.notification import CreateNotificationRequest, MarkReadRequest
from app.services.notification_service import NotificationService

if TYPE_CHECKING:
    from app.models.user import User

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _svc(db: Session, user: User) -> NotificationService:
    return NotificationService(db, user.id)


@router.get("")
def list_notifications(
    unread_only: bool = False,
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db, user).list(unread_only=unread_only, page=page, page_size=page_size))


@router.get("/stats")
def notification_stats(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(_svc(db, user).stats())


@router.post("")
def create_notification(
    data: CreateNotificationRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db, user).create(data))


@router.patch("/{notification_id}/read")
def mark_read(
    notification_id: str,
    data: MarkReadRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db, user).mark_read(notification_id, read=data.read))


@router.post("/read-all")
def mark_all_read(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    count = _svc(db, user).mark_all_read()
    return success({"marked": count})
