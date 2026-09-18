# ============================================================
# 插件系统基础架构（M09 P1）
# 支持私人定制模块插件，对齐 PRD §14 插件生态
# ============================================================
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

import importlib
import importlib.util
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger("app.plugin")


@dataclass
class PluginInfo:
    """插件信息"""
    id: str
    name: str
    version: str
    author: str = ""
    description: str = ""
    enabled: bool = True
    path: str = ""
    entry_point: str = ""
    permissions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PluginContext:
    """插件运行上下文（注入给插件的API）"""
    event_bus: Any  # EventBus
    config: dict[str, Any]
    data_dir: Path
    logger: logging.Logger


# ---------- 插件权限模型（mod-platform P1） ----------
# 白名单式：声明里出现未知权限 → 拒绝加载（fail-closed，不静默放行）
ALLOWED_PERMISSIONS = {
    "network",     # 允许对外 HTTP（插件须自证固定 base URL，见 aihot）
    "db_read",     # 只读业务库
    "files",       # 读写自己的数据目录（data_dir/plugins/<id>/）
}
# 高危权限：声明即拒绝（单进程内无法真正隔离 exec）
DENIED_PERMISSIONS = {"exec", "db_write", "subprocess"}


def validate_permissions(perms: list[str]) -> tuple[bool, str]:
    """校验插件声明的权限。返回 (是否允许, 原因)。"""
    for pname in perms:
        if pname in DENIED_PERMISSIONS:
            return False, f"高危权限被拒绝: {pname}"
        if pname not in ALLOWED_PERMISSIONS:
            return False, f"未知权限: {pname}（允许: {sorted(ALLOWED_PERMISSIONS)}）"
    return True, ""


def safe_call(plugin_id: str, fn: Any, *args: Any, timeout: float | None = None,
              default: Any = None) -> Any:
    """调用插件方法并隔离失败（P1 F3.4）。

    - 任何异常都被吞掉并记录，绝不让插件错误冒泡到宿主请求
    - timeout 不为 None 时在线程中执行并限时，超时返回 default
      （单进程内无法强杀线程，仅保证调用方不被无限阻塞）
    """
    if fn is None:
        return default
    try:
        if timeout is None:
            return fn(*args)
        # 注意：不能用 `with`（退出时会 join 线程，等于没超时）。
        # 超时后立刻返回，线程任其跑完（Python 无法强杀），
        # 保证的是**调用方不被无限阻塞**。
        pool = ThreadPoolExecutor(max_workers=1)
        try:
            fut = pool.submit(fn, *args)
            return fut.result(timeout=timeout)
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
    except FuturesTimeout:
        logger.error("插件调用超时: %s (%ss)", plugin_id, timeout)
        return default
    except Exception:
        logger.exception("插件调用异常已隔离: %s", plugin_id)
        return default


