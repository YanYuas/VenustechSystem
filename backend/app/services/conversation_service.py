# ============================================================
# 第二分身服务（会话 CRUD + 流式对话 + 文档引用上下文）
# 对齐 PRD §10 F4.1-F4.2 / 架构 v2.0 §6.4
# ============================================================
from __future__ import annotations

from typing import AsyncIterator

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundException
from app.models.conversation import Conversation, Message
from app.models.user import User
from app.repositories import (
    ConversationRepository,
    DocumentRepository,
    MessageRepository,
)
from app.schemas.conversation import ConversationOut, MessageOut, SendMessageRequest
from app.services.ai.client import get_llm_client
from app.services.ai.prompt_builder import PromptBuilder

MAX_HISTORY_MESSAGES = 20
MAX_DOC_CONTEXT_CHARS = 2000

# 思维模式 → 采样温度 + 系统提示注入（对齐前端 thinkModes）
MODE_CONFIG: dict[str, dict] = {
    "normal": {"temperature": 0.7, "hint": ""},
    "deep": {"temperature": 0.2, "hint": "请进行深度推理，多角度分析问题，并给出结构化结论。"},
    "creative": {"temperature": 0.9, "hint": "请发散思维，提出新颖、有想象力的想法与思路。"},
    "critical": {"temperature": 0.4, "hint": "请以批判性视角审视，指出潜在问题、风险与盲点。"},
    "brainstorm": {"temperature": 1.0, "hint": "请进行头脑风暴，尽可能多地给出思路和方向，不设限。"},
}


class ConversationService:
    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user
        self.conv_repo = ConversationRepository(db)
        self.msg_repo = MessageRepository(db)
        self.doc_repo = DocumentRepository(db)

    # ---------- 会话 CRUD ----------
    def list(self) -> list[ConversationOut]:
        return [self._conv_out(c) for c in self.conv_repo.list_user(self.user.id)]

    def create(self, title: str | None = None, project_id: str | None = None) -> ConversationOut:
        conv = self.conv_repo.create(
            user_id=self.user.id, title=title or "未命名对话", project_id=project_id
        )
        return self._conv_out(conv)

    def delete(self, conversation_id: str) -> None:
        conv = self._owned(conversation_id)
        self.conv_repo.delete(conv)

    def messages(self, conversation_id: str) -> list[MessageOut]:
        self._owned(conversation_id)
        return [self._msg_out(m) for m in self.msg_repo.list_conversation(conversation_id)]

    # ---------- 流式对话 ----------
    async def stream_messages(
        self, conversation_id: str, data: SendMessageRequest
    ) -> AsyncIterator[dict]:
        """保存用户消息 → 构建上下文 → 流式调用 → 保存助手消息。
        AI 调用失败时保存错误占位消息，保证对话完整性。"""
        conv = self._owned(conversation_id)
        # 1. 保存用户消息
        self.msg_repo.create(
            conversation_id=conv.id,
            role="user",
            content=data.content,
            referenced_doc_ids=data.referenced_doc_ids or [],
        )
        # 2. 构建上下文（含思维模式）
        mode = data.mode if data.mode in MODE_CONFIG else "normal"
        messages = self._build_context(conv.id, data.content, data.referenced_doc_ids or [], mode)
        # 3. 流式调用
        client = get_llm_client(self.user)
        collected: list[str] = []
        error_msg: str | None = None
        try:
            async for chunk in client.stream_chat(
                messages, temperature=MODE_CONFIG[mode]["temperature"]
            ):
                collected.append(chunk)
                yield {"type": "content", "content": chunk}
        except Exception as exc:
            error_msg = str(exc)
            yield {"type": "error", "error": error_msg}
        # 4. 保存助手消息（成功或失败都保存）
        if error_msg:
            full_text = f"[AI 服务异常] {error_msg}"
            tokens = 0
        else:
            full_text = "".join(collected)
            tokens = self._estimate_tokens(messages, full_text)
        self.msg_repo.create(
            conversation_id=conv.id, role="assistant", content=full_text, tokens=tokens
        )
        if not error_msg:
            yield {"type": "done", "tokens": tokens}

    def _build_context(
        self, conversation_id: str, user_content: str, referenced_doc_ids: list[str], mode: str = "normal"
    ) -> list[dict]:
        messages: list[dict] = [{"role": "system", "content": PromptBuilder.system_persona()}]
        hint = MODE_CONFIG.get(mode, MODE_CONFIG["normal"])["hint"]
        if hint:
            messages.append({"role": "system", "content": hint})
        # 引用文档注入 system（避免污染用户消息）
        for doc_id in referenced_doc_ids:
            doc = self.doc_repo.get(doc_id)
            if doc and doc.user_id == self.user.id:
                text = (doc.content or "")[:MAX_DOC_CONTEXT_CHARS]
                messages.append(
                    {"role": "system", "content": f"参考文档《{doc.title}》：\n{text}"}
                )
        # 最近 N 条历史
        for m in self.msg_repo.list_recent(conversation_id, limit=MAX_HISTORY_MESSAGES):
            messages.append({"role": m.role, "content": m.content})
        # 当前消息
        messages.append({"role": "user", "content": user_content})
        return messages

    @staticmethod
    def _estimate_tokens(messages: list[dict], reply: str) -> int:
        """粗略估算 token：中文 1 字≈1.5 token，英文 1 词≈1.3 token。"""
        import re
        def count_tokens(text: str) -> int:
            if not text:
                return 0
            chinese = len(re.findall(r"[\u4e00-\u9fff]", text))
            # 英文单词：连续字母数字
            english_words = len(re.findall(r"[a-zA-Z0-9]+", text))
            return int(chinese * 1.5 + english_words * 1.3)

        total = sum(count_tokens(m.get("content", "")) for m in messages)
        return total + count_tokens(reply)

    # ---------- 内部 ----------
    def _owned(self, conversation_id: str) -> Conversation:
        conv = self.conv_repo.get(conversation_id)
        if conv is None or conv.user_id != self.user.id:
            raise NotFoundException("会话不存在")
        return conv

    @staticmethod
    def _conv_out(c: Conversation) -> ConversationOut:
        return ConversationOut(
            id=c.id, title=c.title, scene=c.scene, project_id=c.project_id,
            created_at=c.created_at, updated_at=c.updated_at,
        )

    @staticmethod
    def _msg_out(m: Message) -> MessageOut:
        return MessageOut(
            id=m.id, conversation_id=m.conversation_id, role=m.role, content=m.content,
            tokens=m.tokens, referenced_doc_ids=list(m.referenced_doc_ids or []),
            created_at=m.created_at,
        )
