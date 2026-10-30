# ============================================================
# Phase6 · AI 服务层测试（AIService 编排 + DeepSeekClient 协议/错误映射）
#
# 覆盖缺口：app/services/ai/ai_service.py（34.1%）、app/services/ai/client.py（45.4%）
# 原则：LLM 一律替身，不联网；重点断言"请求参数 + 错误映射 + 降级/容错分支"。
# ============================================================
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from app.core.exceptions import AIRequestFailedException, NotFoundException
from app.services.ai.ai_service import AIService, _extract_json
from app.services.ai.client import (
    AIResponse,
    DeepSeekClient,
    MockLLMClient,
    get_llm_client,
)
from tests.factories import make_document

PROMPT_KEY = "app.services.ai.ai_service.get_llm_client"


class _FakeLLM:
    def __init__(self, content: str = "", record: list | None = None):
        self.content = content
        self.record = record if record is not None else []

    async def chat(self, messages, *, temperature=0.7, max_tokens=2000) -> AIResponse:
        self.record.append({"messages": messages, "temperature": temperature})
        return AIResponse(content=self.content, tokens=7)


def _svc(db, user, content: str):
    svc = AIService(db, user)
    svc.client = _FakeLLM(content)
    return svc


# ================================================================
# 一、_extract_json（LLM 输出容错解析）
# ================================================================
class TestExtractJson:
    def test_plain_json_object(self):
        assert _extract_json('{"a": 1}') == {"a": 1}

    def test_plain_json_array(self):
        assert _extract_json("[1, 2, 3]") == [1, 2, 3]

    def test_fenced_code_block(self):
        assert _extract_json('```json\n{"tags": ["x"]}\n```') == {"tags": ["x"]}

    def test_fenced_without_language(self):
        assert _extract_json('```\n["a"]\n```') == ["a"]

    def test_embedded_array_is_recovered(self):
        assert _extract_json('好的，结果如下：[{"question": "q1"}] 请查收') == [
            {"question": "q1"}
        ]

    def test_invalid_returns_none(self):
        assert _extract_json("完全不是 JSON") is None

    def test_embedded_array_but_invalid_json_returns_none(self):
        assert _extract_json("[not json]") is None


