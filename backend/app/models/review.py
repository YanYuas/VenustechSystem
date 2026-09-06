# ============================================================
# reviews 表（PRD §15.10）—— data 为 JSON 灵活存储
# ============================================================
from __future__ import annotations

from datetime import date

from sqlalchemy import Date, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin
from app.models.types import JSONType


class Review(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "reviews"
    __table_args__ = (UniqueConstraint("user_id", "type", "review_date"),)

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # 项目关联（M06 F01/F05/F07：项目详情页/时间线/导出需要）
    project_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    type: Mapped[str] = mapped_column(String(10), nullable=False)
    review_date: Mapped[date] = mapped_column(Date, nullable=False)
    data: Mapped[dict] = mapped_column(JSONType, nullable=False)
