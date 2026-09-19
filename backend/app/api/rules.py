# ============================================================
# 规则引擎 API（mod-platform O6 · F4.1 / F4.3）
#
# GET  /rules/domains   领域清单（内置 + 用户扩展，带 source 标记）
# POST /rules/reload    热重载用户扩展层（无需重启）
# POST /rules/preview   调试预览：match_domain 命中 + 前 5 条计划（不落库）
# ============================================================
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.response import success
from app.services.rules import domain_engine

router = APIRouter(prefix="/rules", tags=["rules"])


class PreviewRequest(BaseModel):
    text: str = Field(..., max_length=500)


@router.get("/domains")
def list_domains():
    """领域清单：内置 + 用户扩展（F4.1）"""
    builtin = [d for d in domain_engine.DOMAIN_LIB]
    user = list(domain_engine.user_domains())
    return success({
        "builtin_count": len(builtin),
        "user_count": len(user),
        "domains": [
            {"key": d.key, "name": d.name, "source": "builtin",
             "patterns": list(d.patterns), "units": len(d.units)}
            for d in builtin
        ] + [
            {"key": d.key, "name": d.name, "source": "user",
             "patterns": list(d.patterns), "units": len(d.units)}
            for d in user
        ],
    })


@router.post("/reload")
def reload_domains():
    """热重载用户扩展领域目录（F4.1）"""
    return success(domain_engine.reload_user_domains())


@router.post("/preview")
def preview(req: PreviewRequest):
    """规则引擎调试预览（F4.3）：命中领域 + 前 5 条计划，不落库。"""
    from app.services.rules.domain_engine import (
        build_unit_defs, generic_units, match_domain,
    )

    text = (req.text or "").strip()
    if not text:
        return success({"matched": False, "reason": "empty input", "plans": []})

    domain = match_domain(text)
    if domain is None:
        units = generic_units(text)
        fallback = True
        domain_name, domain_key = None, None
    else:
        units = build_unit_defs(domain, text)
        fallback = False
        domain_name, domain_key = domain.name, domain.key

    plans = []
    for u in units[:5]:
        tasks = getattr(u, "tasks", ()) or ()
        first = tasks[0] if tasks else None
        plans.append({
            "unit": getattr(u, "name", ""),
            "task": getattr(first, "task", "") if first else "",
            "duration": getattr(first, "duration", "") if first else "",
            "acceptance": getattr(first, "acceptance", "") if first else "",
        })
    return success({
        "matched": domain is not None,
        "fallback": fallback,
        "domain_key": domain_key,
        "domain_name": domain_name,
        "matched_patterns": list(domain.patterns) if domain else [],
        "plans": plans,
        "plan_count": len(units),
    })
