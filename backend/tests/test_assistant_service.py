# ============================================================
# Phase6 · AssistantService / 本地规则解析（降级链路）测试
#
# 覆盖缺口：app/services/assistant_service.py（Phase5 基线 28.5%）
# 重点：
#   1. 无 Key 降级：local_parse 的切条 / 时间抠取 / 优先级 / 去前缀；
#   2. DeepSeek 解析：请求参数、JSON 容错、kind/priority 归一、clarifications 截断；
#   3. parse 降级矩阵：空输入 / 无 Key / 上游异常 / 上游空结果；
#   4. apply 白名单落库：task / reminder / note 三类、上限、非法 kind/priority/deadline。
# 全部用替身隔离 HTTP，不联网；库操作用 db_session + test_user。
# ============================================================
from __future__ import annotations

import asyncio
import json
from datetime import date, datetime

import pytest
from sqlalchemy import select

from app.core.exceptions import ValidationException
from app.models.resource import InboxItem
from app.models.task import Task
from app.services.assistant_service import (
    DEFAULT_MODEL,
    AssistantService,
    _deadline_from_text,
    _parse_dt,
    local_parse,
)


def _svc(db, user_id: str) -> AssistantService:
    return AssistantService(db, user_id)


# ================================================================
# 一、_deadline_from_text / local_parse（无 Key 降级核心）
# ================================================================
class TestDeadlineParsing:
    TODAY = date(2026, 10, 28)  # 周三

    def test_no_time_returns_none(self):
        deadline, has_time = _deadline_from_text("买牛奶", self.TODAY)
        assert deadline is None
        assert has_time is False

    @pytest.mark.parametrize(
        "text,expected_date",
        [
            ("今天写周报", "2026-10-28"),
            ("明天交作业", "2026-10-29"),
            ("后天开会", "2026-10-30"),
            # D-22：长词优先（大后天 在 后天 之前），不再被抢先命中为 +2 天
            ("大后天体检", "2026-10-31"),
        ],
    )
    def test_relative_day_hints(self, text, expected_date):
        deadline, has_time = _deadline_from_text(text, self.TODAY)
        assert deadline is not None
        assert deadline.date().isoformat() == expected_date
        assert has_time is False

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("下午3点开会", "2026-10-28T15:00:00"),
            ("晚上8点跑步", "2026-10-28T20:00:00"),
            ("中午12点吃饭", "2026-10-28T12:00:00"),
            ("明天上午9点30分面试", "2026-10-29T09:30:00"),
            ("3点喝咖啡", "2026-10-28T15:00:00"),  # 没说上下午的小时默认下午
            ("25点睡觉", "2026-10-28T23:00:00"),  # 超过 23 点截断
        ],
    )
    def test_explicit_clock_time(self, text, expected):
        deadline, has_time = _deadline_from_text(text, self.TODAY)
        assert deadline is not None
        assert deadline.isoformat() == expected
        assert has_time is True

    def test_grand_day_after_tomorrow_with_clock_time(self):
        """"大后天下午3点" 走 _NUM_TIME 分支，日期 +3、时间 15:00。"""
        deadline, has_time = _deadline_from_text("大后天下午3点开会", self.TODAY)
        assert deadline is not None
        assert deadline.isoformat() == "2026-10-31T15:00:00"
        assert has_time is True

    def test_local_parse_grand_day_after_tomorrow_deadline(self):
        items = local_parse("大后天体检", datetime(2026, 10, 28, 9, 0, 0))
        assert items[0]["deadline"].startswith("2026-10-31")

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("后天下午3点开会", "2026-10-30T15:00:00"),
            ("中午10点吃饭", "2026-10-28T12:00:00"),
        ],
    )
    def test_numeric_time_branches(self, text, expected):
        """覆盖 day_part=后天 / 周X 与中午 h<12 的分支。"""
        deadline, has_time = _deadline_from_text(text, self.TODAY)
        assert deadline is not None
        assert deadline.isoformat() == expected
        assert has_time is True

    def test_numeric_weekday_double_adds_offset_bug(self):
        """BUG(已记录 B-4)：_NUM_TIME 的 day_part=周X 分支里 base 已前进 7 天，

        随后 `offset=(base-today).days` 再叠加一次 → "周三下午3点" 得到 +14 天
        （应为 +7）。本轮只修 D-22 的长词顺序，不改此分支；按当前行为钉住。
        """
        deadline, _ = _deadline_from_text("周三下午3点开会", self.TODAY)
        assert deadline is not None
        assert deadline.date().isoformat() == "2026-11-11"  # 修复后应为 11-04

    def test_next_week_prefix_weekday_double_adds_bug(self):
        """BUG(已记录 B-5)："下周X" 的 `delta += ... if False else delta` 实际执行 delta += delta。"""
        deadline, _ = _deadline_from_text("下周三开会", self.TODAY)
        assert deadline is not None
        assert deadline.date().isoformat() == "2026-11-11"  # 修复后应为 11-04

    def test_next_weekday_rolls_to_next_week(self):
        # 今天周三（weekday=2），"周三" 应推到下周
        deadline, has_time = _deadline_from_text("周三交表", self.TODAY)
        assert deadline is not None
        assert deadline.date().isoformat() == "2026-11-04"
        assert has_time is False


