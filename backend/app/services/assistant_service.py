# ============================================================
# AI 行程助理服务（移动端方案 M2）
#
# 职责链：语音转好的文字 → parse（DeepSeek JSON Mode / 无 Key 降级
# 规则解析）→ 建议列表 → 用户确认 → apply（白名单落库）。
#
# 铁律对账：
# - AI 永不直接写业务表：parse 只返回建议，apply 才走
#   TaskService / ResourceService（正常校验 + 事件总线照常结算 EXP）
# - Key 加密落库（encryption 文件密钥），永不回显前端、不进日志
# - 无 Key 完全可用：本地规则解析降级
# ============================================================
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.encryption import EncryptionManager
from app.core.exceptions import BusinessException, ValidationException
from app.config import get_settings
from app.schemas.task import CreateTaskRequest
from app.services.resource_service import ResourceService, CreateInboxItemRequest
from app.services.task_service import TaskService

DEEPSEEK_BASE = "https://api.deepseek.com/v1"   # 硬编码：防配置注入 SSRF
DEFAULT_MODEL = "deepseek-chat"
_TIMEOUT = 20.0

_KEY_SETTING = "assistant.deepseek_key"
_MODEL_SETTING = "assistant.deepseek_model"

# ---------- 无 Key 降级：本地规则解析 ----------

_TIME_HINTS: list[tuple[str, int]] = [
    ("马上|立刻|现在", 0),
    ("今晚|今天晚上", 0),
    ("今天", 0),
    ("明天", 1),
    ("后天", 2),
    ("大后天", 3),
]
_PRIORITY_WORDS = ("尽快", "紧急", "马上", "立刻", "重要")
_SPLIT_RE = re.compile(r"[。；;！!？?\n]+|然后|接着|另外|还有|以及|，.*?(?:要|得|需要|打算|准备)")
_NUM_TIME = re.compile(r"(今天|明天|后天|大后天|周[一二三四五六日天]|下周[一二三四五六日天])?(?:\s*)(早上|上午|中午|下午|晚上)?\s*(\d{1,2})[点时:：](\d{1,2})?分?")

WEEKDAY = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}


def _deadline_from_text(text: str, today: date) -> tuple[datetime | None, bool]:
    """从一段文本里抠时间。返回 (deadline, 是否带具体时间)。"""
    m = _NUM_TIME.search(text)
    if not m:
        for pat, offset in _TIME_HINTS:
            if re.search(pat, text):
                return datetime.combine(today + timedelta(days=offset), datetime.min.time()), False
        wm = re.search(r"(?:下)?周([一二三四五六日天])", text)
        if wm:
            delta = (WEEKDAY[wm.group(1)] - today.weekday()) % 7 or 7
            if wm.group(0).startswith("下周"):
                delta += 7 - ((today.weekday() + 1) % 7 or 7) if False else delta  # 下周至少推 7 天
            return datetime.combine(today + timedelta(days=delta), datetime.min.time()), False
        return None, False
    day_part, period, hour, minute = m.groups()
    base = today
    if day_part in (None, "今天"):
        offset = 0
    elif day_part == "明天":
        offset = 1
    elif day_part == "后天":
        offset = 2
    elif day_part == "大后天":
        offset = 3
    else:
        base = today + timedelta(days=(WEEKDAY[day_part[-1]] - today.weekday()) % 7 or 7)
        offset = (base - today).days
    h = int(hour)
    if period:
        if period in ("下午", "晚上") and h < 12:
            h += 12
        elif period == "中午" and h < 12:
            h = 12
    elif h <= 7:  # 没说上下午，小数字默认下午（口语习惯："3点"多为下午3点）
        h += 12
    dt = datetime.combine(base + timedelta(days=offset), datetime.min.time()).replace(
        hour=min(h, 23), minute=int(minute or 0)
    )
    return dt, True


def local_parse(text: str, now: datetime) -> list[dict[str, Any]]:
    """无 Key 降级：按标点/连接词切条，抠时间词。诚实标注 source=local。"""
    today = now.date()
    chunks = [c.strip() for c in re.split(r"[。；;！!？?\n]|然后|接着|另外|还有|以及", text) if c.strip()]
    items: list[dict[str, Any]] = []
    for c in chunks:
        c = re.sub(r"^(我|帮我|我要|我得|我需要|记得|别忘了|麻烦|请)\s*", "", c).strip()
        if len(c) < 2 or re.fullmatch(r"(要|得|需要|打算|准备|想)", c):
            continue
        deadline, _ = _deadline_from_text(c, today)
        title = _NUM_TIME.sub("", c).strip() or c
        title = re.sub(r"^(要|得|需要|打算|准备|想|去)", "", title).strip() or title
        items.append({
            "kind": "task",
            "title": title[:40],
            "deadline": deadline.isoformat() if deadline else None,
            "people": [],
            "location": None,
            "priority": "high" if any(w in c for w in _PRIORITY_WORDS) else "medium",
            "notes": c,
        })
    return items


# ---------- DeepSeek 解析 ----------

