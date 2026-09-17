# ============================================================
# identities 身份表（三期 B 阶段 · 总路线波次一「立轴」）
#
# 定位（三期规划 §4.2，勿改方向）：
#   身份是**横切维度**，不是第五个模块。任务 / 项目 / 文档 / 日记 /
#   复盘 / 分身记忆 / 项目记忆 / 收集箱都挂可空 identity_id，
#   读取端按身份过滤与聚合 —— 不制造第二份真相。
#
# 约束：
#   - color_token 只存**设计令牌名**（如 "primary"），禁止存 # 色值
#     （设计令牌唯一来源是 frontend/src/styles/variables.scss）
#   - identity_id 关联是**应用层关联**：迁移里不加外键约束
#     （SQLite 加约束需重建表，风险大；见 0015 迁移注释）
# ============================================================
from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin


class Identity(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "identities"
    __table_args__ = (
        UniqueConstraint("user_id", "slug", name="uq_identities_user_slug"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    slug: Mapped[str] = mapped_column(String(60), nullable=False)
    color_token: Mapped[str] = mapped_column(String(40), nullable=False, default="primary")
    icon: Mapped[str] = mapped_column(String(40), nullable=False, default="star")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
