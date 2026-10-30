# ============================================================
# bootstrap 订阅者（event_handlers / growth_handlers）异常路径测试（Phase9-B）
#
# 这两个模块是「启动期注册 + 运行期后台事件处理」的胶水层，Phase6 term-missing
# 缺口集中在**不常走的分支**：
#   · event_handlers：事件循环缺失/已关闭、后台 future 异常回调、
#     文档 AI 摘要/标签的成功与两类失败隔离、任务通知失败隔离；
#   · growth_handlers：loader 返回 None / EXP<=0 跳过、结算异常被吞、
#     14 个 loader 的「实体不存在」分支、订阅表注册。
#
# 约束：
#   - 不使用真实后台线程做主要断言（除一个受控的「运行中事件循环」用例外）；
#   - 所有 DB 读写走 conftest 的隔离库；AI/通知/GrowthService 全部打桩，
#     不发真实网络请求、不污染全局 event_bus（用 stub bus 替换）。
# ============================================================
from __future__ import annotations

import asyncio
import logging
import time
import types
import uuid
from datetime import datetime, timezone

import pytest

from app.bootstrap import event_handlers as eh
from app.bootstrap import growth_handlers as gh
from app.core.event_bus import EVENT_DOCUMENT_SAVED, EVENT_TASK_COMPLETED
from app.repositories import UserRepository
from app.services.growth_service import EXP_RULES


# ---------------------------------------------------------------- helpers
def _close_coro(coro) -> None:
    """关闭未被 await 的协程，避免 RuntimeWarning 污染测试输出。"""
    close = getattr(coro, "close", None)
    if close is not None:
        close()


class _StubBus:
    def __init__(self):
        self.subscriptions: list[tuple[str, object]] = []

    def subscribe(self, event: str, handler) -> None:
        self.subscriptions.append((event, handler))


class _FakeSession:
    def __init__(self):
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _FakeFuture:
    def __init__(self, exc: BaseException | None = None, raise_on_exception: bool = False):
        self._exc = exc
        self._raise = raise_on_exception

    def exception(self):
        if self._raise:
            raise RuntimeError("future broken")
        return self._exc


# ================================================================
# 一、event_handlers：事件循环调度与异常隔离
# ================================================================
class TestEventLoopDispatch:
    def test_run_async_without_loop_logs_and_skips(self, monkeypatch, caplog):
        after = []

        async def _coro():
            after.append("ran")

        monkeypatch.setattr(eh, "_loop", None)
        coro = _coro()
        try:
            with caplog.at_level(logging.WARNING):
                eh._run_async(coro)
        finally:
            _close_coro(coro)  # 未提交的协程需关闭，避免 never-awaited 警告

        assert after == []                       # 没有循环 → 不执行
        assert "事件循环未初始化，跳过异步事件处理" in caplog.text

    def test_run_async_swallows_closed_loop_runtime_error(self, monkeypatch, caplog):
        monkeypatch.setattr(eh, "_loop", object())  # 非 None 即通过早退判断

        def _raise(*_a, **_kw):
            raise RuntimeError("loop closed")

        monkeypatch.setattr(asyncio, "run_coroutine_threadsafe", _raise)

        async def _coro():
            return 1

        coro = _coro()
        try:
            with caplog.at_level(logging.WARNING):
                eh._run_async(coro)              # 不得抛出
        finally:
            _close_coro(coro)
        assert "事件循环已关闭，丢弃事件" in caplog.text

    def test_run_async_executes_coro_on_running_loop(self, monkeypatch):
        """受控真实循环：证明 run_coroutine_threadsafe 路径能把协程跑完。"""
        import threading

        loop = asyncio.new_event_loop()
        thread = threading.Thread(target=loop.run_forever, daemon=True)
        thread.start()
        done: list[str] = []
        try:
            async def _coro():
                done.append("ran")

            monkeypatch.setattr(eh, "_loop", loop)
            eh._run_async(_coro())
            deadline = time.time() + 3
            while not done and time.time() < deadline:
                time.sleep(0.01)
            assert done == ["ran"]
        finally:
            loop.call_soon_threadsafe(loop.stop)
            thread.join(timeout=3)
            loop.close()

    def test_submit_background_delegates_to_run_async(self, monkeypatch):
        recorded = []
        monkeypatch.setattr(eh, "_run_async", lambda coro: recorded.append(coro))

        async def _coro():
            return 1

        coro = _coro()
        try:
            eh.submit_background(coro)
        finally:
            _close_coro(coro)
        assert recorded == [coro]

    def test_event_wrappers_submit_their_handlers(self, monkeypatch):
        recorded = []
        monkeypatch.setattr(eh, "_run_async", lambda coro: recorded.append(coro))
        try:
            eh.on_document_saved("doc-1")
            eh.on_task_completed("task-1", extra="ignored")
        finally:
            for coro in recorded:
                _close_coro(coro)

        assert [c.cr_code.co_name for c in recorded] == [
            "_handle_document_saved",
            "_handle_task_completed",
        ]

    def test_on_future_done_logs_background_exception(self, caplog):
        with caplog.at_level(logging.ERROR):
            eh._on_future_done(_FakeFuture(exc=ValueError("background boom")))
        assert "后台事件任务异常" in caplog.text

    def test_on_future_done_ignores_successful_future(self, caplog):
        with caplog.at_level(logging.ERROR):
            eh._on_future_done(_FakeFuture(exc=None))
        assert "后台事件任务异常" not in caplog.text

    def test_on_future_done_swallows_broken_future(self, caplog):
        """future.exception() 自己抛异常时也必须被吞掉（回调不能炸后台线程）。"""
        with caplog.at_level(logging.ERROR):
            eh._on_future_done(_FakeFuture(raise_on_exception=True))
        assert "后台事件任务异常" not in caplog.text

    def test_set_event_loop_updates_module_global(self, monkeypatch):
        previous = eh._loop
        marker = object()
        try:
            eh.set_event_loop(marker)  # type: ignore[arg-type]
            assert eh._loop is marker
        finally:
            eh._loop = previous


