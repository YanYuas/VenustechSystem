# ============================================================
# Phase5 · core 基础设施单元测试（security / response / event_bus）
#
# 覆盖缺口（Phase5 基线）：
#   app/core/security.py 54.8% / response.py 100%（信封语义）/ event_bus.py 70.1%
#
# 全部为纯单元测试，不建会话、不落盘、不联网；event_bus 是类级全局状态，
# 每个用例通过 fresh_event_bus fixture 隔离并在结束后原样恢复。
# ============================================================
from __future__ import annotations

import asyncio
import base64
import copy
import json
import time
from collections import deque
from datetime import date, datetime
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from app.core import security
from app.core.event_bus import EventBus, event_bus
from app.core.response import _serialize, error, success
from app.core.security import decrypt_secret, encrypt_secret


# ================================================================
# 一、core/security.py —— API Key 加密/解密的三条后端与失败路径
# ================================================================
def _fake_fernet(prefix: str = "tok:"):
    class FakeEnc:
        is_available = True

        def encrypt(self, plaintext: str) -> bytes:
            return (prefix + plaintext).encode("utf-8")

        def decrypt(self, token) -> str:  # token 可能是 str（来自 ciphertext[7:]）
            raw = token.decode("utf-8") if isinstance(token, bytes) else token
            if not raw.startswith(prefix):
                raise ValueError("bad token")
            return raw[len(prefix):]

    return FakeEnc()


class TestSecretEncryption:
    def test_fernet_backend_takes_precedence_over_plain(self, monkeypatch):
        monkeypatch.setattr(security, "_DPAPI_AVAILABLE", False)
        monkeypatch.setattr("app.core.encryption.get_encryption", lambda: _fake_fernet())
        token = encrypt_secret("sk-abc")
        assert token == "fernet:tok:sk-abc"
        assert decrypt_secret(token) == "sk-abc"

    def test_dpapi_backend_encrypts_with_desc(self, monkeypatch):
        seen = {}

        def fake_protect(data: bytes, desc: str = "") -> bytes:
            seen["data"], seen["desc"] = data, desc
            return b"dpapi-blob"

        monkeypatch.setattr(security, "_DPAPI_AVAILABLE", True)
        monkeypatch.setattr(
            security, "win32crypt",
            SimpleNamespace(CryptProtectData=fake_protect),
            raising=False,
        )
        token = encrypt_secret("secret")
        assert token == "dpapi:" + base64.b64encode(b"dpapi-blob").decode("ascii")
        assert seen["data"] == b"secret"
        assert seen["desc"] == "Venustech API Key"

    def test_dpapi_wins_when_both_backends_available(self, monkeypatch):
        monkeypatch.setattr(
            security, "win32crypt",
            SimpleNamespace(CryptProtectData=lambda data, desc="": b"blob"),
            raising=False,
        )
        monkeypatch.setattr(security, "_DPAPI_AVAILABLE", True)
        monkeypatch.setattr("app.core.encryption.get_encryption", lambda: _fake_fernet())
        assert encrypt_secret("x").startswith("dpapi:")

    def test_dev_plain_fallback_roundtrip_unicode(self, monkeypatch):
        monkeypatch.setattr(security, "_DPAPI_AVAILABLE", False)
        monkeypatch.setattr("app.core.encryption.get_encryption", lambda: None)
        monkeypatch.setattr(
            "app.config.get_settings", lambda: SimpleNamespace(dev=True)
        )
        token = encrypt_secret("密钥中文")
        assert token.startswith("plain:")
        assert decrypt_secret(token) == "密钥中文"

    def test_no_backend_in_non_dev_refuses_plaintext(self, monkeypatch):
        monkeypatch.setattr(security, "_DPAPI_AVAILABLE", False)
        monkeypatch.setattr("app.core.encryption.get_encryption", lambda: None)
        monkeypatch.setattr(
            "app.config.get_settings", lambda: SimpleNamespace(dev=False)
        )
        with pytest.raises(RuntimeError) as exc:
            encrypt_secret("sk-should-not-be-stored")
        assert "拒绝以明文存储密钥" in str(exc.value)

    def test_decrypt_plain_legacy_value(self):
        token = "plain:" + base64.b64encode("legacy".encode("utf-8")).decode("ascii")
        assert decrypt_secret(token) == "legacy"

    def test_decrypt_fernet_without_backend_raises(self, monkeypatch):
        monkeypatch.setattr("app.core.encryption.get_encryption", lambda: None)
        with pytest.raises(ValueError) as exc:
            decrypt_secret("fernet:token")
        assert "Fernet" in str(exc.value)

    def test_decrypt_dpapi_without_backend_raises(self, monkeypatch):
        monkeypatch.setattr(security, "_DPAPI_AVAILABLE", False)
        with pytest.raises(ValueError) as exc:
            decrypt_secret("dpapi:" + base64.b64encode(b"blob").decode("ascii"))
        assert "格式不支持" in str(exc.value)

    def test_decrypt_unknown_prefix_raises(self):
        with pytest.raises(ValueError) as exc:
            decrypt_secret("gpg:whatever")
        assert "格式不支持" in str(exc.value)

    def test_decrypt_dpapi_uses_win32crypt(self, monkeypatch):
        seen = {}

        def fake_unprotect(blob: bytes):
            seen["blob"] = blob
            return None, b"decrypted-plain"

        monkeypatch.setattr(security, "_DPAPI_AVAILABLE", True)
        monkeypatch.setattr(
            security, "win32crypt",
            SimpleNamespace(CryptUnprotectData=fake_unprotect),
            raising=False,
        )
        token = "dpapi:" + base64.b64encode(b"the-blob").decode("ascii")
        assert decrypt_secret(token) == "decrypted-plain"
        assert seen["blob"] == b"the-blob"


