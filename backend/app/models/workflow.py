# ============================================================
# 工作流模型（二期 P1）
# ============================================================
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin, utcnow
from app.models.types import JSONType


class Workflow(UUIDMixin, TimestampMixin, Base):
    """工作流定义"""
    __tablename__ = "workflows"
    __table_args__ = (
        Index("idx_workflows_category", "category"),
        Index("idx_workflows_is_preset", "is_preset"),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)  # study/dev/writing/custom
    scenario: Mapped[str | None] = mapped_column(String(200), nullable=True)  # 适用场景
    # 完整工作流配置：模块组合/文件夹结构/标签体系/任务模板/文档模板/SOP/自动化规则/视图配置
    config: Mapped[dict] = mapped_column(JSONType, default=dict)
    is_preset: Mapped[bool] = mapped_column(default=False)  # 是否预设
    is_active: Mapped[bool] = mapped_column(default=True)
    use_count: Mapped[int] = mapped_column(default=0)


class WorkflowApplication(UUIDMixin, Base):
    """工作流应用记录"""
    __tablename__ = "workflow_applications"
    __table_args__ = (
        Index("idx_workflow_apps_user", "user_id"),
        Index("idx_workflow_apps_workflow", "workflow_id"),
    )

    workflow_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    params: Mapped[dict] = mapped_column(JSONType, default=dict)  # 应用时的参数
    status: Mapped[str] = mapped_column(String(20), default="completed")  # pending/completed/failed
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
