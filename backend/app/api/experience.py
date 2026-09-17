# ============================================================
# 经历视图路由（S6-4 · 只读聚合，不建表）
#
# GET /api/v1/experience   四源（日记/复盘/分身记忆/项目记忆）
#                          按身份过滤后的归并时间线
# ============================================================
from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.response import success
from app.services.experience_service import ExperienceService

if TYPE_CHECKING:
    from app.models.user import User

router = APIRouter(prefix="/experience", tags=["experience"])


@router.get("", summary="经历时间线（四源聚合，只读）")
def list_experience(
    identity_id: str | None = None,
    identity_unassigned: bool = False,
    page: int = 1,
    page_size: int = 30,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    svc = ExperienceService(db, user.id)
    return success(
        svc.list(
            identity_id=identity_id,
            identity_unassigned=identity_unassigned,
            page=page,
            page_size=page_size,
        )
    )
