# ============================================================
# Phase6 · PluginManager 深度测试（app/core/plugin_manager.py，基线 82%）
#
# 重点：发现/加载/卸载状态机、权限 fail-closed、入口缺失/异常隔离、
# 路由收集与上下文权限自检。全部在测试数据目录内造插件，不碰真实插件目录。
# ============================================================
from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

import pytest

from app.config import get_settings
from app.core.plugin_manager import (
    PluginContext,
    PluginInfo,
    PluginManager,
)


@pytest.fixture()
def tmp_plugins_root():
    root = Path(get_settings().data_dir) / f"pm-{uuid.uuid4().hex[:8]}"
    root.mkdir(parents=True, exist_ok=True)
    yield root
    shutil.rmtree(root, ignore_errors=True)


@pytest.fixture()
def manager():
    """隔离 PluginManager 的类级单例状态（含 app lifespan 已加载的 aihot）。"""
    saved = {
        "plugins": dict(PluginManager._plugins),
        "instances": dict(PluginManager._instances),
        "context": PluginManager._context,
    }
    PluginManager._plugins.clear()
    PluginManager._instances.clear()
    PluginManager._context = None
    yield PluginManager
    PluginManager._plugins.clear()
    PluginManager._plugins.update(saved["plugins"])
    PluginManager._instances.clear()
    PluginManager._instances.update(saved["instances"])
    PluginManager._context = saved["context"]


def _plugin_dir(root: Path, pid: str, *, meta: dict | None = None,
                main_src: str | None = None, entry: str = "main.py") -> Path:
    d = root / pid
    d.mkdir(parents=True, exist_ok=True)
    payload = {"id": pid, "name": f"插件{pid}", "version": "1.0.0",
               "entry_point": entry, "permissions": ["route:mount"]}
    if meta:
        payload.update(meta)
    (d / "plugin.json").write_text(json.dumps(payload), encoding="utf-8")
    if main_src is not None:
        (d / entry).write_text(main_src, encoding="utf-8")
    return d


DEFAULT_MAIN = """\
CALLS = []

def initialize(ctx):
    CALLS.append(("init", ctx.plugin_id))

def get_router():
    return {"plugin": "router"}

def shutdown():
    CALLS.append(("shutdown",))
"""


def _init(manager, root: Path):
    manager.initialize(event_bus=None, data_dir=root)
    root.mkdir(parents=True, exist_ok=True)
    return manager


# ================================================================
# 一、初始化 / 发现
# ================================================================
class TestDiscover:
    def test_initialize_creates_context_and_plugins_dir(self, manager, tmp_plugins_root):
        manager.initialize(event_bus=None, data_dir=tmp_plugins_root)
        assert manager._context is not None
        assert (tmp_plugins_root / "plugins").is_dir()

    def test_discover_missing_dir_returns_empty(self, manager, tmp_plugins_root):
        _init(manager, tmp_plugins_root)
        assert manager.discover(tmp_plugins_root / "no-such") == []

    def test_discover_empty_dir_returns_empty(self, manager, tmp_plugins_root):
        _init(manager, tmp_plugins_root)
        plugins_dir = tmp_plugins_root / "plugins"
        plugins_dir.mkdir(parents=True, exist_ok=True)
        assert manager.discover(plugins_dir) == []

    def test_discover_reads_metadata_with_defaults(self, manager, tmp_plugins_root):
        _init(manager, tmp_plugins_root)
        plugins_dir = tmp_plugins_root / "plugins"
        d = plugins_dir / "bare"
        d.mkdir(parents=True)
        (d / "plugin.json").write_text('{"id": "bare"}', encoding="utf-8")
        (d / "main.py").write_text("", encoding="utf-8")

        found = manager.discover(plugins_dir)
        assert [p.id for p in found] == ["bare"]
        info = manager.get_plugin("bare")
        assert isinstance(info, PluginInfo)
        assert info.name == "bare"
        assert info.version == "0.1.0"
        assert info.enabled is True
        assert info.entry_point == "main.py"
        assert info.permissions == []

    def test_discover_skips_invalid_metadata(self, manager, tmp_plugins_root):
        _init(manager, tmp_plugins_root)
        plugins_dir = tmp_plugins_root / "plugins"
        bad = plugins_dir / "bad"
        bad.mkdir(parents=True)
        (bad / "plugin.json").write_text("{not json", encoding="utf-8")
        good = _plugin_dir(plugins_dir, "good", main_src=DEFAULT_MAIN)

        found = manager.discover(plugins_dir)
        assert [p.id for p in found] == ["good"]
        assert manager.get_plugin("bad") is None
        assert good.is_dir()

    def test_discover_ignores_plain_files(self, manager, tmp_plugins_root):
        _init(manager, tmp_plugins_root)
        plugins_dir = tmp_plugins_root / "plugins"
        assert plugins_dir.is_dir()  # initialize 已创建
        (plugins_dir / "readme.txt").write_text("x", encoding="utf-8")
        assert manager.discover(plugins_dir) == []


