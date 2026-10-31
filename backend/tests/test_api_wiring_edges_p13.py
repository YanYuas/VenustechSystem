# ============================================================
# Phase13 · A 类覆盖率补缺：API 装配层（deps 缓存/并发兜底 + assistant 路由）
#
# 覆盖：
#   · api/deps.get_current_user：request.state 命中缓存直接返回（不查库）；
#   · 并发创建 default_user 撞 IntegrityError → rollback 后重查；重查仍无则原样抛；
#   · api/assistant 四个路由的状态/配置/解析/落库装配（service 用替身，不联网）。
# ============================================================
from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy.exc import IntegrityError

from app.api import deps
from app.api.deps import get_current_user


class TestCurrentUserFallbacks:
    def test_cached_user_is_returned_without_db_access(
        self, db_session, test_user, monkeypatch
    ):
        def _no_repo(_db):
            raise AssertionError("缓存命中时不应创建 UserRepository")

        monkeypatch.setattr(deps, "UserRepository", _no_repo)
        request = SimpleNamespace(state=SimpleNamespace(current_user=test_user))

        assert get_current_user(request, db_session) is test_user

    def test_integrity_error_falls_back_to_existing_user(
        self, db_session, test_user, monkeypatch
    ):
        class _RacingRepo:
            def __init__(self, _db):
                self.calls = 0

            def get_by_username(self, _username):
                self.calls += 1
                return None if self.calls == 1 else test_user

            def create(self, **_kwargs):
                raise IntegrityError("INSERT INTO users", {}, Exception("unique"))

        monkeypatch.setattr(deps, "UserRepository", _RacingRepo)
        request = SimpleNamespace(state=SimpleNamespace())

        assert get_current_user(request, db_session) is test_user
        assert request.state.current_user is test_user

    def test_integrity_error_reraises_when_user_still_missing(
        self, db_session, monkeypatch
    ):
        class _AlwaysMissingRepo:
            def __init__(self, _db):
                pass

            def get_by_username(self, _username):
                return None

            def create(self, **_kwargs):
                raise IntegrityError("INSERT INTO users", {}, Exception("unique"))

        monkeypatch.setattr(deps, "UserRepository", _AlwaysMissingRepo)
        request = SimpleNamespace(state=SimpleNamespace())

        with pytest.raises(IntegrityError):
            get_current_user(request, db_session)


class _FakeAssistantService:
    def status(self):
        return {"configured": True, "model": "deepseek-chat"}

    def configure(self, api_key):
        return {"configured": bool(api_key), "key_len": len(api_key)}

    async def parse(self, text):
        return {"items": [{"title": text}], "source": "local"}

    def apply(self, items):
        return {"applied": len(items), "items": items}


@pytest.fixture()
def assistant_service(monkeypatch):
    fake = _FakeAssistantService()
    monkeypatch.setattr("app.api.assistant._svc", lambda _db, _user: fake)
    return fake


class TestAssistantRoutesWiring:
    def _data(self, response) -> dict:
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["code"] == 0, body
        return body["data"]

    def test_status_route(self, client, assistant_service):
        assert self._data(client.get("/api/v1/assistant/status"))["configured"] is True

    def test_config_route_passes_key_to_service(self, client, assistant_service):
        data = self._data(
            client.put("/api/v1/assistant/config", json={"api_key": "sk-12345678"})
        )
        assert data == {"configured": True, "key_len": 11}

    def test_parse_route_returns_items(self, client, assistant_service):
        data = self._data(
            client.post("/api/v1/assistant/parse", json={"text": "明天交作业"})
        )
        assert data["items"] == [{"title": "明天交作业"}]
        assert data["source"] == "local"

    def test_apply_route_serializes_items(self, client, assistant_service):
        data = self._data(client.post(
            "/api/v1/assistant/apply",
            json={"items": [{"title": "买牛奶"}, {"title": "写周报", "kind": "task"}]},
        ))
        assert data["applied"] == 2
        assert {item["title"] for item in data["items"]} == {"买牛奶", "写周报"}
