# ============================================================
# 生活记录 Service（二期 M9）
# 业务逻辑层：编排 Repository，处理事务与业务规则
# ============================================================
from __future__ import annotations

import logging
from sqlalchemy.orm import Session

from app.repositories import HabitRepository, HabitCheckinRepository, MoodRepository, DiaryRepository
from app.schemas.life import CreateHabitRequest, CreateMoodLogRequest, CreateDiaryRequest

logger = logging.getLogger("app.life")


class LifeService:
    """生活记录 业务逻辑层"""

    def __init__(self, db: Session):
        self.db = db
        self.habit_repo = HabitRepository(db)
        self.checkin_repo = HabitCheckinRepository(db)
        self.mood_repo = MoodRepository(db)
        self.diary_repo = DiaryRepository(db)

    # ---------- 基础 CRUD ----------
    def list_habits(self, user_id: str) -> list:
        return self.habit_repo.list_active(user_id)

    def create_habit(self, user_id: str, data: CreateHabitRequest) -> object:
        return self.habit_repo.create(user_id=user_id, **data.model_dump(exclude_none=True))

    def checkin_habit(self, user_id: str, habit_id: str, note: str | None = None) -> dict:
        from datetime import date
        today = date.today()
        existing = self.checkin_repo.get_by_date(habit_id, today)
        if existing:
            return {"habit_id": habit_id, "date": today.isoformat(), "already_checked": True}
        self.checkin_repo.create(user_id=user_id, habit_id=habit_id, checkin_date=today, note=note)
        return {"habit_id": habit_id, "date": today.isoformat(), "status": "checked"}

    def log_mood(self, user_id: str, data: CreateMoodLogRequest) -> object:
        from datetime import date
        logged_date = data.logged_date or date.today()
        return self.mood_repo.create(user_id=user_id, logged_date=logged_date, **data.model_dump(exclude_none=True, exclude={"logged_date"}))

    def list_diaries(self, user_id: str, dimension: str | None = None) -> list:
        if dimension:
            return self.diary_repo.list_by_dimension(user_id, dimension)
        return self.diary_repo.list_by_user(user_id)

    def create_diary(self, user_id: str, data: CreateDiaryRequest) -> object:
        from datetime import date
        diary_date = data.diary_date or date.today()
        return self.diary_repo.create(user_id=user_id, diary_date=diary_date, **data.model_dump(exclude_none=True, exclude={"diary_date"}))

    # ---------- 业务方法 ----------
    def get_habit_streak(self, habit_id: str) -> dict:
        """计算习惯连续打卡天数"""
        # TODO: P0 实现 - 连续打卡计算
        return {"habit_id": habit_id, "current_streak": 0, "longest_streak": 0}

    def get_mood_trend(self, user_id: str, days: int = 30) -> dict:
        """心情趋势分析：平均分、情绪分布、关联标签"""
        # TODO: P0 实现 - 心情趋势聚合
        return {"avg_score": 0, "distribution": {}, "trend": "pending_implementation"}
