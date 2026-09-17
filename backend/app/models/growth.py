# ============================================================
# 成长体系模型（S6-2）
#
# 三张表各司其职：
#   growth_states  —— 当前状态（经验值 / 等级），每用户一条
#   growth_events  —— EXP 流水账本，**带幂等键**（见下）
#   skill_stats    —— 技能分类累计计数（技能树的数据源）
#
# 为什么必须有 growth_events 这张流水表（而不只是在 state 上累加）
#   事件可能被重复投递：同一个任务被反复标记完成、事件在异常后重放等。
#   若直接 `state.exp += n`，重复投递就会**刷分**，且没有任何痕迹可查。
#   流水表用 (user_id, source_key) 唯一索引把幂等性固化在数据库层 ——
#   重复投递直接撞唯一约束被拒，而不是靠调用方"记得去重"。
#
# 为什么成长数据必须落库（而不是像交付物 A 那样放 localStorage）
#   交付物 A 把这套数值存在浏览器 localStorage，于是：不进备份、换设备即
#   归零、清缓存全丢。启明星是「本地优先 + 备份导入导出」，
#   成长数据落库后才第一次真正受数据主权保护 —— 这等于顺手修掉一个
#   已验证的架构缺口。
#
# 同步就绪：三张表都继承 TimestampMixin + SoftDeleteMixin，
# 因此不会拉低 W3「同步就绪性审计」的通过率。
# ============================================================
from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin
from app.models.types import JSONType

# 经验值上限（防止极端值破坏等级递推的可读性；LV30 累计约 107k）
EXP_MAX = 9_999_999


class GrowthState(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    """用户成长状态（单例，每用户一条）。"""

    __tablename__ = "growth_states"
    __table_args__ = (
        Index("idx_growth_states_user", "user_id", unique=True),
    )

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    exp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # level 由 exp 派生（见 growth_service.get_level），此处冗余存储：
    # 让「按等级排序/筛选用户」能走索引，而不必把递推公式搬进 SQL。
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class GrowthEvent(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    """EXP 流水（幂等账本）。"""

    __tablename__ = "growth_events"
    __table_args__ = (
        # 幂等键：同一 user + 同一 source_key 只允许一条
        Index("idx_growth_events_source", "user_id", "source_key", unique=True),
        Index("idx_growth_events_user", "user_id"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # 形如 "task:<id>:completed" / "flashcard:<id>:reviewed"
    # 语义是「这件事的这次结算」—— 同一件事重复投递会撞唯一索引
    source_key: Mapped[str] = mapped_column(String(200), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    exp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # 本次结算归类到的技能分类 id 列表（用于技能树溯源）
    skill_cat_ids: Mapped[list | None] = mapped_column(JSONType, nullable=True)


class SkillStat(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    """技能分类累计计数（技能树的直接数据源）。"""

    __tablename__ = "skill_stats"
    __table_args__ = (
        Index("idx_skill_stats_user_cat", "user_id", "category_id", unique=True),
    )

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    category_id: Mapped[str] = mapped_column(String(50), nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
