# ============================================================
# Learning Service 生产级测试
#
# 三大子模块：学习计划（StudyPlan）、知识卡片（Flashcard + SM-2）、学习时长（StudyTimeLog）
#
# 标准：真数据夹具 + 写操作后查库验证 + SM-2算法正确性 + 增量隔离 + 负向断言
# ============================================================
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from app.core.exceptions import NotFoundException
from app.models.learning import Flashcard, StudyPlan, StudyTimeLog
from app.schemas.learning import (
    CreateFlashcardRequest,
    CreateStudyPlanRequest,
    CreateStudyTimeLogRequest,
    ReviewSubmitRequest,
)
from app.services.learning_service import LearningService
from tests.factories import count_rows


def _make_plan(name="数学分析", **overrides):
    """构造 CreateStudyPlanRequest，所有字段有默认值，可覆盖。"""
    defaults = dict(name=name, description="计划描述", target_date=date(2026, 12, 31),
                     estimated_hours=100)
    defaults.update(overrides)
    return CreateStudyPlanRequest(**defaults)


def _make_card(front="问题", back="答案", **overrides):
    """构造 CreateFlashcardRequest，所有字段有默认值，可覆盖。"""
    defaults = dict(front=front, back=back, card_type="qa", difficulty=3)
    defaults.update(overrides)
    return CreateFlashcardRequest(**defaults)


# ============================================================
# 第 1 组：学习计划 + 知识卡片 + SM-2 + 学习时长
# ============================================================

class TestGroup1PlanCardReviewTime:
    """第1组：计划CRUD + 卡片创建 + SM-2算法 + 学习时长记录。"""

    def test_create_plan_persists_to_db(self, db_session, test_user):
        """创建学习计划后查库验证 name/description/target_date/estimated_hours/user_id。

        防什么：create_plan 如果漏了某个字段，计划创建后该字段为 None，
        前端展示异常。
        """
        svc = LearningService(db_session)
        out = svc.create_plan(test_user.id, _make_plan(
            name="高等代数", description="系统学习线性代数",
            target_date=date(2027, 1, 15), estimated_hours=80,
        ))

        assert out["name"] == "高等代数"
        assert out["status"] == "active"
        assert out["progress"] == 0

        # 查库验证
        db_session.expire_all()
        in_db = db_session.get(StudyPlan, out["id"])
        assert in_db is not None
        assert in_db.name == "高等代数"
        assert in_db.description == "系统学习线性代数"
        assert in_db.target_date == date(2027, 1, 15)
        assert in_db.estimated_hours == 80
        assert in_db.user_id == test_user.id
        assert in_db.status == "active"

    def test_list_plans_pagination(self, db_session, test_user):
        """学习计划分页列表：page_size 限制返回数量，total 是总数。

        防什么：paginate 如果 total 计算错误，前端分页器显示错误的页数。
        """
        svc = LearningService(db_session)
        for i in range(5):
            svc.create_plan(test_user.id, _make_plan(name=f"计划{i}"))

        # 第 1 页，page_size=2
        page1 = svc.list_plans(test_user.id, page=1, page_size=2)
        assert len(page1["list"]) == 2
        assert page1["total"] == 5
        assert page1["page"] == 1

        # 第 3 页，page_size=2（只有 1 条）
        page3 = svc.list_plans(test_user.id, page=3, page_size=2)
        assert len(page3["list"]) == 1
        assert page3["total"] == 5

    def test_create_card_sets_next_review_today(self, db_session, test_user):
        """创建知识卡片后，next_review 自动设为今天，查库验证。

        防什么：create_card 如果漏了 next_review=date.today()，新卡片
        不会出现在今日复习队列中。
        """
        svc = LearningService(db_session)
        out = svc.create_card(test_user.id, _make_card(
            front="什么是极限？", back="极限是...", category="数学分析", difficulty=4,
        ))

        assert out["front"] == "什么是极限？"
        assert out["next_review"] == date.today().isoformat()
        assert out["ef"] == 2.5
        assert out["interval"] == 0
        assert out["repetition"] == 0

        # 查库验证
        db_session.expire_all()
        in_db = db_session.get(Flashcard, out["id"])
        assert in_db.next_review == date.today()
        assert in_db.ef == 2.5
        assert in_db.review_count == 0

    def test_submit_review_quality_5_increases_interval(self, db_session, test_user):
        """SM-2 算法：quality=5（容易）时，第一次复习后 interval=1，第二次后 interval=6。

        防什么：SM-2 算法如果 interval 计算错误，卡片复习间隔会异常，
        间隔重复效果失效。
        """
        svc = LearningService(db_session)
        card = svc.create_card(test_user.id, _make_card(front="Q", back="A"))
        card_id = card["id"]

        # 第一次复习 quality=5 → repetition=1, interval=1
        result1 = svc.submit_review(test_user.id, card_id, ReviewSubmitRequest(quality=5))
        assert result1["repetition"] == 1
        assert result1["interval"] == 1
        assert result1["next_review"] == (date.today() + timedelta(days=1)).isoformat()

        # 查库验证
        db_session.expire_all()
        in_db = db_session.get(Flashcard, card_id)
        assert in_db.repetition == 1
        assert in_db.interval == 1
        assert in_db.review_count == 1

        # 第二次复习 quality=5 → repetition=2, interval=6
        result2 = svc.submit_review(test_user.id, card_id, ReviewSubmitRequest(quality=5))
        assert result2["repetition"] == 2
        assert result2["interval"] == 6

    def test_log_study_time_persists(self, db_session, test_user):
        """记录学习时长后查库验证 duration/subject/logged_date/user_id。

        防什么：log_study_time 如果漏了 logged_date 默认值（今天），
        记录的日期会是 None，统计时丢失。
        """
        svc = LearningService(db_session)
        out = svc.log_study_time(test_user.id, CreateStudyTimeLogRequest(
            duration=45, subject="数学分析", note="第三章极限", source="manual",
        ))

        assert out["duration"] == 45
        assert out["subject"] == "数学分析"
        assert out["logged_date"] == date.today().isoformat()

        # 查库验证
        db_session.expire_all()
        in_db = db_session.get(StudyTimeLog, out["id"])
        assert in_db is not None
        assert in_db.duration == 45
        assert in_db.subject == "数学分析"
        assert in_db.logged_date == date.today()
        assert in_db.user_id == test_user.id


