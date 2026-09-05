# ============================================================
# projects 项目表（PRD §15.x 项目管理）
# ============================================================
from __future__ import annotations

from datetime import date

from sqlalchemy import Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin


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