class TestLocalParse:
    NOW = datetime(2026, 10, 28, 9, 0, 0)

    def test_splits_by_punctuation_and_conjunction(self):
        items = local_parse("写周报。买牛奶；然后给妈妈打电话", self.NOW)
        titles = [i["title"] for i in items]
        assert "写周报" in titles
        assert "买牛奶" in titles
        assert "给妈妈打电话" in titles

    def test_strips_leading_pronouns(self):
        items = local_parse("帮我买牛奶", self.NOW)
        assert items[0]["title"] == "买牛奶"
        # notes 记录的是"去掉引导词后"的文本（与实现一致）
        assert items[0]["notes"] == "买牛奶"

    def test_priority_high_on_urgent_words(self):
        assert local_parse("紧急处理线上告警", self.NOW)[0]["priority"] == "high"
        assert local_parse("尽快回复邮件", self.NOW)[0]["priority"] == "high"
        assert local_parse("整理书架", self.NOW)[0]["priority"] == "medium"

    def test_deadline_is_iso_or_none(self):
        with_dl = local_parse("明天下午3点开会", self.NOW)[0]
        assert with_dl["deadline"] is not None
        assert datetime.fromisoformat(with_dl["deadline"]).hour == 15
        no_dl = local_parse("整理书架", self.NOW)[0]
        assert no_dl["deadline"] is None

    def test_title_strips_time_phrase(self):
        item = local_parse("明天下午3点开会", self.NOW)[0]
        assert "开会" in item["title"]
        assert "明天" not in item["title"]

    def test_skips_too_short_or_filler_chunks(self):
        assert local_parse("。；！", self.NOW) == []
        assert local_parse("要", self.NOW) == []

    def test_item_shape_is_stable(self):
        item = local_parse("买牛奶", self.NOW)[0]
        assert set(item) == {
            "kind", "title", "deadline", "people", "location", "priority", "notes"
        }
        assert item["kind"] == "task"
        assert item["people"] == [] and item["location"] is None

    def test_long_title_truncated_to_40(self):
        item = local_parse("买" + "很长的描述" * 20, self.NOW)[0]
        assert len(item["title"]) <= 40

    def test_parse_dt_handles_invalid_and_empty(self):
        assert _parse_dt(None) is None
        assert _parse_dt("") is None
        assert _parse_dt("not-a-date") is None
        assert _parse_dt("2026-10-28T15:00:00") == datetime(2026, 10, 28, 15, 0, 0)


# ================================================================
# 二、配置（Key 加密落库 / 状态 / 解密失败降级）
# ================================================================
class TestAssistantConfig:
    def test_status_without_key(self, db_session, test_user):
        status = _svc(db_session, test_user.id).status()
        assert status == {"configured": False, "model": DEFAULT_MODEL}

    def test_configure_rejects_short_key(self, db_session, test_user):
        with pytest.raises(ValidationException):
            _svc(db_session, test_user.id).configure("short")

    def test_configure_encrypts_key_and_reports_configured(self, db_session, test_user):
        svc = _svc(db_session, test_user.id)
        status = svc.configure("sk-test-12345678")
        assert status["configured"] is True
        assert status["model"] == DEFAULT_MODEL
        # 落库值必须是密文，且官方读取路径能解回明文
        from app.models.settings import Setting

        raw = db_session.scalars(
            select(Setting).where(
                Setting.user_id == test_user.id,
                Setting.key == "assistant.deepseek_key",
            )
        ).one().value
        assert raw != "sk-test-12345678"
        assert "sk-test-12345678" not in raw
        assert svc._key() == "sk-test-12345678"

    def test_key_decrypt_failure_degrades_to_none(self, db_session, test_user, monkeypatch):
        svc = _svc(db_session, test_user.id)
        svc.configure("sk-test-12345678")

        class BrokenEnc:
            def decrypt(self, _raw):
                raise ValueError("key file replaced")

        monkeypatch.setattr(svc, "_encryption", lambda: BrokenEnc())
        assert svc._key() is None


