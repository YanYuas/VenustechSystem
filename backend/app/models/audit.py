# ============================================================
# 安全审计日志（mod-platform P1 · F5.4）
#
# 记录敏感动作：谁（user）在什么时候对什么（target）做了什么（action），
# 成功与否。配合加密端点的解锁门禁形成"谁能解密"的完整追溯链。
#
# 只增不改：审计记录本身不允许编辑/删除（无 API），保留 deleted_at
# 仅为满足同步引擎的表结构要求（架构守护）。
# ============================================================
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDeleteMixin, UUIDMixin, utcnow

# 审计动作白名单（新增动作必须在此登记，避免任意字符串入库）
AUDIT_ACTIONS = {
    "security.encrypt",
    "security.decrypt",
    "security.rotate_key",
    "vault.unlock",
    "vault.lock",
    "vault.reveal_secret",
    "plugin.load",
    "plugin.error",
    "sync.export",
    "sync.import",
}


class AuditLog(Base, UUIDMixin, SoftDeleteMixin):
    """安全审计日志"""

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_user_created", "user_id", "created_at"),
        Index("ix_audit_logs_action", "action"),
    )

    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ok: Mapped[bool] = mapped_column(default=True, nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    # 同步引擎（S6-3b）要求每张业务表都有 updated_at；审计表只增不改，
    # 这里与 created_at 同值即可。
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
