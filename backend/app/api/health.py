# ============================================================
# 健康检查（Electron 主进程轮询后端就绪）
# ============================================================
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter

from app.config import get_settings
from app.core.response import success

router = APIRouter(tags=["health"])

settings = get_settings()


@router.get("/health")
def health():
    return success(
        {
            "status": "ok",
            "service": settings.app_name,
            "version": settings.version,
            "time": datetime.now().isoformat(),
        }
    )
