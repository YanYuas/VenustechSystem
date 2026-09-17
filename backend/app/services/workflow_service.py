# ============================================================
# 工作流 Service（二期 P1）
# 工作流CRUD + 一键应用引擎
# ============================================================
from __future__ import annotations

import logging
from sqlalchemy.orm import Session

from app.core.event_bus import EVENT_WORKFLOW_APPLIED, event_bus
from app.repositories import WorkflowRepository, WorkflowApplicationRepository
from app.repositories import TaskRepository, TemplateRepository, DomainRepository
from app.schemas.workflow import CreateWorkflowRequest, ApplyWorkflowRequest

logger = logging.getLogger("app.workflow")

# 注：EVENT_WORKFLOW_APPLIED 原定义在此处，2026-09-16 已归位到
# app/core/event_bus.py —— 事件常量集中存放，其他模块订阅时不必反向
# import 本业务模块，ALL_EVENTS 清单也才能穷举。（此处 import 上方即引用）


class WorkflowService:
    """工作流 业务逻辑层"""

    def __init__(self, db: Session):
        self.db = db
        self.logger = logger
        self.wf_repo = WorkflowRepository(db)
        self.app_repo = WorkflowApplicationRepository(db)
        self.task_repo = TaskRepository(db)
        self.template_repo = TemplateRepository(db)
        self.domain_repo = DomainRepository(db)

    # ==================== 工作流CRUD ====================

    def list_workflows(self, category: str | None = None,
                       page: int = 1, page_size: int = 20) -> dict:
        filters = {"is_active": True}
        if category:
            filters["category"] = category
        items, total = self.wf_repo.paginate(page=page, page_size=page_size, **filters)
        return {"list": [self._wf_to_dict(w) for w in items], "total": total, "page": page, "page_size": page_size}

    def list_presets(self) -> dict:
        """预设工作流列表"""
        items = self.wf_repo.list_presets()
        return {"list": [self._wf_to_dict(w) for w in items], "total": len(items)}

    def get_workflow(self, workflow_id: str) -> dict:
        wf = self.wf_repo.get_or_404(workflow_id)
        return self._wf_to_dict(wf)

    def create_workflow(self, user_id: str, data: CreateWorkflowRequest) -> dict:
        wf = self.wf_repo.create(**data.model_dump(exclude_none=True))
        self.logger.info(f"工作流创建: {wf.id}")
        return self._wf_to_dict(wf)

    def update_workflow(self, workflow_id: str, data: dict) -> dict:
        wf = self.wf_repo.get_or_404(workflow_id)
        update_data = {k: v for k, v in data.items() if v is not None}
        updated = self.wf_repo.update(wf, **update_data)
        return self._wf_to_dict(updated)

    def delete_workflow(self, workflow_id: str) -> None:
        wf = self.wf_repo.get_or_404(workflow_id)
        self.wf_repo.delete(wf)

    # ==================== 应用引擎 ====================

    def apply_workflow(self, user_id: str, workflow_id: str, data: ApplyWorkflowRequest) -> dict:
        """
        一键应用工作流
        自动执行：创建标签体系、导入模板、创建初始任务、记录应用历史
        """
        wf = self.wf_repo.get_or_404(workflow_id)
        config = wf.config or {}
        params = data.params or {}

        results = {
            "workflow_name": wf.name,
            "tags_created": 0,
            "templates_created": 0,
            "tasks_created": 0,
            "domains_created": 0,
            "details": [],
        }

        # 1. 创建标签体系（作为领域库）
        tag_system = config.get("tag_system", {})
        if tag_system:
            for category, tags in tag_system.items():
                for tag in tags:
                    try:
                        existing = self.domain_repo.list(name=tag)
                        if not existing:
                            self.domain_repo.create(
                                user_id=user_id,
                                name=tag,
                                icon="🏷️",
                                color="#8B5CF6",
                                sort_order=0,
                            )
                            results["domains_created"] += 1
                    except Exception as e:
                        results["details"].append(f"标签创建失败: {tag} - {e}")

        # 2. 导入文档模板
        doc_templates = config.get("doc_templates", [])
        for tpl_name in doc_templates:
            try:
                existing = self.template_repo.list(name=tpl_name)
                if not existing:
                    self.template_repo.create(
                        user_id=user_id,
                        name=tpl_name,
                        category=wf.category or "workflow",
                        content=f"# {tpl_name}\n\n由「{wf.name}」工作流自动创建\n\n",
                        variables=[],
                    )
                    results["templates_created"] += 1
            except Exception as e:
                results["details"].append(f"模板创建失败: {tpl_name} - {e}")

        # 3. 创建初始任务（基于任务模板）
        task_templates = config.get("task_templates", [])
        project_name = params.get("name") or params.get("project_name") or wf.name
        for tpl in task_templates:
            try:
                title = f"[{project_name}] {tpl['name']}"
                steps = tpl.get("steps", [])
                self.task_repo.create(
                    user_id=user_id,
                    title=title,
                    description=f"由「{wf.name}」工作流自动创建\n步骤: {' → '.join(steps)}",
                    status="todo",
                    priority="medium",
                    project_tag=wf.category or "workflow",
                )
                results["tasks_created"] += 1
            except Exception as e:
                results["details"].append(f"任务创建失败: {tpl.get('name')} - {e}")

        # 4. 更新使用计数
        self.wf_repo.update(wf, use_count=wf.use_count + 1)

        # 5. 记录应用历史
        summary = (
            f"应用「{wf.name}」: 创建{results['domains_created']}个标签, "
            f"{results['templates_created']}个模板, {results['tasks_created']}个任务"
        )
        app_record = self.app_repo.create(
            workflow_id=workflow_id,
            user_id=user_id,
            params=params,
            status="completed",
            result_summary=summary,
        )

        event_bus.publish(EVENT_WORKFLOW_APPLIED, workflow_id=workflow_id, user_id=user_id)
        self.logger.info(f"工作流应用: {workflow_id}, {summary}")

        results["application_id"] = app_record.id
        results["summary"] = summary
        return results

    def list_applications(self, user_id: str, page: int = 1, page_size: int = 20) -> dict:
        """应用历史记录"""
        items, total = self.app_repo.paginate(page=page, page_size=page_size, user_id=user_id)
        return {
            "list": [self._app_to_dict(a) for a in items],
            "total": total, "page": page, "page_size": page_size,
        }

    # ==================== 序列化辅助 ====================

    @staticmethod
    def _wf_to_dict(wf) -> dict:
        return {
            "id": wf.id, "name": wf.name, "description": wf.description,
            "icon": wf.icon, "category": wf.category, "scenario": wf.scenario,
            "config": wf.config or {}, "is_preset": wf.is_preset,
            "is_active": wf.is_active, "use_count": wf.use_count,
            "created_at": wf.created_at.isoformat(), "updated_at": wf.updated_at.isoformat(),
        }

    @staticmethod
    def _app_to_dict(app) -> dict:
        return {
            "id": app.id, "workflow_id": app.workflow_id, "user_id": app.user_id,
            "params": app.params or {}, "status": app.status,
            "result_summary": app.result_summary,
            "applied_at": app.applied_at.isoformat(),
        }