# ================================================================
# 二、load / 权限门禁
# ================================================================
class TestLoad:
    def test_load_unknown_plugin_returns_false(self, manager, tmp_plugins_root):
        _init(manager, tmp_plugins_root)
        assert manager.load("nope") is False

    def test_load_disabled_plugin_returns_false(self, manager, tmp_plugins_root):
        _init(manager, tmp_plugins_root)
        plugins_dir = tmp_plugins_root / "plugins"
        _plugin_dir(plugins_dir, "off", meta={"enabled": False}, main_src=DEFAULT_MAIN)
        manager.discover(plugins_dir)
        assert manager.load("off") is False
        assert not manager.instances()

    def test_load_rejects_denied_permission(self, manager, tmp_plugins_root):
        _init(manager, tmp_plugins_root)
        plugins_dir = tmp_plugins_root / "plugins"
        _plugin_dir(plugins_dir, "evil", meta={"permissions": ["exec"]}, main_src=DEFAULT_MAIN)
        manager.discover(plugins_dir)
        assert manager.load("evil") is False

    def test_load_rejects_unknown_permission(self, manager, tmp_plugins_root):
        _init(manager, tmp_plugins_root)
        plugins_dir = tmp_plugins_root / "plugins"
        _plugin_dir(plugins_dir, "weird", meta={"permissions": ["teleport"]},
                    main_src=DEFAULT_MAIN)
        manager.discover(plugins_dir)
        assert manager.load("weird") is False

    def test_load_missing_entry_file_returns_false(self, manager, tmp_plugins_root):
        _init(manager, tmp_plugins_root)
        plugins_dir = tmp_plugins_root / "plugins"
        _plugin_dir(plugins_dir, "noentry", entry="missing.py")  # 不写 main
        manager.discover(plugins_dir)
        assert manager.load("noentry") is False

    def test_load_success_registers_instance_and_calls_initialize(
        self, manager, tmp_plugins_root
    ):
        _init(manager, tmp_plugins_root)
        plugins_dir = tmp_plugins_root / "plugins"
        _plugin_dir(plugins_dir, "ok", main_src=DEFAULT_MAIN)
        manager.discover(plugins_dir)

        assert manager.load("ok") is True
        module = manager.instances()["ok"]
        assert module.CALLS == [("init", "ok")]
        assert manager.get_status()["loaded"] == 1

    def test_load_isolates_initialize_exception(self, manager, tmp_plugins_root):
        _init(manager, tmp_plugins_root)
        plugins_dir = tmp_plugins_root / "plugins"
        _plugin_dir(plugins_dir, "crash", main_src=(
            "def initialize(ctx):\n    raise RuntimeError('boom')\n"
        ))
        manager.discover(plugins_dir)
        # safe_call 吞掉异常：加载本身仍成功
        assert manager.load("crash") is True

    def test_load_all_returns_per_plugin_results(self, manager, tmp_plugins_root):
        _init(manager, tmp_plugins_root)
        plugins_dir = tmp_plugins_root / "plugins"
        _plugin_dir(plugins_dir, "a", main_src=DEFAULT_MAIN)
        _plugin_dir(plugins_dir, "b", main_src=DEFAULT_MAIN)
        manager.discover(plugins_dir)
        assert manager.load_all() == {"a": True, "b": True}