_SYSTEM_PROMPT = """你是个人行程助理。用户会用口语描述一堆要做的事。把输入拆解成结构化条目。
只输出 JSON（不要输出任何其他文字），格式：
{{"items": [{{"kind": "task", "title": "简短标题（12字内）", "deadline": "2026-09-20T15:00:00",
"people": ["老师"], "location": null, "priority": "high", "notes": "原文里的补充条件"}}],
"clarifications": ["没说清、值得问一句的点"]}}
规则：
- kind 取值 task（要做的事）/ reminder（纯时间点提醒）/ note（备忘，无时间）
- 现在是 {now}；"明天/周五/下周三/下午3点"按此推算出完整 ISO 时间；推不出就给 null
- 一句话里多个事拆成多条；寒暄和无关内容丢弃
- 宁可 null 也不猜；拿不准的写进 clarifications
- priority: 有明确截止时间=high，尽快/紧急=high，否则 medium"""


class AssistantService:
    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id

    # ---------- 配置 ----------

    def status(self) -> dict:
        return {"configured": self._key() is not None, "model": self._model()}

    def configure(self, api_key: str) -> dict:
        if len(api_key) < 8:
            raise ValidationException("API Key 格式不对")
        mgr = self._encryption()
        from app.services.settings_service import SettingsService
        svc = SettingsService(self.db, self.user_id)
        svc.set(_KEY_SETTING, mgr.encrypt(api_key).decode())
        svc.set(_MODEL_SETTING, DEFAULT_MODEL)
        return self.status()

    def _encryption(self) -> EncryptionManager:
        return EncryptionManager(Path(get_settings().data_dir))

    def _model(self) -> str:
        from app.services.settings_service import SettingsService
        return SettingsService(self.db, self.user_id).get(_MODEL_SETTING) or DEFAULT_MODEL

    def _key(self) -> str | None:
        from app.services.settings_service import SettingsService
        raw = SettingsService(self.db, self.user_id).get(_KEY_SETTING)
        if not raw:
            return None
        try:
            return self._encryption().decrypt(raw.encode())
        except Exception:
            return None  # 密钥文件被换等情况：按未配置处理，走降级

    # ---------- parse ----------

    async def parse(self, text: str) -> dict:
        text = (text or "").strip()
        if not text:
            raise ValidationException("内容为空")
        now = datetime.now()
        key = self._key()
        if key:
            try:
                items, clarifications, source = await self._deepseek_parse(text, now, key)
                if items:
                    return {"ok": True, "source": "deepseek", "items": items,
                            "clarifications": clarifications}
            except Exception:
                pass  # 网络/上游任何失败都降级，不 500
        return {"ok": True, "source": "local", "items": local_parse(text, now),
                "clarifications": [], "degraded": key is not None}

    async def _deepseek_parse(self, text: str, now: datetime, key: str) -> tuple[list, list, str]:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{DEEPSEEK_BASE}/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "model": self._model(),
                    "messages": [
                        {"role": "system", "content": _SYSTEM_PROMPT.format(now=now.isoformat())},
                        {"role": "user", "content": text},
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.2,
                    "max_tokens": 1500,
                },
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
        data = json.loads(content)
        items = [i for i in data.get("items", []) if isinstance(i, dict) and i.get("title")]
        for i in items:
            i["kind"] = i.get("kind") if i.get("kind") in ("task", "reminder", "note") else "task"
            i["priority"] = i.get("priority") if i.get("priority") in ("high", "medium", "low") else "medium"
        return items, [str(c) for c in data.get("clarifications", [])][:5], "deepseek"

    # ---------- apply（白名单落库，用户确认后） ----------

    def apply(self, items: list[dict[str, Any]]) -> dict:
        if not items or len(items) > 30:
            raise ValidationException("条目数为空或超出上限（30）")
        task_svc = TaskService(self.db)
        inbox_svc = ResourceService(self.db)
        created = {"task": 0, "reminder": 0, "note": 0}
        ids: list[str] = []
        for it in items:
            kind = it.get("kind") if it.get("kind") in ("task", "reminder", "note") else "task"
            title = str(it.get("title") or "").strip()
            if not title:
                continue
            if kind == "note":
                row = inbox_svc.create_inbox_item(
                    self.user_id, CreateInboxItemRequest(
                        content_type="text", content=title[:200], title=title[:60], source="assistant",
                    )
                )
                created["note"] += 1
            else:
                due = _parse_dt(it.get("deadline"))
                reminder = due if kind == "reminder" else None
                row = task_svc.create(self.user_id, CreateTaskRequest(
                    title=title[:200],
                    description=(it.get("notes") or None),
                    priority=it.get("priority") if it.get("priority") in ("high", "medium", "low") else "medium",
                    due_date=due.date() if due else None,
                    reminder_time=reminder,
                ))
                created["task" if kind == "task" else "reminder"] += 1
            ids.append(row["id"] if isinstance(row, dict) else row.id)
        self.db.commit()
        return {"applied": len(ids), "by_kind": created, "task_ids": ids}


def _parse_dt(v: Any) -> datetime | None:
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v))
    except ValueError:
        return None


# apply 的入参模型（api 层用）
class ApplyItem(BaseModel):
    kind: str = "task"
    title: str = Field(min_length=1, max_length=200)
    deadline: str | None = None
    people: list[str] = Field(default_factory=list)
    location: str | None = None
    priority: str = "medium"
    notes: str | None = None
