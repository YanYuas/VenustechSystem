# ============================================================
# 日志（loguru：控制台 + 按天轮转文件，保留 30 天）
# ============================================================
from __future__ import annotations

import sys

from loguru import logger

from app.config import get_settings


def setup_logger() -> None:
    settings = get_settings()
    logger.remove()
    logger.add(
        sys.stderr,
        level=settings.log_level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level:<7}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    )
    logger.add(
        settings.logs_dir / "{time:YYYY-MM-DD}.log",
        rotation="00:00",
        retention="30 days",
        level=settings.log_level,
        encoding="utf-8",
    )


def get_logger(name: str = "app"):
    return logger.bind(name=name)
