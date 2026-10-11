# ============================================================
# 经历视图路由（S6-4 · 只读聚合，不建表）
#
# GET /api/v1/experience   四源（日记/复盘/分身记忆/项目记忆）
#                          按身份过滤后的归并时间线
# ============================================================
from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.response import success
from app.services.experience_service import ExperienceService

if TYPE_CHECKING:
    from app.models.user import User

router = APIRouter(prefix="/experience", tags=["experience"])

# 分页边界：page_size 上限与 events.py 的 limit 上限一致（同为列表类端点）。
# 为什么要显式约束：裸 int 参数下 `page=0` 会算成 start=-30 → 切片为空 →
# **HTTP 200 但 items 为空**（静默失败，用户只看到「没数据」）；
# `page_size=-1` 同理。参见 tests/test_experience_api.py 第 3 组。
MAX_PAGE_SIZE = 500


@router.get("", summary="经历时间线（四源聚合，只读）")
def list_experience(
    identity_id: str | None = None,
    identity_unassigned: bool = False,
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(30, ge=1, le=MAX_PAGE_SIZE, description=f"每页条数，1-{MAX_PAGE_SIZE}"),
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
