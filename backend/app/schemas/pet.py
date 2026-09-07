# ============================================================
# 桌宠 schema（二期 P1）
# ============================================================
from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class PetConfigOut(BaseModel):
    id: str
    user_id: str
    enabled: bool = True
    size: str = "medium"
    opacity: float = 1.0
    always_on_top: bool = True
    auto_start: bool = False
    position_x: int = 0
    position_y: int = 0
    current_avatar_id: str | None = None
    state_awareness_enabled: bool = True
    action_switch_interval: int = 30
    show_bubble: bool = True
    bubble_duration: int = 5
    click_interaction: bool = True
    draggable: bool = True
    right_click_menu: bool = True
    tts_enabled: bool = False
    tts_voice: str | None = None
    tts_rate: float = 1.0
    tts_pitch: float = 1.0
    tts_volume: float = 0.8
    speak_scene: str = "remind"
    updated_at: datetime


class UpdatePetConfigRequest(BaseModel):
    enabled: bool | None = None
    size: str | None = None
    opacity: float | None = None
    always_on_top: bool | None = None
    auto_start: bool | None = None
    position_x: int | None = None
    position_y: int | None = None
    current_avatar_id: str | None = None
    state_awareness_enabled: bool | None = None
    action_switch_interval: int | None = None
    show_bubble: bool | None = None
    bubble_duration: int | None = None
    click_interaction: bool | None = None
    draggable: bool | None = None
    right_click_menu: bool | None = None
    tts_enabled: bool | None = None
    tts_voice: str | None = None
    tts_rate: float | None = None
    tts_pitch: float | None = None
    tts_volume: float | None = None
    speak_scene: str | None = None


class PetAvatarOut(BaseModel):
    id: str
    user_id: str
    name: str
    description: str | None = None
    avatar_type: str = "builtin"
    image_url: str | None = None
    mode: str = "simple"
    eye_position: dict = {}
    mouth_position: dict = {}
    action_frames: dict = {}
    tags: list = []
    is_active: bool = False
    sort_order: int = 0
    created_at: datetime
    updated_at: datetime


class CreatePetAvatarRequest(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    description: str | None = None
    image_url: str | None = None
    mode: str = "simple"
    eye_position: dict = {}
    mouth_position: dict = {}
    action_frames: dict = {}
    tags: list = []


class PetStateOut(BaseModel):
    """桌宠当前状态（状态感知）"""
    time_state: str  # morning/work/noon/afternoon/evening/night/late_night
    time_label: str
    action: str  # 当前动作
    action_label: str
    mood: str  # happy/neutral/caring/encouraging
    mood_label: str
    bubble_text: str | None = None
    has_todo_tasks: bool = False
    todo_count: int = 0
    recent_mood: str | None = None
