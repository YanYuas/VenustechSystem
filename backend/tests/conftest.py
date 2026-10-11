# ============================================================
# pytest 共享夹具（增强版）
#
# 两层隔离策略：
#   1. Service 层单元测试 → db_session fixture（函数级事务回滚，快且干净）
#   2. API 层集成测试     → clean_db fixture（每个测试前清空业务表）
#
# 为什么 API 层不用事务回滚：
#   database.py 用 NullPool，TestClient 每个请求新建独立 Session，
#   测试代码的 Session 与请求内的 Session 不是同一条连接，无法共享事务。
#   故 API 测试用「清表」实现隔离，Service 测试用「回滚」实现隔离。
# ============================================================
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

# 测试数据目录默认放系统临时目录，避免落在仓库内被同步客户端/杀软锁文件
# （项目已有先例：仓库目录下 SQLite 被同步客户端锁定导致 create_all 永久阻塞）。
# 可用 VENUSTECH_TEST_DATA_DIR 覆盖。
TEST_DATA_DIR = Path(
    os.environ.get("VENUSTECH_TEST_DATA_DIR")
    or (Path(tempfile.gettempdir()) / "venustech_pytest")
)

# 模块级设置环境变量（必须在任何 app 导入之前执行）
os.environ["VENUSTECH_DATA_DIR"] = str(TEST_DATA_DIR)
os.environ["VENUSTECH_DEV"] = "false"
os.environ["VENUSTECH_DEMO_SEED"] = "false"

# 清理旧测试数据
if TEST_DATA_DIR.exists():
    shutil.rmtree(TEST_DATA_DIR, ignore_errors=True)


# ============================================================
# 会话级：app 生命周期 + TestClient
# ============================================================
@pytest.fixture(scope="session", autouse=True)
def _env_setup():
    """会话级：跑迁移建表 + 进入 WAL + 测试后删除数据目录。"""
    from app.migrate import run_migrations

    run_migrations()
    # 与生产启动一致：journal_mode=WAL 只在启动时设置一次（见 app/database.py）。
    # 这里显式调用，保证测试跑在与生产同构的 WAL 模式下。
    from app.database import run_maintenance

    run_maintenance()
    yield
    # 关闭引擎连接，避免 Windows 下 SQLite 文件句柄未释放导致 rmtree 静默失败
    from app.database import engine

    engine.dispose()
    shutil.rmtree(TEST_DATA_DIR, ignore_errors=True)


@pytest.fixture(scope="session")
def client(_env_setup):
    """会话级 TestClient（启动开销大，整个测试会话复用一个实例）。"""
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def default_user_id(client):
    """触发默认用户创建并返回其 id（单用户模式，所有测试共用）。

    直接查库取 id，不依赖 dashboard 响应结构（DashboardUser 不含 id 字段）。
    """
    from app.database import SessionLocal
    from app.repositories import UserRepository

    # 触发一次需要认证的请求，让 get_current_user 自动创建 default_user
    client.get("/api/v1/tasks")
    db = SessionLocal()
    try:
        user = UserRepository(db).get_by_username("default_user")
        assert user is not None, "default_user 未被创建"
        return user.id
    finally:
        db.close()


# ============================================================
# 函数级：Service 层单元测试用（事务回滚隔离）
# ============================================================
@pytest.fixture()
def db_session():
    """函数级独立 Session，测试结束 rollback。

    用法：
        def test_something(db_session):
            svc = TaskService(db_session)
            ...
    """
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


@pytest.fixture()
def test_user(db_session):
    """在回滚事务内创建测试用户，返回 user 对象。

    直接 db.add + flush（不 commit），确保函数结束 rollback 能清理。
    username 用 uuid 保证唯一，避免并发/残留冲突。
    """
    import uuid

    from app.models.user import User

    user = User(
        username=f"test_{uuid.uuid4().hex[:12]}",
        nickname="测试用户",
    )
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture()
def other_user(db_session):
    """第二个测试用户，用于越权测试。"""
    import uuid

    from app.models.user import User

    user = User(
        username=f"other_{uuid.uuid4().hex[:12]}",
        nickname="其他用户",
    )
    db_session.add(user)
    db_session.flush()
    return user


# ============================================================
# 函数级：API 层集成测试用（清表隔离）
# ============================================================
# 清表策略：除「保留表」与 default_user 外，**清空全部业务表**。
# 为什么不再维护一张手写清单：
#   手写清单必须与模型同步维护，漏一个表 → 该表数据跨测试泄漏，
#   而且症状隐蔽（个别测试偶发失败）。改为动态枚举 sqlite_master，
#   新增模块无需改动夹具。
_PRESERVE_TABLES = {"alembic_version"}
_PRESERVE_USERNAME = "default_user"


@pytest.fixture(autouse=True)
def clean_db():
    """每个测试函数执行前清空业务表（API / Service 层共用隔离）。

    实现要点（踩过的坑，改动前务必读完）：

      1. 清表需临时关闭外键，否则父子表删除顺序会互相牵制；
      2. **`PRAGMA foreign_keys` 在事务内是静默无效的**。若用普通 Session
         执行（`db.execute(text("PRAGMA ..."))` 会自动开启事务），PRAGMA 被
         忽略，且会把 `foreign_keys=OFF` **残留在连接上**。NullPool 时代连接
         即用即弃，问题被掩盖；改用连接池后该连接被复用，**级联删除全面失效**
         （2026-07-11 实测：删除 document 后 document_versions 残留 2 行）。
         因此这里用 **AUTOCOMMIT 连接**执行 PRAGMA，并在归还池前恢复
         `foreign_keys=ON`。
      3. 对 Service 层测试同样安全：清表走独立的引擎连接，与测试自身的
         db_session（另一条池连接）互不干扰。
    """
    from app.database import engine

    # AUTOCOMMIT：PRAGMA 才能真正生效（见上方注释 2）
    conn = engine.connect().execution_options(isolation_level="AUTOCOMMIT")
    try:
        conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
        rows = conn.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        for (name,) in rows:
            if name in _PRESERVE_TABLES:
                continue
            if name == "users":
                # 保留 default_user（会话级已创建，清掉会导致后续请求重建、
                # 并使 default_user_id 夹具失效）
                conn.exec_driver_sql(
                    "DELETE FROM users WHERE username <> ?", (_PRESERVE_USERNAME,)
                )
            else:
                conn.exec_driver_sql(f'DELETE FROM "{name}"')
    finally:
        # 必须在归还连接池前恢复，否则污染后续复用该连接的测试
        conn.exec_driver_sql("PRAGMA foreign_keys=ON")
        conn.close()
    yield
