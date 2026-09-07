# ============================================================
# 桌宠 Service（二期 P1）
# 配置 + 形象管理 + 状态感知引擎
# ============================================================
from __future__ import annotations

import logging
from datetime import datetime
from sqlalchemy.orm import Session

from app.repositories.pet_repo import PetConfigRepository, PetAvatarRepository
from app.repositories.task_repo import TaskRepository
from app.repositories.mood_repo import MoodRepository
from app.schemas.pet import UpdatePetConfigRequest, CreatePetAvatarRequest

logger = logging.getLogger("app.pet")

# 时间段定义
TIME_STATES = [
    (6, 9, "morning", "清晨", "stretch", "伸懒腰", "早上好！新的一天开始了~"),
    (9, 12, "work", "工作中", "typing", "认真工作", "专注工作中，加油！"),
    (12, 14, "noon", "午休", "eating", "吃饭休息", "午饭时间到，好好休息~"),
    (14, 18, "afternoon", "下午", "thinking", "思考中", "下午容易困，喝杯水吧"),
    (18, 19, "evening", "下班", "relaxing", "放松中", "今天辛苦了！"),
    (19, 23, "night", "晚间", "reading", "休闲阅读", "晚上好，享受休闲时光"),
    (23, 24, "late_night", "深夜", "sleepy", "犯困了", "夜深了，早点休息哦"),
    (0, 6, "late_night", "深夜", "sleeping", "睡觉中", "已经很晚了，快去睡觉！"),
]

# 心情对应的气泡文案
MOOD_BUBBLES = {
    "happy": ("开心", "happy", "今天心情不错呢！"),
    "sad": ("难过", "caring", "别难过，我陪着你"),
    "anxious": ("焦虑", "encouraging", "深呼吸，一步一步来"),
    "angry": ("生气", "caring", "冷静一下，喝杯水"),
    "neutral": ("平静", "neutral", None),
}


