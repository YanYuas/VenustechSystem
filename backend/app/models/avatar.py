# ============================================================
# 第二分身模型（二期 P1）
# 长期记忆 + 灵感 + 配置
# ============================================================
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, Integer, Float, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin, utcnow
from app.models.types import JSONType


class AvatarMemory(UUIDMixin, TimestampMixin, Base):
    """第二分身长期记忆"""
    __tablename__ = "avatar_memories"
    __table_args__ = (
        Index("idx_avatar_memories_user_type", "user_id", "memory_type"),
        Index("idx_avatar_memories_category", "category"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    memory_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # profile: 用户画像, knowledge: 知识记忆, event: 事件记忆, relation: 关系记忆
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list] = mapped_column(JSONType, default=list)
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)  # 来源：对话/文档/复盘
    source_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)  # 可信度 0-1
    is_verified: Mapped[bool] = mapped_column(default=False)  # 用户已确认
    importance: Mapped[int] = mapped_column(Integer, default=3)  # 重要度 1-5


class AvatarInspiration(UUIDMixin, TimestampMixin, Base):
    """第二分身灵感记录"""
    __tablename__ = "avatar_inspirations"
    __table_args__ = (
        Index("idx_avatar_inspirations_user", "user_id"),
        Index("idx_avatar_inspirations_status", "status"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    domain: Mapped[str | None] = mapped_column(String(50), nullable=True)  # 相关领域
    estimated_value: Mapped[str | None] = mapped_column(String(100), nullable=True)  # 预估价值
    prompt: Mapped[str | None] = mapped_column(Text, nullable=True)  # 生成的详细提示词
    result: Mapped[str | None] = mapped_column(Text, nullable=True)  # 执行结果
    status: Mapped[str] = mapped_column(String(20), default="generated")
    # generated: 已生成, selected: 已选择, executing: 执行中, completed: 已完成, discarded: 已丢弃
    feedback: Mapped[str | None] = mapped_column(String(20), nullable=True)  # useful/useless/normal
    batch_id: Mapped[str | None] = mapped_column(String(36), nullable=True)  # 同一批灵感的ID
    source_type: Mapped[str] = mapped_column(String(20), default="active")  # active/passive


class AvatarConfig(UUIDMixin, Base):
    """第二分身配置（单例，每个用户一条）"""
    __tablename__ = "avatar_configs"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    # 五档自动化 L1-L5
    automation_level: Mapped[str] = mapped_column(String(10), default="L2")
    # 模型配置
    local_model_enabled: Mapped[bool] = mapped_column(default=False)
    local_model_provider: Mapped[str | None] = mapped_column(String(20), nullable=True)  # ollama/lmstudio
    local_model_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    local_model_url: Mapped[str | None] = mapped_column(String(200), nullable=True)
    cloud_model_enabled: Mapped[bool] = mapped_column(default=True)
    cloud_model_provider: Mapped[str | None] = mapped_column(String(20), nullable=True)  # deepseek/openai
    cloud_model_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cloud_api_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # 人格设定
    persona_name: Mapped[str] = mapped_column(String(50), default="启明星")
    persona_setting: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 灵感设置
    inspiration_enabled: Mapped[bool] = mapped_column(default=True)
    inspiration_frequency: Mapped[str] = mapped_column(String(20), default="manual")  # manual/daily/weekly
    inspiration_domains: Mapped[list] = mapped_column(JSONType, default=list)
    # 对话设置
    reply_length: Mapped[str] = mapped_column(String(20), default="medium")  # short/medium/long
    language_style: Mapped[str] = mapped_column(String(20), default="professional")  # casual/professional/cute
    creativity: Mapped[float] = mapped_column(Float, default=0.7)  # 0-1
    # 单项操作自动化覆盖
    operation_overrides: Mapped[dict] = mapped_column(JSONType, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
