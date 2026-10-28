# ============================================================
# Phase5 · API 错误路径与边界测试（覆盖率缺口批次）
#
# 覆盖缺口模块（Phase5 基线 term-missing）：
#   app/api/logs.py 29.6% / api/sync.py 48.4% / api/rules.py 38.9%
#   app/api/auth.py 47.6% / api/plugins.py 60.0% / api/events.py 68.0%
#
# 约定：
#   - 只走 TestClient + conftest fixtures（client / default_user_id / clean_db）；
#   - 所有落盘都写在 VENUSTECH_TEST_DATA_DIR（测试数据目录），不碰真实 var/data；
#   - 每条测试只验证一个行为，断言错误码/状态码/具体字段，不做 assert True。
# ============================================================
from __future__ import annotations

import json
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.config import get_settings
from app.core.event_bus import ALL_EVENTS


# ---------------------------------------------------------------- helpers
def _data_dir() -> Path:
    return Path(get_settings().data_dir)


def _logs_dir() -> Path:
    d = _data_dir() / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_log(name: str, lines: list[str]) -> Path:
    path = _logs_dir() / name
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _ok(resp) -> dict:
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["code"] == 0, body
    assert isinstance(body["timestamp"], int)
    return body["data"]


def _api_error(resp) -> dict:
    """业务异常信封：走全局 AppException handler（HTTP 4xx/5xx + 统一信封）。"""
    body = resp.json()
    assert resp.status_code >= 400, resp.text
    assert body["code"] != 0
    return body


# ================================================================
# 一、logs API（app/api/logs.py）
# ================================================================
class TestLogsApi:
    def test_list_logs_returns_envelope_and_log_dir(self, client):
        data = _ok(client.get("/api/v1/logs"))
        assert set(["files", "dir"]) <= set(data)
        assert data["dir"] == str(_data_dir() / "logs")
        assert isinstance(data["files"], list)

    def test_read_log_tail_returns_last_n_lines(self, client):
        name = f"phase5-{uuid.uuid4().hex[:8]}.log"
        _write_log(name, [f"line-{i}" for i in range(10)])
        try:
            data = _ok(client.get(f"/api/v1/logs/{name}", params={"tail": 3}))
            assert data["filename"] == name
            assert data["total_lines"] == 3
            assert data["content"].splitlines() == ["line-7", "line-8", "line-9"]
        finally:
            (_logs_dir() / name).unlink(missing_ok=True)

    def test_read_log_level_filter_is_case_insensitive(self, client):
        name = f"phase5-{uuid.uuid4().hex[:8]}.log"
        _write_log(name, ["INFO ok", "ERROR boom", "error again", "WARNING hmm"])
        try:
            data = _ok(client.get(f"/api/v1/logs/{name}", params={"level": "error"}))
            assert data["total_lines"] == 2
            assert "INFO" not in data["content"]
            assert "boom" in data["content"] and "again" in data["content"]
        finally:
            (_logs_dir() / name).unlink(missing_ok=True)

    def test_read_log_missing_file_returns_404_code(self, client):
        body = client.get("/api/v1/logs/definitely-missing-phase5.log").json()
        assert body["code"] == 404
        assert "不存在" in body["message"]

    def test_read_log_path_traversal_rejected(self, client):
        body = client.get("/api/v1/logs/..%5C..%5Cevil.log").json()
        assert body["code"] == 400
        assert "非法文件名" in body["message"]

    def test_read_log_tail_out_of_range_returns_validation_400(self, client):
        resp = client.get("/api/v1/logs/whatever.log", params={"tail": 0})
        assert resp.status_code == 400
        body = resp.json()
        assert body["code"] == 1001
        assert body["message"].startswith("参数错误:")

    def test_clear_logs_empties_existing_log_files(self, client):
        a = _write_log(f"phase5-a-{uuid.uuid4().hex[:6]}.log", ["a"])
        b = _write_log(f"phase5-b-{uuid.uuid4().hex[:6]}.log", ["b"])
        try:
            data = _ok(client.post("/api/v1/logs/clear"))
            assert data["cleared"] >= 2
            assert data["failed"] == []
            assert a.read_text(encoding="utf-8") == ""
            assert b.read_text(encoding="utf-8") == ""
        finally:
            a.unlink(missing_ok=True)
            b.unlink(missing_ok=True)

    def test_clear_logs_when_dir_missing_returns_zero(self, client, monkeypatch):
        missing = _data_dir() / f"no-logs-{uuid.uuid4().hex[:6]}"
        monkeypatch.setattr("app.api.logs.settings", SimpleNamespace(data_dir=missing))
        data = _ok(client.post("/api/v1/logs/clear"))
        assert data == {"cleared": 0, "failed": []}

    def test_list_logs_when_dir_missing_returns_empty_list(self, client, monkeypatch):
        missing = _data_dir() / f"no-logs-{uuid.uuid4().hex[:6]}"
        monkeypatch.setattr("app.api.logs.settings", SimpleNamespace(data_dir=missing))
        data = _ok(client.get("/api/v1/logs"))
        assert data["files"] == []
        assert data["dir"] == str(missing / "logs")


