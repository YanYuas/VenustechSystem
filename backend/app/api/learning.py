# ============================================================
# 学习成长 API（二期骨架）
# ============================================================
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/learning", tags=["学习成长"])

@router.get("/plans")
async def list_plans():
    return {"code": 0, "message": "success", "data": {"module": "学习成长", "endpoint": "list_plans", "status": "skeleton"}}
@router.post("/plans")
async def create_plan():
    return {"code": 0, "message": "success", "data": {"module": "学习成长", "endpoint": "create_plan", "status": "skeleton"}}
@router.get("/cards")
async def list_cards():
    return {"code": 0, "message": "success", "data": {"module": "学习成长", "endpoint": "list_cards", "status": "skeleton"}}
@router.post("/cards")
async def create_card():
    return {"code": 0, "message": "success", "data": {"module": "学习成长", "endpoint": "create_card", "status": "skeleton"}}
@router.get("/review/today")
async def today_review():
    return {"code": 0, "message": "success", "data": {"module": "学习成长", "endpoint": "today_review", "status": "skeleton"}}
@router.get("/time/stats")
async def time_stats():
    return {"code": 0, "message": "success", "data": {"module": "学习成长", "endpoint": "time_stats", "status": "skeleton"}}
