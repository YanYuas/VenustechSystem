# ============================================================
# 长期资产库模型（二期 M10）：SOP / Prompt / Skill / 项目记忆
# ============================================================
from __future__ import annotations

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Float, Index
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin, utcnow
from app.models.types import JSONType


class SOP(UUIDMixin, TimestampMixin, Base):
    """SOP流程"""
    __tablename__ = "sops"
    __table_args__ = (
        Index("idx_sops_user_category", "user_id", "category"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    steps: Mapped[list] = mapped_column(JSONType, default=list)
    checklist: Mapped[list] = mapped_column(JSONType, default=list)
    tags: Mapped[list] = mapped_column(JSONType, default=list)
    use_count: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)


class SOPVersion(UUIDMixin, Base):
    """SOP版本历史"""
    __tablename__ = "sop_versions"
    __table_args__ = (
        Index("idx_sop_versions_sop", "sop_id"),
    )

    sop_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sops.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[dict] = mapped_column(JSONType, default=dict)
    change_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=utcnow)


class PromptTemplate(UUIDMixin, TimestampMixin, Base):
    """Prompt模板"""
    __tablename__ = "prompt_templates"
    __table_args__ = (
        Index("idx_prompts_user_category", "user_id", "category"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    role_setting: Mapped[str | None] = mapped_column(Text, nullable=True)
    task_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    constraints: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_format: Mapped[str | None] = mapped_column(Text, nullable=True)
    variables: Mapped[list] = mapped_column(JSONType, default=list)
    use_count: Mapped[int] = mapped_column(Integer, default=0)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)


class Skill(UUIDMixin, TimestampMixin, Base):
    """Skill技能"""
    __tablename__ = "skills"
    __table_args__ = (
        Index("idx_skills_user_category", "user_id", "category"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    methodology: Mapped[str | None] = mapped_column(Text, nullable=True)  # 方法论文档
    proficiency: Mapped[str] = mapped_column(String(20), default="beginner")  # beginner/intermediate/expert
    tags: Mapped[list] = mapped_column(JSONType, default=list)
    use_count: Mapped[int] = mapped_column(Integer, default=0)


class ProjectMemory(UUIDMixin, TimestampMixin, Base):
    """项目记忆"""
    __tablename__ = "project_memories"
    __table_args__ = (
        Index("idx_project_memories_user", "user_id"),
        Index("idx_project_memories_project", "project_id"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    successes: Mapped[str | None] = mapped_column(Text, nullable=True)
    failures: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_assets: Mapped[list] = mapped_column(JSONType, default=list)
    key_metrics: Mapped[dict] = mapped_column(JSONType, default=dict)
    tags: Mapped[list] = mapped_column(JSONType, default=list)