# ============================================================
# 第 2 组：SM-2忘记重置 + 今日复习队列 + 时长统计 + 计划更新删除 + 卡片更新删除
# ============================================================

class TestGroup2Sm2BoundaryStatsUpdateDelete:
    """第2组：SM-2 quality<3重置 + 今日复习队列 + 时长统计趋势 + 计划/卡片更新删除。"""

    def test_submit_review_quality_0_resets_repetition(self, db_session, test_user):
        """SM-2 算法：quality<3（忘记）时，repetition 重置为 0，interval=1（明天再复习）。

        防什么：如果 quality<3 时没有重置 repetition，忘记的卡片会继续
        拉长间隔，用户永远记不住。
        """
        svc = LearningService(db_session)
        card = svc.create_card(test_user.id, _make_card(front="Q", back="A"))
        card_id = card["id"]

        # 先复习一次 quality=5 → repetition=1
        svc.submit_review(test_user.id, card_id, ReviewSubmitRequest(quality=5))

        # 再复习 quality=0（忘记）→ repetition 重置为 0，interval=1
        result = svc.submit_review(test_user.id, card_id, ReviewSubmitRequest(quality=0))
        assert result["repetition"] == 0
        assert result["interval"] == 1
        assert result["next_review"] == (date.today() + timedelta(days=1)).isoformat()

        # 查库验证
        db_session.expire_all()
        in_db = db_session.get(Flashcard, card_id)
        assert in_db.repetition == 0
        assert in_db.interval == 1

    def test_get_today_review_returns_due_cards(self, db_session, test_user):
        """今日复习队列只返回 next_review <= 今天的卡片，未来的不返回。

        防什么：get_today_review 如果漏了 next_review 过滤，会返回所有
        卡片，用户被淹没在不需要今天复习的卡片里。
        """
        svc = LearningService(db_session)
        # 新建卡片 next_review=今天 → 在队列中
        due_card = svc.create_card(test_user.id, _make_card(front="今天复习", back="A"))
        # 造一个未来复习的卡片
        future_card = svc.create_card(test_user.id, _make_card(front="未来复习", back="B"))
        db_session.execute(
            __import__("sqlalchemy").update(Flashcard)
            .where(Flashcard.id == future_card["id"])
            .values(next_review=date.today() + timedelta(days=5))
        )
        db_session.commit()

        result = svc.get_today_review(test_user.id)
        assert result["total"] == 1
        assert result["list"][0]["front"] == "今天复习"

    def test_get_time_stats_aggregates_daily_and_trend(self, db_session, test_user):
        """学习时长统计：按日期聚合，填充空日期，计算总时长和趋势。

        防什么：get_time_stats 如果漏了空日期填充，daily 数组会有缺口，
        前端图表 X 轴不连续。
        """
        svc = LearningService(db_session)
        today = date.today()
        # 今天和昨天各记录 30 分钟
        svc.log_study_time(test_user.id, CreateStudyTimeLogRequest(
            duration=30, subject="数学", logged_date=today,
        ))
        svc.log_study_time(test_user.id, CreateStudyTimeLogRequest(
            duration=30, subject="数学", logged_date=today - timedelta(days=1),
        ))

        stats = svc.get_time_stats(test_user.id, days=7)
        assert stats["total_minutes"] == 60
        assert stats["days"] == 7
        assert len(stats["daily"]) == 7  # 填充了空日期
        # 最近 7 天有学习，前 7 天（如果有的话）没有 → trend=up
        assert stats["trend"] in ("up", "stable")

    def test_update_and_delete_plan(self, db_session, test_user):
        """更新学习计划后查库验证，删除后行消失。

        防什么：update_plan 如果用了全量覆盖而不是增量更新，未传字段
        会被重置为 None。
        """
        svc = LearningService(db_session)
        plan = svc.create_plan(test_user.id, _make_plan(
            name="旧名字", description="旧描述", estimated_hours=50,
        ))

        # 只更新 name 和 progress
        svc.update_plan(test_user.id, plan["id"], {"name": "新名字", "progress": 50})

        # 查库验证
        db_session.expire_all()
        in_db = db_session.get(StudyPlan, plan["id"])
        assert in_db.name == "新名字"
        assert in_db.progress == 50
        assert in_db.description == "旧描述"  # 未指定字段不变
        assert in_db.estimated_hours == 50  # 未指定字段不变

        # 删除
        svc.delete_plan(test_user.id, plan["id"])
        db_session.expire_all()
        assert db_session.get(StudyPlan, plan["id"]) is None

    def test_update_and_delete_card(self, db_session, test_user):
        """更新知识卡片后查库验证，删除后行消失。

        防什么：update_card 如果漏了某个字段处理，该字段无法通过 API 修改。
        """
        svc = LearningService(db_session)
        card = svc.create_card(test_user.id, _make_card(
            front="旧问题", back="旧答案", category="旧分类", difficulty=3,
        ))

        # 更新 front 和 difficulty
        svc.update_card(test_user.id, card["id"], {"front": "新问题", "difficulty": 5})

        # 查库验证
        db_session.expire_all()
        in_db = db_session.get(Flashcard, card["id"])
        assert in_db.front == "新问题"
        assert in_db.difficulty == 5
        assert in_db.back == "旧答案"  # 未指定字段不变
        assert in_db.category == "旧分类"  # 未指定字段不变

        # 删除
        svc.delete_card(test_user.id, card["id"])
        db_session.expire_all()
        assert db_session.get(Flashcard, card["id"]) is None


