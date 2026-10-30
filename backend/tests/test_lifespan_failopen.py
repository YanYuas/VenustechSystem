# ============================================================
# app/main.py 生命周期（lifespan）异常路径与幂等测试（Phase9-B）
#
# 背景：lifespan 里有 7 个启动步骤，其中只有一部分是 fail-open（加密初始化、
# 重复任务、自动备份），其余（迁移/维护/种子/事件订阅注册）按设计是 fatal。
# 这些分支平时不跑，Phase6 term-missing 里 main.py 有 19 行未覆盖 —— 本文件
# 用 monkeypatch 把每一步替换成「记录器」或「抛异常」，逐条断言：
#   · fail-open 步骤抛异常时应用仍能启动 + 对应日志 + 后续步骤仍执行；
#   · fatal 步骤抛异常时启动中断 + 后续步骤**不得**执行（防止误以为 fail-open）；
#   · 正常路径的步骤顺序 / 只执行一次 / 可重复执行；
#   · create_app 的插件失败 fail-open、插件路由前缀、异常处理器（业务/校验/未捕获）；
#   · `if __name__ == "__main__"` 的 uvicorn 启动参数（runpy + 假 uvicorn，不起端口）。
#
# 铁律：**不真启动 uvicorn/端口**；lifespan 里的副作用步骤全部打桩（除被测项），
# 不向全局 event_bus 重复注册订阅者（否则会污染同进程其它用例）。
# ============================================================
from __future__ import annotations

import asyncio
import logging
import runpy
import sys
import types
import uuid
from pathlib import Path

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from app import main as main_mod
from app.core.exceptions import NotFoundException
from app.models.user import User
from app.repositories import UserRepository


# ---------------------------------------------------------------- helpers
def _make_committed_user(db_session, prefix: str = "life") -> User:
    """建一个**已提交**用户：lifespan 用自己的 SessionLocal，读不到未提交行。"""
    user = UserRepository(db_session).create(
        username=f"{prefix}-{uuid.uuid4().hex[:10]}", nickname="生命周期测试"
    )
    db_session.commit()
    return user


def _run_lifespan() -> str:
    """在独立事件循环里跑一次完整 lifespan（含 startup + shutdown）。"""

    async def _go() -> str:
        async with main_mod.lifespan(FastAPI()):
            return "started"

    return asyncio.run(_go())


@pytest.fixture()
def steps(monkeypatch):
    """把 lifespan 的所有副作用步骤替换为记录器，返回 calls 列表。

    默认全部为无害桩；单个用例再 monkeypatch 其中一项为抛异常版本。
    注意：加密初始化 / TaskService / BackupService 是在 lifespan **函数体内**
    import 的，所以必须 patch 源模块的同名属性，而不是 main 模块。
    """
    calls: list = []

    monkeypatch.setattr(main_mod, "setup_logger", lambda: calls.append("setup_logger"))
    monkeypatch.setattr(main_mod, "run_migrations", lambda: calls.append("run_migrations"))
    monkeypatch.setattr(main_mod, "run_maintenance", lambda: calls.append("run_maintenance"))
    monkeypatch.setattr(
        main_mod, "seed_if_empty", lambda db: calls.append("seed_if_empty") or True
    )
    monkeypatch.setattr(
        main_mod, "register_event_handlers", lambda: calls.append("register_event")
    )
    monkeypatch.setattr(
        main_mod, "register_growth_handlers", lambda: calls.append("register_growth")
    )
    monkeypatch.setattr(
        main_mod, "set_event_loop", lambda loop: calls.append(("set_loop", loop))
    )

    import app.core.encryption as encryption_mod

    monkeypatch.setattr(
        encryption_mod,
        "init_encryption",
        lambda data_dir: calls.append(("init_encryption", Path(data_dir))),
    )

    # 重复任务：TaskService 在 lifespan 内 import
    import app.services.task_service as task_service_mod

    class FakeTaskService:
        def __init__(self, db):
            self.db = db

        def generate_recurring_instances(self, user_id: str) -> int:
            calls.append(("recurring", user_id))
            return 0

    monkeypatch.setattr(task_service_mod, "TaskService", FakeTaskService)

    # 自动备份：BackupService 在 lifespan 内 import
    import app.services.backup_service as backup_service_mod

    class FakeBackupService:
        def __init__(self, db, user_id):
            self.user_id = user_id

        def auto_backup_if_due(self):
            calls.append(("backup", self.user_id))
            return {"ran": False}

    monkeypatch.setattr(backup_service_mod, "BackupService", FakeBackupService)
    return calls


