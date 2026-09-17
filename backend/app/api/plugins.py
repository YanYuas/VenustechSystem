# ============================================================
# 插件管理 API（M09 P1）
# ============================================================
from __future__ import annotations

from fastapi import APIRouter

from app.core.plugin_manager import plugin_manager
from app.core.response import success

router = APIRouter(prefix="/plugins", tags=["plugins"])


@router.get("")
def list_plugins():
    """列出所有插件"""
    return success(plugin_manager.get_status())


@router.post("/{plugin_id}/enable")
def enable_plugin(plugin_id: str):
    """启用插件"""
    result = plugin_manager.set_enabled(plugin_id, True)
    return success({"enabled": result, "plugin_id": plugin_id})


@router.post("/{plugin_id}/disable")
def disable_plugin(plugin_id: str):
    """禁用插件"""
    result = plugin_manager.set_enabled(plugin_id, False)
    return success({"disabled": result, "plugin_id": plugin_id})


@router.post("/{plugin_id}/reload")
def reload_plugin(plugin_id: str):
    """重新加载插件"""
    plugin_manager.unload(plugin_id)
    result = plugin_manager.load(plugin_id)
    return success({"reloaded": result, "plugin_id": plugin_id})


@router.post("/discover")
def discover_plugins():
    """重新扫描插件目录"""
    plugins = plugin_manager.discover()
    return success({"discovered": len(plugins), "plugins": [p.id for p in plugins]})