# ================================================================
# 二、event_handlers：文档摘要 / 标签 / 任务通知（异常隔离）
# ================================================================
def _fake_user(api_key: str | None = "fernet:key", ai_enabled: bool = True):
    return types.SimpleNamespace(api_key_encrypted=api_key, ai_enabled=ai_enabled)


def _fake_doc(content: str = "长内容" * 30, **overrides):
    doc = types.SimpleNamespace(
        id=str(uuid.uuid4()), content=content, summary=None, ai_suggested_tags=[]
    )
    for key, value in overrides.items():
        setattr(doc, key, value)
    return doc


class TestDocumentSavedHandler:
    def _patch_lookups(self, monkeypatch, user, doc):
        monkeypatch.setattr(
            eh.UserRepository, "get_by_username", lambda self, name: user
        )
        monkeypatch.setattr(eh.DocumentRepository, "get", lambda self, doc_id: doc)

    def test_skips_when_ai_not_enabled(self, monkeypatch, caplog):
        self._patch_lookups(monkeypatch, user=_fake_user(api_key=None), doc=_fake_doc())

        class _NoAI:
            def __init__(self, *_a, **_kw):  # pragma: no cover - 不应被构造
                raise AssertionError("AI 未启用时不得构造 AIService")

        monkeypatch.setattr(eh, "AIService", _NoAI)
        with caplog.at_level(logging.DEBUG):
            asyncio.run(eh._handle_document_saved("doc-1"))
        assert "AI 未启用，跳过文档自动摘要: doc-1" in caplog.text

    def test_skips_short_document_without_ai_call(self, monkeypatch):
        doc = _fake_doc(content="太短")
        self._patch_lookups(monkeypatch, user=_fake_user(), doc=doc)

        class _NoAI:
            def __init__(self, *_a, **_kw):  # pragma: no cover
                raise AssertionError("内容过短时不得构造 AIService")

        monkeypatch.setattr(eh, "AIService", _NoAI)
        asyncio.run(eh._handle_document_saved("doc-short"))
        assert doc.summary is None and doc.ai_suggested_tags == []

    def test_summary_and_tags_are_persisted(self, monkeypatch, caplog):
        user = _fake_user()
        doc = _fake_doc()
        self._patch_lookups(monkeypatch, user=user, doc=doc)

        class _FakeAI:
            def __init__(self, db, user_obj):
                self.user = user_obj

            async def summarize(self, doc_id):
                return types.SimpleNamespace(summary="自动摘要" * 10)

            async def suggest_tags(self, doc_id):
                return types.SimpleNamespace(tags=["效率", "方法论", "工具", "学习", "复盘"])

        monkeypatch.setattr(eh, "AIService", _FakeAI)
        with caplog.at_level(logging.INFO):
            asyncio.run(eh._handle_document_saved("doc-ok"))

        assert doc.summary == ("自动摘要" * 10)[:500]
        assert doc.ai_suggested_tags == ["效率", "方法论", "工具", "学习", "复盘"][:10]
        assert "文档自动摘要完成: doc-ok" in caplog.text
        assert "文档标签建议完成: doc-ok" in caplog.text

    def test_summary_failure_does_not_block_tags(self, monkeypatch, caplog):
        doc = _fake_doc()
        self._patch_lookups(monkeypatch, user=_fake_user(), doc=doc)

        class _FakeAI:
            def __init__(self, db, user_obj):
                pass

            async def summarize(self, doc_id):
                raise RuntimeError("summary boom")

            async def suggest_tags(self, doc_id):
                return types.SimpleNamespace(tags=["标签A"])

        monkeypatch.setattr(eh, "AIService", _FakeAI)
        with caplog.at_level(logging.INFO):
            asyncio.run(eh._handle_document_saved("doc-sum-fail"))

        assert doc.summary is None                  # 摘要失败不落半截数据
        assert doc.ai_suggested_tags == ["标签A"]   # 标签步骤照常执行
        assert "文档自动摘要失败: doc-sum-fail" in caplog.text
        assert "文档标签建议完成: doc-sum-fail" in caplog.text

    def test_tag_failure_keeps_summary_and_is_logged(self, monkeypatch, caplog):
        doc = _fake_doc()
        self._patch_lookups(monkeypatch, user=_fake_user(), doc=doc)

        class _FakeAI:
            def __init__(self, db, user_obj):
                pass

            async def summarize(self, doc_id):
                return types.SimpleNamespace(summary="有效摘要")

            async def suggest_tags(self, doc_id):
                raise RuntimeError("tags boom")

        monkeypatch.setattr(eh, "AIService", _FakeAI)
        with caplog.at_level(logging.ERROR):
            asyncio.run(eh._handle_document_saved("doc-tag-fail"))

        assert doc.summary == "有效摘要"
        assert doc.ai_suggested_tags == []
        assert "文档标签建议失败: doc-tag-fail" in caplog.text


