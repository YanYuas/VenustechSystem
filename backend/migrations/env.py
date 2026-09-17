# ============================================================
# Alembic 环境（支持程序内 run_migrations 与 CLI 双入口）
#
# 连接串的**唯一真相来源**是 app.config.settings（受 VENUSTECH_DATA_DIR
# 环境变量控制），而不是 alembic.ini 里那行 sqlalchemy.url。
#
# 为什么必须统一（2026-09-16 实测发现的问题）：
#   app/migrate.py（后端启动时自动迁移）会显式执行
#       cfg.set_main_option("sqlalchemy.url", get_settings().db_url)
#   所以那条路径一直是对的。
#
#   但**手动执行 `alembic upgrade head` 走的是本文件**，此前直接读 ini 里
#   写死的 `sqlite:///./data/app.db` —— 于是出现割裂：
#     · 按《分支开发指南》设了 VENUSTECH_DATA_DIR 后用 dev.ps1 启动 → 生效
#       （因为 dev.ps1 起的是 uvicorn，走 migrate.py）
#     · 同一个环境变量下手动跑 alembic → **被无视，迁移静默打到主库**
#
#   同一件事有两个真相来源，必然在某条路径上出错；而出错方式是"静默写错库"，
#   对本地优先应用来说就是**分支开发把主库改了**。此处收敛到 settings。
# ============================================================
import sys
from pathlib import Path

# 保证任意 cwd 下都能 import app 包（Electron 子进程启动）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from logging.config import fileConfig  # noqa: E402

from alembic import context  # noqa: E402
from sqlalchemy import engine_from_config, pool  # noqa: E402

from app import models  # noqa: F401, E402  确保所有表注册到 metadata
from app.config import get_settings  # noqa: E402
from app.database import Base  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    """当前应使用的连接串（由 settings 派生，尊重 VENUSTECH_DATA_DIR）。"""
    return get_settings().db_url


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section, {})
    # 覆盖 ini 中的占位 url —— 否则 CLI 会连到写死的主库
    section["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
