# ============================================================
# A 类剩余 API 端点补测（Phase12-B）：auth / avatar / conversation / asset / pet
#
# 来源 task-47 审计（Phase12 基线 term-missing）：
#   · app/api/auth.py 59-64（POST /auth/init 正文）
#   · app/api/avatar.py 38/43/100/145/154（5 个只读/配置端点）
#   · app/api/conversation.py 75/101/106/111/120-121（SSE 异常事件 + 4 个 AI 接口）
#   · app/services/asset_service.py 164-168（Prompt category 过滤）
#   · app/services/pet_service.py 98/257-258/273-274（切换形象 + 两处降级）
#
# 一律走 conftest 的 `client`（单用户 default_user 自动认证）+ factories；
# AI 相关全部 monkeypatch 掉（不联网、不超过 1ms）。错误分支断言「状态码 + 统一信封 code」。
# 注意：PATCH /auth/me、/auth/init 会改 default_user —— 统一用 `user_state`
# fixture 在用例结束后从 DB 快照恢复，避免污染同会话其它用例。
# ============================================================
from __future__ import annotations

import json
import logging

import pytest

from app.api import conversation as conv_api
from app.core.exceptions import AIServiceException
from app.database import SessionLocal
from app.models.user import User
from app.schemas.conversation import (
    AiInspirationResult,
    AiSummaryResult,
    AiTagsResult,
    ReflectionQuestion,
)
from app.services.pet_service import PetService

# default_user 上会被端到端修改的列（快照/恢复用）
_MUTABLE_COLUMNS = (
    "nickname", "avatar_path", "theme", "api_key_encrypted", "automation_level",
    "pet_position", "pet_topmost", "inspiration_probability", "ai_enabled",
)


def _snapshot_default_user() -> dict:
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(username="default_user").one()
        return {column: getattr(user, column) for column in _MUTABLE_COLUMNS}
    finally:
        db.close()


def _restore_default_user(snapshot: dict) -> None:
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(username="default_user").one()
        for column, value in snapshot.items():
            setattr(user, column, value)
        db.commit()
    finally:
        db.close()


@pytest.fixture()
def user_state(default_user_id):
    """改 default_user 的用例统一恢复快照，避免影响其它用例的 AI/主题假设。"""
    snapshot = _snapshot_default_user()
    yield snapshot
    _restore_default_user(snapshot)


def _api_data(response) -> dict:
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["code"] == 0, body
    return body["data"]


