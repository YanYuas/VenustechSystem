# ============================================================
# 工作流 Repository（二期 P1）
# ============================================================
from __future__ import annotations

from app.repositories.base import BaseRepository
from app.models.workflow import Workflow, WorkflowApplication


class WorkflowRepository(BaseRepository[Workflow]):
    """工作流 数据访问层"""
    model = Workflow

    def list_presets(self) -> list[Workflow]:
        return self.list(is_preset=True, is_active=True)

    def list_by_user(self, user_id: str) -> list[Workflow]:
        return self.list(is_preset=False)


class WorkflowApplicationRepository(BaseRepository[WorkflowApplication]):
    """工作流应用记录 数据访问层"""
    model = WorkflowApplication
