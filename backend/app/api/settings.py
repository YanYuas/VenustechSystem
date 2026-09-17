# ============================================================
# 用户配置路由（PRD §15.11）
# ------------------------------------------------------------
# GET /api/v1/settings          读取全部配置（含默认值）
# PUT /api/v1/settings          批量写入配置
# ============================================================
from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.response import success
from app.schemas.settings import UpdateSettingsRequest
from app.services.settings_service import SettingsService

if TYPE_CHECKING:
    from app.models.user import User

router = APIRouter(prefix="/settings", tags=["settings"])


def _svc(db: Session, user: User) -> SettingsService:
    return SettingsService(db, user.id)


@router.get("", summary="读取用户配置")
def list_settings(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success({"values": _svc(db, user).all()})


@router.put("", summary="批量写入用户配置")
def update_settings(
    data: UpdateSettingsRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success({"values": _svc(db, user).set_many(data.values)})
