# ============================================================
# 人生报告路由（S6-5 · 只读聚合）
#
# GET /api/v1/report   三轴聚合 JSON；前端渲染为单文件 HTML 下载
# ============================================================
from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.response import success
from app.services.report_service import ReportService

if TYPE_CHECKING:
    from app.models.user import User

router = APIRouter(prefix="/report", tags=["report"])


@router.get("", summary="人生报告（身份×成长×档案 三轴聚合）")
def get_report(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(ReportService(db, user.id, user.nickname).get())