# ================================================================
# 二、AIService 编排（摘要/标签/灵感/反思问题）
# ================================================================
class TestAIServiceOrchestration:
    def test_summarize_missing_document_raises(self, db_session, test_user):
        svc = AIService(db_session, test_user)
        with pytest.raises(NotFoundException):
            asyncio.run(svc.summarize("no-such-doc"))

    def test_summarize_returns_stripped_content(self, db_session, test_user):
        doc = make_document(db_session, test_user.id, title="标题", content="正文" * 30)
        svc = _svc(db_session, test_user, "  摘要内容  ")
        result = asyncio.run(svc.summarize(doc.id))
        assert result.summary == "摘要内容"
        assert svc.client.record[0]["temperature"] == 0.3
        assert "标题" in svc.client.record[0]["messages"][-1]["content"]

    def test_suggest_tags_parses_list_and_limits(self, db_session, test_user):
        doc = make_document(db_session, test_user.id, title="t", content="c" * 60)
        svc = _svc(db_session, test_user, '["AI", "工具", "", "超长标签名称应该被截断到十个字"]')
        result = asyncio.run(svc.suggest_tags(doc.id))
        assert result.tags[:2] == ["AI", "工具"]
        assert len(result.tags) <= 5
        assert all(len(tag) <= 10 for tag in result.tags)

    def test_suggest_tags_handles_non_list_json(self, db_session, test_user):
        doc = make_document(db_session, test_user.id, title="t", content="c" * 60)
        assert asyncio.run(_svc(db_session, test_user, '{"tags": ["a"]}').suggest_tags(doc.id)).tags == []

    def test_suggest_tags_handles_invalid_json(self, db_session, test_user):
        doc = make_document(db_session, test_user.id, title="t", content="c" * 60)
        assert asyncio.run(_svc(db_session, test_user, "oops").suggest_tags(doc.id)).tags == []

    def test_suggest_tags_caps_at_five(self, db_session, test_user):
        doc = make_document(db_session, test_user.id, title="t", content="c" * 60)
        content = json.dumps([f"t{i}" for i in range(9)])
        assert len(asyncio.run(_svc(db_session, test_user, content).suggest_tags(doc.id)).tags) == 5

    def test_inspiration_returns_content_and_defaults(self, db_session, test_user):
        doc = make_document(db_session, test_user.id, title="t", content="c" * 60)
        svc = _svc(db_session, test_user, "  灵感正文 ")
        result = asyncio.run(svc.inspiration(doc.id))
        assert result.inspiration == "灵感正文"
        assert result.direction == ["（方向要点待生成）"]
        assert result.prompt == ""
        assert svc.client.record[0]["temperature"] == 0.9

    def test_inspiration_missing_document_raises(self, db_session, test_user):
        with pytest.raises(NotFoundException):
            asyncio.run(_svc(db_session, test_user, "x").inspiration("missing"))

    def test_reflection_questions_from_list_of_dicts(self, db_session, test_user):
        content = json.dumps([{"question": "Q1"}, {"question": "Q2"}, {"question": ""}])
        questions = asyncio.run(
            _svc(db_session, test_user, content).reflection_questions("daily", {})
        )
        assert [q.question for q in questions] == ["Q1", "Q2"]

    def test_reflection_questions_from_list_of_strings(self, db_session, test_user):
        questions = asyncio.run(
            _svc(db_session, test_user, '["字符串问题"]').reflection_questions("daily", {})
        )
        assert [q.question for q in questions] == ["字符串问题"]

    def test_reflection_questions_caps_at_three(self, db_session, test_user):
        content = json.dumps([{"question": f"Q{i}"} for i in range(5)])
        questions = asyncio.run(
            _svc(db_session, test_user, content).reflection_questions("daily", {})
        )
        assert len(questions) == 3

    def test_reflection_questions_fallback_on_invalid_json(self, db_session, test_user):
        questions = asyncio.run(
            _svc(db_session, test_user, "not json").reflection_questions("daily", {})
        )
        assert len(questions) == 3
        assert questions[0].question == "今天最有成就感的一件事是什么？"

    def test_reflection_questions_usage_prompt_contains_review_data(self, db_session, test_user):
        svc = _svc(db_session, test_user, '["Q"]')
        asyncio.run(svc.reflection_questions("weekly", {"mood": 4}))
        prompt = svc.client.record[0]["messages"][-1]["content"]
        assert "mood" in prompt


# ================================================================
# 三、DeepSeekClient：请求构造 / 重试 / 错误映射
# ================================================================
class _Resp:
    def __init__(self, status_code: int, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}

    def json(self):
        return self._payload


class _FakeAsyncClient:
    script: list = []
    calls: list = []

    def __init__(self, *args, **kwargs):
        _FakeAsyncClient.last_kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, **kwargs):
        _FakeAsyncClient.calls.append({"url": url, **kwargs})
        item = _FakeAsyncClient.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture()
def fake_http(monkeypatch):
    import httpx

    _FakeAsyncClient.script = []
    _FakeAsyncClient.calls = []

    async def _no_sleep(_seconds):
        return None

    monkeypatch.setattr("app.services.ai.client.httpx.AsyncClient", _FakeAsyncClient)
    monkeypatch.setattr("app.services.ai.client.asyncio.sleep", _no_sleep)
    return SimpleNamespace(client=_FakeAsyncClient, http_error=httpx.HTTPError)


def _client() -> DeepSeekClient:
    return DeepSeekClient("sk-key", "https://api.deepseek.com/v1/", "deepseek-chat", 30.0)


