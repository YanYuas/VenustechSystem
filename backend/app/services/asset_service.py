# ============================================================
# 长期资产库 Service（二期 M10 P0）
# SOP(版本管理) + Prompt模板 + Skill技能 + 项目记忆
# ============================================================
from __future__ import annotations

import logging
import re
from sqlalchemy.orm import Session

from app.core.event_bus import EVENT_SOP_USED, EVENT_PROMPT_USED, EVENT_PROJECT_MEMORY_CREATED, event_bus
from app.core.exceptions import ValidationException
from app.repositories import SOPRepository, SOPVersionRepository, PromptRepository, SkillRepository, ProjectMemoryRepository
from app.repositories.identity_repo import IdentityRepository
from app.schemas.asset import CreateSOPRequest, CreatePromptTemplateRequest, CreateSkillRequest, CreateProjectMemoryRequest

logger = logging.getLogger("app.asset")


class AssetService:
    """长期资产库 业务逻辑层"""

    def __init__(self, db: Session):
        self.db = db
        self.logger = logger
        self.sop_repo = SOPRepository(db)
        self.sop_ver_repo = SOPVersionRepository(db)
        self.prompt_repo = PromptRepository(db)
        self.skill_repo = SkillRepository(db)
        self.memory_repo = ProjectMemoryRepository(db)

    # ==================== SOP 流程 ====================

    def list_sops(self, user_id: str, category: str | None = None,
                  page: int = 1, page_size: int = 20) -> dict:
        filters = {"user_id": user_id}
        if category:
            filters["category"] = category
        items, total = self.sop_repo.paginate(page=page, page_size=page_size, **filters)
        return {"list": [self._sop_to_dict(s) for s in items], "total": total, "page": page, "page_size": page_size}

    def get_sop(self, sop_id: str) -> dict:
        sop = self.sop_repo.get_or_404(sop_id)
        return self._sop_to_dict(sop)

    def create_sop(self, user_id: str, data: CreateSOPRequest) -> dict:
        sop = self.sop_repo.create(user_id=user_id, **data.model_dump(exclude_none=True))
        self.logger.info(f"SOP创建: {sop.id}")
        return self._sop_to_dict(sop)

    def update_sop(self, sop_id: str, data: dict, change_note: str | None = None) -> dict:
        """更新SOP，自动保存旧版本到版本历史"""
        sop = self.sop_repo.get_or_404(sop_id)
        # 保存旧版本
        old_version = sop.version
        old_content = {
            "steps": sop.steps, "checklist": sop.checklist,
            "description": sop.description, "name": sop.name,
        }
        self.sop_ver_repo.create(
            sop_id=sop_id,
            version=old_version,
            content=old_content,
            change_note=change_note or f"更新至v{old_version + 1}",
        )
        # 更新SOP
        update_data = {k: v for k, v in data.items() if v is not None}
        update_data["version"] = old_version + 1
        updated = self.sop_repo.update(sop, **update_data)
        self.logger.info(f"SOP更新: {sop_id}, v{old_version}→v{updated.version}")
        return self._sop_to_dict(updated)

    def delete_sop(self, sop_id: str) -> None:
        sop = self.sop_repo.get_or_404(sop_id)
        self.sop_repo.delete(sop)

    def use_sop(self, sop_id: str) -> dict:
        """使用SOP（计数+1，返回步骤清单）"""
        sop = self.sop_repo.get_or_404(sop_id)
        updated = self.sop_repo.update(sop, use_count=sop.use_count + 1)
        event_bus.publish(EVENT_SOP_USED, sop_id=sop_id, use_count=updated.use_count)
        return self._sop_to_dict(updated)

    def list_sop_versions(self, sop_id: str) -> dict:
        """SOP版本历史"""
        versions = self.sop_ver_repo.list(sop_id=sop_id)
        # 按版本号降序
        versions_sorted = sorted(versions, key=lambda v: v.version, reverse=True)
        return {
            "sop_id": sop_id,
            "versions": [self._sop_ver_to_dict(v) for v in versions_sorted],
        }

    # ==================== Prompt 模板 ====================

    def list_prompts(self, user_id: str, category: str | None = None,
                     page: int = 1, page_size: int = 20) -> dict:
        filters = {"user_id": user_id}
        if category:
            filters["category"] = category
        items, total = self.prompt_repo.paginate(page=page, page_size=page_size, **filters)
        return {"list": [self._prompt_to_dict(p) for p in items], "total": total, "page": page, "page_size": page_size}

    def get_prompt(self, prompt_id: str) -> dict:
        prompt = self.prompt_repo.get_or_404(prompt_id)
        return self._prompt_to_dict(prompt)

    def create_prompt(self, user_id: str, data: CreatePromptTemplateRequest) -> dict:
        prompt = self.prompt_repo.create(user_id=user_id, **data.model_dump(exclude_none=True))
        self.logger.info(f"Prompt创建: {prompt.id}")
        return self._prompt_to_dict(prompt)

    def update_prompt(self, prompt_id: str, data: dict) -> dict:
        prompt = self.prompt_repo.get_or_404(prompt_id)
        update_data = {k: v for k, v in data.items() if v is not None}
        updated = self.prompt_repo.update(prompt, **update_data)
        return self._prompt_to_dict(updated)

    def delete_prompt(self, prompt_id: str) -> None:
        prompt = self.prompt_repo.get_or_404(prompt_id)
        self.prompt_repo.delete(prompt)

    def apply_prompt(self, prompt_id: str, variables: dict[str, str]) -> dict:
        """应用Prompt模板（变量替换 + 使用计数）"""
        prompt = self.prompt_repo.get_or_404(prompt_id)
        # 组装完整prompt
        parts = []
        if prompt.role_setting:
            parts.append(f"# 角色设定\n{prompt.role_setting}")
        if prompt.task_description:
            parts.append(f"# 任务描述\n{prompt.task_description}")
        if prompt.constraints:
            parts.append(f"# 约束条件\n{prompt.constraints}")
        if prompt.output_format:
            parts.append(f"# 输出格式\n{prompt.output_format}")
        full_prompt = "\n\n".join(parts)

        # 变量替换 {{variable}}
        used_vars = []
        for var_name, var_value in variables.items():
            placeholder = "{{" + var_name + "}}"
            if placeholder in full_prompt:
                full_prompt = full_prompt.replace(placeholder, str(var_value))
                used_vars.append(var_name)

        # 计数
        updated = self.prompt_repo.update(prompt, use_count=prompt.use_count + 1)
        event_bus.publish(EVENT_PROMPT_USED, prompt_id=prompt_id, use_count=updated.use_count)

        return {
            "prompt_id": prompt_id,
            "rendered": full_prompt,
            "variables_used": used_vars,
            "use_count": updated.use_count,
        }

    def rate_prompt(self, prompt_id: str, rating: float) -> dict:
        """评分Prompt（1-5分，取平均）"""
        prompt = self.prompt_repo.get_or_404(prompt_id)
        if prompt.rating:
            new_rating = round((prompt.rating + rating) / 2, 1)
        else:
            new_rating = rating
        updated = self.prompt_repo.update(prompt, rating=new_rating)
        return self._prompt_to_dict(updated)

    # ==================== Skill 技能库 ====================

    def list_skills(self, user_id: str, category: str | None = None,
                    page: int = 1, page_size: int = 20) -> dict:
        filters = {"user_id": user_id}
        if category:
            filters["category"] = category
        items, total = self.skill_repo.paginate(page=page, page_size=page_size, **filters)
        return {"list": [self._skill_to_dict(s) for s in items], "total": total, "page": page, "page_size": page_size}

    def create_skill(self, user_id: str, data: CreateSkillRequest) -> dict:
        skill = self.skill_repo.create(user_id=user_id, **data.model_dump(exclude_none=True))
        self.logger.info(f"Skill创建: {skill.id}")
        return self._skill_to_dict(skill)

    def update_skill(self, skill_id: str, data: dict) -> dict:
        skill = self.skill_repo.get_or_404(skill_id)
        update_data = {k: v for k, v in data.items() if v is not None}
        updated = self.skill_repo.update(skill, **update_data)
        return self._skill_to_dict(updated)

    def delete_skill(self, skill_id: str) -> None:
        skill = self.skill_repo.get_or_404(skill_id)
        self.skill_repo.delete(skill)

    def use_skill(self, skill_id: str) -> dict:
        skill = self.skill_repo.get_or_404(skill_id)
        updated = self.skill_repo.update(skill, use_count=skill.use_count + 1)
        return self._skill_to_dict(updated)

    # ==================== 项目记忆 ====================

    def list_memories(self, user_id: str, project_id: str | None = None,
                      page: int = 1, page_size: int = 20) -> dict:
        filters = {"user_id": user_id}
        if project_id:
            filters["project_id"] = project_id
        items, total = self.memory_repo.paginate(page=page, page_size=page_size, **filters)
        return {"list": [self._memory_to_dict(m) for m in items], "total": total, "page": page, "page_size": page_size}

    def get_memory(self, memory_id: str) -> dict:
        memory = self.memory_repo.get_or_404(memory_id)
        return self._memory_to_dict(memory)

    def create_memory(self, user_id: str, data: CreateProjectMemoryRequest) -> dict:
        if data.identity_id is not None:
            # 身份轴写入前校验（三期 B）：identity_id 无外键约束，归属在此把关
            identity = IdentityRepository(self.db).get(data.identity_id)
            if identity is None or identity.user_id != user_id or identity.deleted_at is not None:
                raise ValidationException("身份不存在")
        memory = self.memory_repo.create(user_id=user_id, **data.model_dump(exclude_none=True))
        event_bus.publish(EVENT_PROJECT_MEMORY_CREATED, memory_id=memory.id)
        self.logger.info(f"项目记忆创建: {memory.id}")
        return self._memory_to_dict(memory)

    def update_memory(self, memory_id: str, data: dict) -> dict:
        memory = self.memory_repo.get_or_404(memory_id)
        update_data = {k: v for k, v in data.items() if v is not None}
        updated = self.memory_repo.update(memory, **update_data)
        return self._memory_to_dict(updated)

    def delete_memory(self, memory_id: str) -> None:
        memory = self.memory_repo.get_or_404(memory_id)
        self.memory_repo.delete(memory)

    # ==================== 序列化辅助 ====================

    @staticmethod
    def _sop_to_dict(sop) -> dict:
        return {
            "id": sop.id, "name": sop.name, "category": sop.category,
            "description": sop.description, "steps": sop.steps or [],
            "checklist": sop.checklist or [], "tags": sop.tags or [],
            "use_count": sop.use_count, "version": sop.version,
            "created_at": sop.created_at.isoformat(), "updated_at": sop.updated_at.isoformat(),
        }

    @staticmethod
    def _sop_ver_to_dict(ver) -> dict:
        return {
            "id": ver.id, "sop_id": ver.sop_id, "version": ver.version,
            "content": ver.content or {}, "change_note": ver.change_note,
            "created_at": ver.created_at.isoformat() if ver.created_at else None,
        }

    @staticmethod
    def _prompt_to_dict(prompt) -> dict:
        return {
            "id": prompt.id, "name": prompt.name, "category": prompt.category,
            "description": prompt.description, "role_setting": prompt.role_setting,
            "task_description": prompt.task_description, "constraints": prompt.constraints,
            "output_format": prompt.output_format, "variables": prompt.variables or [],
            "use_count": prompt.use_count, "rating": prompt.rating,
            "created_at": prompt.created_at.isoformat(), "updated_at": prompt.updated_at.isoformat(),
        }

    @staticmethod
    def _skill_to_dict(skill) -> dict:
        return {
            "id": skill.id, "name": skill.name, "category": skill.category,
            "description": skill.description, "methodology": skill.methodology,
            "proficiency": skill.proficiency, "tags": skill.tags or [],
            "use_count": skill.use_count,
            "created_at": skill.created_at.isoformat(), "updated_at": skill.updated_at.isoformat(),
        }

    @staticmethod
    def _memory_to_dict(memory) -> dict:
        return {
            "id": memory.id, "project_id": memory.project_id, "name": memory.name,
            "summary": memory.summary, "successes": memory.successes,
            "failures": memory.failures, "extracted_assets": memory.extracted_assets or [],
            "key_metrics": memory.key_metrics or {}, "tags": memory.tags or [],
            "identity_id": memory.identity_id,
            "created_at": memory.created_at.isoformat(), "updated_at": memory.updated_at.isoformat(),
        }
