# ============================================================
# 长期资产库 Service（二期 M10）
# 业务逻辑层：编排 Repository，处理事务与业务规则
# ============================================================
from __future__ import annotations

import logging
from sqlalchemy.orm import Session

from app.repositories import SOPRepository, PromptRepository, SkillRepository, ProjectMemoryRepository
from app.schemas.asset import CreateSOPRequest, CreatePromptTemplateRequest, CreateSkillRequest, CreateProjectMemoryRequest

logger = logging.getLogger("app.asset")


class AssetService:
    """长期资产库 业务逻辑层"""

    def __init__(self, db: Session):
        self.db = db
        self.sop_repo = SOPRepository(db)
        self.prompt_repo = PromptRepository(db)
        self.skill_repo = SkillRepository(db)
        self.memory_repo = ProjectMemoryRepository(db)

    # ---------- 基础 CRUD ----------
    def list_sops(self, user_id: str, category: str | None = None) -> list:
        filters = {"user_id": user_id}
        if category:
            filters["category"] = category
        return self.sop_repo.list(**filters)

    def create_sop(self, user_id: str, data: CreateSOPRequest) -> object:
        return self.sop_repo.create(user_id=user_id, **data.model_dump(exclude_none=True))

    def list_prompts(self, user_id: str, category: str | None = None) -> list:
        filters = {"user_id": user_id}
        if category:
            filters["category"] = category
        return self.prompt_repo.list(**filters)

    def create_prompt(self, user_id: str, data: CreatePromptTemplateRequest) -> object:
        return self.prompt_repo.create(user_id=user_id, **data.model_dump(exclude_none=True))

    def list_skills(self, user_id: str) -> list:
        return self.skill_repo.list_by_user(user_id)

    def create_skill(self, user_id: str, data: CreateSkillRequest) -> object:
        return self.skill_repo.create(user_id=user_id, **data.model_dump(exclude_none=True))

    def list_memories(self, user_id: str, project_id: str | None = None) -> list:
        if project_id:
            return self.memory_repo.list_by_project(project_id)
        return self.memory_repo.list_by_user(user_id)

    def create_memory(self, user_id: str, data: CreateProjectMemoryRequest) -> object:
        return self.memory_repo.create(user_id=user_id, **data.model_dump(exclude_none=True))

    # ---------- 业务方法 ----------
    def increment_use_count(self, repo, item_id: str) -> None:
        """通用：使用次数+1（SOP/Prompt/Skill）"""
        item = repo.get_or_404(item_id)
        repo.update(item, use_count=item.use_count + 1)

    def extract_project_memory(self, project_id: str) -> dict:
        """从项目数据自动提取记忆：成功经验/失败教训/可复用资产"""
        # TODO: P1 实现 - AI辅助项目复盘提取
        return {"project_id": project_id, "extracted": "pending_implementation"}
