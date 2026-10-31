# ============================================================
# Phase12 · D-48：异步事件投递回归（静默丢失 + 延迟失败可观测）
#
# 背景 bug：event_bus.publish 的 async 分支用 asyncio.get_event_loop()——在无运行
# loop 的同步线程里会拿到「创建但未运行」的 loop，create_task 排队后永远不执行，
# 却仍把 called +1：handler 静默丢失、统计却显示成功。
#
# 本文件覆盖：
#   · 同步上下文（无运行 loop）→ handler 必须真实执行（副作用断言）+ called 正确；
#   · 同步上下文 handler 抛错 → failed_handlers + exception 日志；
#   · 在运行中的 loop 内 publish → 排队并在下一轮 loop 执行；
#   · 排队 task 延迟失败/取消 → done_callback 写 history/statistics + 日志，
#     不静默吞（called 语义：**成功排队即算 called**，失败通过 failed_handlers 反映）。
# ============================================================
from __future__ import annotations

import asyncio
import uuid

import pytest

from app.core.event_bus import EventBus


def _unique_event(prefix: str) -> str:
    return f"p12.async.{prefix}.{uuid.uuid4().hex[:8]}"


@pytest.fixture()
def cleanup_event():
    """登记测试事件，结束清理订阅/统计/窗口，避免污染同进程其它用例。"""
    events: list[str] = []

    def register(event: str) -> str:
        events.append(event)
        return event

    yield register
    for event in events:
        EventBus._async_handlers.pop(event, None)
        EventBus._stats.pop(event, None)
        EventBus._window.pop(event, None)


def _last_record(event: str):
    return [r for r in EventBus._history if r.event == event][-1]


class TestAsyncPublishWithoutRunningLoop:
    """同步测试函数内没有运行中的 loop —— 旧实现会静默排队丢失。"""

    def test_handler_really_executes(self, cleanup_event):
        event = cleanup_event(_unique_event("sync-ok"))
        seen: list[dict] = []

        async def handler(**kwargs):
            seen.append(kwargs)

        EventBus.subscribe_async(event, handler)
        EventBus.publish(event, payload="sync")

        # 副作用断言：handler 真的执行了（而不是排队后永不运行）
        assert seen == [{"payload": "sync"}]
        record = _last_record(event)
        assert record.handlers_called == 1
        assert record.success is True
        assert record.failed_handlers == []

    def test_failure_is_recorded_and_logged(self, cleanup_event, caplog):
        import logging

        event = cleanup_event(_unique_event("sync-fail"))

        async def handler(**_kwargs):
            raise ValueError("sync-path boom")

        EventBus.subscribe_async(event, handler)
        with caplog.at_level(logging.ERROR):
            EventBus.publish(event)

        record = _last_record(event)
        assert record.success is False
        assert record.failed_handlers == ["handler"]
        assert record.handlers_called == 0
        assert "异步事件处理失败" in caplog.text
        stats = EventBus.get_stats()["by_event"][event]
        assert stats["failed"] == 1


class TestAsyncPublishInsideRunningLoop:
    """有运行中的 loop：排队执行（called 表示「成功排队」）。"""

    def test_queued_handler_runs_and_called_counts(self, cleanup_event):
        event = cleanup_event(_unique_event("loop-ok"))
        seen: list[str] = []

        async def handler(**kwargs):
            seen.append(kwargs["payload"])

        EventBus.subscribe_async(event, handler)

        async def scenario():
            EventBus.publish(event, payload="in-loop")
            record = _last_record(event)
            assert record.handlers_called == 1     # 排队即计 called（语义已注释）
            assert seen == []                      # 尚未调度执行
            await asyncio.sleep(0.01)              # 让 loop 跑完 task
            return record

        record = asyncio.run(scenario())
        assert seen == ["in-loop"]
        assert record.success is True
        assert record.failed_handlers == []

    def test_deferred_failure_is_not_silently_swallowed(self, cleanup_event, caplog):
        import logging

        event = cleanup_event(_unique_event("loop-fail"))

        async def handler(**_kwargs):
            raise RuntimeError("deferred boom")

        EventBus.subscribe_async(event, handler)

        async def scenario():
            EventBus.publish(event)
            await asyncio.sleep(0.01)
            return _last_record(event)

        with caplog.at_level(logging.ERROR):
            record = asyncio.run(scenario())

        assert record.success is False
        assert record.failed_handlers == ["handler"]
        assert "异步事件处理失败（延迟）" in caplog.text
        stats = EventBus.get_stats()["by_event"][event]
        assert stats["failed"] == 1
        assert "handler" in stats["failed_handlers"]

    def test_cancelled_task_is_observable(self, cleanup_event, caplog):
        import logging

        event = cleanup_event(_unique_event("loop-cancel"))

        async def handler(**_kwargs):
            await asyncio.sleep(5)

        EventBus.subscribe_async(event, handler)

        async def scenario():
            EventBus.publish(event)
            await asyncio.sleep(0)
            current = asyncio.current_task()
            pending = [t for t in asyncio.all_tasks() if t is not current]
            assert len(pending) == 1
            pending[0].cancel()
            await asyncio.sleep(0.01)
            return _last_record(event)

        with caplog.at_level(logging.WARNING):
            record = asyncio.run(scenario())

        assert record.success is False
        assert record.failed_handlers == ["handler"]
        assert "异步事件处理被取消" in caplog.text
