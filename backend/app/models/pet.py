# ============================================================
# 桌宠模型（二期 P1）
# 配置 + 形象
# ============================================================
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, Integer, Boolean, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin, utcnow
from app.models.types import JSONType


class PetConfig(UUIDMixin, SoftDeleteMixin, Base):
    """桌宠配置（单例，每个用户一条）"""
    __tablename__ = "pet_configs"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    # 显示设置
    enabled: Mapped[bool] = mapped_column(default=True)
    size: Mapped[str] = mapped_column(String(10), default="medium")  # small/medium/large
    opacity: Mapped[float] = mapped_column(default=1.0)  # 0.3-1.0
    always_on_top: Mapped[bool] = mapped_column(default=True)
    auto_start: Mapped[bool] = mapped_column(default=False)
    position_x: Mapped[int] = mapped_column(default=0)
    position_y: Mapped[int] = mapped_column(default=0)
    # 当前形象
    current_avatar_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # 状态感知
    state_awareness_enabled: Mapped[bool] = mapped_column(default=True)
    action_switch_interval: Mapped[int] = mapped_column(default=30)  # 秒
    show_bubble: Mapped[bool] = mapped_column(default=True)
    bubble_duration: Mapped[int] = mapped_column(default=5)  # 秒
    # 互动设置
    click_interaction: Mapped[bool] = mapped_column(default=True)
    draggable: Mapped[bool] = mapped_column(default=True)
    right_click_menu: Mapped[bool] = mapped_column(default=True)
    # 语音设置
    tts_enabled: Mapped[bool] = mapped_column(default=False)
    tts_voice: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tts_rate: Mapped[float] = mapped_column(default=1.0)  # 0.5-2.0
    tts_pitch: Mapped[float] = mapped_column(default=1.0)  # 0.5-2.0
    tts_volume: Mapped[float] = mapped_column(default=0.8)  # 0-1.0
    speak_scene: Mapped[str] = mapped_column(String(20), default="remind")  # never/remind/interact/celebrate/always
    # ---------- S6-2 四维陪伴数值（自 localStorage 迁入）----------
    # 语义沿用交付物 A：亲密度 / 饱食度 / 心情 / 精力，取值 0-100。
    #
    # 为什么必须落库：这四个数值原本只写在浏览器
    # localStorage['venustech_pet_stats']，于是不进备份、换设备即归零、
    # 清缓存全丢。而陪伴数据恰恰是用户投入时间最多、最不可再生的部分，
    # 放进易失存储与「本地优先 + 数据主权」的产品定位直接冲突。
    #
    # 衰减策略：读取时按 stats_updated_at 与当前时间差**惰性计算**，
    # 而不是靠定时任务改写数值 —— 否则会出现"应用没开就不衰减"，
    # 或后端在用户不知情时持续写库两种情况。
    intimacy: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    satiety: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    mood: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    energy: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    stats_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class PetAvatar(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    """桌宠形象（多套可切换）"""
    __tablename__ = "pet_avatars"
    __table_args__ = (
        Index("idx_pet_avatars_user", "user_id"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(String(200), nullable=True)
    avatar_type: Mapped[str] = mapped_column(String(20), default="builtin")  # builtin/custom
    # 形象数据
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)  # 主图
    mode: Mapped[str] = mapped_column(String(20), default="simple")  # simple(静态+表情)/advanced(多帧)
    # 简单模式：表情位置
    eye_position: Mapped[dict] = mapped_column(JSONType, default=dict)  # {left:{x,y}, right:{x,y}}
    mouth_position: Mapped[dict] = mapped_column(JSONType, default=dict)  # {x,y,width,height}
    # 进阶模式：多帧动作
    action_frames: Mapped[dict] = mapped_column(JSONType, default=dict)  # {idle:[url1,url2], work:[...], sleep:[...]}
    # 元数据
    tags: Mapped[list] = mapped_column(JSONType, default=list)
    is_active: Mapped[bool] = mapped_column(default=False)
    sort_order: Mapped[int] = mapped_column(default=0)