# ================================================================
# 二、core/response.py —— 统一信封 + 递归序列化 + 时间单位
# ================================================================
class _Sample(BaseModel):
    name: str
    dt: datetime
    day: date


class TestResponseEnvelope:
    def test_success_envelope_shape(self):
        body = success({"a": 1})
        assert set(body) == {"code", "message", "data", "timestamp"}
        assert body["code"] == 0
        assert body["message"] == "success"
        assert body["data"] == {"a": 1}

    def test_success_timestamp_is_epoch_seconds(self):
        before = int(time.time())
        body = success(None)
        after = int(time.time())
        assert isinstance(body["timestamp"], int)
        assert before <= body["timestamp"] <= after + 1
        assert 1_000_000_000 < body["timestamp"] < 10_000_000_000  # 秒级，不是毫秒

    def test_success_custom_message_and_default_data(self):
        body = success(message="done")
        assert body["message"] == "done"
        assert body["data"] is None

    def test_error_envelope(self):
        body = error(404, "不存在")
        assert body["code"] == 404
        assert body["message"] == "不存在"
        assert body["data"] is None
        assert isinstance(body["timestamp"], int)

    def test_serialize_pydantic_model_to_json(self):
        model = _Sample(name="x", dt=datetime(2026, 1, 2, 3, 4, 5), day=date(2026, 1, 2))
        assert _serialize(model) == {
            "name": "x",
            "dt": "2026-01-02T03:04:05",
            "day": "2026-01-02",
        }

    def test_serialize_nested_containers(self):
        payload = {
            "list": [_Sample(name="a", dt=datetime(2026, 1, 1), day=date(2026, 1, 1))],
            "tuple": (1, 2),
            "nested": {"when": datetime(2026, 5, 6, 7, 8, 9)},
        }
        out = _serialize(payload)
        assert isinstance(out["list"], list)
        assert out["list"][0]["dt"] == "2026-01-01T00:00:00"
        assert out["tuple"] == [1, 2]
        assert out["nested"]["when"] == "2026-05-06T07:08:09"

    def test_success_output_is_json_serializable(self):
        body = success(_Sample(name="x", dt=datetime(2026, 1, 1), day=date(2026, 1, 1)))
        assert json.loads(json.dumps(body))["data"]["name"] == "x"

    def test_serialize_primitives_pass_through(self):
        for value in (1, "s", True, None, 1.5):
            assert _serialize(value) == value


# ================================================================
# 三、core/event_bus.py —— 订阅/发布/失败隔离/历史/统计
# ================================================================
@pytest.fixture()
def fresh_event_bus():
    saved = {
        "handlers": {k: list(v) for k, v in EventBus._handlers.items()},
        "async_handlers": {k: list(v) for k, v in EventBus._async_handlers.items()},
        "history": deque(EventBus._history, maxlen=EventBus._history.maxlen),
        "stats": copy.deepcopy(EventBus._stats),
        "window": {k: deque(v) for k, v in EventBus._window.items()},
    }
    EventBus._handlers.clear()
    EventBus._async_handlers.clear()
    EventBus._history.clear()
    EventBus._stats.clear()
    EventBus._window.clear()
    yield event_bus
    EventBus._handlers.clear()
    EventBus._handlers.update(saved["handlers"])
    EventBus._async_handlers.clear()
    EventBus._async_handlers.update(saved["async_handlers"])
    EventBus._history.clear()
    EventBus._history.extend(saved["history"])
    EventBus._stats.clear()
    EventBus._stats.update(saved["stats"])
    EventBus._window.clear()
    EventBus._window.update(saved["window"])