# ================================================================
# 三、权限 / 卸载 / 路由
# ================================================================
class TestPermissionsAndLifecycle:
    def test_has_permission_matrix(self, manager, tmp_plugins_root):
        _init(manager, tmp_plugins_root)
        plugins_dir = tmp_plugins_root / "plugins"
        _plugin_dir(plugins_dir, "p", meta={"permissions": ["route:mount", "db_write"]})
        manager.discover(plugins_dir)
        assert manager.has_permission("p", "route:mount") is True
        assert manager.has_permission("p", "network") is False
        assert manager.has_permission("p", "db_write") is False  # 高危即使声明也不可用
        assert manager.has_permission("unknown", "route:mount") is False

    def test_unload_calls_shutdown_and_is_idempotent(self, manager, tmp_plugins_root):
        _init(manager, tmp_plugins_root)
        plugins_dir = tmp_plugins_root / "plugins"
        _plugin_dir(plugins_dir, "u", main_src=DEFAULT_MAIN)
        manager.discover(plugins_dir)
        manager.load("u")
        module = manager.instances()["u"]

        assert manager.unload("u") is True
        assert module.CALLS[-1] == ("shutdown",)
        assert "u" not in manager.instances()
        assert manager.unload("u") is False

    def test_set_enabled_toggles_load_state(self, manager, tmp_plugins_root):
        _init(manager, tmp_plugins_root)
        plugins_dir = tmp_plugins_root / "plugins"
        _plugin_dir(plugins_dir, "t", main_src=DEFAULT_MAIN)
        manager.discover(plugins_dir)

        assert manager.set_enabled("unknown", True) is False
        assert manager.set_enabled("t", True) is True
        assert "t" in manager.instances()
        assert manager.set_enabled("t", False) is True
        assert "t" not in manager.instances()
        assert manager.get_plugin("t").enabled is False

    def test_list_and_status(self, manager, tmp_plugins_root):
        _init(manager, tmp_plugins_root)
        plugins_dir = tmp_plugins_root / "plugins"
        _plugin_dir(plugins_dir, "s1", main_src=DEFAULT_MAIN)
        _plugin_dir(plugins_dir, "s2", meta={"enabled": False}, main_src=DEFAULT_MAIN)
        manager.discover(plugins_dir)

        assert sorted(p.id for p in manager.list_plugins()) == ["s1", "s2"]
        status = manager.get_status()
        assert status["total"] == 2
        assert status["enabled"] == 1
        assert status["loaded"] == 0

    def test_get_routers_collects_and_skips_failures(self, manager, tmp_plugins_root):
        _init(manager, tmp_plugins_root)
        plugins_dir = tmp_plugins_root / "plugins"
        _plugin_dir(plugins_dir, "r1", main_src=DEFAULT_MAIN)
        _plugin_dir(plugins_dir, "r2", main_src=(
            "def get_router():\n    raise RuntimeError('router boom')\n"
        ))
        _plugin_dir(plugins_dir, "r3", main_src="no_router = True\n")
        manager.discover(plugins_dir)
        manager.load_all()

        routers = manager().get_routers()
        assert routers == {"r1": {"plugin": "router"}}


# ================================================================
# 四、PluginContext 权限自检
# ================================================================
class TestPluginContext:
    def _ctx(self, data_dir: Path, plugin_id: str) -> PluginContext:
        return PluginContext(
            event_bus=None, config={}, data_dir=data_dir, logger=None, plugin_id=plugin_id
        )

    def test_mount_router_requires_permission(self, manager, tmp_plugins_root):
        _init(manager, tmp_plugins_root)
        plugins_dir = tmp_plugins_root / "plugins"
        _plugin_dir(plugins_dir, "denied", meta={"permissions": []})
        manager.discover(plugins_dir)
        ctx = self._ctx(tmp_plugins_root, "denied")
        with pytest.raises(PermissionError):
            ctx.mount_router(object())

    def test_mount_router_succeeds_when_permission_declared(self, manager, tmp_plugins_root):
        _init(manager, tmp_plugins_root)
        plugins_dir = tmp_plugins_root / "plugins"
        _plugin_dir(plugins_dir, "allowed", meta={"permissions": ["route:mount"]})
        manager.discover(plugins_dir)
        ctx = self._ctx(tmp_plugins_root, "allowed")
        router = object()
        ctx.mount_router(router)
        assert ctx.router is router
