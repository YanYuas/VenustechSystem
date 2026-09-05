# ============================================================
# LLM 客户端抽象（对齐架构 v2.0 §6.2）
# - DeepSeekClient：httpx 实现 OpenAI 兼容接口（零 openai 依赖）
# - MockLLMClient：未配 Key / 离线时的确定性 mock（骨架/演示可跑）
# ============================================================
from __future__ import annotations

import json
import asyncio
from abc import ABC, abstractmethod
from typing import AsyncIterator, NamedTuple

import httpx

from app.core.exceptions import AIKeyMissingException, AIRequestFailedException
from app.core.security import decrypt_secret
from app.config import get_settings


class AIResponse(NamedTuple):
    content: str
    tokens: int = 0


class LLMClient(ABC):
    @abstractmethod
    async def chat(self, messages: list[dict], *, temperature: float = 0.7,
                   max_tokens: int = 2000) -> AIResponse:
        """非流式对话，返回完整内容 + token 消耗。"""

    @abstractmethod
    async def stream_chat(self, messages: list[dict], *, temperature: float = 0.7,
                          max_tokens: int = 2000) -> AsyncIterator[str]:
        """流式对话，逐块产出文本。"""


class DeepSeekClient(LLMClient):
    # 网络错误重试：最多2次，指数退避（1s → 2s）
    _MAX_RETRIES = 2
    _RETRY_BASE_DELAY = 1.0

    def __init__(self, api_key: str, base_url: str, model: str, timeout: float):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = httpx.Timeout(timeout, connect=5.0)

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def _request_with_retry(self, url: str, payload: dict) -> dict:
        """带指数退避重试的 POST 请求（仅网络错误重试，HTTP 错误不重试）。"""
        last_exc: Exception | None = None
        for attempt in range(self._MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(url, json=payload, headers=self._headers())
                if resp.status_code != 200:
                    raise AIRequestFailedException(f"AI 请求失败: HTTP {resp.status_code}")
                return resp.json()
            except httpx.HTTPError as exc:
                last_exc = exc
                if attempt < self._MAX_RETRIES:
                    await asyncio.sleep(self._RETRY_BASE_DELAY * (2 ** attempt))
                    continue
                raise AIRequestFailedException(f"AI 请求失败: {exc}") from exc
        # 理论上不会走到这里
        raise AIRequestFailedException(f"AI 请求失败: {last_exc}")

    async def chat(self, messages, *, temperature=0.7, max_tokens=2000) -> AIResponse:
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        data = await self._request_with_retry(url, payload)
        content = data["choices"][0]["message"]["content"]
        tokens = (data.get("usage") or {}).get("total_tokens", 0)
        return AIResponse(content=content, tokens=int(tokens))

    async def stream_chat(self, messages, *, temperature=0.7, max_tokens=2000) -> AsyncIterator[str]:
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream("POST", url, json=payload, headers=self._headers()) as resp:
                    if resp.status_code != 200:
                        await resp.aread()
                        raise AIRequestFailedException(f"AI 请求失败: HTTP {resp.status_code}")
                    async for line in resp.aiter_lines():
                        line = line.strip()
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        delta = (chunk.get("choices") or [{}])[0].get("delta", {}).get("content")
                        if delta:
                            yield delta
        except httpx.HTTPError as exc:
            raise AIRequestFailedException(f"AI 流式中断: {exc}") from exc


class MockLLMClient(LLMClient):
    """未配置 Key / 离线时的确定性 mock（不消费 API，保证演示可跑）。"""

    async def chat(self, messages, *, temperature=0.7, max_tokens=2000) -> AIResponse:
        user_content = messages[-1]["content"] if messages else ""
        text = (
            "（演示模式）这是第二分身的模拟回复。你说的是："
            f"{user_content[:80]}\n\n"
            "配置 DeepSeek API Key（设置页）后将接入真实模型对话。"
        )
        return AIResponse(content=text, tokens=0)

    async def stream_chat(self, messages, *, temperature=0.7, max_tokens=2000) -> AsyncIterator[str]:
        resp = await self.chat(messages, temperature=temperature, max_tokens=max_tokens)
        for i in range(0, len(resp.content), 10):
            yield resp.content[i:i + 10]


def get_llm_client(user) -> LLMClient:
    """按用户是否配置 Key 返回 DeepSeek 或 Mock 客户端。"""
    settings = get_settings()
    if user and user.api_key_encrypted:
        try:
            key = decrypt_secret(user.api_key_encrypted)
            if key:
                return DeepSeekClient(key, settings.ai_base_url, settings.ai_model, settings.ai_timeout)
        except Exception:
            pass
    return MockLLMClient()
