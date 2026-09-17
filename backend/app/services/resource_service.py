# ============================================================
# 资源中心 Service（二期 M7 P0）
# 业务逻辑层：收集箱 + 模板库 + 领域库
# ============================================================
from __future__ import annotations

import logging
import re
from datetime import datetime
from sqlalchemy.orm import Session

from app.core.event_bus import EVENT_INBOX_ITEM_CREATED, EVENT_INBOX_ITEM_PROCESSED, event_bus
from app.repositories import InboxItemRepository, TemplateRepository, DomainRepository
from app.schemas.resource import (
    CreateInboxItemRequest, UpdateInboxItemRequest,
    CreateTemplateRequest, CreateDomainRequest,
)

logger = logging.getLogger("app.resource")


class ResourceService:
    """资源中心 业务逻辑层"""

    def __init__(self, db: Session):
        self.db = db
        self.logger = logger
        self.inbox_repo = InboxItemRepository(db)
        self.template_repo = TemplateRepository(db)
        self.domain_repo = DomainRepository(db)

    # ==================== 收集箱 ====================

    def list_inbox(self, user_id: str, status: str | None = None,
                   page: int = 1, page_size: int = 20) -> dict:
        """收集箱列表（分页）"""
        filters = {"user_id": user_id}
        if status:
            filters["status"] = status
        items, total = self.inbox_repo.paginate(page=page, page_size=page_size, **filters)
        return {
            "list": [self._inbox_to_dict(i) for i in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def get_inbox_item(self, item_id: str) -> dict:
        item = self.inbox_repo.get_or_404(item_id)
        return self._inbox_to_dict(item)

    def create_inbox_item(self, user_id: str, data: CreateInboxItemRequest) -> dict:
        """创建收集箱条目，发布事件"""
        item = self.inbox_repo.create(user_id=user_id, **data.model_dump(exclude_none=True))
        event_bus.publish(EVENT_INBOX_ITEM_CREATED, item_id=item.id, user_id=user_id,
                       content_type=item.content_type)
        self.logger.info(f"收集箱条目创建: {item.id} ({item.content_type})")
        return self._inbox_to_dict(item)

    def update_inbox_item(self, item_id: str, data: UpdateInboxItemRequest) -> dict:
        item = self.inbox_repo.get_or_404(item_id)
        updated = self.inbox_repo.update(item, **data.model_dump(exclude_none=True))
        return self._inbox_to_dict(updated)

    def delete_inbox_item(self, item_id: str) -> None:
        item = self.inbox_repo.get_or_404(item_id)
        self.inbox_repo.delete(item)
        self.logger.info(f"收集箱条目删除: {item_id}")

    def process_inbox_item(self, item_id: str, action: str,
                           target_id: str | None = None) -> dict:
        """处理收集箱条目
        action: archive(归档) / delete(删除) / convert_task(转任务) / convert_doc(转文档)
        """
        item = self.inbox_repo.get_or_404(item_id)
        result = {"item_id": item_id, "action": action}

        if action == "archive":
            self.inbox_repo.update(item, status="archived", processed_at=datetime.utcnow())
            result["status"] = "archived"
        elif action == "delete":
            self.inbox_repo.delete(item)
            result["status"] = "deleted"
        elif action == "convert_task":
            # 转为任务：创建任务条目（调用task service）
            # TODO: 接入TaskService创建任务
            self.inbox_repo.update(item, status="processed", processed_at=datetime.utcnow())
            result["status"] = "processed"
            result["converted_to"] = "task"
            result["target_id"] = target_id
        elif action == "convert_doc":
            # 转为文档
            self.inbox_repo.update(item, status="processed", processed_at=datetime.utcnow())
            result["status"] = "processed"
            result["converted_to"] = "document"
            result["target_id"] = target_id
        else:
            raise ValueError(f"不支持的处理动作: {action}")

        event_bus.publish(EVENT_INBOX_ITEM_PROCESSED, item_id=item_id, action=action)
        self.logger.info(f"收集箱条目处理: {item_id} -> {action}")
        return result

    def batch_process(self, user_id: str, item_ids: list[str], action: str) -> dict:
        """批量处理收集箱条目"""
        results = []
        for item_id in item_ids:
            try:
                r = self.process_inbox_item(item_id, action)
                results.append({"id": item_id, "success": True, **r})
            except Exception as e:
                results.append({"id": item_id, "success": False, "error": str(e)})
        success_count = sum(1 for r in results if r["success"])
        return {"total": len(item_ids), "success": success_count, "failed": len(item_ids) - success_count, "results": results}

    # ==================== 模板库 ====================

    def list_templates(self, user_id: str, category: str | None = None,
                       page: int = 1, page_size: int = 20) -> dict:
        filters = {"user_id": user_id}
        if category:
            filters["category"] = category
        items, total = self.template_repo.paginate(page=page, page_size=page_size, **filters)
        return {
            "list": [self._template_to_dict(t) for t in items],
            "total": total, "page": page, "page_size": page_size,
        }

    def create_template(self, user_id: str, data: CreateTemplateRequest) -> dict:
        tpl = self.template_repo.create(user_id=user_id, **data.model_dump(exclude_none=True))
        return self._template_to_dict(tpl)

    def update_template(self, template_id: str, data: dict) -> dict:
        tpl = self.template_repo.get_or_404(template_id)
        updated = self.template_repo.update(tpl, **data)
        return self._template_to_dict(updated)

    def delete_template(self, template_id: str) -> None:
        tpl = self.template_repo.get_or_404(template_id)
        self.template_repo.delete(tpl)

    def apply_template(self, template_id: str, variables: dict) -> dict:
        """应用模板：变量替换生成最终内容"""
        tpl = self.template_repo.get_or_404(template_id)
        content = tpl.content
        # 替换 {{variable}} 格式的变量
        def replace_var(match):
            var_name = match.group(1).strip()
            return str(variables.get(var_name, match.group(0)))
        rendered = re.sub(r'\{\{(\w+)\}\}', replace_var, content)
        # 使用次数+1
        self.template_repo.update(tpl, use_count=tpl.use_count + 1)
        return {"template_id": template_id, "rendered": rendered, "variables_used": list(variables.keys())}

    # ==================== 领域库 ====================

    def list_domains(self, user_id: str) -> list:
        domains = self.domain_repo.list_ordered(user_id)
        return [self._domain_to_dict(d) for d in domains]

    def create_domain(self, user_id: str, data: CreateDomainRequest) -> dict:
        domain = self.domain_repo.create(user_id=user_id, **data.model_dump(exclude_none=True))
        return self._domain_to_dict(domain)

    def update_domain(self, domain_id: str, data: dict) -> dict:
        domain = self.domain_repo.get_or_404(domain_id)
        updated = self.domain_repo.update(domain, **data)
        return self._domain_to_dict(updated)

    def delete_domain(self, domain_id: str) -> None:
        domain = self.domain_repo.get_or_404(domain_id)
        self.domain_repo.delete(domain)

    # ==================== 序列化辅助 ====================

    @staticmethod
    def _inbox_to_dict(item) -> dict:
        return {
            "id": item.id, "content_type": item.content_type,
            "content": item.content, "title": item.title,
            "preview_url": item.preview_url, "file_path": item.file_path,
            "source": item.source, "tags": item.tags or [],
            "status": item.status, "processed_at": item.processed_at.isoformat() if item.processed_at else None,
            "created_at": item.created_at.isoformat(), "updated_at": item.updated_at.isoformat(),
        }

    @staticmethod
    def _template_to_dict(tpl) -> dict:
        return {
            "id": tpl.id, "name": tpl.name, "category": tpl.category,
            "description": tpl.description, "content": tpl.content,
            "variables": tpl.variables or [], "tags": tpl.tags or [],
            "is_builtin": tpl.is_builtin, "use_count": tpl.use_count,
            "created_at": tpl.created_at.isoformat(), "updated_at": tpl.updated_at.isoformat(),
        }

    @staticmethod
    def _domain_to_dict(domain) -> dict:
        return {
            "id": domain.id, "name": domain.name, "description": domain.description,
            "icon": domain.icon, "color": domain.color, "sort_order": domain.sort_order,
            "created_at": domain.created_at.isoformat(), "updated_at": domain.updated_at.isoformat(),
        }
