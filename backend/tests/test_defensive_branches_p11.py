# ============================================================
# 防御/边界分支补测（Phase11-C · A 类「可测未测」）
#
# 来源：Phase11 覆盖率审计导出的 Top missed 模块。本文件只覆盖**A 类**
# （普通错误分支/边界，进程内可安全构造），不含 B/C/D 类：
#   · avatar_service：记忆/灵感过滤、身份归属校验、统计、配置自动创建
#   · task_service：归档项目只读、空串解除项目、批量失败计数、番茄钟、
#     重复任务 _next_occurrence 的 daily/weekly/monthly/未知类型分支
#   · ai_service.verify_api：空响应 / HTTP 401|500 / 非 HTTP 异常 的失败原因区分
#   · dashboard_service：资源/学习/生活/资产四个聚合降级（fail-open）分支
#   · api/health：磁盘、库连接两个降级分支
#   · core/event_bus：无事件循环时的异步 handler 执行 + 异步 handler 失败记录
#   · repositories/task_repo：list_user_tasks 五个过滤条件、身份轴过滤/未归类
#   · services/sync/engine：apply 的 skipped 分支、非法 ISO 解析、游标非法值、超大包
# ============================================================
from __future__ import annotations

import asyncio
import logging
import types
import uuid
from datetime import date, datetime, timedelta

import pytest

from app.api import health as health_mod
from app.core import event_bus as eb_mod
from app.core.event_bus import EventBus
from app.core.exceptions import (
    AIRequestFailedException,
    NotFoundException,
    TaskStateException,
    ValidationException,
)
from app.models.settings import Setting
from app.repositories import ProjectRepository, TaskRepository
from app.schemas.avatar import CreateMemoryRequest, UpdateConfigRequest
from app.schemas.task import BatchTaskRequest, CreateTaskRequest, UpdateTaskRequest
from app.services.ai import ai_service as ai_mod
from app.services.ai.ai_service import AIService
from app.services.avatar_service import AvatarService
from app.services.dashboard_service import (
    ASSET_CATEGORIES,
    LIFE_CATEGORIES,
    RESOURCE_CATEGORIES,
    DashboardService,
)
from app.services.sync.engine import SyncEngine
from app.services.task_service import TaskService
from tests.factories import make_avatar_memory, make_identity, make_task


def _boom(*_args, **_kwargs):
    raise RuntimeError("probe: 聚合失败")


# ================================================================
# 一、avatar_service：过滤 / 归属 / 统计 / 配置
# ================================================================
class TestAvatarMemoryBranches:
    def test_list_memories_filters_by_type(self, db_session, test_user):
        make_avatar_memory(db_session, test_user.id, memory_type="event", title="事件记忆")
        make_avatar_memory(db_session, test_user.id, memory_type="profile", title="画像记忆")
        db_session.commit()

        svc = AvatarService(db_session)
        events = svc.list_memories(test_user.id, memory_type="event")

        assert events["total"] == 1
        assert [m["title"] for m in events["list"]] == ["事件记忆"]
        assert events["list"][0]["memory_type"] == "event"

    def test_create_memory_with_unknown_identity_is_rejected(self, db_session, test_user):
        svc = AvatarService(db_session)
        request = CreateMemoryRequest(
            memory_type="event", title="带幽灵身份的记忆", identity_id="ghost-identity"
        )

        with pytest.raises(ValidationException, match="身份不存在"):
            svc.create_memory(test_user.id, request)

    def test_get_memory_stats_counts_types_and_verified(self, db_session, test_user):
        first = make_avatar_memory(db_session, test_user.id, memory_type="event", title="e1")
        make_avatar_memory(db_session, test_user.id, memory_type="event", title="e2")
        make_avatar_memory(db_session, test_user.id, memory_type="profile", title="p1")
        db_session.commit()
        first.is_verified = True
        db_session.commit()

        stats = AvatarService(db_session).get_memory_stats(test_user.id)

        assert stats["event"] == 2
        assert stats["profile"] == 1
        assert stats["total"] == 3
        assert stats["verified"] == 1

    def test_get_and_update_config_auto_create_then_reuse(self, db_session, test_user):
        svc = AvatarService(db_session)

        created = svc.get_config(test_user.id)
        assert created["automation_level"] == "L2"      # 默认档位
        assert created["persona_name"] is not None

        updated = svc.update_config(test_user.id, UpdateConfigRequest(persona_name="小启"))
        assert updated["persona_name"] == "小启"
        assert updated["id"] == created["id"]           # 复用同一行，不重复创建

        again = svc.get_config(test_user.id)
        assert again["id"] == created["id"]
        assert again["persona_name"] == "小启"