class TestDeepSeekClient:
    def test_init_normalizes_base_url_and_timeout(self):
        client = _client()
        assert client.base_url == "https://api.deepseek.com/v1"
        assert client.api_key == "sk-key"
        assert client.model == "deepseek-chat"

    def test_headers(self):
        assert _client()._headers() == {
            "Authorization": "Bearer sk-key",
            "Content-Type": "application/json",
        }

    def test_chat_success_payload_and_tokens(self, fake_http):
        fake_http.client.script.append(
            _Resp(200, {"choices": [{"message": {"content": "hello"}}],
                        "usage": {"total_tokens": 42}})
        )
        result = asyncio.run(_client().chat([{"role": "user", "content": "hi"}], temperature=0.2))
        assert result == AIResponse(content="hello", tokens=42)
        call = fake_http.client.calls[0]
        assert call["url"] == "https://api.deepseek.com/v1/chat/completions"
        assert call["json"]["stream"] is False
        assert call["json"]["temperature"] == 0.2
        assert call["headers"]["Authorization"] == "Bearer sk-key"

    def test_chat_missing_usage_defaults_to_zero_tokens(self, fake_http):
        fake_http.client.script.append(
            _Resp(200, {"choices": [{"message": {"content": "x"}}]})
        )
        assert asyncio.run(_client().chat([])).tokens == 0

    def test_chat_non_200_raises_without_retry(self, fake_http):
        fake_http.client.script.append(_Resp(401, {}))
        with pytest.raises(AIRequestFailedException) as exc:
            asyncio.run(_client().chat([]))
        assert "HTTP 401" in str(exc.value)
        assert len(fake_http.client.calls) == 1  # HTTP 错误不重试

    def test_chat_retries_on_network_error_then_succeeds(self, fake_http):
        fake_http.client.script.extend([
            fake_http.http_error("conn reset"),
            _Resp(200, {"choices": [{"message": {"content": "ok"}}]}),
        ])
        assert asyncio.run(_client().chat([])).content == "ok"
        assert len(fake_http.client.calls) == 2

    def test_chat_retries_exhausted_raises(self, fake_http):
        fake_http.client.script.extend([
            fake_http.http_error("e1"),
            fake_http.http_error("e2"),
            fake_http.http_error("e3"),
        ])
        with pytest.raises(AIRequestFailedException):
            asyncio.run(_client().chat([]))
        assert len(fake_http.client.calls) == 3  # 1 + MAX_RETRIES

    @pytest.mark.parametrize(
        "payload,cause_type",
        [
            ({}, KeyError),                                    # 缺 choices
            ({"choices": []}, IndexError),                     # choices 为空
            ({"choices": [{}]}, KeyError),                     # 缺 message
            ({"choices": [{"message": {}}]}, KeyError),        # 缺 content
            ({"choices": [{"message": {"content": None}}]}, TypeError),  # content 非字符串
            ({"usage": {"total_tokens": None},
              "choices": [{"message": {"content": "x"}}]}, TypeError),
        ],
    )
    def test_malformed_200_payload_maps_to_ai_exception(
        self, fake_http, payload, cause_type
    ):
        """D-23：200 但响应结构异常 → AIRequestFailedException（保留原因链），不再裸 KeyError。"""
        fake_http.client.script.append(_Resp(200, payload))
        with pytest.raises(AIRequestFailedException) as exc:
            asyncio.run(_client().chat([]))
        assert "AI 响应格式异常" in str(exc.value)
        assert isinstance(exc.value.__cause__, cause_type)

    def test_invalid_json_body_maps_to_ai_exception(self, fake_http):
        class _BadJsonResp(_Resp):
            def json(self):
                raise ValueError("Expecting value")

        fake_http.client.script.append(_BadJsonResp(200, {}))
        with pytest.raises(AIRequestFailedException) as exc:
            asyncio.run(_client().chat([]))
        assert "AI 响应格式异常" in str(exc.value)


class _StreamResp:
    def __init__(self, status_code: int, lines: list[str]):
        self.status_code = status_code
        self._lines = lines
        self.read = False

    async def aread(self):
        self.read = True
        return b""

    async def aiter_lines(self):
        for line in self._lines:
            yield line