def _fake_settings(tmp_path: Path, demo_seed: bool = False):
    """lifespan 只用到 data_dir / demo_seed 两个属性。"""
    return types.SimpleNamespace(data_dir=tmp_path, demo_seed=demo_seed)


# ================================================================
# 一、正常路径：顺序 / 幂等 / 日志
# ================================================================
class TestLifespanHappyPath:
    def test_steps_run_once_in_order(self, steps, db_session, tmp_path, monkeypatch):
        monkeypatch.setattr(main_mod, "settings", _fake_settings(tmp_path))
        _make_committed_user(db_session)
        assert _run_lifespan() == "started"

        assert steps.index("setup_logger") == 0
        assert steps.index("run_migrations") < steps.index("run_maintenance")
        first_tuple_pos = next(
            i for i, step in enumerate(steps) if isinstance(step, tuple)
        )
        assert steps.index("run_maintenance") < first_tuple_pos
        # 事件与成长订阅者：事件先注册、成长后注册
        assert steps.index("register_event") < steps.index("register_growth")
        # 每个「一次性步骤」只执行一次
        for step in ("setup_logger", "run_migrations", "run_maintenance",
                     "register_event", "register_growth"):
            assert steps.count(step) == 1
        # set_event_loop 必须拿到真实运行中的事件循环
        loop_calls = [s for s in steps if isinstance(s, tuple) and s[0] == "set_loop"]
        assert len(loop_calls) == 1
        assert isinstance(loop_calls[0][1], asyncio.AbstractEventLoop)

    def test_logs_startup_complete_and_encryption_ready(self, steps, tmp_path, monkeypatch, caplog):
        monkeypatch.setattr(main_mod, "settings", _fake_settings(tmp_path))
        with caplog.at_level(logging.INFO):
            _run_lifespan()
        assert "加密管理器已初始化" in caplog.text
        assert "后端启动完成" in caplog.text

    def test_lifespan_is_repeatable(self, steps, tmp_path, monkeypatch):
        """重复执行（测试/热重载场景）不破坏幂等缝：每一步各 2 次。"""
        monkeypatch.setattr(main_mod, "settings", _fake_settings(tmp_path))
        _run_lifespan()
        _run_lifespan()
        assert steps.count("run_migrations") == 2
        assert steps.count("register_event") == 2
        assert steps.count("register_growth") == 2

    def test_demo_seed_runs_only_when_enabled(self, steps, db_session, tmp_path, monkeypatch):
        monkeypatch.setattr(main_mod, "settings", _fake_settings(tmp_path, demo_seed=False))
        _run_lifespan()
        assert "seed_if_empty" not in steps

        steps.clear()
        monkeypatch.setattr(main_mod, "settings", _fake_settings(tmp_path, demo_seed=True))
        _run_lifespan()
        assert steps.count("seed_if_empty") == 1


