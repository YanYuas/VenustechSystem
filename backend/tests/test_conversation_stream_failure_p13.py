# ============================================================
# Phase13 · A 类覆盖率补缺：对话流式 AI 失败降级
#
# 覆盖 ConversationService.stream_messages 的 except 分支：
#   · AI 流式调用抛错 → yield error 事件，**仍保存**助手占位消息
#     （"[AI 服务异常] ..."，tokens=0），保证对话完整性；
#   · _estimate_tokens 空文本 → 0。
# ============================================================
from __future__ import annotations

import asyncio

from app.schemas.conversation import SendMessageRequest
from app.services.conversation_service import ConversationService


class _FailingClient:
    """模拟 provider 在流式响应中途/开始即失败。"""

    async def stream_chat(self, _messages, temperature=0.7):
        raise RuntimeError("upstream 502")
        yield  # pragma: no cover - 语法上保持 async generator


def _collect(agen) -> list[dict]:
    async def run() -> list[dict]:
        out = []
        async for event in agen:
            out.append(event)
        return out

    return asyncio.run(run())


class TestConversationStreamFailure:
    def test_failure_emits_error_and_saves_fallback_message(
        self, db_session, test_user, monkeypatch
    ):
        svc = ConversationService(db_session, test_user)
        conv = svc.create(title="降级会话")
        monkeypatch.setattr(
            "app.services.conversation_service.get_llm_client",
            lambda _user: _FailingClient(),
        )

        events = _collect(svc.stream_messages(conv.id, SendMessageRequest(content="你好")))

        assert {"type": "error", "error": "upstream 502"} in events
        assert not any(e.get("type") == "done" for e in events)   # 失败不发 done

        # 助手占位消息仍落库（内容含异常原因、tokens=0）
        messages = svc.msg_repo.list_recent(conv.id, limit=10)
        assistant = [m for m in messages if m.role == "assistant"]
        assert len(assistant) == 1
        assert assistant[0].content == "[AI 服务异常] upstream 502"
        assert assistant[0].tokens == 0
        # 用户消息也保留（先落库再调 AI）
        assert any(m.role == "user" and m.content == "你好" for m in messages)

    def test_estimate_tokens_empty_text_is_zero(self):
        assert ConversationService._estimate_tokens([{"content": ""}], "") == 0