# ================================================================
# 二、task_service：归档项目 / 批量 / 番茄钟 / 重复任务
# ================================================================
class TestTaskServiceBranches:
    def test_create_task_with_owned_identity(self, db_session, test_user):
        identity = make_identity(db_session, test_user.id, name="写作线")
        db_session.commit()

        out = TaskService(db_session).create(
            test_user.id, CreateTaskRequest(title="带身份的任务", identity_id=identity.id)
        )

        assert out.identity_id == identity.id

    def test_update_task_under_archived_project_is_read_only(self, db_session, test_user):
        project = ProjectRepository(db_session).create(
            user_id=test_user.id, name="已归档项目", status="archived"
        )
        db_session.commit()
        task = make_task(db_session, test_user.id, title="归档项目任务",
                         project_id=project.id)
        db_session.commit()

        with pytest.raises(TaskStateException, match="所属项目已归档"):
            TaskService(db_session).update(
                test_user.id, task.id, UpdateTaskRequest(title="不允许的修改")
            )

    def test_update_with_blank_project_id_clears_link(self, db_session, test_user):
        project = ProjectRepository(db_session).create(user_id=test_user.id, name="进行中项目")
        db_session.commit()
        task = make_task(db_session, test_user.id, title="待解除项目", project_id=project.id)
        db_session.commit()

        out = TaskService(db_session).update(
            test_user.id, task.id, UpdateTaskRequest(project_id="")
        )
        db_session.refresh(task)
        assert out.project_id is None
        assert task.project_id is None

    def test_batch_set_priority_invalid_counts_as_failed(self, db_session, test_user):
        first = make_task(db_session, test_user.id, title="批量A")
        second = make_task(db_session, test_user.id, title="批量B")
        db_session.commit()

        result = TaskService(db_session).batch(
            test_user.id,
            BatchTaskRequest(task_ids=[first.id, second.id], action="set_priority",
                             priority="super-high"),
        )

        assert result.affected == 0
        assert result.failed == 2
        db_session.refresh(first)
        assert first.priority == "medium"        # 非法优先级不落库

    def test_batch_missing_task_is_counted_as_failed(self, db_session, test_user):
        existing = make_task(db_session, test_user.id, title="存在的任务")
        db_session.commit()

        result = TaskService(db_session).batch(
            test_user.id,
            BatchTaskRequest(task_ids=[existing.id, "ghost-task"], action="complete"),
        )

        assert result.affected == 1
        assert result.failed == 1
        db_session.refresh(existing)
        assert existing.status == "completed"

    def test_focus_stop_unknown_session_is_not_found(self, db_session, test_user):
        with pytest.raises(NotFoundException, match="专注会话不存在"):
            TaskService(db_session).focus_stop(test_user.id, "ghost-session")

    def test_recurring_template_without_type_is_skipped(self, db_session, test_user):
        make_task(db_session, test_user.id, title="无类型重复任务",
                  recurrence={"interval": 1})
        db_session.commit()

        assert TaskService(db_session).generate_recurring_instances(test_user.id) == 0

    def test_next_occurrence_monthly_clamps_to_28_and_weekly_future_is_none(self):
        # monthly：base=1月31日，推进到 ≥3月1日 → 3月28日（31 日被钳到 28，避免非法日期）
        assert TaskService._next_occurrence(
            date(2026, 1, 31), date(2026, 3, 1), "monthly", {}
        ) == date(2026, 3, 28)
        # weekly：base 在未来 → 60 天窗口内无 ≥base 的匹配日 → None
        today = date.today()
        assert TaskService._next_occurrence(
            today + timedelta(days=100), today, "weekly", {}
        ) is None
        # 未知周期类型 → None（不生成实例）
        assert TaskService._next_occurrence(today, today, "yearly", {}) is None

    def test_recurring_weekly_template_generates_due_instance(self, db_session, test_user):
        today = date.today()
        # 模板 due_date 必须在过去：exists_instance 按「同 title + 同 due_date」判重，
        # 若模板本身 due_date=today 会被当成已生成实例 → 永远生成 0 个。
        make_task(db_session, test_user.id, title="每周复盘",
                  due_date=today - timedelta(days=7),
                  recurrence={"type": "weekly", "days": [today.weekday()]})
        db_session.commit()

        assert TaskService(db_session).generate_recurring_instances(test_user.id) == 1
        # 幂等：再跑一次不重复生成
        assert TaskService(db_session).generate_recurring_instances(test_user.id) == 0


