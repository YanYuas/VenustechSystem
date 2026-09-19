# ============================================================
# 设置变更历史（mod-platform P2 · F6.2）
#
# 每次 PUT /settings 记录一条（时间 / key / 旧值 / 新值），保留最近 200 条，
# 支持单 key 回滚。敏感值在**写入时即脱敏**——历史表里永远不存密钥原文。
# ============================================================
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDeleteMixin, UUIDMixin, utcnow

# 命中这些子串的 key，其值在历史中脱敏
SENSITIVE_KEY_HINTS = ("key", "secret", "token", "password", "verifier", "salt")


def mask_value(key: str, value: str | None) -> str | None:
    """敏感值脱敏：只保留前 3 个字符 + `***`（F6.2 验收要求）。"""
    if value is None:
        return None
    if any(hint in key.lower() for hint in SENSITIVE_KEY_HINTS):
        head = value[:3] if len(value) >= 3 else ""
        return f"{head}***"
    return value[:200]


class SettingHistory(Base, UUIDMixin, SoftDeleteMixin):
    __tablename__ = "settings_history"
    __table_args__ = (
        Index("ix_settings_history_user_created", "user_id", "created_at"),
        Index("ix_settings_history_key", "key"),
    )

    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    key: Mapped[str] = mapped_column(String(200), nullable=False)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
