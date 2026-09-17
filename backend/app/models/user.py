# ============================================================
# users 表（PRD §15.1）—— 单用户，default_user
# ============================================================
from __future__ import annotations

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin
from app.models.types import JSONType


class User(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, default="default_user"
    )
    nickname: Mapped[str] = mapped_column(
        String(50), nullable=False, default="启明星用户"
    )
    avatar_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    theme: Mapped[str] = mapped_column(String(20), default="purple")
    automation_level: Mapped[str] = mapped_column(String(10), default="L2")
    pet_position: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    pet_topmost: Mapped[bool] = mapped_column(Boolean, default=True)
    inspiration_probability: Mapped[int] = mapped_column(Integer, default=60)
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    language: Mapped[str] = mapped_column(String(20), default="zh-CN")