# ================================================================
# 三、ai_service.verify_api：失败原因区分
# ================================================================
def _patch_deepseek(monkeypatch, *, exc=None, content="pong"):
    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def chat(self, messages, **kwargs):
            if exc is not None:
                raise exc
            return types.SimpleNamespace(content=content)

    monkeypatch.setattr(ai_mod, "DeepSeekClient", _FakeClient)


class _LogSpy:
    """替身 logger：记录 warning/exception 的原始格式串与参数。"""

    def __init__(self):
        self.events: list[tuple[str, str, tuple]] = []

    def warning(self, message, *args, **_kw):
        self.events.append(("warning", message, args))

    def exception(self, message, *args, **_kw):
        self.events.append(("exception", message, args))

    def messages(self, level: str) -> list[str]:
        return [msg for lvl, msg, _args in self.events if lvl == level]


class TestVerifyApiFailureReasons:
    def test_success_returns_model(self, monkeypatch):
        from app.config import get_settings

        _patch_deepseek(monkeypatch)
        result = asyncio.run(AIService.verify_api(None, "sk-valid"))
        assert result.valid is True
        assert result.model == get_settings().ai_model

    def test_empty_content_is_invalid(self, monkeypatch):
        spy = _LogSpy()
        _patch_deepseek(monkeypatch, content="")
        monkeypatch.setattr(ai_mod, "logger", spy)

        result = asyncio.run(AIService.verify_api(None, "sk-empty"))

        assert result.valid is False
        assert result.reason == "模型返回空响应"
        assert any("模型返回空内容" in msg for msg in spy.messages("warning"))

    def test_http_401_reports_invalid_key(self, monkeypatch):
        _patch_deepseek(monkeypatch, exc=AIRequestFailedException("AI 请求失败: HTTP 401"))
        result = asyncio.run(AIService.verify_api(None, "sk-bad"))
        assert result.valid is False
        assert result.reason == "API Key 无效或无权限（HTTP 401/403）"

    def test_http_500_reports_service_unavailable(self, monkeypatch):
        _patch_deepseek(monkeypatch, exc=AIRequestFailedException("AI 请求失败: HTTP 500"))
        result = asyncio.run(AIService.verify_api(None, "sk-x"))
        assert result.valid is False
        assert result.reason == "服务不可用：AI 请求失败: HTTP 500"

    def test_non_http_exception_reports_request_exception(self, monkeypatch):
        spy = _LogSpy()
        _patch_deepseek(monkeypatch, exc=OSError("network down"))
        monkeypatch.setattr(ai_mod, "logger", spy)

        result = asyncio.run(AIService.verify_api(None, "sk-x"))

        assert result.valid is False
        assert result.reason == "请求异常：OSError"
        assert any(
            "API Key 校验异常（非 HTTP 错误，可能是网络/超时）" in msg
            for msg in spy.messages("exception")
        )


# ================================================================
# 四、dashboard：四个聚合降级（fail-open）分支
# ================================================================
class TestDashboardDegradation:
    def test_resource_center_degrades_to_placeholder(self, db_session, test_user,
                                                    monkeypatch, caplog):
        svc = DashboardService(db_session, test_user)
        monkeypatch.setattr(svc.inbox_repo, "count", _boom)
        with caplog.at_level(logging.WARNING):
            data = svc.get()
        assert data.resource_center.status == "planned"
        assert [c.id for c in data.resource_center.categories] == [
            c.id for c in RESOURCE_CATEGORIES
        ]
        assert "资源中心数据聚合失败，降级为占位" in caplog.text

    def test_learning_degrades_to_placeholder(self, db_session, test_user,
                                              monkeypatch, caplog):
        svc = DashboardService(db_session, test_user)
        monkeypatch.setattr(svc.learning_svc, "list_plans", _boom)
        with caplog.at_level(logging.WARNING):
            data = svc.get()
        assert data.learning.status == "planned"
        assert "学习成长数据聚合失败，降级为占位" in caplog.text

    def test_life_degrades_to_placeholder(self, db_session, test_user,
                                          monkeypatch, caplog):
        svc = DashboardService(db_session, test_user)
        monkeypatch.setattr(svc.habit_repo, "count", _boom)
        with caplog.at_level(logging.WARNING):
            data = svc.get()
        assert data.life.status == "planned"
        assert [c.id for c in data.life.categories] == [c.id for c in LIFE_CATEGORIES]
        assert "生活记录数据聚合失败，降级为占位" in caplog.text

    def test_assets_degrades_to_placeholder(self, db_session, test_user,
                                            monkeypatch, caplog):
        svc = DashboardService(db_session, test_user)
        monkeypatch.setattr(svc.sop_repo, "count", _boom)
        with caplog.at_level(logging.WARNING):
            data = svc.get()
        assert data.assets.status == "planned"
        assert [c.id for c in data.assets.categories] == [c.id for c in ASSET_CATEGORIES]
        assert "长期资产库数据聚合失败，降级为占位" in caplog.text


