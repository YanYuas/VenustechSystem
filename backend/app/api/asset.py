# ============================================================
# 长期资产库 API（二期骨架）
# ============================================================
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/asset", tags=["长期资产库"])

@router.get("/sops")
async def list_sops():
    return {"code": 0, "message": "success", "data": {"module": "长期资产库", "endpoint": "list_sops", "status": "skeleton"}}
@router.post("/sops")
async def create_sop():
    return {"code": 0, "message": "success", "data": {"module": "长期资产库", "endpoint": "create_sop", "status": "skeleton"}}
@router.get("/prompts")
async def list_prompts():
    return {"code": 0, "message": "success", "data": {"module": "长期资产库", "endpoint": "list_prompts", "status": "skeleton"}}
@router.post("/prompts")
async def create_prompt():
    return {"code": 0, "message": "success", "data": {"module": "长期资产库", "endpoint": "create_prompt", "status": "skeleton"}}
@router.get("/skills")
async def list_skills():
    return {"code": 0, "message": "success", "data": {"module": "长期资产库", "endpoint": "list_skills", "status": "skeleton"}}
@router.get("/memories")
async def list_memories():
    return {"code": 0, "message": "success", "data": {"module": "长期资产库", "endpoint": "list_memories", "status": "skeleton"}}