# ================================================================
# 一、auth：init / PATCH me / verify-api
# ================================================================
class TestAuthEndpoints:
    def test_init_sets_nickname_and_encrypts_api_key(self, client, user_state):
        r = client.post("/api/v1/auth/init",
                        json={"nickname": "新昵称", "api_key": "sk-test-123"})

        data = _api_data(r)
        assert data["nickname"] == "新昵称"
        assert data["api_key_configured"] is True
        # GET /auth/me 读到的就是落库后的状态
        assert _api_data(client.get("/api/v1/auth/me"))["nickname"] == "新昵称"

    def test_init_without_api_key_keeps_existing_key_state(self, client, user_state):
        before = _api_data(client.get("/api/v1/auth/me"))
        r = client.post("/api/v1/auth/init", json={"nickname": "只改昵称"})

        data = _api_data(r)
        assert data["nickname"] == "只改昵称"
        # api_key 传空/不传 → 不覆盖已有加密 Key
        assert data["api_key_configured"] == before["api_key_configured"]

    def test_init_validation_error_uses_unified_envelope(self, client):
        r = client.post("/api/v1/auth/init", json={"nickname": ""})   # min_length=1

        assert r.status_code == 400
        body = r.json()
        assert body["code"] == 1001
        assert body["message"].startswith("参数错误")

    def test_patch_me_updates_scalar_fields(self, client, user_state):
        r = client.patch("/api/v1/auth/me", json={
            "nickname": "改过的昵称",
            "theme": "dark",
            "automation_level": "L3",
        })

        data = _api_data(r)
        assert data["nickname"] == "改过的昵称"
        assert data["theme"] == "dark"
        assert data["automation_level"] == "L3"
        assert _api_data(client.get("/api/v1/auth/me"))["theme"] == "dark"

    def test_patch_me_pet_position_partial_update_merges_coordinates(self, client, user_state):
        # D-17 回归：exclude_unset 会裁掉嵌套模型未显式给出的坐标，必须沿用旧值
        _api_data(client.patch("/api/v1/auth/me",
                               json={"pet_position": {"x": 100, "y": 200}}))
        r = client.patch("/api/v1/auth/me", json={"pet_position": {"x": 300}})

        pet = _api_data(r)["pet_position"]
        assert pet == {"x": 300, "y": 200}      # y 不被默认值 880 打回

    def test_patch_me_empty_body_keeps_config_unchanged(self, client, user_state):
        before = _api_data(client.get("/api/v1/auth/me"))
        r = client.patch("/api/v1/auth/me", json={})

        assert _api_data(r) == before

    def test_verify_api_returns_provider_result(self, client, monkeypatch):
        calls: list[str] = []

        class _FakeAIService:
            def __init__(self, db, user):
                pass

            async def verify_api(self, api_key):
                calls.append(api_key)
                return AiSummaryResult(summary="unused")  # 占位，下面替换

        # verify_api 期望 ApiVerifyResult；直接用真实 schema
        from app.schemas.auth import ApiVerifyResult

        class _FakeVerifyService(_FakeAIService):
            async def verify_api(self, api_key):
                calls.append(api_key)
                return ApiVerifyResult(valid=True, model="deepseek-chat")

        monkeypatch.setattr("app.api.auth.AIService", _FakeVerifyService)
        r = client.post("/api/v1/auth/verify-api", json={"api_key": " sk-abc "})

        data = _api_data(r)
        assert data["valid"] is True
        assert data["model"] == "deepseek-chat"
        assert calls == ["sk-abc"]                     # 传给 provider 前已 strip

    def test_verify_api_failure_reason_is_passed_through(self, client, monkeypatch):
        from app.schemas.auth import ApiVerifyResult

        class _FakeVerifyService:
            def __init__(self, db, user):
                pass

            async def verify_api(self, api_key):
                return ApiVerifyResult(valid=False, reason="API Key 无效或无权限（HTTP 401/403）")

        monkeypatch.setattr("app.api.auth.AIService", _FakeVerifyService)
        data = _api_data(client.post("/api/v1/auth/verify-api", json={"api_key": "sk-bad"}))
        assert data["valid"] is False
        assert data["reason"] == "API Key 无效或无权限（HTTP 401/403）"


