# ============================================================
# 第二分身 API（二期 P1）
# 长期记忆 + 灵感工作流 + 五档配置
# ============================================================
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.response import success
from app.models.user import User
from app.schemas.avatar import CreateMemoryRequest, GenerateInspirationRequest, UpdateConfigRequest
from app.services.avatar_service import AvatarService

router = APIRouter(prefix="/avatar", tags=["第二分身"])


def _svc(db: Session) -> AvatarService:
    return AvatarService(db)


# ==================== 长期记忆 ====================

@router.get("/memories", summary="记忆列表（按类型筛选）")
async def list_memories(
    memory_type: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).list_memories(user.id, memory_type, page, page_size))


@router.get("/memories/stats", summary="记忆统计")
async def memory_stats(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(_svc(db).get_memory_stats(user.id))


@router.post("/memories", summary="创建记忆")
async def create_memory(
    data: CreateMemoryRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).create_memory(user.id, data))


@router.patch("/memories/{memory_id}", summary="更新记忆")
async def update_memory(
    memory_id: str,
    data: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).update_memory(memory_id, data))


@router.delete("/memories/{memory_id}", summary="删除记忆")
async def delete_memory(memory_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _svc(db).delete_memory(memory_id)
    return success(None)


@router.post("/memories/{memory_id}/verify", summary="确认/取消确认记忆")
async def verify_memory(
    memory_id: str,
    verified: bool = True,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).verify_memory(memory_id, verified))


# ==================== 灵感工作流 ====================

@router.post("/inspirations/generate", summary="生成灵感（一批）")
async def generate_inspirations(
    data: GenerateInspirationRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).generate_inspirations(user.id, data))


@router.get("/inspirations", summary="灵感列表")
async def list_inspirations(
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).list_inspirations(user.id, status, page, page_size))


@router.post("/inspirations/{inspiration_id}/select", summary="选择灵感（生成提示词）")
async def select_inspiration(
    inspiration_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).select_inspiration(inspiration_id))


@router.post("/inspirations/{inspiration_id}/execute", summary="执行灵感")
async def execute_inspiration(
    inspiration_id: str,
    result: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).execute_inspiration(inspiration_id, result))


@router.post("/inspirations/{inspiration_id}/feedback", summary="灵感反馈")
async def feedback_inspiration(
    inspiration_id: str,
    feedback: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).feedback_inspiration(inspiration_id, feedback))


@router.post("/inspirations/{inspiration_id}/discard", summary="丢弃灵感")
async def discard_inspiration(
    inspiration_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).discard_inspiration(inspiration_id))


# ==================== 配置管理 ====================

@router.get("/config", summary="获取分身配置")
async def get_config(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(_svc(db).get_config(user.id))


@router.patch("/config", summary="更新分身配置")
async def update_config(
    data: UpdateConfigRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).update_config(user.id, data))
