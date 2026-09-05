# ============================================================
# 数据库连接（SQLite WAL + NullPool + PRAGMA 调优）
# 对齐技术架构 v2.0 §5.1-5.2
# ============================================================
from __future__ import annotations

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.config import get_settings

# Base 定义在 models.base，此处再导出供 Alembic env/迁移引用
from app.models.base import Base  # noqa: F401

settings = get_settings()

# NullPool：每次 checkout 新建连接、用完即关。
# 之前用 StaticPool 单连接被 FastAPI 线程池多线程共享，两个请求的事务
# 在同一条连接上交错，未提交的写入会被别的请求 commit/rollback 波及。
# WAL 支持多连接并发读 + 单写排队，busy_timeout=5000 兜底写锁竞争。
engine = create_engine(
    settings.db_url,
    connect_args={"check_same_thread": False},
    poolclass=NullPool,
    echo=False,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_conn, _record):
    """连接时执行 PRAGMA 调优（对齐架构 v2.0 §5.1）。"""
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")      # 读写并发 + 崩溃恢复
    cur.execute("PRAGMA busy_timeout=5000")     # 写锁等待 5s
    cur.execute("PRAGMA foreign_keys=ON")       # 外键约束
    cur.execute("PRAGMA cache_size=-20000")     # 20MB 缓存
    cur.execute("PRAGMA temp_store=MEMORY")     # 临时表内存
    cur.execute("PRAGMA synchronous=NORMAL")    # WAL 下足够安全，更快
    cur.close()


def run_maintenance() -> None:
    """启动时维护：WAL checkpoint 截断 + 优化查询计划。"""
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.exec_driver_sql("PRAGMA optimize")
