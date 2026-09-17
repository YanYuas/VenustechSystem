# ============================================================
# 内部事件总线（模块解耦，对齐架构 v2.0 §3.4）
# 典型：document.saved → AI 摘要/标签异步处理
# M09 P0 增强：异步事件、事件历史、统计、更多事件类型
# ============================================================
from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from typing import Any, Callable

logger = logging.getLogger("app.event_bus")

# ---------- 事件类型常量 ----------
EVENT_TASK_COMPLETED = "task.completed"
EVENT_TASK_CREATED = "task.created"
EVENT_TASK_UPDATED = "task.updated"
EVENT_TASK_DELETED = "task.deleted"
EVENT_DOCUMENT_SAVED = "document.saved"
EVENT_DOCUMENT_CREATED = "document.created"
EVENT_DOCUMENT_DELETED = "document.deleted"
EVENT_REVIEW_GENERATED = "review.generated"
EVENT_REVIEW_CREATED = "review.created"
EVENT_INSPIRATION_GENERATED = "inspiration.generated"
EVENT_PROJECT_CREATED = "project.created"
EVENT_PROJECT_UPDATED = "project.updated"
EVENT_CONVERSATION_MESSAGE = "conversation.message"
EVENT_PET_ACTION = "pet.action"
EVENT_BACKUP_EXPORTED = "backup.exported"
EVENT_BACKUP_IMPORTED = "backup.imported"
EVENT_SYSTEM_STARTUP = "system.startup"
EVENT_SYSTEM_SHUTDOWN = "system.shutdown"

# ---------- 二期新模块事件 ----------
EVENT_INBOX_ITEM_CREATED = "inbox.item.created"
EVENT_INBOX_ITEM_PROCESSED = "inbox.item.processed"
EVENT_FLASHCARD_REVIEWED = "flashcard.reviewed"
EVENT_STUDY_TIME_LOGGED = "study.time.logged"
EVENT_HABIT_CHECKIN = "habit.checkin"
EVENT_MOOD_LOGGED = "mood.logged"
EVENT_DIARY_CREATED = "diary.created"
EVENT_SOP_USED = "sop.used"
EVENT_PROMPT_USED = "prompt.used"
EVENT_PROJECT_MEMORY_CREATED = "project.memory.created"

# 2026-09-16 归位：此前定义在 services/workflow_service.py 中。
# 事件常量分散在业务模块里有两个问题：
#   1. 其他模块要订阅它时必须 import 那个业务模块 —— core 层反向依赖
#      services 层，方向是倒置的；
#   2. 下面的 ALL_EVENTS 无法穷举真实事件，"列出全部事件"这类功能会漏项。
EVENT_WORKFLOW_APPLIED = "workflow.applied"

ALL_EVENTS = [
    EVENT_TASK_COMPLETED, EVENT_TASK_CREATED, EVENT_TASK_UPDATED, EVENT_TASK_DELETED,
    EVENT_DOCUMENT_SAVED, EVENT_DOCUMENT_CREATED, EVENT_DOCUMENT_DELETED,
    EVENT_REVIEW_GENERATED, EVENT_REVIEW_CREATED,
    EVENT_INSPIRATION_GENERATED,
    EVENT_PROJECT_CREATED, EVENT_PROJECT_UPDATED,
    EVENT_CONVERSATION_MESSAGE, EVENT_PET_ACTION,
    EVENT_BACKUP_EXPORTED, EVENT_BACKUP_IMPORTED,
    EVENT_SYSTEM_STARTUP, EVENT_SYSTEM_SHUTDOWN,
    # 二期
    EVENT_INBOX_ITEM_CREATED, EVENT_INBOX_ITEM_PROCESSED,
    EVENT_FLASHCARD_REVIEWED, EVENT_STUDY_TIME_LOGGED,
    EVENT_HABIT_CHECKIN, EVENT_MOOD_LOGGED, EVENT_DIARY_CREATED,
    EVENT_SOP_USED, EVENT_PROMPT_USED, EVENT_PROJECT_MEMORY_CREATED,
    EVENT_WORKFLOW_APPLIED,
]


class EventRecord:
    """事件记录（用于历史追踪）"""
    __slots__ = ("event", "timestamp", "kwargs", "handlers_called", "success")

    def __init__(self, event: str, kwargs: dict, handlers_called: int, success: bool):
        self.event = event
        self.timestamp = time.time()
        self.kwargs = kwargs
        self.handlers_called = handlers_called
        self.success = success

    def to_dict(self) -> dict:
        return {
            "event": self.event,
            "time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.timestamp)),
            "handlers": self.handlers_called,
            "success": self.success,
        }


class EventBus:
    _handlers: dict[str, list[Callable]] = {}
    _async_handlers: dict[str, list[Callable]] = {}
    _history: deque[EventRecord] = deque(maxlen=500)
    _stats: dict[str, dict] = {}

    @classmethod
    def subscribe(cls, event: str, handler: Callable) -> None:
        """订阅同步事件"""
        cls._handlers.setdefault(event, []).append(handler)
        logger.debug("订阅事件: %s (handler=%s)", event, handler.__name__)

    @classmethod
    def subscribe_async(cls, event: str, handler: Callable) -> None:
        """订阅异步事件（handler 为协程函数）"""
        cls._async_handlers.setdefault(event, []).append(handler)
        logger.debug("订阅异步事件: %s (handler=%s)", event, handler.__name__)

    @classmethod
    def publish(cls, event: str, **kwargs: Any) -> None:
        """发布同步事件"""
        handlers = cls._handlers.get(event, [])
        called = 0
        success = True
        for handler in handlers:
            try:
                handler(**kwargs)
                called += 1
            except Exception:
                success = False
                logger.exception("事件处理失败: %s (handler=%s)", event, handler.__name__)

        # 异步事件放入事件循环
        async_handlers = cls._async_handlers.get(event, [])
        if async_handlers:
            try:
                loop = asyncio.get_event_loop()
                for handler in async_handlers:
                    loop.create_task(handler(**kwargs))
                    called += 1
            except RuntimeError:
                # 没有事件循环时，用 asyncio.run 执行
                for handler in async_handlers:
                    try:
                        asyncio.run(handler(**kwargs))
                        called += 1
                    except Exception:
                        success = False
                        logger.exception("异步事件处理失败: %s", event)

        # 记录历史和统计
        cls._history.append(EventRecord(event, kwargs, called, success))
        stat = cls._stats.setdefault(event, {"count": 0, "success": 0, "failed": 0})
        stat["count"] += 1
        stat["success" if success else "failed"] += 1

    @classmethod
    def get_history(cls, event: str | None = None, limit: int = 50) -> list[dict]:
        """获取事件历史"""
        records = list(cls._history)
        if event:
            records = [r for r in records if r.event == event]
        return [r.to_dict() for r in records[-limit:]]

    @classmethod
    def get_stats(cls) -> dict:
        """获取事件统计"""
        return {
            "total_events": sum(s["count"] for s in cls._stats.values()),
            "by_event": cls._stats,
            "active_subscriptions": {
                event: len(handlers) for event, handlers in cls._handlers.items()
            },
            "async_subscriptions": {
                event: len(handlers) for event, handlers in cls._async_handlers.items()
            },
        }

    @classmethod
    def clear_history(cls) -> None:
        """清空事件历史"""
        cls._history.clear()


event_bus = EventBus()