# ================================================================
# 二、sync API（app/api/sync.py）
# ================================================================
class TestSyncApi:
    def test_packages_points_at_exports_dir(self, client):
        data = _ok(client.get("/api/v1/sync/packages"))
        assert data["dir"] == str(_data_dir() / "exports")
        assert isinstance(data["items"], list)

    def test_export_missing_directory_returns_400(self, client):
        target = _data_dir() / f"no-such-{uuid.uuid4().hex[:6]}"
        resp = client.post("/api/v1/sync/export", json={"dir": str(target)})
        body = _api_error(resp)
        assert resp.status_code == 400
        assert body["code"] == 1001
        assert "目录不存在" in body["message"]

    def test_export_default_dir_creates_package_and_lists_it(self, client):
        data = _ok(client.post("/api/v1/sync/export", json={}))
        path = Path(data["path"])
        try:
            assert path.is_file()
            assert path.parent == _data_dir() / "exports"
            assert isinstance(data["row_count"], int)
            listed = _ok(client.get("/api/v1/sync/packages"))
            assert path.name in [item["name"] for item in listed["items"]]
        finally:
            path.unlink(missing_ok=True)

    def test_preview_missing_file_returns_400(self, client):
        resp = client.post(
            "/api/v1/sync/preview",
            json={"path": str(_data_dir() / "definitely-missing.json")},
        )
        body = _api_error(resp)
        assert resp.status_code == 400
        assert "文件不存在" in body["message"]

    def test_preview_package_of_other_user_rejected(self, client, default_user_id):
        pkg = _data_dir() / f"ctx-{uuid.uuid4().hex[:6]}.json"
        pkg.write_text(
            json.dumps({"user_id": "someone-else", "tables": {}}), encoding="utf-8"
        )
        try:
            resp = client.post("/api/v1/sync/preview", json={"path": str(pkg)})
            body = _api_error(resp)
            assert resp.status_code == 400
            assert "其他用户" in body["message"]
            assert default_user_id  # 触发默认用户，保证走的是真实认证
        finally:
            pkg.unlink(missing_ok=True)

    def test_preview_valid_exported_package_returns_summary(self, client):
        exported = _ok(client.post("/api/v1/sync/export", json={}))
        path = Path(exported["path"])
        try:
            data = _ok(
                client.post("/api/v1/sync/preview", json={"path": str(path)})
            )
            assert set(["total", "by_op", "by_table", "samples"]) <= set(data)
            assert data["propagate_deletes"] is False
        finally:
            path.unlink(missing_ok=True)

    def test_import_missing_file_returns_400(self, client):
        resp = client.post(
            "/api/v1/sync/import",
            json={"path": str(_data_dir() / "definitely-missing.json")},
        )
        body = _api_error(resp)
        assert resp.status_code == 400
        assert "同步包不存在" in body["message"]

    def test_import_wrong_package_version_returns_400(self, client, default_user_id):
        pkg = _data_dir() / f"badver-{uuid.uuid4().hex[:6]}.json"
        pkg.write_text(
            json.dumps({"version": 999, "user_id": default_user_id, "tables": {}}),
            encoding="utf-8",
        )
        try:
            resp = client.post("/api/v1/sync/import", json={"path": str(pkg)})
            body = _api_error(resp)
            assert resp.status_code == 400
            assert "版本不兼容" in body["message"]
        finally:
            pkg.unlink(missing_ok=True)

    def test_import_package_of_other_user_rejected(self, client):
        pkg = _data_dir() / f"other-{uuid.uuid4().hex[:6]}.json"
        pkg.write_text(
            json.dumps({"version": 1, "user_id": "someone-else", "tables": {}}),
            encoding="utf-8",
        )
        try:
            resp = client.post("/api/v1/sync/import", json={"path": str(pkg)})
            body = _api_error(resp)
            assert resp.status_code == 400
            assert "其他用户" in body["message"]
        finally:
            pkg.unlink(missing_ok=True)

    def test_import_own_package_returns_stats(self, client):
        exported = _ok(client.post("/api/v1/sync/export", json={}))
        path = Path(exported["path"])
        try:
            data = _ok(client.post("/api/v1/sync/import", json={"path": str(path)}))
            assert set(["ops", "insert", "update", "delete", "skipped"]) <= set(data)
        finally:
            path.unlink(missing_ok=True)


