# ============================================================
# Phase6 · AI HOT 插件测试（app/plugins_builtin/aihot/main.py，基线 28.1%）
#
# 重点：缓存两级降级（内存 → 磁盘）、上游异常不 500、参数白名单、
# daily 的 404 有界回退。所有 HTTP 用替身，不联网。
# ============================================================
from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.config import get_settings
from app.plugins_builtin.aihot import main as aihot


@pytest.fixture()
def plugin_ctx():
    """隔离模块级 _ctx/_cache（插件是模块单例，不能串味）。"""
    saved_ctx = aihot._ctx
    saved_cache = dict(aihot._cache)
    aihot._cache.clear()
    cache_dir = Path(get_settings().data_dir) / "plugins" / "aihot"
    shutil.rmtree(cache_dir, ignore_errors=True)
    ctx = SimpleNamespace(data_dir=Path(get_settings().data_dir), plugin_id="aihot")
    aihot.initialize(ctx)
    yield ctx
    aihot._ctx = saved_ctx
    aihot._cache.clear()
    aihot._cache.update(saved_cache)
    shutil.rmtree(Path(get_settings().data_dir) / "plugins" / "aihot", ignore_errors=True)


class _Resp:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx

            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}",
                request=httpx.Request("GET", "https://x"),
                response=httpx.Response(self.status_code),
            )

    def json(self):
        return self._payload


class _FakeClient:
    script: list = []
    calls: list = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url, **kwargs):
        _FakeClient.calls.append({"url": url, **kwargs})
        item = _FakeClient.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture()
def fake_http(monkeypatch):
    _FakeClient.script = []
    _FakeClient.calls = []
    monkeypatch.setattr("app.plugins_builtin.aihot.main.httpx.AsyncClient", _FakeClient)
    return _FakeClient


# ================================================================
# 一、缓存层（_cache_file/_save_cache/_load_cache）
# ================================================================
class TestCacheLayer:
    def test_cache_file_none_without_context(self):
        aihot._ctx = None
        assert aihot._cache_file("x") is None

    def test_cache_save_and_load_roundtrip(self, plugin_ctx):
        aihot._save_cache("items", {"hello": "world"})
        assert aihot._load_cache("items") == {"hello": "world"}
        path = plugin_ctx.data_dir / "plugins" / "aihot" / "items.json"
        assert path.is_file()

    def test_load_cache_missing_file_returns_none(self, plugin_ctx):
        assert aihot._load_cache("never-written") is None

    def test_load_cache_corrupted_json_returns_none(self, plugin_ctx):
        path = plugin_ctx.data_dir / "plugins" / "aihot" / "broken.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{not json", encoding="utf-8")
        assert aihot._load_cache("broken") is None

    def test_cache_file_oserror_returns_none(self, plugin_ctx):
        """data_dir 指向普通文件 → mkdir 抛 OSError → 返回 None（不冒泡）。"""
        blocker = Path(get_settings().data_dir) / "aihot-blocker-file"
        blocker.write_text("x", encoding="utf-8")
        plugin_ctx.data_dir = blocker
        assert aihot._cache_file("items") is None

    def test_save_cache_oserror_is_swallowed(self, plugin_ctx, monkeypatch):
        target = Path(get_settings().data_dir) / "no-such-dir" / "items.json"
        monkeypatch.setattr(aihot, "_cache_file", lambda name: target)
        # 写失败只 pass，不抛 —— 但「吞掉异常」不等于成功：必须没留下任何文件
        aihot._save_cache("items", {"a": 1})
        assert target.parent.exists() is False
        assert target.exists() is False

    def test_save_cache_without_context_is_noop(self, monkeypatch):
        aihot._ctx = None
        written: list[str] = []
        monkeypatch.setattr(Path, "write_text", lambda self, *a, **k: written.append(str(self)))
        aihot._save_cache("x", {"a": 1})
        # 无 context 时必须"什么都不做"：不落盘（不是"只要不抛异常"就算通过）
        assert written == []
        assert aihot._cache_file("x") is None


