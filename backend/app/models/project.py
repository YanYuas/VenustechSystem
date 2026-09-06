# ============================================================
# projects 项目表 + project_milestones 里程碑表（PRD §15.x 项目管理）
# ============================================================
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin
from app.models.types import StringListType


class Project(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "projects"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    color: Mapped[str] = mapped_column(String(20), nullable=False, default="#7c5cff")
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )  # active / archived / completed
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    sort_order: Mapped[int] = mapped_column(default=0)

    tasks: Mapped[list["Task"]] = relationship(
        back_populates="project",
        primaryjoin="Project.id == Task.project_id",
        foreign_keys="Task.project_id",
    )
    milestones: Mapped[list["ProjectMilestone"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="ProjectMilestone.sort_order",
    )


class ProjectMilestone(UUIDMixin, TimestampMixin, Base):
    """项目里程碑（M06 F03）：关键节点追踪，可关联任务。"""

    __tablename__ = "project_milestones"

    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    task_ids: Mapped[list] = mapped_column(StringListType, default=list)
    sort_order: Mapped[int] = mapped_column(default=0)

    project: Mapped[Project] = relationship(back_populates="milestones")
