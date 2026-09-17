# ============================================================
# 健康检查 + 系统信息（M09 P0）
# Electron 主进程轮询后端就绪 + 前端设置页展示系统状态
# ============================================================
from __future__ import annotations

import logging
import os
import platform
import sys
from datetime import datetime

from fastapi import APIRouter
from sqlalchemy import text

from app.config import get_settings
from app.core.response import success
from app.database import engine

logger = logging.getLogger("app.health")

router = APIRouter(tags=["health"])

settings = get_settings()


def _get_disk_usage(path: str) -> dict:
    """获取磁盘使用情况"""
    try:
        import shutil
        total, used, free = shutil.disk_usage(path)
        return {
            "total_gb": round(total / (1024 ** 3), 2),
            "used_gb": round(used / (1024 ** 3), 2),
            "free_gb": round(free / (1024 ** 3), 2),
            "usage_percent": round(used / total * 100, 1),
        }
    except Exception:
        logger.warning("磁盘使用率读取失败，降级为 0: %s", path, exc_info=True)
        return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "usage_percent": 0}


def _get_db_size() -> float:
    """获取数据库文件大小（MB）。

    修复（2026-09-15）：原实现读 `settings.database_url`，但 Settings 上**没有该属性**
    （实际属性名是 `db_url`），getattr 恒取到 "" → startswith 判断永远为假
    → 函数恒返回 0.0，健康检查与设置页的「数据库大小」永远是 0 MB。
    改为直接使用 `settings.db_path`（已是指向库文件的 Path），比解析 URL 更可靠。
    """
    try:
        db_path = getattr(settings, "db_path", None)
        if db_path and os.path.exists(db_path):
            return round(os.path.getsize(db_path) / (1024 * 1024), 2)
    except Exception:
        logger.warning("数据库大小读取失败", exc_info=True)
    return 0.0


def _check_db_connection() -> bool:
    """检查数据库连接。

    修复（2026-09-15）：原实现传裸字符串 `conn.execute("SELECT 1")`，在 SQLAlchemy 2.0
    下抛 `ObjectNotExecutableError` 并被 except 吞掉 → 函数恒返回 False，
    **数据库明明可连，健康检查却永远报「未连接」**。改用 text() 包裹。
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        logger.warning("数据库连接检查失败", exc_info=True)
        return False


@router.get("/health")
def health():
    """基础健康检查"""
    return success(
        {
            "status": "ok",
            "service": settings.app_name,
            "version": settings.version,
            "time": datetime.now().isoformat(),
        }
    )


@router.get("/health/detailed")
def health_detailed():
    """详细健康检查：系统信息 + 数据库 + 存储"""
    data_dir = getattr(settings, "data_dir", os.path.join(os.path.expanduser("~"), ".venustech"))
    return success(
        {
            "status": "ok",
            "service": settings.app_name,
            "version": settings.version,
            "time": datetime.now().isoformat(),
            "uptime": None,  # 后续可添加上线时间统计
            "system": {
                "os": platform.system(),
                "os_version": platform.version(),
                "platform": platform.platform(),
                "python_version": sys.version.split()[0],
                "machine": platform.machine(),
                "processor": platform.processor() or "unknown",
            },
            "database": {
                "connected": _check_db_connection(),
                "type": "sqlite",
                "size_mb": _get_db_size(),
            },
            "storage": _get_disk_usage(data_dir),
            "data_dir": os.path.abspath(data_dir),
            "paths": {
                "data_dir": os.path.abspath(data_dir),
                "backup_dir": os.path.abspath(os.path.join(data_dir, "backups")),
                "log_dir": os.path.abspath(os.path.join(data_dir, "logs")),
            },
        }
    )


@router.get("/system/info")
def system_info():
    """系统信息（供设置页展示）"""
    data_dir = getattr(settings, "data_dir", os.path.join(os.path.expanduser("~"), ".venustech"))
    return success(
        {
            "app": {
                "name": settings.app_name,
                "version": settings.version,
                "slogan": "方向启明，人生推演",
            },
            "system": {
                "os": platform.system(),
                "os_version": platform.version(),
                "python": sys.version.split()[0],
            },
            "data_dir": os.path.abspath(data_dir),
            "database_size_mb": _get_db_size(),
            "disk": _get_disk_usage(data_dir),
        }
    )