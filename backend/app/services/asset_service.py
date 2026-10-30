# ============================================================
# 长期资产库 Service（二期 M10 P0）
# SOP(版本管理) + Prompt模板 + Skill技能 + 项目记忆
# ============================================================
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.event_bus import EVENT_SOP_USED, EVENT_PROMPT_USED, EVENT_PROJECT_MEMORY_CREATED, event_bus
from app.core.exceptions import NotFoundException, ValidationException
from app.repositories import SOPRepository, SOPVersionRepository, PromptRepository, SkillRepository, ProjectMemoryRepository, ProjectRepository
from app.repositories.identity_repo import IdentityRepository
from app.schemas.asset import CreateSOPRequest, CreatePromptTemplateRequest, CreateSkillRequest, CreateProjectMemoryRequest
from app.core.logger import get_logger

logger = get_logger("app.asset")


class AssetService:
    """长期资产库 业务逻辑层"""

    # ---------- PATCH 允许修改的字段白名单 ----------
    # 为什么必须有（2026-10-11 补测发现）：PATCH 端点的请求体是**裸 dict**
    # （api 层签名 `data: dict`），而 Service 侧是无差别 setattr ——
    # 客户端传 {"user_id": "<他人>"} 即可把资产改归他人，
    # 传 {"id": "x"} 甚至能改主键、让记录"消失"。
    # task_service.py 早已用 _UPDATABLE_FIELDS 白名单解决同一类问题，此处对齐。
    _SOP_FIELDS = {"name", "category", "description", "steps", "checklist", "tags"}
    _PROMPT_FIELDS = {
        "name", "category", "description", "role_setting",
        "task_description", "constraints", "output_format", "variables",
    }
    _SKILL_FIELDS = {"name", "category", "description", "methodology", "proficiency", "tags"}
    _MEMORY_FIELDS = {
        "name", "project_id", "summary", "successes", "failures",
        "extracted_assets", "key_metrics", "tags", "identity_id",
    }

    def __init__(self, db: Session):
        self.db = db
        self.logger = logger
        self.sop_repo = SOPRepository(db)
        self.sop_ver_repo = SOPVersionRepository(db)
        self.prompt_repo = PromptRepository(db)
        self.skill_repo = SkillRepository(db)
        self.memory_repo = ProjectMemoryRepository(db)
        self.project_repo = ProjectRepository(db)

    # ==================== 通用守卫 ====================

    def _owned(self, repo, obj_id: str, user_id: str, label: str):
        """按 id 取资产并校验归属，取不到或非本人一律 404。

        修复（2026-10-11）：此前 get/update/delete/use 全部直接用
        `repo.get_or_404(id)`，**只校验存在性、不校验归属**，任何人拿到
        一个 id 就能读改删他人的 SOP / Prompt / Skill / 项目记忆（IDOR）。
        本项目其余 Service（task/notification/document/life/panel/review…）
        一律在 Service 层做 `obj.user_id != user_id` 校验，此处补齐以对齐约定。
        刻意返回「不存在」而非「无权限」：不向调用方泄露该 id 是否存在。
        """
        obj = repo.get(obj_id)
        if obj is None or obj.user_id != user_id:
            raise NotFoundException(f"{label}不存在")
        return obj

    @staticmethod
    def _pick(data: dict, allowed: set[str]) -> dict:
        """只保留白名单字段；`None` 一并丢弃（PATCH 不支持把字段置空）。

        两条语义各自都有测试钉住（test_asset_production.py）：
        白名单防越权改字段，丢弃 None 保留既有契约（想清空请传空串）。
        """
        return {k: v for k, v in data.items() if k in allowed and v is not None}

    def _ensure_identity_owned(self, user_id: str, identity_id: str) -> None:
        """身份轴写入前校验（三期 B）：identity_id 无外键约束，归属在此把关。"""
        identity = IdentityRepository(self.db).get(identity_id)
        if identity is None or identity.user_id != user_id or identity.deleted_at is not None:
            raise ValidationException("身份不存在")

    def _ensure_project_owned(self, user_id: str, project_id: str) -> None:
        """项目轴写入前校验：project_id 有外键，但提前校验给出友好错误而非 500。

        修复（2026-10-11）：原先只在 create_memory 校验 identity_id，
        project_id 完全不校验，两个后果 —— 传不存在的 id 会撞外键抛
        IntegrityError（未经捕获 → 500「服务器内部错误」），传他人的 id
        则被静默接受（跨用户挂靠）。对齐 task_service._ensure_project_owned。
        D-06：查询下沉到 ProjectRepository.get_by_id（已含 user_id 过滤）。
        """
        project = self.project_repo.get_by_id(user_id, project_id)
        if project is None or project.deleted_at is not None:
            raise ValidationException("项目不存在")

    # ==================== SOP 流程 ====================

    def list_sops(self, user_id: str, category: str | None = None,
                  page: int = 1, page_size: int = 20) -> dict:
        filters = {"user_id": user_id}
        if category:
            filters["category"] = category
        items, total = self.sop_repo.paginate(page=page, page_size=page_size, **filters)
        return {"list": [self._sop_to_dict(s) for s in items], "total": total, "page": page, "page_size": page_size}

    def get_sop(self, user_id: str, sop_id: str) -> dict:
        sop = self._owned(self.sop_repo, sop_id, user_id, "SOP")
        return self._sop_to_dict(sop)

    def create_sop(self, user_id: str, data: CreateSOPRequest) -> dict:
        sop = self.sop_repo.create(user_id=user_id, **data.model_dump(exclude_none=True))
        self.logger.info("SOP创建: {}", sop.id)
        return self._sop_to_dict(sop)

    def update_sop(self, user_id: str, sop_id: str, data: dict,
                   change_note: str | None = None) -> dict:
        """更新SOP，自动保存旧版本到版本历史"""
        sop = self._owned(self.sop_repo, sop_id, user_id, "SOP")
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
        update_data = self._pick(data, self._SOP_FIELDS)
        update_data["version"] = old_version + 1
        updated = self.sop_repo.update(sop, **update_data)
        self.logger.info("SOP更新: {}, v{}→v{}", sop_id, old_version, updated.version)
        return self._sop_to_dict(updated)

    def delete_sop(self, user_id: str, sop_id: str) -> None:
        sop = self._owned(self.sop_repo, sop_id, user_id, "SOP")
        self.sop_repo.delete(sop)

    def use_sop(self, user_id: str, sop_id: str) -> dict:
        """使用SOP（计数+1，返回步骤清单）"""
        sop = self._owned(self.sop_repo, sop_id, user_id, "SOP")
        updated = self.sop_repo.update(sop, use_count=sop.use_count + 1)
        # 写完 → commit → publish：EXP 结算订阅者用独立 Session 反查 SOP
        self.db.commit()
        event_bus.publish(EVENT_SOP_USED, sop_id=sop_id, use_count=updated.use_count)
        return self._sop_to_dict(updated)

    def list_sop_versions(self, user_id: str, sop_id: str) -> dict:
        """SOP版本历史"""
        self._owned(self.sop_repo, sop_id, user_id, "SOP")
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

    def get_prompt(self, user_id: str, prompt_id: str) -> dict:
        prompt = self._owned(self.prompt_repo, prompt_id, user_id, "Prompt模板")
        return self._prompt_to_dict(prompt)

    def create_prompt(self, user_id: str, data: CreatePromptTemplateRequest) -> dict:
        prompt = self.prompt_repo.create(user_id=user_id, **data.model_dump(exclude_none=True))
        self.logger.info("Prompt创建: {}", prompt.id)
        return self._prompt_to_dict(prompt)

    def update_prompt(self, user_id: str, prompt_id: str, data: dict) -> dict:
        prompt = self._owned(self.prompt_repo, prompt_id, user_id, "Prompt模板")
        updated = self.prompt_repo.update(prompt, **self._pick(data, self._PROMPT_FIELDS))
        return self._prompt_to_dict(updated)

    def delete_prompt(self, user_id: str, prompt_id: str) -> None:
        prompt = self._owned(self.prompt_repo, prompt_id, user_id, "Prompt模板")
        self.prompt_repo.delete(prompt)

    def apply_prompt(self, user_id: str, prompt_id: str, variables: dict[str, str]) -> dict:
        """应用Prompt模板（变量替换 + 使用计数）"""
        prompt = self._owned(self.prompt_repo, prompt_id, user_id, "Prompt模板")
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
        # 写完 → commit → publish：EXP 结算订阅者用独立 Session 反查 Prompt
        self.db.commit()
        event_bus.publish(EVENT_PROMPT_USED, prompt_id=prompt_id, use_count=updated.use_count)

        return {
            "prompt_id": prompt_id,
            "rendered": full_prompt,
            "variables_used": used_vars,
            "use_count": updated.use_count,
        }

    def rate_prompt(self, user_id: str, prompt_id: str, rating: float) -> dict:
        """评分Prompt（1-5分，取平均）。

        注：评分取「上一次评分与本次的均值」（无独立评分表，无法算全量平均），
        结果保留 1 位小数。属已知设计取舍，非缺陷 —— 单条记录只存一个标量。
        范围由 API 层 Query(ge=1, le=5) 兜底。
        """
        prompt = self._owned(self.prompt_repo, prompt_id, user_id, "Prompt模板")
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
        self.logger.info("Skill创建: {}", skill.id)
        return self._skill_to_dict(skill)

    def update_skill(self, user_id: str, skill_id: str, data: dict) -> dict:
        skill = self._owned(self.skill_repo, skill_id, user_id, "技能")
        updated = self.skill_repo.update(skill, **self._pick(data, self._SKILL_FIELDS))
        return self._skill_to_dict(updated)

    def delete_skill(self, user_id: str, skill_id: str) -> None:
        skill = self._owned(self.skill_repo, skill_id, user_id, "技能")
        self.skill_repo.delete(skill)

    def use_skill(self, user_id: str, skill_id: str) -> dict:
        skill = self._owned(self.skill_repo, skill_id, user_id, "技能")
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

    def get_memory(self, user_id: str, memory_id: str) -> dict:
        memory = self._owned(self.memory_repo, memory_id, user_id, "项目记忆")
        return self._memory_to_dict(memory)

    def create_memory(self, user_id: str, data: CreateProjectMemoryRequest) -> dict:
        if data.identity_id is not None:
            self._ensure_identity_owned(user_id, data.identity_id)
        if data.project_id is not None:
            self._ensure_project_owned(user_id, data.project_id)
        memory = self.memory_repo.create(user_id=user_id, **data.model_dump(exclude_none=True))
        # 写完 → commit → publish：EXP 结算订阅者用独立 Session 反查项目记忆
        self.db.commit()
        event_bus.publish(EVENT_PROJECT_MEMORY_CREATED, memory_id=memory.id)
        self.logger.info("项目记忆创建: {}", memory.id)
        return self._memory_to_dict(memory)

    def update_memory(self, user_id: str, memory_id: str, data: dict) -> dict:
        memory = self._owned(self.memory_repo, memory_id, user_id, "项目记忆")
        update_data = self._pick(data, self._MEMORY_FIELDS)
        if update_data.get("identity_id") is not None:
            self._ensure_identity_owned(user_id, update_data["identity_id"])
        if update_data.get("project_id") is not None:
            self._ensure_project_owned(user_id, update_data["project_id"])
        updated = self.memory_repo.update(memory, **update_data)
        return self._memory_to_dict(updated)

    def delete_memory(self, user_id: str, memory_id: str) -> None:
        memory = self._owned(self.memory_repo, memory_id, user_id, "项目记忆")
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