# ================================================================
# 二、avatar：5 个此前未测的只读/配置端点
# ================================================================
class TestAvatarReadEndpoints:
    def _create_memory(self, client, memory_type: str, title: str) -> dict:
        r = client.post("/api/v1/avatar/memories", json={
            "memory_type": memory_type, "title": title,
        })
        return _api_data(r)

    def test_list_memories_filters_by_type(self, client, default_user_id):
        self._create_memory(client, "profile", "画像A")
        self._create_memory(client, "event", "事件B")

        data = _api_data(client.get("/api/v1/avatar/memories",
                                    params={"memory_type": "profile"}))
        assert data["total"] == 1
        assert [m["title"] for m in data["list"]] == ["画像A"]

        all_data = _api_data(client.get("/api/v1/avatar/memories"))
        assert all_data["total"] == 2                  # 无过滤返回全部

    def test_memory_stats_endpoint(self, client, default_user_id):
        self._create_memory(client, "profile", "画像A")
        event = self._create_memory(client, "event", "事件B")
        _api_data(client.post(f"/api/v1/avatar/memories/{event['id']}/verify?verified=true"))

        stats = _api_data(client.get("/api/v1/avatar/memories/stats"))
        assert stats["profile"] == 1
        assert stats["event"] == 1
        assert stats["total"] == 2
        assert stats["verified"] == 1

    def test_list_inspirations_filters_by_status(self, client, default_user_id):
        batch = _api_data(client.post("/api/v1/avatar/inspirations/generate",
                                      json={"domain": "学习", "count": 2}))
        first_id = batch["inspirations"][0]["id"]
        _api_data(client.post(f"/api/v1/avatar/inspirations/{first_id}/select"))

        selected = _api_data(client.get("/api/v1/avatar/inspirations",
                                        params={"status": "selected"}))
        assert selected["total"] == 1
        assert selected["list"][0]["id"] == first_id
        assert selected["list"][0]["status"] == "selected"

        generated = _api_data(client.get("/api/v1/avatar/inspirations",
                                         params={"status": "generated"}))
        assert generated["total"] == 1                # 另一条仍是 generated

    def test_get_config_creates_default_row(self, client, default_user_id):
        config = _api_data(client.get("/api/v1/avatar/config"))
        assert config["automation_level"] == "L2"
        assert config["id"]
        # 再取一次：复用同一行，不重复创建
        assert _api_data(client.get("/api/v1/avatar/config"))["id"] == config["id"]

    def test_update_config_persists_persona(self, client, default_user_id):
        config = _api_data(client.get("/api/v1/avatar/config"))
        updated = _api_data(client.patch("/api/v1/avatar/config",
                                         json={"persona_name": "小启", "creativity": 70}))
        assert updated["id"] == config["id"]
        assert updated["persona_name"] == "小启"
        assert updated["creativity"] == 70
        assert _api_data(client.get("/api/v1/avatar/config"))["persona_name"] == "小启"


# ================================================================
# 三、conversation：4 个 AI 接口 + SSE 异常事件
# ================================================================
class TestConversationAiEndpoints:
    def test_summarize_returns_summary(self, client, monkeypatch):
        class _FakeAIService:
            def __init__(self, db, user):
                pass

            async def summarize(self, document_id):
                return AiSummaryResult(summary=f"摘要:{document_id}")

        monkeypatch.setattr(conv_api, "AIService", _FakeAIService)
        data = _api_data(client.post("/api/v1/ai/summarize", json={"document_id": "doc-1"}))
        assert data["summary"] == "摘要:doc-1"

    def test_suggest_tags_returns_tags(self, client, monkeypatch):
        class _FakeAIService:
            def __init__(self, db, user):
                pass

            async def suggest_tags(self, document_id):
                return AiTagsResult(tags=["效率", "复盘"])

        monkeypatch.setattr(conv_api, "AIService", _FakeAIService)
        data = _api_data(client.post("/api/v1/ai/suggest-tags", json={"document_id": "doc-2"}))
        assert data["tags"] == ["效率", "复盘"]

    def test_inspiration_returns_direction(self, client, monkeypatch):
        class _FakeAIService:
            def __init__(self, db, user):
                pass

            async def inspiration(self, document_id):
                return AiInspirationResult(inspiration="换个角度", direction=["时间线"], prompt="p")

        monkeypatch.setattr(conv_api, "AIService", _FakeAIService)
        data = _api_data(client.post("/api/v1/ai/inspiration", json={"document_id": "doc-3"}))
        assert data["inspiration"] == "换个角度"
        assert data["direction"] == ["时间线"]

    def test_reflection_questions_returns_list(self, client, monkeypatch):
        class _FakeAIService:
            def __init__(self, db, user):
                pass

            async def reflection_questions(self, review_type, data):
                return [ReflectionQuestion(question=f"{review_type}-Q1"),
                        ReflectionQuestion(question="Q2")]

        monkeypatch.setattr(conv_api, "AIService", _FakeAIService)
        data = _api_data(client.post("/api/v1/ai/reflection-questions",
                                     json={"review_type": "weekly", "data": {}}))
        assert [item["question"] for item in data] == ["weekly-Q1", "Q2"]
        assert all("answer" in item for item in data)   # 结构完整（answer 可空）

    @staticmethod
    def _sse_events(response) -> list[dict]:
        assert response.status_code == 200, response.text
        assert response.headers["content-type"].startswith("text/event-stream")
        events = []
        for line in response.text.splitlines():
            if line.startswith("data: "):
                events.append(json.loads(line[len("data: "):]))
        return events

    def test_send_message_unknown_conversation_emits_error_event(self, client, default_user_id):
        r = client.post("/api/v1/conversations/ghost-conversation/messages",
                        json={"content": "你好"})

        events = self._sse_events(r)
        assert events == [{"type": "error", "error": "会话不存在", "code": 1002}]

    def test_send_message_ai_service_exception_emits_error_event(self, client, monkeypatch):
        conversation = _api_data(client.post("/api/v1/conversations", json={}))

        async def _explode(self, conversation_id, data):
            raise AIServiceException("AI 服务不可用")
            yield {}   # pragma: no cover - 让函数成为 async generator

        monkeypatch.setattr(conv_api.ConversationService, "stream_messages", _explode)
        r = client.post(f"/api/v1/conversations/{conversation['id']}/messages",
                        json={"content": "你好"})

        events = self._sse_events(r)
        assert events == [{"type": "error", "error": "AI 服务不可用"}]
        assert "code" not in events[0]          # AIServiceException 分支不带 code


