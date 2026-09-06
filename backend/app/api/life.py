# ============================================================
# 生活记录 API（二期骨架）
# ============================================================
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/life", tags=["生活记录"])

@router.get("/habits")
async def list_habits():
    return {"code": 0, "message": "success", "data": {"module": "生活记录", "endpoint": "list_habits", "status": "skeleton"}}
@router.post("/habits")
async def create_habit():
    return {"code": 0, "message": "success", "data": {"module": "生活记录", "endpoint": "create_habit", "status": "skeleton"}}
@router.post("/habits/{habit_id}/check-in")
async def checkin_habit():
    return {"code": 0, "message": "success", "data": {"module": "生活记录", "endpoint": "checkin_habit", "status": "skeleton"}}
@router.get("/moods")
async def list_moods():
    return {"code": 0, "message": "success", "data": {"module": "生活记录", "endpoint": "list_moods", "status": "skeleton"}}
@router.post("/moods")
async def create_mood():
    return {"code": 0, "message": "success", "data": {"module": "生活记录", "endpoint": "create_mood", "status": "skeleton"}}
@router.get("/diaries")
async def list_diaries():
    return {"code": 0, "message": "success", "data": {"module": "生活记录", "endpoint": "list_diaries", "status": "skeleton"}}