class PluginManager:
    """插件管理器：发现、加载、启用/禁用插件"""

    _plugins: dict[str, PluginInfo] = {}
    _instances: dict[str, Any] = {}
    _context: PluginContext | None = None

    @classmethod
    def initialize(cls, event_bus: Any, data_dir: Path, config: dict | None = None):
        """初始化插件管理器"""
        cls._context = PluginContext(
            event_bus=event_bus,
            config=config or {},
            data_dir=data_dir,
            logger=logger,
        )
        # 创建插件目录
        plugins_dir = data_dir / "plugins"
        plugins_dir.mkdir(parents=True, exist_ok=True)
        logger.info("插件管理器初始化完成，插件目录: %s", plugins_dir)

    @classmethod
    def discover(cls, plugins_dir: Path | None = None) -> list[PluginInfo]:
        """发现插件目录中的所有插件"""
        if plugins_dir is None:
            plugins_dir = cls._context.data_dir / "plugins" if cls._context else Path("plugins")

        discovered = []
        if not plugins_dir.exists():
            return discovered

        for item in plugins_dir.iterdir():
            if item.is_dir() and (item / "plugin.json").exists():
                try:
                    import json
                    with open(item / "plugin.json", "r", encoding="utf-8") as f:
                        meta = json.load(f)
                    info = PluginInfo(
                        id=meta.get("id", item.name),
                        name=meta.get("name", item.name),
                        version=meta.get("version", "0.1.0"),
                        author=meta.get("author", ""),
                        description=meta.get("description", ""),
                        enabled=meta.get("enabled", True),
                        path=str(item),
                        entry_point=meta.get("entry_point", "main.py"),
                        permissions=meta.get("permissions", []),
                        metadata=meta.get("metadata", {}),
                    )
                    cls._plugins[info.id] = info
                    discovered.append(info)
                    logger.debug("发现插件: %s v%s", info.name, info.version)
                except Exception as e:
                    logger.warning("插件元数据读取失败: %s (%s)", item, e)

        return discovered

    @classmethod
    def load(cls, plugin_id: str) -> bool:
        """加载指定插件"""
        info = cls._plugins.get(plugin_id)
        if not info:
            logger.error("插件不存在: %s", plugin_id)
            return False
        if not info.enabled:
            logger.info("插件已禁用，跳过加载: %s", plugin_id)
            return False

        # 权限门禁（P1）：声明不合法 → 拒绝加载，fail-closed
        ok, reason = validate_permissions(info.permissions)
        if not ok:
            logger.error("插件权限校验未通过，拒绝加载: %s (%s)", plugin_id, reason)
            return False

        try:
            entry_path = Path(info.path) / info.entry_point
            if not entry_path.exists():
                logger.error("插件入口不存在: %s", entry_path)
                return False

            spec = importlib.util.spec_from_file_location(
                f"plugin_{plugin_id}", str(entry_path)
            )
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # 调用插件的 initialize 函数
                if hasattr(module, "initialize") and cls._context:
                    safe_call(plugin_id, getattr(module, "initialize"), cls._context,
                              timeout=10)

                cls._instances[plugin_id] = module
                logger.info("插件加载成功: %s v%s", info.name, info.version)
                return True
        except Exception as e:
            logger.exception("插件加载失败: %s (%s)", plugin_id, e)
        return False

    @classmethod
    def load_all(cls) -> dict[str, bool]:
        """加载所有已发现的插件"""
        results = {}
        for plugin_id in cls._plugins:
            results[plugin_id] = cls.load(plugin_id)
        return results

    @classmethod
    def has_permission(cls, plugin_id: str, permission: str) -> bool:
        """运行时权限校验：插件实际调用敏感能力前必须先过这一关。"""
        info = cls._plugins.get(plugin_id)
        if info is None:
            return False
        return permission in info.permissions and permission in ALLOWED_PERMISSIONS

    @classmethod
    def unload(cls, plugin_id: str) -> bool:
        """卸载插件"""
        if plugin_id in cls._instances:
            instance = cls._instances[plugin_id]
            if hasattr(instance, "shutdown"):
                # 卸载清理同样隔离（超时 5s），失败不阻断卸载
                safe_call(plugin_id, getattr(instance, "shutdown"), timeout=5)
            del cls._instances[plugin_id]
            logger.info("插件已卸载: %s", plugin_id)
            return True
        return False

    @classmethod
    def list_plugins(cls) -> list[PluginInfo]:
        """列出所有插件"""
        return list(cls._plugins.values())

    @classmethod
    def instances(cls) -> dict[str, Any]:
        """已加载的插件模块（S6-6：供宿主挂载插件路由等）"""
        return dict(cls._instances)

    def get_routers(self) -> dict[str, Any]:
        """收集已加载插件暴露的 APIRouter（约定：模块提供 get_router()）。"""
        routers: dict[str, Any] = {}
        for pid, module in self._instances.items():
            factory = getattr(module, "get_router", None)
            if callable(factory):
                try:
                    routers[pid] = factory()
                except Exception:
                    logger.exception("插件路由获取失败: %s", pid)
        return routers

    @classmethod
    def get_plugin(cls, plugin_id: str) -> PluginInfo | None:
        """获取插件信息"""
        return cls._plugins.get(plugin_id)

    @classmethod
    def set_enabled(cls, plugin_id: str, enabled: bool) -> bool:
        """启用/禁用插件"""
        info = cls._plugins.get(plugin_id)
        if not info:
            return False
        info.enabled = enabled
        if enabled and plugin_id not in cls._instances:
            cls.load(plugin_id)
        elif not enabled and plugin_id in cls._instances:
            cls.unload(plugin_id)
        return True

    @classmethod
    def get_status(cls) -> dict:
        """获取插件系统状态"""
        return {
            "total": len(cls._plugins),
            "enabled": sum(1 for p in cls._plugins.values() if p.enabled),
            "loaded": len(cls._instances),
            "plugins": [
                {
                    "id": p.id,
                    "name": p.name,
                    "version": p.version,
                    "enabled": p.enabled,
                    "loaded": p.id in cls._instances,
                    "description": p.description,
                }
                for p in cls._plugins.values()
            ],
        }


# 全局单例
plugin_manager = PluginManager()