# ================================================================
# 四、asset：Prompt 列表 category 过滤
# ================================================================
class TestAssetPromptCategoryFilter:
    def test_list_prompts_filters_by_category(self, client, default_user_id):
        for name, category in (("P-写作", "写作"), ("P-学习", "学习")):
            _api_data(client.post("/api/v1/assets/prompts",
                                  json={"name": name, "category": category}))

        filtered = _api_data(client.get("/api/v1/assets/prompts",
                                        params={"category": "写作"}))
        assert filtered["total"] == 1
        assert [p["name"] for p in filtered["list"]] == ["P-写作"]

        all_prompts = _api_data(client.get("/api/v1/assets/prompts"))
        assert all_prompts["total"] == 2


# ================================================================
# 五、pet：切换形象 + 两处状态感知降级
# ================================================================
class TestPetAvatarAndDegradation:
    def test_activate_avatar_and_sync_config(self, client, default_user_id):
        avatar = _api_data(client.post("/api/v1/pet/avatars", json={"name": "小猫"}))
        assert avatar["is_active"] is False

        activated = _api_data(client.post(f"/api/v1/pet/avatars/{avatar['id']}/activate"))
        assert activated["current_avatar_id"] == avatar["id"]

        avatars = _api_data(client.get("/api/v1/pet/avatars"))
        rows = {row["id"]: row for row in avatars}
        assert rows[avatar["id"]]["is_active"] is True
        # update_config 的切换分支（pet_service.py:98）：走 _owned_avatar + _set_active_avatar
        config = _api_data(client.patch("/api/v1/pet/config",
                                        json={"current_avatar_id": avatar["id"]}))
        assert config["current_avatar_id"] == avatar["id"]

    def test_state_degrades_when_task_sensing_fails(
        self, db_session, test_user, monkeypatch, caplog
    ):
        svc = PetService(db_session)

        def _boom(*_args, **_kwargs):
            raise RuntimeError("任务查询失败")

        monkeypatch.setattr(svc.task_repo, "count_due_today_open", _boom)
        with caplog.at_level(logging.WARNING):
            state = svc.get_current_state(test_user.id)

        assert state["has_todo_tasks"] is False
        assert state["todo_count"] == 0
        assert state["mood"] == "neutral"          # 心情感知不受影响
        assert "桌宠任务感知失败（降级为无待办）" in caplog.text

    def test_state_degrades_when_mood_sensing_fails(
        self, db_session, test_user, monkeypatch, caplog
    ):
        svc = PetService(db_session)

        def _boom(*_args, **_kwargs):
            raise RuntimeError("心情查询失败")

        monkeypatch.setattr(svc.mood_repo, "list", _boom)
        with caplog.at_level(logging.WARNING):
            state = svc.get_current_state(test_user.id)

        assert state["mood"] == "neutral"
        assert state["mood_label"] == "平静"
        assert "桌宠心情感知失败（降级为平静）" in caplog.text