# ================================================================
# 三、rules API（app/api/rules.py）
# ================================================================
class TestRulesApi:
    def test_domains_lists_builtin_and_user_sources(self, client):
        data = _ok(client.get("/api/v1/rules/domains"))
        assert data["builtin_count"] >= 13
        assert isinstance(data["user_count"], int)
        assert len(data["domains"]) == data["builtin_count"] + data["user_count"]
        for item in data["domains"]:
            assert item["source"] in ("builtin", "user")
            assert set(["key", "name", "patterns", "units"]) <= set(item)

    def test_preview_empty_text_is_not_matched(self, client):
        data = _ok(client.post("/api/v1/rules/preview", json={"text": "   "}))
        assert data["matched"] is False
        assert data["reason"] == "empty input"
        assert data["plans"] == []

    def test_preview_missing_text_returns_400(self, client):
        resp = client.post("/api/v1/rules/preview", json={})
        body = _api_error(resp)
        assert resp.status_code == 400
        assert body["code"] == 1001

    def test_preview_over_max_length_returns_400(self, client):
        resp = client.post("/api/v1/rules/preview", json={"text": "x" * 501})
        body = _api_error(resp)
        assert resp.status_code == 400
        assert body["code"] == 1001

    def test_preview_generic_text_returns_fallback_plan(self, client):
        data = _ok(client.post("/api/v1/rules/preview", json={"text": "随便学点新东西"}))
        assert data["plan_count"] >= 1
        assert len(data["plans"]) <= 5
        assert data["fallback"] is (not data["matched"])
        for plan in data["plans"]:
            assert set(["unit", "task", "duration", "acceptance"]) == set(plan)

    def test_reload_returns_dict_summary(self, client):
        data = _ok(client.post("/api/v1/rules/reload"))
        assert isinstance(data, dict)

    def test_post_domains_is_method_not_allowed(self, client):
        assert client.post("/api/v1/rules/domains").status_code == 405


# ================================================================
# 四、auth API（app/api/auth.py）
# ================================================================
class TestAuthApi:
    def test_me_returns_expected_config_fields(self, client):
        data = _ok(client.get("/api/v1/auth/me"))
        assert isinstance(data["nickname"], str)
        assert isinstance(data["api_key_configured"], bool)
        assert set(["x", "y"]) == set(data["pet_position"])
        assert data["pet_position"]["x"] == 1770
        assert data["automation_level"] in ("L1", "L2", "L3")

    def test_patch_me_updates_nickname(self, client):
        data = _ok(client.patch("/api/v1/auth/me", json={"nickname": "新昵称"}))
        assert data["nickname"] == "新昵称"
        # 还原，避免影响其他测试对默认昵称的假设
        _ok(client.patch("/api/v1/auth/me", json={"nickname": "启明星用户"}))

    def test_patch_me_explicit_null_keeps_value(self, client):
        """auth 的更新实现是 `if value is not None`（null 跳过），与 ADR-0008 的服务层语义不同。"""
        before = _ok(client.get("/api/v1/auth/me"))["nickname"]
        after = _ok(client.patch("/api/v1/auth/me", json={"nickname": None}))
        assert after["nickname"] == before

    def test_patch_me_empty_body_is_noop(self, client):
        before = _ok(client.get("/api/v1/auth/me"))
        after = _ok(client.patch("/api/v1/auth/me", json={}))
        assert after["nickname"] == before["nickname"]
        assert after["theme"] == before["theme"]

    def test_patch_me_invalid_probability_returns_400(self, client):
        resp = client.patch("/api/v1/auth/me", json={"inspiration_probability": 101})
        body = _api_error(resp)
        assert resp.status_code == 400
        assert body["code"] == 1001

    @pytest.mark.xfail(
        reason="BUG(Phase5 记录): auth.py:78-80 对 model_dump() 后的 dict 取 pet.x → AttributeError(500)",
        strict=True,
    )
    def test_patch_me_pet_position_roundtrip(self, client):
        data = _ok(client.patch("/api/v1/auth/me", json={"pet_position": {"x": 12, "y": 34}}))
        assert data["pet_position"] == {"x": 12, "y": 34}

    def test_init_empty_nickname_returns_400(self, client):
        resp = client.post("/api/v1/auth/init", json={"nickname": ""})
        body = _api_error(resp)
        assert resp.status_code == 400
        assert body["code"] == 1001

    def test_verify_api_delegates_to_ai_service(self, client, monkeypatch):
        """端点接线：不真的打外网，用 Fake AIService 验证入参与返回。"""
        seen: dict = {}

        class FakeAI:
            def __init__(self, db, user):
                self.user = user

            async def verify_api(self, api_key: str):
                seen["api_key"] = api_key
                return {"valid": True, "model": "fake-model", "reason": ""}

        monkeypatch.setattr("app.api.auth.AIService", FakeAI)
        data = _ok(client.post("/api/v1/auth/verify-api", json={"api_key": " sk-test "}))
        assert data["valid"] is True
        assert data["model"] == "fake-model"
        assert seen["api_key"] == "sk-test"  # 端点会 strip 首尾空白


