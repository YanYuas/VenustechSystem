# ============================================================
# 学习成长 Service（二期 M8 P0）
# 学习计划 + 知识卡片(SM-2) + 学习时长统计
# ============================================================
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from sqlalchemy.orm import Session

from app.core.event_bus import EVENT_FLASHCARD_REVIEWED, EVENT_STUDY_TIME_LOGGED, event_bus
from app.repositories import StudyPlanRepository, FlashcardRepository, StudyTimeRepository
from app.schemas.learning import (
    CreateStudyPlanRequest, CreateFlashcardRequest,
    ReviewSubmitRequest, CreateStudyTimeLogRequest,
)

logger = logging.getLogger("app.learning")


class LearningService:
    """学习成长 业务逻辑层"""

    def __init__(self, db: Session):
        self.db = db
        self.logger = logger
        self.plan_repo = StudyPlanRepository(db)
        self.card_repo = FlashcardRepository(db)
        self.time_repo = StudyTimeRepository(db)

    # ==================== 学习计划 ====================

    def list_plans(self, user_id: str, page: int = 1, page_size: int = 20) -> dict:
        items, total = self.plan_repo.paginate(page=page, page_size=page_size, user_id=user_id)
        return {"list": [self._plan_to_dict(p) for p in items], "total": total, "page": page, "page_size": page_size}

    def create_plan(self, user_id: str, data: CreateStudyPlanRequest) -> dict:
        plan = self.plan_repo.create(user_id=user_id, **data.model_dump(exclude_none=True))
        self.logger.info(f"学习计划创建: {plan.id}")
        return self._plan_to_dict(plan)

    def update_plan(self, plan_id: str, data: dict) -> dict:
        plan = self.plan_repo.get_or_404(plan_id)
        updated = self.plan_repo.update(plan, **data)
        return self._plan_to_dict(updated)

    def delete_plan(self, plan_id: str) -> None:
        plan = self.plan_repo.get_or_404(plan_id)
        self.plan_repo.delete(plan)

    # ==================== 知识卡片 + SM-2 ====================

    def list_cards(self, user_id: str, plan_id: str | None = None,
                   page: int = 1, page_size: int = 20) -> dict:
        filters = {"user_id": user_id}
        if plan_id:
            filters["plan_id"] = plan_id
        items, total = self.card_repo.paginate(page=page, page_size=page_size, **filters)
        return {"list": [self._card_to_dict(c) for c in items], "total": total, "page": page, "page_size": page_size}

    def create_card(self, user_id: str, data: CreateFlashcardRequest) -> dict:
        card = self.card_repo.create(
            user_id=user_id,
            next_review=date.today(),
            **data.model_dump(exclude_none=True),
        )
        self.logger.info(f"知识卡片创建: {card.id}")
        return self._card_to_dict(card)

    def update_card(self, card_id: str, data: dict) -> dict:
        card = self.card_repo.get_or_404(card_id)
        updated = self.card_repo.update(card, **data)
        return self._card_to_dict(updated)

    def delete_card(self, card_id: str) -> None:
        card = self.card_repo.get_or_404(card_id)
        self.card_repo.delete(card)

    def get_today_review(self, user_id: str) -> dict:
        """今日待复习卡片队列"""
        today = date.today()
        cards = self.card_repo.list_due_today(user_id, today)
        return {
            "list": [self._card_to_dict(c) for c in cards],
            "total": len(cards),
            "date": today.isoformat(),
        }

    def submit_review(self, card_id: str, data: ReviewSubmitRequest) -> dict:
        """
        SM-2 间隔重复算法
        quality: 0-5 (0-2=忘记, 3=困难, 4=良好, 5=容易)
        """
        card = self.card_repo.get_or_404(card_id)
        quality = data.quality
        today = date.today()

        # SM-2 核心算法
        ef = card.ef
        repetition = card.repetition
        prev_interval = card.interval

        # 更新 EF: EF' = EF + (0.1 - (5-q)*(0.08+(5-q)*0.02))
        ef = ef + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        if ef < 1.3:
            ef = 1.3

        if quality < 3:
            # 忘记：重置重复次数，明天再复习
            repetition = 0
            interval = 1
        else:
            repetition += 1
            if repetition == 1:
                interval = 1
            elif repetition == 2:
                interval = 6
            else:
                interval = round(prev_interval * ef)

        next_review = today + timedelta(days=interval)

        # 更新卡片
        updated = self.card_repo.update(
            card,
            ef=round(ef, 2),
            repetition=repetition,
            interval=interval,
            next_review=next_review,
            last_reviewed_at=datetime.utcnow(),
            review_count=card.review_count + 1,
        )

        event_bus.publish(EVENT_FLASHCARD_REVIEWED, card_id=card_id, quality=quality,
                          next_interval=interval)
        self.logger.info(f"卡片复习: {card_id}, quality={quality}, next={next_review}")

        return {
            "card_id": card_id,
            "quality": quality,
            "ef": round(ef, 2),
            "repetition": repetition,
            "interval": interval,
            "next_review": next_review.isoformat(),
        }

    # ==================== 学习时长 ====================

    def log_study_time(self, user_id: str, data: CreateStudyTimeLogRequest) -> dict:
        logged_date = data.logged_date or date.today()
        log = self.time_repo.create(
            user_id=user_id,
            logged_date=logged_date,
            **data.model_dump(exclude_none=True, exclude={"logged_date"}),
        )
        event_bus.publish(EVENT_STUDY_TIME_LOGGED, log_id=log.id, duration=log.duration)
        return self._time_to_dict(log)

    def get_time_stats(self, user_id: str, days: int = 30) -> dict:
        """学习时长统计：近N天每日时长、总时长、趋势"""
        today = date.today()
        start_date = today - timedelta(days=days - 1)
        logs = self.time_repo.list_by_date_range(user_id, start_date, today)

        # 按日期聚合
        daily_map: dict[str, int] = {}
        for log in logs:
            d = log.logged_date.isoformat() if hasattr(log.logged_date, 'isoformat') else str(log.logged_date)
            daily_map[d] = daily_map.get(d, 0) + log.duration

        # 填充空日期
        daily = []
        for i in range(days):
            d = (start_date + timedelta(days=i)).isoformat()
            daily.append({"date": d, "minutes": daily_map.get(d, 0)})

        total_minutes = sum(daily_map.values())
        avg_minutes = round(total_minutes / days, 1) if days > 0 else 0

        # 简单趋势：最近7天 vs 前7天
        recent = sum(d["minutes"] for d in daily[-7:])
        previous = sum(d["minutes"] for d in daily[-14:-7]) if len(daily) >= 14 else 0
        trend = "up" if recent > previous else ("down" if recent < previous else "stable")

        return {
            "total_minutes": total_minutes,
            "avg_minutes": avg_minutes,
            "daily": daily,
            "trend": trend,
            "days": days,
        }

    # ==================== 序列化辅助 ====================

    @staticmethod
    def _plan_to_dict(plan) -> dict:
        return {
            "id": plan.id, "name": plan.name, "description": plan.description,
            "target_date": plan.target_date.isoformat() if plan.target_date else None,
            "estimated_hours": plan.estimated_hours, "progress": plan.progress,
            "status": plan.status, "config": plan.config or {},
            "created_at": plan.created_at.isoformat(), "updated_at": plan.updated_at.isoformat(),
        }

    @staticmethod
    def _card_to_dict(card) -> dict:
        return {
            "id": card.id, "plan_id": card.plan_id,
            "front": card.front, "back": card.back, "card_type": card.card_type,
            "category": card.category, "tags": card.tags or [],
            "difficulty": card.difficulty, "ef": card.ef,
            "interval": card.interval, "repetition": card.repetition,
            "next_review": card.next_review.isoformat() if card.next_review else None,
            "last_reviewed_at": card.last_reviewed_at.isoformat() if card.last_reviewed_at else None,
            "review_count": card.review_count,
            "created_at": card.created_at.isoformat(), "updated_at": card.updated_at.isoformat(),
        }

    @staticmethod
    def _time_to_dict(log) -> dict:
        return {
            "id": log.id, "plan_id": log.plan_id, "subject": log.subject,
            "duration": log.duration, "note": log.note, "source": log.source,
            "logged_date": log.logged_date.isoformat() if hasattr(log.logged_date, 'isoformat') else str(log.logged_date),
            "created_at": log.created_at.isoformat(),
        }
