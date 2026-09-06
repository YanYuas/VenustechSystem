# ============================================================
# 资源中心 Service（二期 M7）
# 业务逻辑层：编排 Repository，处理事务与业务规则
# ============================================================
from __future__ import annotations

import logging
from sqlalchemy.orm import Session

from app.repositories import InboxItemRepository, TemplateRepository, DomainRepository
from app.schemas.resource import CreateInboxItemRequest, UpdateInboxItemRequest, CreateTemplateRequest, CreateDomainRequest

logger = logging.getLogger("app.resource")


class ResourceService:
    """资源中心 业务逻辑层"""

    def __init__(self, db: Session):
        self.db = db
        self.logger = logger
        self.inbox_repo = InboxItemRepository(db)
        self.template_repo = TemplateRepository(db)
        self.domain_repo = DomainRepository(db)

    # ---------- 基础 CRUD ----------
    def list_inbox(self, user_id: str, status: str | None = None) -> list:
        if status:
            return self.inbox_repo.list(user_id=user_id, status=status)
        return self.inbox_repo.list_by_user(user_id)

    def create_inbox_item(self, user_id: str, data: CreateInboxItemRequest) -> object:
        return self.inbox_repo.create(user_id=user_id, **data.model_dump(exclude_none=True))

    def update_inbox_item(self, item_id: str, data: UpdateInboxItemRequest) -> object:
        item = self.inbox_repo.get_or_404(item_id)
        return self.inbox_repo.update(item, **data.model_dump(exclude_none=True))

    def list_templates(self, user_id: str, category: str | None = None) -> list:
        filters = {"user_id": user_id}
        if category:
            filters["category"] = category
        return self.template_repo.list(**filters)

    def create_template(self, user_id: str, data: CreateTemplateRequest) -> object:
        return self.template_repo.create(user_id=user_id, **data.model_dump(exclude_none=True))

    def list_domains(self, user_id: str) -> list:
        return self.domain_repo.list_ordered(user_id)

    def create_domain(self, user_id: str, data: CreateDomainRequest) -> object:
        return self.domain_repo.create(user_id=user_id, **data.model_dump(exclude_none=True))

    # ---------- 业务方法（P0阶段实现） ----------
    def process_inbox_item(self, item_id: str, action: str, target_id: str | None = None) -> dict:
        """处理收集箱条目：转为任务/文档/归档/删除"""
        # TODO: P0 实现 - 收集箱处理工作流
        return {"item_id": item_id, "action": action, "status": "pending_implementation"}

    def apply_template(self, template_id: str, variables: dict) -> dict:
        """应用模板：变量替换生成最终内容"""
        # TODO: P0 实现 - 模板变量替换引擎
        return {"template_id": template_id, "rendered": "pending_implementation"}