class TestEventBus:
    def test_subscribe_and_publish_calls_handler_with_kwargs(self, fresh_event_bus):
        seen = {}

        def handler(**kwargs):
            seen.update(kwargs)

        fresh_event_bus.subscribe("phase5.test", handler)
        fresh_event_bus.publish("phase5.test", task_id="t1", n=2)

        assert seen == {"task_id": "t1", "n": 2}
        record = fresh_event_bus.get_history("phase5.test")[-1]
        assert record["handlers"] == 1
        assert record["success"] is True
        assert record["failed_handlers"] == []

    def test_handler_exception_is_isolated_and_recorded(self, fresh_event_bus):
        def boom(**_kwargs):
            raise RuntimeError("handler exploded")

        def ok(**_kwargs):
            return None

        fresh_event_bus.subscribe("phase5.fail", boom)
        fresh_event_bus.subscribe("phase5.fail", ok)
        fresh_event_bus.publish("phase5.fail")  # 不得向上冒泡

        record = fresh_event_bus.get_history("phase5.fail")[-1]
        assert record["success"] is False
        assert record["failed_handlers"] == ["boom"]
        stats = fresh_event_bus.get_stats()["by_event"]["phase5.fail"]
        assert stats["count"] == 1 and stats["failed"] == 1
        assert stats["consecutive_failures"] == 1
        assert stats["alert"] is True  # 失败率 100% 超过阈值

    def test_consecutive_failures_are_counted(self, fresh_event_bus):
        def boom(**_kwargs):
            raise ValueError("x")

        fresh_event_bus.subscribe("phase5.consecutive", boom)
        for _ in range(5):
            fresh_event_bus.publish("phase5.consecutive")
        stats = fresh_event_bus.get_stats()["by_event"]["phase5.consecutive"]
        assert stats["consecutive_failures"] == 5
        assert stats["alert"] is True

    def test_success_resets_consecutive_failure_counter(self, fresh_event_bus):
        state = {"fail": True}

        def maybe(**_kwargs):
            if state["fail"]:
                raise RuntimeError("x")

        fresh_event_bus.subscribe("phase5.reset", maybe)
        fresh_event_bus.publish("phase5.reset")
        state["fail"] = False
        fresh_event_bus.publish("phase5.reset")
        stats = fresh_event_bus.get_stats()["by_event"]["phase5.reset"]
        assert stats["consecutive_failures"] == 0
        assert stats["count"] == 2 and stats["success"] == 1

    def test_window_failure_rate_half(self, fresh_event_bus):
        state = {"ok": True}

        def maybe(**_kwargs):
            if not state["ok"]:
                raise RuntimeError("x")

        fresh_event_bus.subscribe("phase5.rate", maybe)
        fresh_event_bus.publish("phase5.rate")
        state["ok"] = False
        fresh_event_bus.publish("phase5.rate")
        stats = fresh_event_bus.get_stats()["by_event"]["phase5.rate"]
        assert stats["failure_rate_1m"] == pytest.approx(0.5, abs=0.001)

    def test_history_filter_and_limit(self, fresh_event_bus):
        for i in range(3):
            fresh_event_bus.publish("phase5.a", i=i)
        for i in range(2):
            fresh_event_bus.publish("phase5.b", i=i)
        assert len(fresh_event_bus.get_history("phase5.a")) == 3
        assert len(fresh_event_bus.get_history("phase5.b")) == 2
        assert len(fresh_event_bus.get_history(limit=2)) == 2
        assert fresh_event_bus.get_history()[-1]["event"] in ("phase5.a", "phase5.b")

    def test_clear_history(self, fresh_event_bus):
        fresh_event_bus.publish("phase5.clear")
        assert fresh_event_bus.get_history("phase5.clear")
        fresh_event_bus.clear_history()
        assert fresh_event_bus.get_history("phase5.clear") == []

    def test_unknown_event_still_counted(self, fresh_event_bus):
        fresh_event_bus.publish("phase5.never-subscribed")
        stats = fresh_event_bus.get_stats()
        assert stats["by_event"]["phase5.never-subscribed"]["count"] == 1
        assert stats["total_events"] >= 1

    def test_async_handler_runs_in_running_loop(self, fresh_event_bus):
        seen: list[str] = []

        async def async_handler(**kwargs):
            seen.append(kwargs["payload"])

        fresh_event_bus.subscribe_async("phase5.async", async_handler)

        async def scenario():
            fresh_event_bus.publish("phase5.async", payload="hello")
            await asyncio.sleep(0.01)

        asyncio.run(scenario())
        assert seen == ["hello"]
        assert fresh_event_bus.get_history("phase5.async")[-1]["success"] is True

    def test_subscriptions_list_handler_names(self, fresh_event_bus):
        def named_handler(**_kwargs):
            return None

        fresh_event_bus.subscribe("phase5.names", named_handler)
        names = fresh_event_bus.get_subscriptions()["sync"]["phase5.names"]
        assert names and names[0].endswith("named_handler")