# ================================================================
# 五、health：磁盘 / 数据库连接降级
# ================================================================
class TestHealthDegradation:
    def test_disk_usage_failure_returns_zeros(self, monkeypatch, caplog):
        import shutil

        def _raise(_path):
            raise OSError("disk unavailable")

        monkeypatch.setattr(shutil, "disk_usage", _raise)
        with caplog.at_level(logging.WARNING):
            usage = health_mod._get_disk_usage("/nonexistent")

        assert usage == {"total_gb": 0, "used_gb": 0, "free_gb": 0, "usage_percent": 0}
        assert "磁盘使用率读取失败，降级为 0" in caplog.text

    def test_db_size_failure_returns_zero(self, monkeypatch, caplog):
        def _raise(_path):
            raise OSError("stat failed")

        # 只替换 health 模块内的 os 引用：exists 恒真 → 走到 getsize 抛错分支
        monkeypatch.setattr(
            health_mod, "os",
            types.SimpleNamespace(path=types.SimpleNamespace(exists=lambda _p: True,
                                                            getsize=_raise)),
        )
        with caplog.at_level(logging.WARNING):
            assert health_mod._get_db_size() == 0.0
        assert "数据库大小读取失败" in caplog.text

    def test_db_connection_failure_returns_false(self, monkeypatch, caplog):
        class _BrokenEngine:
            def connect(self):
                raise RuntimeError("database locked")

        monkeypatch.setattr(health_mod, "engine", _BrokenEngine())
        with caplog.at_level(logging.WARNING):
            assert health_mod._check_db_connection() is False
        assert "数据库连接检查失败" in caplog.text


# ================================================================
# 六、event_bus：无事件循环的异步 handler / 异步 handler 失败
# ================================================================
def _raise_no_loop():
    raise RuntimeError("no running event loop")


class TestEventBusAsyncBranches:
    def _fake_loopless_asyncio(self):
        # 只替换 event_bus 模块内的 asyncio 引用，避免影响 pytest 自身
        return types.SimpleNamespace(
            get_event_loop=_raise_no_loop,
            get_running_loop=_raise_no_loop,
            run=asyncio.run,
        )

    def _cleanup(self, event: str) -> None:
        EventBus._async_handlers.pop(event, None)
        EventBus._stats.pop(event, None)
        EventBus._window.pop(event, None)

    def test_publish_without_loop_runs_async_handler(self, monkeypatch):
        event = f"p11.async.ok.{uuid.uuid4().hex[:8]}"
        ran: list[dict] = []

        async def handler(**kwargs):
            ran.append(kwargs)

        EventBus.subscribe_async(event, handler)
        monkeypatch.setattr(eb_mod, "asyncio", self._fake_loopless_asyncio())
        try:
            EventBus.publish(event, n=1)
        finally:
            self._cleanup(event)

        assert ran == [{"n": 1}]                       # asyncio.run 兜底确实执行了
        record = [r for r in EventBus._history if r.event == event][-1]
        assert record.success is True
        assert record.handlers_called == 1

    def test_publish_async_handler_failure_is_recorded(self, monkeypatch, caplog):
        event = f"p11.async.fail.{uuid.uuid4().hex[:8]}"

        async def handler(**_kwargs):
            raise ValueError("async boom")

        EventBus.subscribe_async(event, handler)
        monkeypatch.setattr(eb_mod, "asyncio", self._fake_loopless_asyncio())
        with caplog.at_level(logging.ERROR):
            try:
                EventBus.publish(event)
            finally:
                self._cleanup(event)

        record = [r for r in EventBus._history if r.event == event][-1]
        assert record.success is False
        assert record.failed_handlers == ["handler"]
        assert record.handlers_called == 0
        assert "异步事件处理失败" in caplog.text


