# ============================================================
# 数据库连接（SQLite WAL + 小连接池 + PRAGMA 调优）
# 对齐技术架构 v2.0 §5.1-5.2
# ============================================================
from __future__ import annotations

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.config import get_settings

# Base 定义在 models.base，此处再导出供 Alembic env/迁移引用
from app.models.base import Base  # noqa: F401

settings = get_settings()

# 小连接池（QueuePool），**不再用 NullPool**。
#
# 历史沿革：
#   1) 最初用 StaticPool 单连接 → 被 FastAPI 线程池多线程共享，两个请求的
#      事务在同一条连接上交错，未提交的写入会被别的请求 commit/rollback 波及；
#   2) 改用 NullPool（每次 checkout 新建、用完即关）解决了交错问题，
#      **但引入了更隐蔽的缺陷**（2026-10-10 实测定位）：
#
#      NullPool + WAL 组合下连接被反复开关，**最后一条连接关闭时 SQLite 会
#      对 WAL 做 checkpoint 并把 `-wal`/`-shm` 拆掉**；紧随其后新建的连接
#      撞上 WAL 重建/恢复窗口，会被 SQLite 标记为只读，写入报
#      `sqlite3.OperationalError: attempt to write a readonly database`。
#      该标记是**连接级且瞬时**的：换一条新连接立刻恢复正常（实测印证）。
#
#      实测数据（backend/tests，同一组合跑 4 次）：
#        · NullPool ：2~4 条随机失败，单轮 ~22s
#        · 小连接池 ：0 条失败（4/4 稳定），单轮 ~8s
#
#   3) 现在用 QueuePool：每个 Session 从池中独占一条连接 →
#      **既不会跨请求交错**（保留 2 的收益），又让池中常驻连接**托住 WAL
#      不被反复拆除**（消除只读竞态）。附带收益：省去反复建连开销，测试
#      套件整体提速约 60%。
#
# 池容量：本地单用户应用，峰并发个位数，5+5 足够。
engine = create_engine(
    settings.db_url,
    connect_args={"check_same_thread": False},
    pool_size=5,
    max_overflow=5,
    pool_recycle=1800,
    echo=False,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_conn, _record):
    """连接时执行 PRAGMA 调优（对齐架构 v2.0 §5.1）。

    注意：**这里刻意不设置 `journal_mode=WAL`**。
    journal_mode 是**数据库文件的持久属性**（写进文件头一次即长期有效），
    不是连接级设置。若放在这里逐连接执行：

      1. 属多余开销（属性早已持久化）；
      2. 每条连接都要重新声明 WAL，与「最后一条连接关闭时 SQLite 对 WAL
         做 checkpoint」相互竞争，会让连接被标记为只读，写入抛
         `sqlite3.OperationalError: attempt to write a readonly database`
         （2026-10-10 实测：开启本行时测试套件随机 2~4 条失败，移除后稳定）。

    WAL 改由 `run_maintenance()` 在应用启动时设置一次。
    其余 PRAGMA 是**连接级**的，必须每条连接都设。
    """
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA busy_timeout=5000")     # 写锁等待 5s
    cur.execute("PRAGMA foreign_keys=ON")       # 外键约束
    cur.execute("PRAGMA cache_size=-20000")     # 20MB 缓存
    cur.execute("PRAGMA temp_store=MEMORY")     # 临时表内存
    cur.execute("PRAGMA synchronous=NORMAL")    # WAL 下足够安全，更快
    cur.close()


def run_maintenance() -> None:
    """启动时维护：进入 WAL 模式 + WAL checkpoint 截断 + 优化查询计划。

    `journal_mode=WAL` 是持久属性，只在启动时设置一次即可（见上方注释）。
    设置失败不致命：退化为 DELETE journal（功能正确，仅并发写性能下降），
    因此这里不让异常冒泡阻断启动。
    """
    from app.core.logger import get_logger

    logger = get_logger("database")
    with engine.connect() as conn:
        # 只需一次；返回值为最终生效的 journal_mode（'wal' / 'delete' ...）
        try:
            mode = conn.exec_driver_sql("PRAGMA journal_mode=WAL").scalar()
            if str(mode).lower() != "wal":
                logger.warning("WAL 模式未能启用，当前 journal_mode={}（功能正常，并发写性能下降）", mode)
        except Exception:  # noqa: BLE001 — 降级不阻断启动
            logger.exception("设置 WAL 模式失败，退化为默认 journal 模式")
        conn.exec_driver_sql("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.exec_driver_sql("PRAGMA optimize")
