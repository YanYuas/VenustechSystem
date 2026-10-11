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
from app.core.exceptions import NotFoundException, ValidationException
from app.repositories import InboxItemRepository, TemplateRepository, DomainRepository
from app.schemas.resource import (
    CreateInboxItemRequest, UpdateInboxItemRequest,
    CreateTemplateRequest, CreateDomainRequest,
)

logger = logging.getLogger("app.resource")

# 收集箱状态白名单：模型注释即权威（pending/processed/archived）。
# 不加白名单的话，写入任意字符串既不报错也永不出现在任何筛选结果里 —— 静默失败。
INBOX_STATUSES = {"pending", "processed", "archived"}
# 处理动作白名单（原实现落到 else 分支抛裸 ValueError → 500，这里改为 400）
PROCESS_ACTIONS = {"archive", "delete", "convert_task", "convert_doc"}

# 更新字段白名单（mass-assignment 防线）。
# 这两个端点在 API 层收的是**裸 dict**，若不加白名单则客户端可改 user_id / id /
# use_count / is_builtin —— 前者等于把记录送给别人，后者可绕过"使用次数"语义。
_TEMPLATE_UPDATABLE = {"name", "category", "description", "content", "variables", "tags"}
_DOMAIN_UPDATABLE = {"name", "description", "icon", "color", "sort_order"}


class ResourceService:
    """资源中心 业务逻辑层

    user_id（可选，构造时注入）：
      单条 读取/更新/删除/处理/应用 操作必须做归属校验。
      二期初版这些方法一律走 `repo.get_or_404(id)`，只查存在性不查归属
      —— 任何登录用户拿到 id 即可读改删他人的收集箱条目 / 模板 / 领域
      （与 asset 模块同类的 IDOR）。归属不符统一返回 404，不泄漏存在性。

      user_id 为 None 时退化为"只查存在性"，供内部统计类调用方（不接触
      他人 id）继续使用；面向用户的 API 层一律注入 user.id。
    """

    def __init__(self, db: Session, user_id: str | None = None):
        self.db = db
        self.user_id = user_id
        self.logger = logger
        self.inbox_repo = InboxItemRepository(db)
        self.template_repo = TemplateRepository(db)
        self.domain_repo = DomainRepository(db)

    # ==================== 归属校验 ====================

    def _owned(self, repo, obj_id: str):
        """按 id 取单条并校验归属；不符或不存在都抛 404（同一文案，不泄漏存在性）。"""
        obj = repo.get_or_404(obj_id)
        if self.user_id is not None and getattr(obj, "user_id", None) != self.user_id:
            raise NotFoundException("资源不存在")
        return obj

    # ==================== 收集箱 ====================

    def list_inbox(self, user_id: str, status: str | None = None,
                   page: int = 1, page_size: int = 20) -> dict:
        """收集箱列表（分页）"""
        filters = {"user_id": user_id}
        if status:
            if status not in INBOX_STATUSES:
                raise ValidationException(f"非法状态（白名单: {sorted(INBOX_STATUSES)}）")
            filters["status"] = status
        items, total = self.inbox_repo.paginate(page=page, page_size=page_size, **filters)
        return {
            "list": [self._inbox_to_dict(i) for i in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def get_inbox_item(self, item_id: str) -> dict:
        item = self._owned(self.inbox_repo, item_id)
        return self._inbox_to_dict(item)

    def create_inbox_item(self, user_id: str, data: CreateInboxItemRequest) -> dict:
        """创建收集箱条目，发布事件"""
        item = self.inbox_repo.create(user_id=user_id, **data.model_dump(exclude_none=True))
        event_bus.publish(EVENT_INBOX_ITEM_CREATED, item_id=item.id, user_id=user_id,
                       content_type=item.content_type)
        self.logger.info(f"收集箱条目创建: {item.id} ({item.content_type})")
        return self._inbox_to_dict(item)

    def update_inbox_item(self, item_id: str, data: UpdateInboxItemRequest) -> dict:
        item = self._owned(self.inbox_repo, item_id)
        payload = data.model_dump(exclude_none=True)
        status = payload.get("status")
        if status is not None and status not in INBOX_STATUSES:
            raise ValidationException(f"非法状态（白名单: {sorted(INBOX_STATUSES)}）")
        updated = self.inbox_repo.update(item, **payload)
        return self._inbox_to_dict(updated)

    def delete_inbox_item(self, item_id: str) -> None:
        item = self._owned(self.inbox_repo, item_id)
        self.inbox_repo.delete(item)
        self.logger.info(f"收集箱条目删除: {item_id}")

    def process_inbox_item(self, item_id: str, action: str,
                           target_id: str | None = None) -> dict:
        """处理收集箱条目
        action: archive(归档) / delete(删除) / convert_task(转任务) / convert_doc(转文档)
        """
        # 参数先于查询校验：非法 action 是 400，不该被"条目不存在"的 404 掩盖
        if action not in PROCESS_ACTIONS:
            raise ValidationException(f"不支持的处理动作: {action}（白名单: {sorted(PROCESS_ACTIONS)}）")
        item = self._owned(self.inbox_repo, item_id)
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
        else:  # convert_doc
            self.inbox_repo.update(item, status="processed", processed_at=datetime.utcnow())
            result["status"] = "processed"
            result["converted_to"] = "document"
            result["target_id"] = target_id

        event_bus.publish(EVENT_INBOX_ITEM_PROCESSED, item_id=item_id, action=action)
        self.logger.info(f"收集箱条目处理: {item_id} -> {action}")
        return result

    def batch_process(self, user_id: str, item_ids: list[str], action: str) -> dict:
        """批量处理收集箱条目

        逐条容错：单条失败不中断整批，结果逐条回传（调用方按 results 决定重试）。
        这是**有意的**异常收敛，不是吞异常 —— 每条失败的原因都写进结果里。
        """
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
        tpl = self._owned(self.template_repo, template_id)
        payload = {k: v for k, v in data.items()
                   if k in _TEMPLATE_UPDATABLE and v is not None}
        updated = self.template_repo.update(tpl, **payload)
        return self._template_to_dict(updated)

    def delete_template(self, template_id: str) -> None:
        tpl = self._owned(self.template_repo, template_id)
        self.template_repo.delete(tpl)

    def apply_template(self, template_id: str, variables: dict) -> dict:
        """应用模板：变量替换生成最终内容"""
        tpl = self._owned(self.template_repo, template_id)
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
        domain = self._owned(self.domain_repo, domain_id)
        payload = {k: v for k, v in data.items()
                   if k in _DOMAIN_UPDATABLE and v is not None}
        updated = self.domain_repo.update(domain, **payload)
        return self._domain_to_dict(updated)

    def delete_domain(self, domain_id: str) -> None:
        domain = self._owned(self.domain_repo, domain_id)
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
