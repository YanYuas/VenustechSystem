# ============================================================
# 复盘路由（PRD §13.6）
# GET /reviews/{date} 用日期；DELETE/POST 用 UUID id
# ============================================================
from __future__ import annotations

from typing import TYPE_CHECKING

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.response import success
from app.schemas.review import ConvertTaskRequest, UpsertReviewRequest
from app.services.review_service import ReviewService


if TYPE_CHECKING:
    from app.models.user import User

router = APIRouter(prefix="/reviews", tags=["reviews"])


def _svc(db: Session, user: User) -> ReviewService:
    return ReviewService(db, user.id)


@router.get("")
def list_reviews(
    type: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db, user).list(type_=type, page=page, page_size=page_size))


@router.put("")
def upsert_review(data: UpsertReviewRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(_svc(db, user).upsert(data))


@router.get("/{review_date}")
def get_review(review_date: date, type: str = "daily", db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(_svc(db, user).get(review_date, type))


@router.delete("/{review_id}")
def delete_review(review_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _svc(db, user).delete(review_id)
    return success()


@router.get("/{review_date}/auto-fill")
def auto_fill(review_date: date, type: str = "daily", db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(_svc(db, user).auto_fill(review_date, type))


@router.post("/{review_id}/convert-task")
def convert_task(
    review_id: str,
    data: ConvertTaskRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db, user).convert_task(review_id, data))