class _FakeStreamClient:
    script: list = []
    calls: list = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def stream(self, method, url, **kwargs):
        _FakeStreamClient.calls.append({"method": method, "url": url, **kwargs})
        item = _FakeStreamClient.script.pop(0)
        response = item if isinstance(item, _StreamResp) else None
        error = item if isinstance(item, Exception) else None

        class _Ctx:
            async def __aenter__(self_inner):
                if error is not None:
                    raise error
                return response

            async def __aexit__(self_inner, *exc):
                return False

        return _Ctx()


class TestDeepSeekStream:
    @pytest.fixture()
    def fake_stream(self, monkeypatch):
        _FakeStreamClient.script = []
        _FakeStreamClient.calls = []
        monkeypatch.setattr(
            "app.services.ai.client.httpx.AsyncClient", _FakeStreamClient
        )
        return _FakeStreamClient

    async def _collect(self, gen):
        return [chunk async for chunk in gen]

    def test_stream_yields_deltas_and_stops_on_done(self, fake_stream):
        fake_stream.script.append(_StreamResp(200, [
            'data: {"choices": [{"delta": {"content": "你"}}]}',
            'data: {"choices": [{"delta": {"content": "好"}}]}',
            "data: [DONE]",
            'data: {"choices": [{"delta": {"content": "不该出现"}}]}',
        ]))
        chunks = asyncio.run(self._collect(_client().stream_chat([])))
        assert chunks == ["你", "好"]
        assert fake_stream.calls[0]["method"] == "POST"
        assert fake_stream.calls[0]["json"]["stream"] is True

    def test_stream_skips_invalid_json_and_empty_delta(self, fake_stream):
        fake_stream.script.append(_StreamResp(200, [
            "event: ping",
            "data: not-json",
            'data: {"choices": [{"delta": {}}]}',
            'data: {"choices": [{"delta": {"content": "ok"}}]}',
        ]))
        assert asyncio.run(self._collect(_client().stream_chat([]))) == ["ok"]

    def test_stream_non_200_raises(self, fake_stream):
        fake_stream.script.append(_StreamResp(500, []))
        with pytest.raises(AIRequestFailedException) as exc:
            asyncio.run(self._collect(_client().stream_chat([])))
        assert "HTTP 500" in str(exc.value)

    def test_stream_http_error_maps_to_stream_interrupted(self, fake_stream):
        fake_stream.script.append(ValueError("not http error"))  # 先验证非 HTTP 异常不在此捕获
        with pytest.raises(ValueError):
            asyncio.run(self._collect(_client().stream_chat([])))

    def test_stream_http_error_wrapped(self, fake_stream):
        import httpx

        fake_stream.script.append(httpx.HTTPError("boom"))
        with pytest.raises(AIRequestFailedException) as exc:
            asyncio.run(self._collect(_client().stream_chat([])))
        assert "流式中断" in str(exc.value)


# ================================================================
# 四、get_llm_client 选择逻辑
# ================================================================
class TestGetLlmClient:
    def test_without_key_returns_mock(self):
        assert isinstance(get_llm_client(SimpleNamespace(id="u", api_key_encrypted=None)), MockLLMClient)

    def test_with_key_returns_deepseek(self, monkeypatch):
        monkeypatch.setattr("app.services.ai.client.decrypt_secret", lambda _raw: "sk-decrypted")
        client = get_llm_client(SimpleNamespace(id="u", api_key_encrypted="fernet:x"))
        assert isinstance(client, DeepSeekClient)
        assert client.api_key == "sk-decrypted"
        assert client.base_url.startswith("http")

    def test_decrypt_failure_falls_back_to_mock(self, monkeypatch):
        def boom(_raw):
            raise ValueError("kdf failed")

        monkeypatch.setattr("app.services.ai.client.decrypt_secret", boom)
        assert isinstance(
            get_llm_client(SimpleNamespace(id="u", api_key_encrypted="fernet:x")),
            MockLLMClient,
        )

    def test_empty_decrypted_key_falls_back_to_mock(self, monkeypatch):
        monkeypatch.setattr("app.services.ai.client.decrypt_secret", lambda _raw: "")
        assert isinstance(
            get_llm_client(SimpleNamespace(id="u", api_key_encrypted="fernet:x")),
            MockLLMClient,
        )