# ================================================================
# 二、_fetch：live → cache（内存/磁盘）→ 诚实报错
# ================================================================
class TestFetchFallback:
    def test_live_success_caches_memory_and_disk(self, plugin_ctx, fake_http):
        fake_http.script.append(_Resp(200, {"items": [1, 2]}))
        result = asyncio.run(aihot._fetch("items", "/items", {"window": "24h"}))
        # D-24：_fetch 返回**裸结果**，信封只由端点在唯一一层包
        assert result["ok"] is True
        assert result["source"] == "live"
        assert result["data"] == {"items": [1, 2]}
        assert aihot._cache["items"] == {"items": [1, 2]}
        assert (plugin_ctx.data_dir / "plugins" / "aihot" / "items.json").is_file()

    def test_live_failure_uses_memory_cache(self, plugin_ctx, fake_http):
        aihot._cache["items"] = {"cached": True}
        fake_http.script.append(RuntimeError("network down"))
        result = asyncio.run(aihot._fetch("items", "/items", {}))
        assert result["ok"] is True
        assert result["source"] == "cache"
        assert result["degraded"] is True
        assert result["data"] == {"cached": True}

    def test_live_failure_uses_disk_cache(self, plugin_ctx, fake_http):
        aihot._save_cache("items", {"disk": True})
        aihot._cache.clear()
        fake_http.script.append(RuntimeError("down"))
        result = asyncio.run(aihot._fetch("items", "/items", {}))
        assert result["data"] == {"disk": True}
        assert result["degraded"] is True

    def test_live_failure_without_cache_reports_honest_error(self, plugin_ctx, fake_http):
        fake_http.script.append(RuntimeError("upstream down"))
        result = asyncio.run(aihot._fetch("items", "/items", {}))
        assert result["ok"] is False
        assert "AI HOT 暂不可达" in result["error"]
        assert len(result["error"]) <= 200

    def test_http_status_error_is_caught(self, plugin_ctx, fake_http):
        fake_http.script.append(_Resp(503, {}))
        result = asyncio.run(aihot._fetch("items", "/items", {}))
        assert result["ok"] is False


# ================================================================
# 三、items：参数白名单与校验
# ================================================================
class TestItemsEndpoint:
    def test_invalid_window_rejected_before_http(self, plugin_ctx, fake_http):
        result = asyncio.run(aihot.items(window="30d"))
        assert result["code"] == 0
        assert result["data"]["ok"] is False
        assert "window" in result["data"]["error"]
        assert fake_http.calls == []

    def test_invalid_mode_rejected(self, plugin_ctx, fake_http):
        result = asyncio.run(aihot.items(window="24h", mode="latest"))
        assert result["data"]["ok"] is False
        assert "mode" in result["data"]["error"]

    def test_unsafe_category_rejected(self, plugin_ctx, fake_http):
        result = asyncio.run(
            aihot.items(window="24h", mode="selected", limit=10, category="../../etc/passwd")
        )
        assert result["data"]["ok"] is False
        assert "category" in result["data"]["error"]

    def test_valid_request_passes_whitelisted_params(self, plugin_ctx, fake_http):
        fake_http.script.append(_Resp(200, {"data": []}))
        asyncio.run(aihot.items(window="7d", mode="all", limit=3, category="ai-ml", q="  agent  "))
        call = fake_http.calls[0]
        assert call["url"] == "https://aihot.virxact.com/api/v1/items"
        assert call["params"] == {
            "window": "7d", "mode": "all", "limit": 3, "by": "timeline",
            "category": "ai-ml", "q": "agent",
        }

    def test_fetch_result_single_envelope(self, plugin_ctx, monkeypatch):
        """D-24：_fetch 返回裸结果，items 端点只包一层 success（无双重信封）。"""
        async def fake_fetch(name, path, params):
            return {"ok": True, "source": "live", "data": {"items": []}}

        monkeypatch.setattr(aihot, "_fetch", fake_fetch)
        result = asyncio.run(
            aihot.items(window="24h", mode="selected", limit=10, category=None, q=None)
        )
        assert result["code"] == 0
        assert result["data"] == {"ok": True, "source": "live", "data": {"items": []}}
        assert "code" not in result["data"], "不得出现内层信封"
        assert "timestamp" not in result["data"]