class TestTaskCompletedHandler:
    def test_missing_task_returns_without_notification(self, monkeypatch):
        created = []
        monkeypatch.setattr(eh.TaskRepository, "get", lambda self, task_id: None)
        monkeypatch.setattr(
            eh.NotificationRepository,
            "create",
            lambda self, **kw: created.append(kw),
        )
        asyncio.run(eh._handle_task_completed("ghost-task"))
        assert created == []

    def test_notification_failure_is_swallowed(self, monkeypatch, caplog):
        task = types.SimpleNamespace(
            id="t-1", user_id="u-1", title="写周报" * 30
        )
        monkeypatch.setattr(eh.TaskRepository, "get", lambda self, task_id: task)

        def _boom(self, **_kw):
            raise RuntimeError("notification boom")

        monkeypatch.setattr(eh.NotificationRepository, "create", _boom)
        with caplog.at_level(logging.ERROR):
            asyncio.run(eh._handle_task_completed("t-1"))   # 不得抛出
        assert "创建任务完成通知失败" in caplog.text

    def test_notification_created_and_committed(self, monkeypatch, db_session):
        user = UserRepository(db_session).create(
            username=f"eh-{uuid.uuid4().hex[:10]}", nickname="事件测试"
        )
        db_session.commit()
        task = types.SimpleNamespace(id="t-2", user_id=user.id, title="完成我")
        monkeypatch.setattr(eh.TaskRepository, "get", lambda self, task_id: task)

        asyncio.run(eh._handle_task_completed("t-2"))

        from app.models.notification import Notification

        db_session.expire_all()
        rows = db_session.query(Notification).filter_by(source_id="t-2").all()
        assert len(rows) == 1
        assert rows[0].user_id == user.id
        assert rows[0].title == "任务已完成"
        assert "完成我" in rows[0].content


