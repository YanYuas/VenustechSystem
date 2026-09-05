# ============================================================
# AI 服务编排（摘要/标签/灵感/反思问题/Key 校验）
# 对齐 PRD §13.5 AI 接口
# ============================================================
from __future__ import annotations

import json
import re

from app.core.exceptions import AIServiceException, NotFoundException
from app.models.document import Document
from app.models.user import User
from app.repositories import DocumentRepository
from app.schemas.conversation import (
    AiInspirationResult,
    AiSummaryResult,
    AiTagsResult,
    ReflectionQuestion,
)
from app.schemas.auth import ApiVerifyResult
from app.services.ai.client import DeepSeekClient, LLMClient, get_llm_client
from app.services.ai.prompt_builder import PromptBuilder


def _extract_json(text: str):
    """从 LLM 输出中提取 JSON 数组/对象（容错解析）。"""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\[.*\]", text, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                return None
    return None


class AIService:
    def __init__(self, db, user: User):
        self.db = db
        self.user = user
        self.doc_repo = DocumentRepository(db)
        self.client: LLMClient = get_llm_client(user)

    async def summarize(self, document_id: str) -> AiSummaryResult:
        doc = self._get_doc(document_id)
        messages = PromptBuilder.summary_prompt(doc.title, doc.content or "")
        resp = await self.client.chat(messages, temperature=0.3)
        return AiSummaryResult(summary=resp.content.strip())

    async def suggest_tags(self, document_id: str) -> AiTagsResult:
        doc = self._get_doc(document_id)
        existing = doc.tags or []
        messages = PromptBuilder.tag_prompt(doc.title, doc.content or "", existing)
        resp = await self.client.chat(messages, temperature=0.3)
        data = _extract_json(resp.content)
        if isinstance(data, list):
            tags = [str(t).strip()[:10] for t in data if str(t).strip()]
        else:
            tags = []
        return AiTagsResult(tags=tags[:5])

    async def inspiration(self, document_id: str) -> AiInspirationResult:
        doc = self._get_doc(document_id)
        messages = PromptBuilder.inspiration_prompt(doc.title, doc.content or "")
        resp = await self.client.chat(messages, temperature=0.9)
        return AiInspirationResult(
            inspiration=resp.content.strip(),
            direction=["（方向要点待生成）"],
            prompt="",
        )

    async def reflection_questions(self, review_type: str, data: dict) -> list[ReflectionQuestion]:
        messages = PromptBuilder.reflection_prompt(data)
        resp = await self.client.chat(messages, temperature=0.7)
        parsed = _extract_json(resp.content)
        questions: list[ReflectionQuestion] = []
        if isinstance(parsed, list):
            for q in parsed[:3]:
                text = str(q).strip() if isinstance(q, str) else str(q.get("question", "")).strip()
                if text:
                    questions.append(ReflectionQuestion(question=text))
        # 兜底：解析失败给通用问题
        if not questions:
            questions = [
                ReflectionQuestion(question="今天最有成就感的一件事是什么？"),
                ReflectionQuestion(question="有什么可以做得更好的地方？"),
                ReflectionQuestion(question="明天最重要的一件事是什么？"),
            ]
        return questions

    async def verify_api(self, api_key: str) -> ApiVerifyResult:
        """校验 API Key：真实调用一次极短对话。"""
        from app.config import get_settings
        settings_api = get_settings()
        client = DeepSeekClient(api_key, settings_api.ai_base_url, settings_api.ai_model, 10.0)
        try:
            resp = await client.chat([{"role": "user", "content": "ping"}], max_tokens=5)
            if resp.content:
                return ApiVerifyResult(valid=True, model=settings_api.ai_model)
        except Exception:
            pass
        return ApiVerifyResult(valid=False)

    def _get_doc(self, document_id: str) -> Document:
        doc = self.doc_repo.get(document_id)
        if doc is None:
            raise NotFoundException("文档不存在")
        return doc
