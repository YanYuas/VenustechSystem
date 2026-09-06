# ============================================================
# 学习成长 Service（二期 M8）
# 业务逻辑层：编排 Repository，处理事务与业务规则
# ============================================================
from __future__ import annotations

import logging
from sqlalchemy.orm import Session

from app.repositories import StudyPlanRepository, FlashcardRepository, StudyTimeRepository
from app.schemas.learning import CreateStudyPlanRequest, CreateFlashcardRequest, ReviewSubmitRequest, CreateStudyTimeLogRequest

logger = logging.getLogger("app.learning")


class LearningService:
    """学习成长 业务逻辑层"""

    def __init__(self, db: Session):
        self.db = db
        self.logger = logger
        self.plan_repo = StudyPlanRepository(db)
        self.card_repo = FlashcardRepository(db)
        self.time_repo = StudyTimeRepository(db)

    # ---------- 基础 CRUD ----------
    def list_plans(self, user_id: str) -> list:
        return self.plan_repo.list_by_user(user_id)

    def create_plan(self, user_id: str, data: CreateStudyPlanRequest) -> object:
        return self.plan_repo.create(user_id=user_id, **data.model_dump(exclude_none=True))

    def list_cards(self, user_id: str, plan_id: str | None = None) -> list:
        filters = {"user_id": user_id}
        if plan_id:
            filters["plan_id"] = plan_id
        return self.card_repo.list(**filters)

    def create_card(self, user_id: str, data: CreateFlashcardRequest) -> object:
        return self.card_repo.create(user_id=user_id, **data.model_dump(exclude_none=True))

    def log_study_time(self, user_id: str, data: CreateStudyTimeLogRequest) -> object:
        from datetime import date
        logged_date = data.logged_date or date.today()
        return self.time_repo.create(user_id=user_id, logged_date=logged_date, **data.model_dump(exclude_none=True, exclude={"logged_date"}))

    # ---------- SM-2 间隔重复算法 ----------
    def get_today_review(self, user_id: str) -> list:
        """获取今日待复习卡片队列"""
        from datetime import date
        return self.card_repo.list_due_today(user_id, date.today())

    def submit_review(self, card_id: str, data: ReviewSubmitRequest) -> dict:
        """提交复习结果，SM-2算法更新间隔"""
        # TODO: P0 实现 - SM-2 间隔重复算法
        # quality 0-5: 0-2=忘记, 3=困难, 4=良好, 5=容易
        return {"card_id": card_id, "quality": data.quality, "next_interval": "pending_implementation"}

    def get_time_stats(self, user_id: str, days: int = 30) -> dict:
        """学习时长统计：近N天每日时长、总时长、趋势"""
        # TODO: P0 实现 - 学习时长聚合统计
        return {"total_minutes": 0, "daily": [], "trend": "pending_implementation"}