# ================================================================
# 三、DeepSeek 解析（替身 httpx，断言请求参数与容错）
# ================================================================
class _FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class _FakeAsyncClient:
    """记录请求的 httpx.AsyncClient 替身。"""

    calls: list[dict] = []
    response: _FakeResponse = _FakeResponse(200, {})

    def __init__(self, *args, **kwargs):
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, **kwargs):
        _FakeAsyncClient.calls.append({"url": url, **kwargs})
        return _FakeAsyncClient.response


class TestDeepSeekParse:
    def _install(self, monkeypatch, payload: dict, status: int = 200):
        _FakeAsyncClient.calls = []
        _FakeAsyncClient.response = _FakeResponse(status, payload)
        monkeypatch.setattr(
            "app.services.assistant_service.httpx.AsyncClient", _FakeAsyncClient
        )

    def test_request_uses_hardcoded_base_and_bearer(
        self, db_session, test_user, monkeypatch
    ):
        content = json.dumps({"items": [{"title": "买牛奶", "kind": "task"}]})
        self._install(monkeypatch, {"choices": [{"message": {"content": content}}]})
        svc = _svc(db_session, test_user.id)
        items, clarifications, source = asyncio.run(
            svc._deepseek_parse("买牛奶", datetime(2026, 10, 28, 9), "sk-key")
        )
        call = _FakeAsyncClient.calls[0]
        assert call["url"] == "https://api.deepseek.com/v1/chat/completions"
        assert call["headers"]["Authorization"] == "Bearer sk-key"
        payload = call["json"]
        assert payload["response_format"] == {"type": "json_object"}
        assert payload["stream"] is False if "stream" in payload else True
        assert payload["messages"][0]["role"] == "system"
        assert payload["messages"][1] == {"role": "user", "content": "买牛奶"}
        assert source == "deepseek"
        assert clarifications == []
        assert items[0]["title"] == "买牛奶"

    def test_invalid_items_are_filtered_and_enums_normalized(
        self, db_session, test_user, monkeypatch
    ):
        content = json.dumps({
            "items": [
                {"title": "有效任务"},
                {"title": ""},
                "not-a-dict",
                {"title": "怪类型", "kind": "weird", "priority": "urgent"},
                {"title": "提醒", "kind": "reminder", "priority": "low"},
            ],
            "clarifications": [f"q{i}" for i in range(6)],
        })
        self._install(monkeypatch, {"choices": [{"message": {"content": content}}]})
        svc = _svc(db_session, test_user.id)
        items, clarifications, _ = asyncio.run(
            svc._deepseek_parse("x", datetime(2026, 10, 28, 9), "sk-key")
        )
        assert [i["title"] for i in items] == ["有效任务", "怪类型", "提醒"]
        assert items[0]["kind"] == "task" and items[0]["priority"] == "medium"
        assert items[1]["kind"] == "task" and items[1]["priority"] == "medium"
        assert items[2]["kind"] == "reminder" and items[2]["priority"] == "low"
        assert len(clarifications) == 5  # 截断到 5

    def test_http_error_propagates_for_parse_to_degrade(
        self, db_session, test_user, monkeypatch
    ):
        self._install(monkeypatch, {}, status=500)
        svc = _svc(db_session, test_user.id)
        with pytest.raises(RuntimeError):
            asyncio.run(svc._deepseek_parse("x", datetime(2026, 10, 28, 9), "k"))


