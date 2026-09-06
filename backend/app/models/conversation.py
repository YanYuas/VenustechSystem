# ============================================================
# conversations + messages（PRD §15.8-15.9）
# ============================================================
from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin
from app.models.types import StringListType


class Conversation(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "conversations"

    # 会话列表按 user_id 过滤，加索引
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # 项目关联（M06 F01/F05/F07：项目详情页/时间线/导出需要）
    project_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    scene: Mapped[str] = mapped_column(String(30), default="general")

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )


class Message(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "messages"

    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    referenced_doc_ids: Mapped[list] = mapped_column(StringListType, default=list)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
