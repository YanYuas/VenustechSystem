# ============================================================
# 成长体系 API（S6-2）
# 经验值 / 等级 / 技能树 / 等级门槛表
# ============================================================
from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.response import success
from app.services.growth_service import (
    EXP_RULES,
    LEVEL_TABLE,
    MAX_LEVEL,
    TOTAL_EXP_TO_MAX,
    GrowthService,
)
from app.services.rules.skill_cats import SKILL_CATS

if TYPE_CHECKING:
    from app.models.user import User

router = APIRouter(prefix="/growth", tags=["成长体系"])


@router.get("/state", summary="成长状态（经验值 / 等级 / 升级进度）")
async def get_state(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(GrowthService(db).get_state(user.id))


@router.get("/events", summary="EXP 流水（最近 N 条）")
async def list_events(
    limit: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success({"list": GrowthService(db).list_events(user.id, limit)})


@router.get("/skills", summary="技能树（按累计次数降序）")
async def skill_tree(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """只返回有计数的分类；分类总数由 /growth/levels 提供。"""
    return success({"list": GrowthService(db).get_skill_tree(user.id)})


@router.get("/levels", summary="等级门槛表 + 全部技能分类 + EXP 规则")
async def levels():
    """静态元数据，供前端绘制进度条与技能选择器。

    不依赖用户数据，因此不需要鉴权之外的处理。
    """
    return success({
        "max_level": MAX_LEVEL,
        "total_exp_to_max": TOTAL_EXP_TO_MAX,
        "table": list(LEVEL_TABLE),
        "exp_rules": EXP_RULES,
        "skill_categories": [
            {"id": c.id, "name": c.name} for c in SKILL_CATS
        ],
    })