# ================================================================
# 二、fatal 步骤：必须中断启动，且后续步骤不执行
# ================================================================
class TestLifespanFatalSteps:
    def test_migration_failure_aborts_startup(self, steps, tmp_path, monkeypatch):
        monkeypatch.setattr(main_mod, "settings", _fake_settings(tmp_path))

        def _boom():
            raise RuntimeError("migrate boom")

        monkeypatch.setattr(main_mod, "run_migrations", _boom)
        with pytest.raises(RuntimeError, match="migrate boom"):
            _run_lifespan()
        assert steps == ["setup_logger"]          # 迁移之后的所有步骤都没跑

    def test_maintenance_failure_aborts_startup(self, steps, tmp_path, monkeypatch):
        monkeypatch.setattr(main_mod, "settings", _fake_settings(tmp_path))

        def _boom():
            raise RuntimeError("maintenance boom")

        monkeypatch.setattr(main_mod, "run_maintenance", _boom)
        with pytest.raises(RuntimeError, match="maintenance boom"):
            _run_lifespan()
        assert "run_maintenance" not in steps
        assert not any(isinstance(s, tuple) for s in steps)   # 加密/set_loop 都没到

    def test_event_handler_registration_failure_aborts_startup(
        self, steps, tmp_path, monkeypatch
    ):
        """设计如此：订阅者注册失败 = 事件永远不处理，启动应失败而非静默。

        （对照：加密/重复任务/自动备份是 fail-open。）
        """
        monkeypatch.setattr(main_mod, "settings", _fake_settings(tmp_path))

        def _boom():
            raise RuntimeError("subscribe boom")

        monkeypatch.setattr(main_mod, "register_event_handlers", _boom)
        with pytest.raises(RuntimeError, match="subscribe boom"):
            _run_lifespan()
        assert "register_growth" not in steps

    def test_growth_handler_registration_failure_aborts_startup(
        self, steps, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(main_mod, "settings", _fake_settings(tmp_path))

        def _boom():
            raise RuntimeError("growth subscribe boom")

        monkeypatch.setattr(main_mod, "register_growth_handlers", _boom)
        with pytest.raises(RuntimeError, match="growth subscribe boom"):
            _run_lifespan()
        assert "register_event" in steps          # 前一步已执行

    def test_demo_seed_failure_propagates(self, steps, tmp_path, monkeypatch):
        """观察记录：demo_seed 分支**没有** try/except（main.py:59-60）。

        demo 模式下种子失败会阻断启动；默认生产配置 demo_seed=False 不受影响。
        本用例钉住现状，避免未来无意把它变成静默失败。
        """
        monkeypatch.setattr(main_mod, "settings", _fake_settings(tmp_path, demo_seed=True))

        def _boom(db):
            raise ValueError("seed boom")

        monkeypatch.setattr(main_mod, "seed_if_empty", _boom)
        with pytest.raises(ValueError, match="seed boom"):
            _run_lifespan()
        assert "register_event" not in steps


# ================================================================
# 三、fail-open 步骤：抛异常应用仍启动 + 有日志 + 后续步骤继续
# ================================================================
class TestLifespanFailOpen:
    def test_encryption_init_failure_is_fail_open(
        self, steps, db_session, tmp_path, monkeypatch, caplog
    ):
        monkeypatch.setattr(main_mod, "settings", _fake_settings(tmp_path))
        import app.core.encryption as encryption_mod

        def _boom(_data_dir):
            raise OSError("no key dir")

        monkeypatch.setattr(encryption_mod, "init_encryption", _boom)
        _make_committed_user(db_session)

        with caplog.at_level(logging.INFO):
            assert _run_lifespan() == "started"
        assert "加密管理器初始化失败（敏感信息加密将不可用）" in caplog.text
        assert "加密管理器已初始化" not in caplog.text
        # 失败不阻断：后续订阅注册照常
        assert "register_event" in steps and "register_growth" in steps

    def test_recurring_task_failure_is_fail_open(
        self, steps, db_session, tmp_path, monkeypatch, caplog
    ):
        monkeypatch.setattr(main_mod, "settings", _fake_settings(tmp_path))
        import app.services.task_service as task_service_mod

        class ExplodingTaskService:
            def __init__(self, db):
                pass

            def generate_recurring_instances(self, user_id):
                raise RuntimeError("recurring boom")

        monkeypatch.setattr(task_service_mod, "TaskService", ExplodingTaskService)
        _make_committed_user(db_session)

        with caplog.at_level(logging.INFO):
            assert _run_lifespan() == "started"
        assert "重复任务生成失败（不影响启动）" in caplog.text
        assert "register_event" in steps

    def test_recurring_success_logs_generated_count(
        self, steps, db_session, tmp_path, monkeypatch, caplog
    ):
        from sqlalchemy import func, select

        from app.database import SessionLocal

        monkeypatch.setattr(main_mod, "settings", _fake_settings(tmp_path))
        import app.services.task_service as task_service_mod

        class CountingTaskService:
            def __init__(self, db):
                pass

            def generate_recurring_instances(self, user_id):
                return 2

        monkeypatch.setattr(task_service_mod, "TaskService", CountingTaskService)
        _make_committed_user(db_session)
        # lifespan 对**每个用户**都调一次；全量跑时库里还有 default_user，
        # 所以期望值必须按真实用户数动态算，不能写死 2。
        probe = SessionLocal()
        try:
            user_count = int(probe.scalar(select(func.count()).select_from(User)) or 0)
        finally:
            probe.close()
        assert user_count >= 1

        with caplog.at_level(logging.INFO):
            _run_lifespan()
        assert f"重复任务生成 {2 * user_count} 个实例" in caplog.text

    def test_recurring_runs_for_each_existing_user(self, steps, db_session, tmp_path, monkeypatch):
        monkeypatch.setattr(main_mod, "settings", _fake_settings(tmp_path))
        first = _make_committed_user(db_session, prefix="life-a")
        second = _make_committed_user(db_session, prefix="life-b")

        _run_lifespan()
        recurring_users = {s[1] for s in steps if isinstance(s, tuple) and s[0] == "recurring"}
        assert {first.id, second.id} <= recurring_users

    def test_backup_ran_logs_path(self, steps, db_session, tmp_path, monkeypatch, caplog):
        monkeypatch.setattr(main_mod, "settings", _fake_settings(tmp_path))
        import app.services.backup_service as backup_service_mod

        class RanBackupService:
            def __init__(self, db, user_id):
                pass

            def auto_backup_if_due(self):
                return {"ran": True, "path": "/tmp/demo-backup.zip"}

        monkeypatch.setattr(backup_service_mod, "BackupService", RanBackupService)
        _make_committed_user(db_session)

        with caplog.at_level(logging.INFO):
            _run_lifespan()
        assert "自动备份完成: /tmp/demo-backup.zip" in caplog.text

    def test_backup_failure_is_fail_open(
        self, steps, db_session, tmp_path, monkeypatch, caplog
    ):
        monkeypatch.setattr(main_mod, "settings", _fake_settings(tmp_path))
        import app.services.backup_service as backup_service_mod

        class ExplodingBackupService:
            def __init__(self, db, user_id):
                pass

            def auto_backup_if_due(self):
                raise RuntimeError("backup boom")

        monkeypatch.setattr(backup_service_mod, "BackupService", ExplodingBackupService)
        _make_committed_user(db_session)

        with caplog.at_level(logging.INFO):
            assert _run_lifespan() == "started"
        assert "自动备份检查失败（不影响启动）" in caplog.text
        assert "register_growth" in steps


# ================================================================
# 四、create_app：插件 fail-open / 路由前缀 / 中间件
# ================================================================
@pytest.fixture()
def quiet_plugins(monkeypatch):
    """把插件装配替换为无害桩，让 create_app 快速、无副作用。"""
    from app.core.plugin_manager import plugin_manager

    calls: list = []
    monkeypatch.setattr(plugin_manager, "initialize", lambda **kw: calls.append("initialize"))
    monkeypatch.setattr(plugin_manager, "discover", lambda *a, **kw: calls.append("discover"))
    monkeypatch.setattr(plugin_manager, "load_all", lambda: calls.append("load_all"))
    monkeypatch.setattr(plugin_manager, "get_routers", lambda: {})
    return calls


class TestCreateApp:
    @staticmethod
    def _paths(app: FastAPI) -> set[str]:
        # FastAPI 0.141 的 include_router 是惰性的（_IncludedRouter），
        # 路由表要等 OpenAPI schema 构建时才铺平 —— 用 openapi() 取路径最稳。
        return set(app.openapi()["paths"])

    def test_create_app_attaches_lifespan_and_core_routes(self, quiet_plugins):
        app = main_mod.create_app()
        # FastAPI 会把 router 的 lifespan 与 app 自身合并成一个 context manager，
        # 不能按函数同一性断言；这里断言「存在可调用的 lifespan」+ 路由齐全。
        assert callable(app.router.lifespan_context)
        paths = self._paths(app)
        assert "/api/v1/tasks" in paths
        assert any(p.startswith("/api/v1/health") for p in paths)

    def test_create_app_mounts_plugin_routers_with_prefix(self, quiet_plugins, monkeypatch):
        from app.core.plugin_manager import plugin_manager

        router = APIRouter()

        @router.get("/items")
        async def _items():
            return {"ok": True}

        monkeypatch.setattr(plugin_manager, "get_routers", lambda: {"fakehot": router})
        app = main_mod.create_app()
        assert "/api/v1/plugins/fakehot/items" in self._paths(app)

    def test_create_app_plugin_failure_is_fail_open(self, monkeypatch, caplog):
        """插件装配任一环节抛异常 → 主应用仍可用（fail-open）+ exception 日志。"""
        from app.core.plugin_manager import plugin_manager

        monkeypatch.setattr(plugin_manager, "initialize", lambda **kw: None)
        monkeypatch.setattr(plugin_manager, "discover", lambda *a, **kw: None)

        def _boom():
            raise RuntimeError("plugin boom")

        monkeypatch.setattr(plugin_manager, "load_all", _boom)

        with caplog.at_level(logging.ERROR):
            app = main_mod.create_app()
        assert isinstance(app, FastAPI)
        assert "/api/v1/tasks" in self._paths(app)
        assert "插件系统初始化失败（不影响主应用）" in caplog.text

    def test_create_app_enables_cors(self, quiet_plugins):
        from fastapi.middleware.cors import CORSMiddleware

        app = main_mod.create_app()
        assert any(m.cls is CORSMiddleware for m in app.user_middleware)


# ================================================================
# 五、异常处理器（业务 / 参数校验 / 未捕获）
# ================================================================
@pytest.fixture()
def probe_client(quiet_plugins):
    """带三条测试路由的独立 app（不污染全局 app 的路由表）。

    lifespan 换成 no-op：本组只测异常处理器，不需要跑迁移/种子/订阅注册。
    """
    from contextlib import asynccontextmanager

    app = main_mod.create_app()

    @app.get("/__probe/app-exception")
    async def _app_exc():
        raise NotFoundException("资源不存在")

    @app.get("/__probe/validation")
    async def _validation(q: int):
        return {"q": q}

    @app.get("/__probe/unhandled")
    async def _unhandled():
        raise RuntimeError("kaboom")

    @asynccontextmanager
    async def _noop_lifespan(_app):
        yield

    app.router.lifespan_context = _noop_lifespan
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


class TestExceptionHandlers:
    def test_app_exception_handler_returns_business_envelope(self, probe_client, caplog):
        with caplog.at_level(logging.WARNING):
            resp = probe_client.get("/__probe/app-exception")
        assert resp.status_code == 404
        body = resp.json()
        assert body["code"] == 1002 and body["message"] == "资源不存在"
        assert "业务异常 1002: 资源不存在" in caplog.text

    def test_validation_error_handler_returns_1001(self, probe_client):
        resp = probe_client.get("/__probe/validation", params={"q": "not-int"})
        assert resp.status_code == 400
        body = resp.json()
        assert body["code"] == 1001
        assert body["message"].startswith("参数错误")
        assert "q" in body["message"]          # 带字段定位

    def test_unhandled_exception_handler_returns_500_without_detail(
        self, probe_client, caplog
    ):
        with caplog.at_level(logging.ERROR):
            resp = probe_client.get("/__probe/unhandled")
        assert resp.status_code == 500
        body = resp.json()
        assert body["code"] == 5000
        assert body["message"] == "服务器内部错误"
        assert body["data"] is None
        assert isinstance(body["timestamp"], int)   # 统一信封字段
        assert "detail" not in body                 # 不泄漏堆栈
        assert "未捕获异常" in caplog.text


# ================================================================
# 六、`if __name__ == "__main__"` 入口（runpy，不起端口）
# ================================================================
class TestMainEntrypoint:
    def test_main_block_calls_uvicorn_run_with_settings(self, monkeypatch):
        recorded: list = []

        fake_uvicorn = types.ModuleType("uvicorn")

        def _run(app_path, **kwargs):
            recorded.append((app_path, kwargs))

        fake_uvicorn.run = _run
        monkeypatch.setitem(sys.modules, "uvicorn", fake_uvicorn)

        runpy.run_module("app.main", run_name="__main__")

        assert len(recorded) == 1
        app_path, kwargs = recorded[0]
        assert app_path == "app.main:app"
        assert kwargs == {
            "host": main_mod.settings.host,
            "port": main_mod.settings.port,
            "reload": main_mod.settings.dev,
        }

    @pytest.mark.skipif(sys.platform != "win32", reason="仅 Windows 走 stdout UTF-8 重配分支")
    def test_win32_stdout_reconfigure_failure_is_swallowed(self, monkeypatch):
        """main.py:12-17：Windows 下 stdout.reconfigure 失败必须被吞掉（不阻断导入）。"""

        class _NoReconfigure:
            def write(self, *_a, **_kw):  # pragma: no cover - 不应被调用
                pass

            def flush(self):  # pragma: no cover
                pass

        monkeypatch.setattr(sys, "stdout", _NoReconfigure())
        module = runpy.run_module("app.main", run_name="phase9_probe")
        assert isinstance(module["app"], FastAPI)