# ================================================================
# 四、hot_topics / daily（含 404 有界回退）
# ================================================================
class TestHotTopicsAndDaily:
    def test_hot_topics_live(self, plugin_ctx, fake_http):
        fake_http.script.append(_Resp(200, {"hot": True}))
        result = asyncio.run(aihot.hot_topics())
        assert result["code"] == 0
        assert result["data"]["ok"] is True
        assert result["data"]["data"] == {"hot": True}  # 单信封：data = 裸结果
        assert fake_http.calls[0]["url"].endswith("/hot-topics")

    def test_daily_live_ok(self, plugin_ctx, fake_http):
        fake_http.script.append(_Resp(200, {"date": "2026-10-28"}))
        result = asyncio.run(aihot.daily())
        assert result["code"] == 0
        assert result["data"]["ok"] is True
        assert result["data"]["source"] == "live"
        assert result["data"]["data"] == {"date": "2026-10-28"}
        assert fake_http.calls[0]["url"].endswith("/dailies/latest")

    def test_daily_fallback_when_latest_fails(self, plugin_ctx, fake_http):
        """D-24 运行期可达性：latest 404 → /dailies 索引 → 真实日期再取。

        全程走真实 _fetch 路径（只替身 HTTP），断言 source=live/fallback-* 分支
        不再是死代码。
        """
        fake_http.script.extend([
            _Resp(404, {}),
            _Resp(200, {"dailies": [{"date": "2026-10-28"}]}),
            _Resp(200, {"date": "2026-10-28", "items": [{"title": "日报"}]}),
        ])
        result = asyncio.run(aihot.daily())
        assert result["code"] == 0
        assert result["data"]["ok"] is True
        assert result["data"]["source"] == "live/fallback-2026-10-28"
        assert result["data"]["data"]["items"] == [{"title": "日报"}]
        urls = [c["url"] for c in fake_http.calls]
        assert urls[0].endswith("/dailies/latest")
        assert urls[1].endswith("/dailies")
        assert urls[2].endswith("/dailies/2026-10-28")

    def test_daily_fallback_empty_index(self, plugin_ctx, fake_http):
        fake_http.script.extend([_Resp(404, {}), _Resp(200, {"dailies": []})])
        result = asyncio.run(aihot.daily())
        assert result["data"]["ok"] is False
        assert "暂无日报" in result["data"]["error"]

    def test_daily_fallback_index_without_date(self, plugin_ctx, fake_http):
        fake_http.script.extend([
            _Resp(404, {}),
            _Resp(200, {"items": [{"title": "no-date"}]}),
        ])
        result = asyncio.run(aihot.daily())
        assert result["data"]["ok"] is False
        assert "索引异常" in result["data"]["error"]

    def test_daily_fallback_uses_cache_on_exception(self, plugin_ctx, monkeypatch, fake_http):
        async def fake_fetch(name, path, params):
            return {"ok": False, "error": "404"}

        monkeypatch.setattr(aihot, "_fetch", fake_fetch)
        aihot._cache["daily"] = {"cached": "daily"}
        fake_http.script.append(RuntimeError("index down"))
        result = asyncio.run(aihot.daily())
        assert result["data"]["source"] == "cache"
        assert result["data"]["data"] == {"cached": "daily"}

    def test_daily_fallback_no_cache_returns_error(self, plugin_ctx, fake_http):
        """latest 404 + 索引异常 + 无缓存 → 诚实错误（覆盖 daily 最终兜底）。"""
        fake_http.script.extend([_Resp(404, {}), RuntimeError("index down")])
        result = asyncio.run(aihot.daily())
        assert result["data"]["ok"] is False
        assert "AI HOT 暂不可达" in result["data"]["error"]

    def test_initialize_and_get_router(self, plugin_ctx):
        assert aihot.get_router() is aihot.router
        assert aihot._ctx is plugin_ctx
