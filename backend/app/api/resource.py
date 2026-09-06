# ============================================================
# 资源中心 API（二期骨架）
# ============================================================
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/resource", tags=["资源中心"])

@router.get("/inbox")
async def list_inbox():
    return {"code": 0, "message": "success", "data": {"module": "资源中心", "endpoint": "list_inbox", "status": "skeleton"}}
@router.post("/inbox")
async def create_inbox_item():
    return {"code": 0, "message": "success", "data": {"module": "资源中心", "endpoint": "create_inbox_item", "status": "skeleton"}}
@router.get("/templates")
async def list_templates():
    return {"code": 0, "message": "success", "data": {"module": "资源中心", "endpoint": "list_templates", "status": "skeleton"}}
@router.post("/templates")
async def create_template():
    return {"code": 0, "message": "success", "data": {"module": "资源中心", "endpoint": "create_template", "status": "skeleton"}}
@router.get("/domains")
async def list_domains():
    return {"code": 0, "message": "success", "data": {"module": "资源中心", "endpoint": "list_domains", "status": "skeleton"}}