# ================================================================
# 三、event_handlers：订阅注册
# ================================================================
class TestRegisterEventHandlers:
    def test_registers_both_business_subscriptions(self, monkeypatch, caplog):
        bus = _StubBus()
        monkeypatch.setattr(eh, "event_bus", bus)
        with caplog.at_level(logging.INFO):
            eh.register_event_handlers()

        assert [event for event, _ in bus.subscriptions] == [
            EVENT_DOCUMENT_SAVED,
            EVENT_TASK_COMPLETED,
        ]
        assert bus.subscriptions[0][1] is eh.on_document_saved
        assert bus.subscriptions[1][1] is eh.on_task_completed
        assert "事件总线订阅者已注册（AI并发上限: 2）" in caplog.text


# ================================================================
# 四、growth_handlers：通用结算 _grant 的跳过/异常分支
# ================================================================
class _AwardRecorder:
    calls: list[dict] = []

    def __init__(self, db):
        self.db = db

    def award(self, **kwargs):
        _AwardRecorder.calls.append(kwargs)


@pytest.fixture()
def grant_env(monkeypatch):
    """_grant 的隔离环境：假 SessionLocal + 记录型 GrowthService。"""
    session = _FakeSession()
    monkeypatch.setattr(gh, "SessionLocal", lambda: session)
    monkeypatch.setattr(gh, "GrowthService", _AwardRecorder)
    _AwardRecorder.calls = []
    return session


def _loader_result(value):
    return lambda db: value


class TestGrant:
    def test_loader_none_skips_award(self, grant_env):
        asyncio.run(gh._grant("task.completed", "k", "label", _loader_result(None)))
        assert _AwardRecorder.calls == []
        assert grant_env.closed is True

    def test_zero_exp_skips_award(self, grant_env):
        asyncio.run(
            gh._grant("task.completed", "k", "label", _loader_result(("u-1", "text")), exp=0)
        )
        assert _AwardRecorder.calls == []
        assert grant_env.closed is True

    def test_unknown_event_type_without_exp_skips_award(self, grant_env):
        asyncio.run(gh._grant("unknown.event", "k", "label", _loader_result(("u-1", None))))
        assert _AwardRecorder.calls == []

    def test_explicit_exp_awards_with_given_weight(self, grant_env):
        asyncio.run(
            gh._grant("task.completed", "task:1:completed", "完成任务",
                      _loader_result(("u-1", "写周报")), exp=7)
        )
        assert _AwardRecorder.calls == [{
            "user_id": "u-1", "source_key": "task:1:completed",
            "event_type": "task.completed", "exp": 7,
            "label": "完成任务", "classified_text": "写周报",
        }]
        assert grant_env.closed is True

    def test_default_weight_comes_from_exp_rules(self, grant_env):
        asyncio.run(
            gh._grant("task.completed", "k2", "完成任务", _loader_result(("u-2", None)))
        )
        assert _AwardRecorder.calls[0]["exp"] == EXP_RULES["task.completed"]

    def test_loader_exception_swallowed_and_logged(self, grant_env, caplog):
        def _boom(db):
            raise RuntimeError("loader boom")

        with caplog.at_level(logging.ERROR):
            asyncio.run(gh._grant("task.completed", "bad-key", "label", _boom))
        assert "EXP 结算失败: bad-key" in caplog.text
        assert _AwardRecorder.calls == []
        assert grant_env.closed is True

    def test_submit_delegates_to_background_submitter(self, monkeypatch):
        recorded = []
        monkeypatch.setattr(gh, "submit_background", lambda coro: recorded.append(coro))
        loader = _loader_result(("u", None))
        coro = gh._grant("task.completed", "k", "label", loader)
        try:
            gh._submit("task.completed", "k", "label", loader)
            assert len(recorded) == 1
            assert recorded[0].cr_code is gh._grant.__code__
        finally:
            _close_coro(coro)
            _close_coro(recorded[0])


# ================================================================
# 五、growth_handlers：14 个订阅者入口 + loader 的「实体不存在」分支
# ================================================================
@pytest.fixture()
def captured_submissions(monkeypatch):
    """捕获每个 on_* 入口提交的 loader，便于直接对 loader 做断言。"""
    captured: list[tuple[str, str, str, object, int | None]] = []

    def _fake_submit(event_type, source_key, label, loader, exp=None):
        captured.append((event_type, source_key, label, loader, exp))

    monkeypatch.setattr(gh, "_submit", _fake_submit)
    return captured


