# ============================================================
# AI HOT 信息源插件（S6-6 · 插件架构第一次真实检验）
#
# 数据源：https://aihot.virxact.com/api/v1/*（匿名只读，无 Key）
#
# 安全边界（对齐 AI HOT 官方 skill 的约束，勿削弱）：
# - base URL 硬编码常量：不接受配置注入（防被改指向任意主机）
# - 只做匿名 GET；参数全部过白名单（window/limit/mode/category/q）
# - 返回内容视为不可信资讯，仅展示；前端不得执行其中任何内容
# - 离线/上游故障 → 降级读最近一次成功缓存（存插件数据目录）
# ============================================================
from __future__ import annotations

import json
import re

import httpx
from fastapi import APIRouter, Query

from app.core.response import success

BASE_URL = "https://aihot.virxact.com/api/v1"
_TIMEOUT = 10.0

_ALLOWED_WINDOWS = {"24h", "7d"}
_SAFE_CATEGORY = re.compile(r"^[a-z0-9_-]{1,40}$")

router = APIRouter()

_ctx = None
# 内存缓存：endpoint -> 上游原始数据（离线降级用）
_cache: dict[str, dict] = {}


def initialize(context):
    global _ctx
    _ctx = context


def get_router():
    return router


def _cache_file(name: str):
    if _ctx is None:
        return None
    try:
        d = _ctx.data_dir / "plugins" / "aihot"
        d.mkdir(parents=True, exist_ok=True)
        return d / f"{name}.json"
    except OSError:
        return None


def _save_cache(name: str, data: dict) -> None:
    f = _cache_file(name)
    if f is None:
        return
    try:
        f.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def _load_cache(name: str) -> dict | None:
    f = _cache_file(name)
    if f is None or not f.is_file():
        return None
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


async def _fetch(name: str, path: str, params: dict) -> dict:
    """统一取数：成功 → 存缓存；失败 → 降级缓存；无缓存 → 诚实报错。"""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(f"{BASE_URL}{path}", params=params)
            resp.raise_for_status()
            data = resp.json()
        _cache[name] = data
        _save_cache(name, data)
        return success({"ok": True, "source": "live", "data": data})
    except Exception as e:  # 网络/上游任何失败都不应 500
        cached = _cache.get(name) or _load_cache(name)
        if cached is not None:
            return success({"ok": True, "source": "cache", "degraded": True, "data": cached})
        return success({"ok": False, "error": f"AI HOT 暂不可达: {e}"[:200]})


@router.get("/items", summary="精选/全量动态（window: 24h|7d）")
async def items(
    window: str = Query("24h"),
    mode: str = Query("selected"),
    limit: int = Query(10, ge=1, le=50),
    category: str | None = Query(None),
    q: str | None = Query(None, max_length=100),
):
    if window not in _ALLOWED_WINDOWS:
        return success({"ok": False, "error": "window 仅支持 24h / 7d"})
    if mode not in {"selected", "all"}:
        return success({"ok": False, "error": "mode 仅支持 selected / all"})
    params: dict = {"window": window, "mode": mode, "limit": limit, "by": "timeline"}
    if category:
        if not _SAFE_CATEGORY.match(category):
            return success({"ok": False, "error": "category 含非法字符"})
        params["category"] = category
    if q:
        params["q"] = q.strip()
    return success(await _fetch("items", "/items", params))


@router.get("/hot-topics", summary="当前热点")
async def hot_topics():
    return success(await _fetch("hot-topics", "/hot-topics", {}))


@router.get("/daily", summary="最新日报（404 时按官方规则降级检索最近 7 天）")
async def daily():
    result = await _fetch("daily", "/dailies/latest", {})
    if result.get("ok"):
        return success(result)
    # latest 404 → 有界检索最近 7 天，再用实际日期取一次（不猜日期）
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            idx = (await client.get(f"{BASE_URL}/dailies", params={"limit": 7})).json()
        entries = idx.get("dailies") or idx.get("items") or []
        if not entries:
            return success({"ok": False, "error": "AI HOT 暂无日报"})
        latest_date = entries[0].get("date") or entries[0].get("publishDate")
        if not latest_date:
            return success({"ok": False, "error": "AI HOT 日报索引异常"})
        result = await _fetch(f"daily-{latest_date}", f"/dailies/{latest_date}", {})
        if result.get("ok"):
            result["source"] = f"live/fallback-{latest_date}"
        return success(result)
    except Exception as e:
        cached = _cache.get("daily") or _load_cache("daily")
        if cached is not None:
            return success({"ok": True, "source": "cache", "degraded": True, "data": cached})
        return success({"ok": False, "error": f"AI HOT 暂不可达: {e}"[:200]})