# ================================================================
# 七、task_repo：过滤条件（含身份轴）
# ================================================================
class TestTaskRepositoryFilters:
    def test_list_user_tasks_applies_each_filter(self, db_session, test_user):
        project = ProjectRepository(db_session).create(user_id=test_user.id, name="过滤项目")
        db_session.commit()
        first = make_task(db_session, test_user.id, title="命中过滤", status="pending",
                          priority="high", project_tag="整理", project_id=project.id,
                          due_date=date.today())
        second = make_task(db_session, test_user.id, title="不命中", status="completed",
                           priority="low")
        db_session.commit()

        repo = TaskRepository(db_session)
        ids = lambda rows: [t.id for t in rows]  # noqa: E731
        assert ids(repo.list_user_tasks(test_user.id, status="completed")) == [second.id]
        assert ids(repo.list_user_tasks(test_user.id, priority="high")) == [first.id]
        assert ids(repo.list_user_tasks(test_user.id, project_tag="整理")) == [first.id]
        assert ids(repo.list_user_tasks(test_user.id, project_id=project.id)) == [first.id]
        assert ids(repo.list_user_tasks(test_user.id, due_date=date.today())) == [first.id]
        assert len(repo.list_user_tasks(test_user.id)) == 2

    def test_list_paginated_identity_filters(self, db_session, test_user):
        identity = make_identity(db_session, test_user.id, name="身份轴")
        assigned = make_task(db_session, test_user.id, title="已归类")
        assigned.identity_id = identity.id
        unassigned = make_task(db_session, test_user.id, title="未归类")
        unassigned.identity_id = None
        db_session.commit()

        repo = TaskRepository(db_session)
        assert [t.id for t in repo.list_paginated(
            test_user.id, identity_id=identity.id)] == [assigned.id]
        assert [t.id for t in repo.list_paginated(
            test_user.id, identity_unassigned=True)] == [unassigned.id]


# ================================================================
# 八、sync/engine：apply skipped / ISO 解析 / 游标 / 超大包
# ================================================================
class TestSyncEngineDefensive:
    def test_apply_skips_mismatched_insert_and_update(self, db_session, test_user):
        existing = make_task(db_session, test_user.id, title="已存在任务")
        db_session.commit()
        engine = SyncEngine(db_session, test_user.id)

        stats = engine.apply([
            {"table": "tasks", "row": {"id": existing.id}, "op": "insert"},   # id 已存在
            {"table": "tasks", "row": {"id": "ghost-id"}, "op": "update"},    # id 不存在
        ])

        assert stats == {"insert": 0, "update": 0, "delete": 0, "skipped": 2}
        # 注：apply 里「无 deleted_at 的表收到 delete → skipped」分支在当前
        # 49 张表上不可达（全部继承 SoftDeleteMixin），归 B 类不可达防御。

    def test_decode_row_tolerates_invalid_iso_datetime(self, db_session, test_user):
        engine = SyncEngine(db_session, test_user.id)
        bad = engine._decode_row("tasks", {"created_at": "2026-13-45T99:99:99"})
        assert bad["created_at"] == "2026-13-45T99:99:99"     # 解析失败原样保留
        good = engine._decode_row("tasks", {"created_at": "2026-01-02T03:04:05"})
        assert good["created_at"] == datetime(2026, 1, 2, 3, 4, 5)

    def test_export_cursor_ignores_blank_or_invalid_value(self, db_session, test_user):
        engine = SyncEngine(db_session, test_user.id)
        db_session.add(Setting(user_id=test_user.id, key="sync.last_export_at", value="   "))
        db_session.commit()
        assert engine._export_cursor() is None

        row = db_session.query(Setting).filter_by(
            user_id=test_user.id, key="sync.last_export_at").one()
        row.value = "not-a-datetime"
        db_session.commit()
        assert engine._export_cursor() is None

    def test_load_package_rejects_oversize_file(self, tmp_path):
        package = tmp_path / "huge-sync.json"
        with open(package, "wb") as fh:
            fh.seek(50 * 1024 * 1024)      # 稀疏文件：秒级创建 50MB+1 字节
            fh.write(b"x")

        with pytest.raises(ValueError, match="同步包超过 50MB 上限"):
            SyncEngine.load_package(package)
