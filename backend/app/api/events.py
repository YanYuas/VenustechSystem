# ============================================================
# 事件总线 API（M09 P0）
# 查看事件统计、历史、订阅情况
# ============================================================
from __future__ import annotations

from fastapi import APIRouter, Query

from app.core.event_bus import event_bus, ALL_EVENTS
from app.core.response import success

router = APIRouter(prefix="/events", tags=["events"])


@router.get("/stats")
def event_stats():
    """事件统计"""
    return success(event_bus.get_stats())


@router.get("/history")
def event_history(
    event: str | None = Query(None, description="筛选特定事件"),
    limit: int = Query(50, ge=1, le=500),
):
    """事件历史"""
    return success(event_bus.get_history(event=event, limit=limit))


@router.get("/types")
def event_types():
    """所有支持的事件类型"""
    return success({"events": ALL_EVENTS, "count": len(ALL_EVENTS)})


@router.post("/clear-history")
def clear_history():
    """清空事件历史"""
    event_bus.clear_history()
    return success({"cleared": True})


@router.post("/test/{event}")
def test_event(event: str):
    """测试发布事件（开发调试用）"""
    event_bus.publish(event, source="api_test", timestamp=True)
    return success({"published": event})