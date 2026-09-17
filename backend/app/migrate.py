# ============================================================
# Alembic 迁移入口（程序内调用，兼容 Electron 子进程任意 cwd）
# ============================================================
from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config

from app.config import get_settings


def run_migrations() -> None:
    """执行数据库迁移到 head（启动 lifespan 调用）。"""
    backend_dir = Path(__file__).resolve().parent.parent
    cfg = Config(str(backend_dir / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_dir / "migrations"))
    cfg.set_main_option("sqlalchemy.url", get_settings().db_url)
    command.upgrade(cfg, "head")
