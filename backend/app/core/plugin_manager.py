# ============================================================
# 插件系统基础架构（M09 P1）
# 支持私人定制模块插件，对齐 PRD §14 插件生态
# ============================================================
from __future__ import annotations

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
                    module.initialize(cls._context)

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
    def unload(cls, plugin_id: str) -> bool:
        """卸载插件"""
        if plugin_id in cls._instances:
            instance = cls._instances[plugin_id]
            if hasattr(instance, "shutdown"):
                try:
                    instance.shutdown()
                except Exception:
                    pass
            del cls._instances[plugin_id]
            logger.info("插件已卸载: %s", plugin_id)
            return True
        return False

    @classmethod
    def list_plugins(cls) -> list[PluginInfo]:
        """列出所有插件"""
        return list(cls._plugins.values())

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