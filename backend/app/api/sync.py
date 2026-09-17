# ============================================================
# 同步路由（S6-3b · P0 抽象层 + 本地适配器）
#
# POST /api/v1/sync/export   导出 JSON 同步包到本地目录
# POST /api/v1/sync/import   导入同步包（diff + LWW 应用，返回统计）
# GET  /api/v1/sync/policy   SYNC_POLICY 表分级（可见性/验收用）
# ============================================================
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.exceptions import ValidationException
from app.core.response import success
from app.core.sync import SyncEngine

if TYPE_CHECKING:
    from app.models.user import User

router = APIRouter(prefix="/sync", tags=["sync"])


class ExportRequest(BaseModel):
    dir: str | None = Field(None, max_length=500)  # 缺省 → {data_dir}/exports


class ImportRequest(BaseModel):
    path: str = Field(..., min_length=1, max_length=500)


def _default_export_dir() -> Path:
    from app.config import get_settings
    d = Path(get_settings().data_dir) / "exports"
    d.mkdir(parents=True, exist_ok=True)
    return d


@router.get("/policy", summary="SYNC_POLICY 表分级")
def policy(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    engine = SyncEngine(db, user.id)
    return success({"policy": engine.policy_report(), "synced_tables": engine.synced_tables()})


@router.get("/packages", summary="列出可导入的同步包（导出目录内，按时间倒序）")
def packages(user: User = Depends(get_current_user)):
    d = _default_export_dir()
    items = [
        {"name": p.name, "path": str(p), "size": p.stat().st_size,
         "modified_at": p.stat().st_mtime}
        for p in sorted(d.glob("qimingxing-sync-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    ]
    return success({"dir": str(d), "items": items[:20]})


@router.post("/export", summary="导出同步包（本地适配器；缺省导出到数据目录 exports/）")
def export(data: ExportRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        target = Path(data.dir) if data.dir else _default_export_dir()
        path = SyncEngine(db, user.id).export_to(target)
    except ValueError as e:
        raise ValidationException(str(e))
    return success({"path": str(path)})


@router.post("/import", summary="导入同步包（diff + LWW）")
def import_(data: ImportRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    engine = SyncEngine(db, user.id)
    try:
        payload = SyncEngine.load_package(Path(data.path))
    except ValueError as e:
        raise ValidationException(str(e))
    if payload.get("user_id") != user.id:
        raise ValidationException("同步包属于其他用户，拒绝导入")
    ops = engine.diff(payload["tables"])
    stats = engine.apply(ops)
    return success({"ops": len(ops), **stats})