# ================================================================
# 五、plugins + events API（app/api/plugins.py · app/api/events.py）
# ================================================================
class TestPluginsApi:
    def test_list_plugins_returns_status_shape(self, client):
        data = _ok(client.get("/api/v1/plugins"))
        assert set(["total", "enabled", "loaded", "plugins"]) == set(data)
        assert isinstance(data["plugins"], list)
        assert data["enabled"] <= data["total"]

    def test_enable_unknown_plugin_returns_false(self, client):
        data = _ok(client.post("/api/v1/plugins/no-such-plugin-xyz/enable"))
        assert data["enabled"] is False
        assert data["plugin_id"] == "no-such-plugin-xyz"

    def test_disable_unknown_plugin_returns_false(self, client):
        data = _ok(client.post("/api/v1/plugins/no-such-plugin-xyz/disable"))
        assert data["disabled"] is False

    def test_reload_unknown_plugin_returns_false(self, client):
        data = _ok(client.post("/api/v1/plugins/no-such-plugin-xyz/reload"))
        assert data["reloaded"] is False

    def test_discover_returns_count(self, client):
        data = _ok(client.post("/api/v1/plugins/discover"))
        assert isinstance(data["discovered"], int)
        assert isinstance(data["plugins"], list)


class TestEventsApi:
    def test_event_types_are_complete_and_unique(self, client):
        data = _ok(client.get("/api/v1/events/types"))
        assert data["events"] == ALL_EVENTS
        assert data["count"] == len(ALL_EVENTS)
        assert len(set(ALL_EVENTS)) == len(ALL_EVENTS)

    def test_publish_then_history_then_clear(self, client):
        event = f"phase5.demo.{uuid.uuid4().hex[:6]}"
        _ok(client.post(f"/api/v1/events/test/{event}"))
        history = _ok(client.get("/api/v1/events/history", params={"event": event, "limit": 5}))
        assert any(rec["event"] == event for rec in history)
        assert all(rec["success"] is True for rec in history)

        _ok(client.post("/api/v1/events/clear-history"))
        assert _ok(client.get("/api/v1/events/history", params={"event": event})) == []

    def test_history_limit_validation(self, client):
        resp = client.get("/api/v1/events/history", params={"limit": 0})
        body = _api_error(resp)
        assert resp.status_code == 400
        assert body["code"] == 1001

    def test_subscriptions_expose_sync_and_async_maps(self, client):
        data = _ok(client.get("/api/v1/events/subscriptions"))
        assert set(data) == {"sync", "async"}
        assert isinstance(data["sync"], dict)
        assert isinstance(data["async"], dict)

    def test_stats_contains_thresholds_and_totals(self, client):
        data = _ok(client.get("/api/v1/events/stats"))
        assert set(["total_events", "by_event", "active_subscriptions",
                    "async_subscriptions", "thresholds"]) == set(data)
        assert data["thresholds"]["consecutive_fail_alert"] >= 1
