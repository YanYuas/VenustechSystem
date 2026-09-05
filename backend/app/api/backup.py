# ============================================================
# 备份 / 数据统计 路由（PRD §13.8）
# ============================================================
from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.response import success
from app.services.backup_service import BackupService


if TYPE_CHECKING:
    from app.models.user import User

router = APIRouter(prefix="/backup", tags=["backup"])
data_router = APIRouter(prefix="/data", tags=["data"])


def _svc(db: Session, user: User) -> BackupService:
    return BackupService(db, user.id)


@router.post("/export")
def export(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(_svc(db, user).export())


@router.post("/import")
def import_backup(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # 同步路由（线程池执行）：zip 校验/解压/写盘最多 100MB，
    # 若为 async def 会全程阻塞事件循环，卡死所有并发请求（含 30s 轮询）
    content = file.file.read()
    return success(_svc(db, user).import_(content, file.filename or "backup.zip"))


@data_router.get("/stats")
def data_stats(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(_svc(db, user).stats())
