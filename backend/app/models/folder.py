# ============================================================
# folders 表（PRD §15.4）—— 含收集箱（is_inbox）
# ============================================================
from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin


class Folder(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "folders"
    __table_args__ = (
        Index(
            "idx_folders_user_name_parent",
            "user_id",
            "parent_id",
            "name",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
        ),
    )

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    parent_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("folders.id", ondelete="SET NULL"), nullable=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_inbox: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