# ============================================================
# 第 3 组：越权校验（修复前：update/delete/submit_review 均无 user_id 校验）
# ============================================================

class TestGroup3OwnershipValidation:
    """第3组：其他用户操作计划/卡片/复习均抛 NotFoundException，不泄露资源存在性。"""

    def test_update_plan_other_user_raises_not_found(self, db_session, test_user, other_user):
        """其他用户更新我的学习计划 → NotFoundException（越权）。

        防什么：修复前 update_plan 直接 get_or_404(plan_id)，不校验 user_id，
        用户 A 可以修改用户 B 的计划名称和进度。
        """
        svc = LearningService(db_session)
        plan = svc.create_plan(test_user.id, _make_plan(name="我的计划"))

        with pytest.raises(NotFoundException, match="学习计划不存在"):
            svc.update_plan(other_user.id, plan["id"], {"name": "被篡改"})

        # 查库验证：计划未被修改
        db_session.expire_all()
        in_db = db_session.get(StudyPlan, plan["id"])
        assert in_db.name == "我的计划"

    def test_delete_plan_other_user_raises_not_found(self, db_session, test_user, other_user):
        """其他用户删除我的学习计划 → NotFoundException（越权）。

        防什么：修复前 delete_plan 直接 get_or_404(plan_id)，不校验 user_id，
        用户 A 可以删除用户 B 的计划。
        """
        svc = LearningService(db_session)
        plan = svc.create_plan(test_user.id, _make_plan(name="我的计划"))

        with pytest.raises(NotFoundException, match="学习计划不存在"):
            svc.delete_plan(other_user.id, plan["id"])

        # 查库验证：计划仍存在
        db_session.expire_all()
        assert db_session.get(StudyPlan, plan["id"]) is not None

    def test_update_card_other_user_raises_not_found(self, db_session, test_user, other_user):
        """其他用户更新我的知识卡片 → NotFoundException（越权）。

        防什么：修复前 update_card 直接 get_or_404(card_id)，不校验 user_id，
        用户 A 可以修改用户 B 的卡片内容。
        """
        svc = LearningService(db_session)
        card = svc.create_card(test_user.id, _make_card(front="我的问题", back="我的答案"))

        with pytest.raises(NotFoundException, match="知识卡片不存在"):
            svc.update_card(other_user.id, card["id"], {"front": "被篡改"})

        # 查库验证：卡片未被修改
        db_session.expire_all()
        in_db = db_session.get(Flashcard, card["id"])
        assert in_db.front == "我的问题"

    def test_delete_card_other_user_raises_not_found(self, db_session, test_user, other_user):
        """其他用户删除我的知识卡片 → NotFoundException（越权）。

        防什么：修复前 delete_card 直接 get_or_404(card_id)，不校验 user_id，
        用户 A 可以删除用户 B 的卡片。
        """
        svc = LearningService(db_session)
        card = svc.create_card(test_user.id, _make_card(front="我的问题", back="我的答案"))

        with pytest.raises(NotFoundException, match="知识卡片不存在"):
            svc.delete_card(other_user.id, card["id"])

        # 查库验证：卡片仍存在
        db_session.expire_all()
        assert db_session.get(Flashcard, card["id"]) is not None

    def test_submit_review_other_user_raises_not_found(self, db_session, test_user, other_user):
        """其他用户复习我的卡片 → NotFoundException（越权）。

        防什么：修复前 submit_review 直接 get_or_404(card_id)，不校验 user_id，
        用户 A 可以对用户 B 的卡片提交复习，干扰其 SM-2 间隔重复算法。
        """
        svc = LearningService(db_session)
        card = svc.create_card(test_user.id, _make_card(front="Q", back="A"))

        with pytest.raises(NotFoundException, match="知识卡片不存在"):
            svc.submit_review(other_user.id, card["id"], ReviewSubmitRequest(quality=5))

        # 查库验证：卡片 SM-2 参数未被修改
        db_session.expire_all()
        in_db = db_session.get(Flashcard, card["id"])
        assert in_db.repetition == 0
        assert in_db.review_count == 0