class PetService:
    """桌宠 业务逻辑层"""

    def __init__(self, db: Session):
        self.db = db
        self.logger = logger
        self.config_repo = PetConfigRepository(db)
        self.avatar_repo = PetAvatarRepository(db)
        self.task_repo = TaskRepository(db)
        self.mood_repo = MoodRepository(db)

    # ==================== 配置管理 ====================

    def get_config(self, user_id: str) -> dict:
        config = self.config_repo.get_by_user(user_id)
        if not config:
            config = self.config_repo.create(user_id=user_id)
        return self._config_to_dict(config)

    def update_config(self, user_id: str, data: UpdatePetConfigRequest) -> dict:
        config = self.config_repo.get_by_user(user_id)
        if not config:
            config = self.config_repo.create(user_id=user_id)
        update_data = {k: v for k, v in data.model_dump(exclude_none=True).items()}
        # 如果切换了当前形象，更新is_active
        if "current_avatar_id" in update_data and update_data["current_avatar_id"]:
            self._set_active_avatar(user_id, update_data["current_avatar_id"])
        updated = self.config_repo.update(config, **update_data)
        self.logger.info(f"桌宠配置更新: {user_id}")
        return self._config_to_dict(updated)

    def _set_active_avatar(self, user_id: str, avatar_id: str) -> None:
        """设置当前激活的形象，其他设为非激活"""
        avatars = self.avatar_repo.list_by_user(user_id)
        for av in avatars:
            self.avatar_repo.update(av, is_active=(av.id == avatar_id))

    # ==================== 形象管理 ====================

    def list_avatars(self, user_id: str) -> list[dict]:
        avatars = self.avatar_repo.list_by_user(user_id)
        # 如果没有形象，创建默认形象
        if not avatars:
            default = self.avatar_repo.create(
                user_id=user_id, name="启明星", description="默认桌宠形象",
                avatar_type="builtin", mode="simple", is_active=True, sort_order=0,
            )
            avatars = [default]
        return [self._avatar_to_dict(a) for a in avatars]

    def create_avatar(self, user_id: str, data: CreatePetAvatarRequest) -> dict:
        avatar = self.avatar_repo.create(user_id=user_id, **data.model_dump(exclude_none=True))
        return self._avatar_to_dict(avatar)

    def update_avatar(self, avatar_id: str, data: dict) -> dict:
        avatar = self.avatar_repo.get_or_404(avatar_id)
        update_data = {k: v for k, v in data.items() if v is not None}
        updated = self.avatar_repo.update(avatar, **update_data)
        return self._avatar_to_dict(updated)

    def delete_avatar(self, avatar_id: str) -> None:
        avatar = self.avatar_repo.get_or_404(avatar_id)
        self.avatar_repo.delete(avatar)

    def set_active_avatar(self, user_id: str, avatar_id: str) -> dict:
        self._set_active_avatar(user_id, avatar_id)
        config = self.config_repo.get_by_user(user_id)
        if config:
            self.config_repo.update(config, current_avatar_id=avatar_id)
        return self.get_config(user_id)

    # ==================== 状态感知引擎 ====================

    def get_current_state(self, user_id: str) -> dict:
        """
        综合时间/任务/心情，计算桌宠当前状态
        """
        now = datetime.now()
        hour = now.hour

        # 1. 时间感知
        time_state = "night"
        time_label = "晚间"
        action = "reading"
        action_label = "休闲阅读"
        bubble_text = "晚上好，享受休闲时光"

        for start, end, state, label, act, act_label, bubble in TIME_STATES:
            if start <= hour < end:
                time_state, time_label, action, action_label, bubble_text = state, label, act, act_label, bubble
                break

        # 2. 任务感知
        todo_count = 0
        has_todo = False
        try:
            tasks = self.task_repo.list(user_id=user_id, status="todo", limit=10)
            todo_count = len(tasks)
            has_todo = todo_count > 0
            if has_todo and time_state in ("work", "afternoon"):
                action = "focused"
                action_label = "专注中"
                bubble_text = f"还有{todo_count}个任务待完成，加油！"
        except Exception:
            pass

        # 3. 心情感知（最近一条心情记录）
        mood = "neutral"
        mood_label = "平静"
        recent_mood = None
        try:
            moods = self.mood_repo.list(user_id=user_id, limit=1)
            if moods:
                recent_mood = moods[0].mood if hasattr(moods[0], 'mood') else None
                if recent_mood in MOOD_BUBBLES:
                    mood_label, mood, mood_bubble = MOOD_BUBBLES[recent_mood]
                    if mood_bubble:
                        bubble_text = mood_bubble
        except Exception:
            pass

        return {
            "time_state": time_state,
            "time_label": time_label,
            "action": action,
            "action_label": action_label,
            "mood": mood,
            "mood_label": mood_label,
            "bubble_text": bubble_text,
            "has_todo_tasks": has_todo,
            "todo_count": todo_count,
            "recent_mood": recent_mood,
        }

    # ==================== 序列化辅助 ====================

    @staticmethod
    def _config_to_dict(config) -> dict:
        return {
            "id": config.id, "user_id": config.user_id,
            "enabled": config.enabled, "size": config.size,
            "opacity": config.opacity, "always_on_top": config.always_on_top,
            "auto_start": config.auto_start,
            "position_x": config.position_x, "position_y": config.position_y,
            "current_avatar_id": config.current_avatar_id,
            "state_awareness_enabled": config.state_awareness_enabled,
            "action_switch_interval": config.action_switch_interval,
            "show_bubble": config.show_bubble,
            "bubble_duration": config.bubble_duration,
            "click_interaction": config.click_interaction,
            "draggable": config.draggable,
            "right_click_menu": config.right_click_menu,
            "tts_enabled": config.tts_enabled,
            "tts_voice": config.tts_voice,
            "tts_rate": config.tts_rate,
            "tts_pitch": config.tts_pitch,
            "tts_volume": config.tts_volume,
            "speak_scene": config.speak_scene,
            "updated_at": config.updated_at.isoformat(),
        }

    @staticmethod
    def _avatar_to_dict(avatar) -> dict:
        return {
            "id": avatar.id, "user_id": avatar.user_id,
            "name": avatar.name, "description": avatar.description,
            "avatar_type": avatar.avatar_type, "image_url": avatar.image_url,
            "mode": avatar.mode,
            "eye_position": avatar.eye_position or {},
            "mouth_position": avatar.mouth_position or {},
            "action_frames": avatar.action_frames or {},
            "tags": avatar.tags or [],
            "is_active": avatar.is_active,
            "sort_order": avatar.sort_order,
            "created_at": avatar.created_at.isoformat(),
            "updated_at": avatar.updated_at.isoformat(),
        }
