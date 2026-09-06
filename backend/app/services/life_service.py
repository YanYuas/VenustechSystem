# ============================================================
# 生活记录 Service（二期 M9 P0）
# 习惯打卡 + 心情记录 + 日记
# ============================================================
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from sqlalchemy.orm import Session

from app.core.event_bus import EVENT_HABIT_CHECKIN, EVENT_MOOD_LOGGED, EVENT_DIARY_CREATED, event_bus
from app.repositories import HabitRepository, HabitCheckinRepository, MoodRepository, DiaryRepository
from app.schemas.life import CreateHabitRequest, CreateMoodLogRequest, CreateDiaryRequest

logger = logging.getLogger("app.life")


class LifeService:
    """生活记录 业务逻辑层"""

    def __init__(self, db: Session):
        self.db = db
        self.logger = logger
        self.habit_repo = HabitRepository(db)
        self.checkin_repo = HabitCheckinRepository(db)
        self.mood_repo = MoodRepository(db)
        self.diary_repo = DiaryRepository(db)

    # ==================== 习惯追踪 ====================

    def list_habits(self, user_id: str, page: int = 1, page_size: int = 20) -> dict:
        items, total = self.habit_repo.paginate(page=page, page_size=page_size, user_id=user_id)
        today = date.today()
        result = []
        for habit in items:
            checked_today = len(self.checkin_repo.list(habit_id=habit.id, checkin_date=today)) > 0
            streak = self._calc_streak(habit.id)
            d = self._habit_to_dict(habit)
            d["checked_today"] = checked_today
            d["current_streak"] = streak
            result.append(d)
        return {"list": result, "total": total, "page": page, "page_size": page_size}

    def create_habit(self, user_id: str, data: CreateHabitRequest) -> dict:
        habit = self.habit_repo.create(user_id=user_id, **data.model_dump(exclude_none=True))
        self.logger.info(f"习惯创建: {habit.id}")
        return self._habit_to_dict(habit)

    def update_habit(self, habit_id: str, data: dict) -> dict:
        habit = self.habit_repo.get_or_404(habit_id)
        updated = self.habit_repo.update(habit, **data)
        return self._habit_to_dict(updated)

    def delete_habit(self, habit_id: str) -> None:
        habit = self.habit_repo.get_or_404(habit_id)
        self.habit_repo.delete(habit)

    def checkin_habit(self, habit_id: str, checkin_date: date | None = None) -> dict:
        """习惯打卡（幂等：同一天重复打卡返回已有记录）"""
        habit = self.habit_repo.get_or_404(habit_id)
        cdate = checkin_date or date.today()
        existing = self.checkin_repo.list(habit_id=habit_id, checkin_date=cdate)
        if existing:
            return self._checkin_to_dict(existing[0])
        checkin = self.checkin_repo.create(
            habit_id=habit_id,
            user_id=habit.user_id,
            checkin_date=cdate,
        )
        event_bus.publish(EVENT_HABIT_CHECKIN, habit_id=habit_id, date=cdate.isoformat())
        self.logger.info(f"习惯打卡: {habit_id} @ {cdate}")
        return self._checkin_to_dict(checkin)

    def uncheck_habit(self, habit_id: str, checkin_date: date | None = None) -> None:
        """取消打卡"""
        cdate = checkin_date or date.today()
        records = self.checkin_repo.list(habit_id=habit_id, checkin_date=cdate)
        for r in records:
            self.checkin_repo.delete(r)

    def get_habit_calendar(self, habit_id: str, year: int, month: int) -> dict:
        """获取习惯某月打卡日历"""
        start = date(year, month, 1)
        if month == 12:
            end = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end = date(year, month + 1, 1) - timedelta(days=1)
        checkins = self.checkin_repo.list(habit_id=habit_id)
        checked_dates = set()
        for c in checkins:
            cd = c.checkin_date if hasattr(c.checkin_date, 'year') else date.fromisoformat(str(c.checkin_date))
            if start <= cd <= end:
                checked_dates.add(cd.isoformat())
        days_in_month = (end - start).days + 1
        first_weekday = start.weekday()
        calendar = []
        for _ in range(first_weekday):
            calendar.append(None)
        for day in range(1, days_in_month + 1):
            d = date(year, month, day)
            calendar.append({
                "day": day,
                "date": d.isoformat(),
                "checked": d.isoformat() in checked_dates,
                "is_today": d == date.today(),
            })
        streak = self._calc_streak(habit_id)
        return {
            "habit_id": habit_id,
            "year": year,
            "month": month,
            "calendar": calendar,
            "current_streak": streak,
            "total_checkins": len(checkins),
        }

    def _calc_streak(self, habit_id: str) -> int:
        """计算连续打卡天数（从今天往前数）"""
        today = date.today()
        streak = 0
        checkins = self.checkin_repo.list(habit_id=habit_id)
        checked_set = set()
        for c in checkins:
            cd = c.checkin_date if hasattr(c.checkin_date, 'year') else date.fromisoformat(str(c.checkin_date))
            checked_set.add(cd)
        current = today
        while current in checked_set:
            streak += 1
            current -= timedelta(days=1)
        return streak

    # ==================== 心情记录 ====================

    def list_moods(self, user_id: str, page: int = 1, page_size: int = 20) -> dict:
        items, total = self.mood_repo.paginate(page=page, page_size=page_size, user_id=user_id)
        return {"list": [self._mood_to_dict(m) for m in items], "total": total, "page": page, "page_size": page_size}

    def create_mood(self, user_id: str, data: CreateMoodLogRequest) -> dict:
        log_date = data.logged_date or date.today()
        mood = self.mood_repo.create(
            user_id=user_id,
            logged_date=log_date,
            **data.model_dump(exclude_none=True, exclude={"logged_date"}),
        )
        event_bus.publish(EVENT_MOOD_LOGGED, mood_id=mood.id, score=mood.score)
        return self._mood_to_dict(mood)

    def delete_mood(self, mood_id: str) -> None:
        mood = self.mood_repo.get_or_404(mood_id)
        self.mood_repo.delete(mood)

    def get_mood_stats(self, user_id: str, days: int = 30) -> dict:
        """心情统计：近N天平均心情、分布、趋势"""
        today = date.today()
        start_date = today - timedelta(days=days - 1)
        moods = self.mood_repo.list(user_id=user_id)
        in_range = []
        for m in moods:
            md = m.logged_date if hasattr(m.logged_date, 'year') else date.fromisoformat(str(m.logged_date))
            if start_date <= md <= today:
                in_range.append((md, m))
        if not in_range:
            return {"avg_score": 0, "count": 0, "distribution": {}, "daily": [], "trend": "stable"}
        avg_score = round(sum(m.score for _, m in in_range) / len(in_range), 1)
        distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for _, m in in_range:
            distribution[m.score] = distribution.get(m.score, 0) + 1
        daily_map: dict[str, float] = {}
        for d, m in in_range:
            daily_map[d.isoformat()] = m.score
        daily = [{"date": d, "score": daily_map[d]} for d in sorted(daily_map.keys())]
        recent = [m.score for d, m in in_range if d >= today - timedelta(days=6)]
        previous = [m.score for d, m in in_range if today - timedelta(days=13) <= d < today - timedelta(days=6)]
        recent_avg = sum(recent) / len(recent) if recent else 0
        prev_avg = sum(previous) / len(previous) if previous else 0
        trend = "up" if recent_avg > prev_avg + 0.3 else ("down" if recent_avg < prev_avg - 0.3 else "stable")
        return {
            "avg_score": avg_score,
            "count": len(in_range),
            "distribution": distribution,
            "daily": daily,
            "trend": trend,
            "days": days,
        }

    # ==================== 日记 ====================

    def list_diaries(self, user_id: str, page: int = 1, page_size: int = 20) -> dict:
        items, total = self.diary_repo.paginate(page=page, page_size=page_size, user_id=user_id)
        return {"list": [self._diary_to_dict(d) for d in items], "total": total, "page": page, "page_size": page_size}

    def get_diary(self, diary_id: str) -> dict:
        diary = self.diary_repo.get_or_404(diary_id)
        return self._diary_to_dict(diary)

    def create_diary(self, user_id: str, data: CreateDiaryRequest) -> dict:
        diary_date = data.diary_date or date.today()
        diary = self.diary_repo.create(
            user_id=user_id,
            diary_date=diary_date,
            **data.model_dump(exclude_none=True, exclude={"diary_date"}),
        )
        event_bus.publish(EVENT_DIARY_CREATED, diary_id=diary.id)
        self.logger.info(f"日记创建: {diary.id}")
        return self._diary_to_dict(diary)

    def update_diary(self, diary_id: str, data: dict) -> dict:
        diary = self.diary_repo.get_or_404(diary_id)
        updated = self.diary_repo.update(diary, **data)
        return self._diary_to_dict(updated)

    def delete_diary(self, diary_id: str) -> None:
        diary = self.diary_repo.get_or_404(diary_id)
        self.diary_repo.delete(diary)

    # ==================== 序列化辅助 ====================

    @staticmethod
    def _habit_to_dict(habit) -> dict:
        return {
            "id": habit.id, "name": habit.name,
            "icon": habit.icon, "color": habit.color,
            "frequency": habit.frequency, "target_per_week": habit.target_per_week,
            "goal_days": habit.goal_days, "status": habit.status,
            "reminder_time": habit.reminder_time.isoformat() if habit.reminder_time else None,
            "created_at": habit.created_at.isoformat(), "updated_at": habit.updated_at.isoformat(),
        }

    @staticmethod
    def _checkin_to_dict(checkin) -> dict:
        return {
            "id": checkin.id, "habit_id": checkin.habit_id,
            "checkin_date": checkin.checkin_date.isoformat() if hasattr(checkin.checkin_date, 'isoformat') else str(checkin.checkin_date),
            "note": checkin.note, "created_at": checkin.created_at.isoformat(),
        }

    @staticmethod
    def _mood_to_dict(mood) -> dict:
        return {
            "id": mood.id, "score": mood.score,
            "content": mood.content, "tags": mood.tags or [],
            "logged_date": mood.logged_date.isoformat() if hasattr(mood.logged_date, 'isoformat') else str(mood.logged_date),
            "created_at": mood.created_at.isoformat(),
        }

    @staticmethod
    def _diary_to_dict(diary) -> dict:
        return {
            "id": diary.id, "dimension": diary.dimension,
            "title": diary.title, "content": diary.content,
            "diary_date": diary.diary_date.isoformat() if hasattr(diary.diary_date, 'isoformat') else str(diary.diary_date),
            "tags": diary.tags or [],
            "created_at": diary.created_at.isoformat(), "updated_at": diary.updated_at.isoformat(),
        }