class TestGrowthHandlerLoaders:
    def test_task_completed_loader_returns_none_for_missing_task(
        self, captured_submissions, db_session
    ):
        gh.on_task_completed_growth("ghost-task")
        _, _, _, loader, _ = captured_submissions[0]
        assert loader(db_session) is None

    def test_study_time_loader_returns_none_for_missing_log(
        self, captured_submissions, db_session
    ):
        gh.on_study_time_logged_growth("ghost-log", duration=25)
        event_type, source_key, label, loader, exp = captured_submissions[0]
        assert event_type == "study.time.logged"
        assert source_key == "study:ghost-log"
        assert label == "学习 25 分钟"
        assert exp == gh.exp_for_study_minutes(25)
        assert loader(db_session) is None

    def test_diary_loader_returns_none_for_missing_diary(
        self, captured_submissions, db_session
    ):
        gh.on_diary_created_growth("ghost-diary")
        _, _, _, loader, _ = captured_submissions[0]
        assert loader(db_session) is None

    def test_project_memory_loader_returns_none_for_missing_memory(
        self, captured_submissions, db_session
    ):
        gh.on_project_memory_created_growth("ghost-memory")
        _, _, _, loader, _ = captured_submissions[0]
        assert loader(db_session) is None

    def test_workflow_loader_prefers_explicit_user_id(self, captured_submissions, db_session):
        gh.on_workflow_applied_growth("wf-1", user_id="u-from-event")
        _, _, _, loader, _ = captured_submissions[0]
        assert loader(db_session) == ("u-from-event", None)

    def test_workflow_loader_falls_back_to_repo_lookup(
        self, captured_submissions, db_session
    ):
        gh.on_workflow_applied_growth("ghost-workflow")
        _, _, _, loader, _ = captured_submissions[0]
        assert loader(db_session) is None      # 工作流不存在 → 放弃结算

    @pytest.mark.parametrize(
        ("handler", "kwargs", "expected_event"),
        [
            (gh.on_task_created_growth, {"task_id": "t"}, "task.created"),
            (gh.on_document_saved_growth, {"document_id": "d"}, "document.saved"),
            (gh.on_flashcard_reviewed_growth, {"card_id": "c"}, "flashcard.reviewed"),
            (gh.on_habit_checkin_growth, {"habit_id": "h", "date": "2026-01-01"}, "habit.checkin"),
            (gh.on_mood_logged_growth, {"mood_id": "m"}, "mood.logged"),
            (gh.on_sop_used_growth, {"sop_id": "s"}, "sop.used"),
            (gh.on_prompt_used_growth, {"prompt_id": "p"}, "prompt.used"),
            (gh.on_project_memory_created_growth, {"memory_id": "mm"}, "project.memory.created"),
            (gh.on_inbox_item_created_growth, {"item_id": "i"}, "inbox.item.created"),
            (gh.on_inbox_item_processed_growth, {"item_id": "i", "action": "archive"}, "inbox.item.processed"),
        ],
    )
    def test_all_event_entries_submit_expected_event(
        self, captured_submissions, handler, kwargs, expected_event
    ):
        handler(**kwargs)
        assert len(captured_submissions) == 1
        event_type, source_key, _label, _loader, _exp = captured_submissions[0]
        assert event_type == expected_event
        assert kwargs.get("task_id") or kwargs.get("document_id") or source_key

    def test_stamp_is_second_precision(self):
        stamp = gh._stamp()
        now = int(datetime.now(timezone.utc).timestamp())
        assert stamp.isdigit()
        assert abs(int(stamp) - now) <= 5


class TestRegisterGrowthHandlers:
    def test_registers_all_fourteen_subscriptions(self, monkeypatch, caplog):
        bus = _StubBus()
        monkeypatch.setattr(gh, "event_bus", bus)
        with caplog.at_level(logging.INFO):
            gh.register_growth_handlers()

        assert len(bus.subscriptions) == len(gh._SUBSCRIPTIONS) == 14
        assert [e for e, _ in bus.subscriptions] == [
            e for e, _ in gh._SUBSCRIPTIONS
        ]
        assert "成长体系订阅者已注册（14 个事件）" in caplog.text

    def test_subscriptions_are_unique_events(self):
        events = [event for event, _ in gh._SUBSCRIPTIONS]
        assert len(events) == len(set(events)), "同一事件不得重复订阅两次"
