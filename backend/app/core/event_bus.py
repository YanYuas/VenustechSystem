# ============================================================
# 内部事件总线（模块解耦，对齐架构 v2.0 §3.4）
# 典型：document.saved → AI 摘要/标签异步处理
# ============================================================
from __future__ import annotations

import logging
from typing import Any, Callable

logger = logging.getLogger("app.event_bus")

EVENT_TASK_COMPLETED = "task.completed"
EVENT_TASK_CREATED = "task.created"
EVENT_DOCUMENT_SAVED = "document.saved"
EVENT_REVIEW_GENERATED = "review.generated"
EVENT_INSPIRATION_GENERATED = "inspiration.generated"


class EventBus:
    _handlers: dict[str, list[Callable]] = {}

    @classmethod
    def subscribe(cls, event: str, handler: Callable) -> None:
        cls._handlers.setdefault(event, []).append(handler)

    @classmethod
    def publish(cls, event: str, **kwargs: Any) -> None:
        for handler in cls._handlers.get(event, []):
            try:
                handler(**kwargs)
            except Exception:  # 事件处理失败不阻断主流程
                logger.exception("事件处理失败: %s", event)


event_bus = EventBus()