# ================================================================
# 四、parse 降级矩阵
# ================================================================
class TestParseDegradation:
    def test_empty_text_rejected(self, db_session, test_user):
        with pytest.raises(ValidationException):
            asyncio.run(_svc(db_session, test_user.id).parse("   "))

    def test_without_key_uses_local_parser(self, db_session, test_user):
        result = asyncio.run(_svc(db_session, test_user.id).parse("买牛奶"))
        assert result["source"] == "local"
        assert result["degraded"] is False  # 字段恒存在；无 Key 不算降级
        assert result["items"][0]["title"] == "买牛奶"
        assert result["clarifications"] == []

    def test_upstream_failure_degrades_with_flag(self, db_session, test_user, monkeypatch):
        svc = _svc(db_session, test_user.id)
        monkeypatch.setattr(svc, "_key", lambda: "sk-key")

        async def boom(*_args, **_kwargs):
            raise RuntimeError("network down")

        monkeypatch.setattr(svc, "_deepseek_parse", boom)
        result = asyncio.run(svc.parse("买牛奶"))
        assert result["source"] == "local"
        assert result["degraded"] is True

    def test_upstream_empty_items_degrades(self, db_session, test_user, monkeypatch):
        svc = _svc(db_session, test_user.id)
        monkeypatch.setattr(svc, "_key", lambda: "sk-key")

        async def empty(*_args, **_kwargs):
            return [], [], "deepseek"

        monkeypatch.setattr(svc, "_deepseek_parse", empty)
        result = asyncio.run(svc.parse("买牛奶"))
        assert result["source"] == "local"
        assert result["degraded"] is True

    def test_upstream_success_uses_deepseek_source(self, db_session, test_user, monkeypatch):
        svc = _svc(db_session, test_user.id)
        monkeypatch.setattr(svc, "_key", lambda: "sk-key")

        async def ok(*_args, **_kwargs):
            return [{"kind": "task", "title": "AI 拆出的任务"}], ["要问一句"], "deepseek"

        monkeypatch.setattr(svc, "_deepseek_parse", ok)
        result = asyncio.run(svc.parse("开会"))
        assert result["source"] == "deepseek"
        assert result["items"][0]["title"] == "AI 拆出的任务"
        assert result["clarifications"] == ["要问一句"]
        assert "degraded" not in result


# ================================================================
# 五、apply（白名单落库）
# ================================================================
class TestApply:
    def test_empty_or_too_many_items_rejected(self, db_session, test_user):
        svc = _svc(db_session, test_user.id)
        with pytest.raises(ValidationException):
            svc.apply([])
        with pytest.raises(ValidationException):
            svc.apply([{"title": "x"}] * 31)

    def test_task_reminder_note_are_written_to_expected_tables(self, db_session, test_user):
        svc = _svc(db_session, test_user.id)
        result = svc.apply([
            {"kind": "task", "title": "写周报", "priority": "high",
             "deadline": "2026-10-30T15:00:00", "notes": "补充数据"},
            {"kind": "reminder", "title": "开会提醒", "deadline": "2026-10-30T14:00:00"},
            {"kind": "note", "title": "灵感：做个小工具"},
        ])
        assert result["applied"] == 3
        assert result["by_kind"] == {"task": 1, "reminder": 1, "note": 1}
        assert len(result["task_ids"]) == 3
        tasks = list(db_session.scalars(select(Task).where(Task.user_id == test_user.id)))
        # task + reminder 都落 tasks 表；reminder 额外带 reminder_time
        assert len(tasks) == 2
        reminder = next(t for t in tasks if t.title == "开会提醒")
        assert reminder.reminder_time is not None
        notes = list(db_session.scalars(
            select(InboxItem).where(InboxItem.user_id == test_user.id)
        ))
        assert len(notes) == 1 and notes[0].source == "assistant"

    def test_empty_title_skipped_and_unknown_kind_treated_as_task(self, db_session, test_user):
        svc = _svc(db_session, test_user.id)
        result = svc.apply([
            {"kind": "task", "title": "   "},
            {"kind": "weird", "title": "未知类型条目"},
        ])
        assert result["applied"] == 1
        assert result["by_kind"]["task"] == 1

    def test_invalid_priority_falls_back_to_medium(self, db_session, test_user):
        svc = _svc(db_session, test_user.id)
        svc.apply([{"kind": "task", "title": "优先级非法", "priority": "urgent"}])
        task = db_session.scalars(
            select(Task).where(Task.user_id == test_user.id)
        ).one()
        assert task.priority == "medium"

    def test_invalid_deadline_string_does_not_break_apply(self, db_session, test_user):
        svc = _svc(db_session, test_user.id)
        result = svc.apply([{"kind": "task", "title": "坏时间", "deadline": "明天下午"}])
        assert result["applied"] == 1
        task = db_session.scalars(select(Task).where(Task.user_id == test_user.id)).one()
        assert task.due_date is None
