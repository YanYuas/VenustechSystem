# ============================================================
# 长期资产库 API（二期 M10 P0）
# SOP + Prompt模板 + Skill技能 + 项目记忆
# ============================================================
from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.response import success
from app.schemas.asset import CreateSOPRequest, CreatePromptTemplateRequest, CreateSkillRequest, CreateProjectMemoryRequest
from app.services.asset_service import AssetService

if TYPE_CHECKING:
    # 仅用于 user 参数的类型标注（依赖注入由 deps.get_current_user 提供），
    # 运行期不需要该名字 —— 架构守护测试要求 api 层不得运行时 import models。
    from app.models.user import User

router = APIRouter(prefix="/assets", tags=["长期资产库"])


def _svc(db: Session) -> AssetService:
    return AssetService(db)


# ==================== SOP 流程 ====================

@router.get("/sops", summary="SOP列表（分页+分类筛选）")
async def list_sops(
    category: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).list_sops(user.id, category, page, page_size))


@router.get("/sops/{sop_id}", summary="SOP详情")
async def get_sop(sop_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(_svc(db).get_sop(sop_id))


@router.post("/sops", summary="创建SOP")
async def create_sop(
    data: CreateSOPRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).create_sop(user.id, data))


@router.patch("/sops/{sop_id}", summary="更新SOP（自动版本管理）")
async def update_sop(
    sop_id: str,
    data: dict,
    change_note: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).update_sop(sop_id, data, change_note))


@router.delete("/sops/{sop_id}", summary="删除SOP")
async def delete_sop(sop_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _svc(db).delete_sop(sop_id)
    return success(None)


@router.post("/sops/{sop_id}/use", summary="使用SOP（计数+返回步骤）")
async def use_sop(sop_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(_svc(db).use_sop(sop_id))


@router.get("/sops/{sop_id}/versions", summary="SOP版本历史")
async def list_sop_versions(sop_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(_svc(db).list_sop_versions(sop_id))


# ==================== Prompt 模板 ====================

@router.get("/prompts", summary="Prompt模板列表")
async def list_prompts(
    category: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).list_prompts(user.id, category, page, page_size))


@router.get("/prompts/{prompt_id}", summary="Prompt详情")
async def get_prompt(prompt_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(_svc(db).get_prompt(prompt_id))


@router.post("/prompts", summary="创建Prompt模板")
async def create_prompt(
    data: CreatePromptTemplateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).create_prompt(user.id, data))


@router.patch("/prompts/{prompt_id}", summary="更新Prompt模板")
async def update_prompt(
    prompt_id: str,
    data: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).update_prompt(prompt_id, data))


@router.delete("/prompts/{prompt_id}", summary="删除Prompt模板")
async def delete_prompt(prompt_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _svc(db).delete_prompt(prompt_id)
    return success(None)


@router.post("/prompts/{prompt_id}/apply", summary="应用Prompt模板（变量替换）")
async def apply_prompt(
    prompt_id: str,
    variables: dict[str, str],
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).apply_prompt(prompt_id, variables))


@router.post("/prompts/{prompt_id}/rate", summary="评分Prompt模板")
async def rate_prompt(
    prompt_id: str,
    rating: float,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).rate_prompt(prompt_id, rating))


# ==================== Skill 技能库 ====================

@router.get("/skills", summary="技能列表")
async def list_skills(
    category: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).list_skills(user.id, category, page, page_size))


@router.post("/skills", summary="创建技能")
async def create_skill(
    data: CreateSkillRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).create_skill(user.id, data))


@router.patch("/skills/{skill_id}", summary="更新技能")
async def update_skill(
    skill_id: str,
    data: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).update_skill(skill_id, data))


@router.delete("/skills/{skill_id}", summary="删除技能")
async def delete_skill(skill_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _svc(db).delete_skill(skill_id)
    return success(None)


@router.post("/skills/{skill_id}/use", summary="使用技能（计数）")
async def use_skill(skill_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(_svc(db).use_skill(skill_id))


# ==================== 项目记忆 ====================

@router.get("/memories", summary="项目记忆列表")
async def list_memories(
    project_id: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).list_memories(user.id, project_id, page, page_size))


@router.get("/memories/{memory_id}", summary="项目记忆详情")
async def get_memory(memory_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(_svc(db).get_memory(memory_id))


@router.post("/memories", summary="创建项目记忆")
async def create_memory(
    data: CreateProjectMemoryRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).create_memory(user.id, data))


@router.patch("/memories/{memory_id}", summary="更新项目记忆")
async def update_memory(
    memory_id: str,
    data: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db).update_memory(memory_id, data))


@router.delete("/memories/{memory_id}", summary="删除项目记忆")
async def delete_memory(memory_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _svc(db).delete_memory(memory_id)
    return success(None)
