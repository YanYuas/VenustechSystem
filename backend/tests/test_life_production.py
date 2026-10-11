# ============================================================
# Life Service 生产级测试
#
# 生活记录（二期 M9）：习惯打卡 + 心情记录 + 日记
#
# 标准：真数据夹具 + 写操作后查库验证 + 幂等性 + 增量隔离 + 负向断言
# ============================================================
from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.models.life import Diary, Habit, HabitCheckin, MoodLog
from app.schemas.life import CreateDiaryRequest, CreateHabitRequest, CreateMoodLogRequest
from app.services.life_service import LifeService


def _make_habit(name="早起", **overrides):
    """构造 CreateHabitRequest，所有字段有默认值，可覆盖。"""
    defaults = dict(name=name, icon="sun", color="#FFD700", frequency="daily",
                     target_per_week=7, goal_days=30)
    defaults.update(overrides)
    return CreateHabitRequest(**defaults)


def _make_mood(score=4, **overrides):
    """构造 CreateMoodLogRequest，所有字段有默认值，可覆盖。"""
    defaults = dict(score=score, tags=["开心"], content="今天心情不错")
    defaults.update(overrides)
    return CreateMoodLogRequest(**defaults)


def _make_diary(title="今日日记", **overrides):
    """构造 CreateDiaryRequest，所有字段有默认值，可覆盖。"""
    defaults = dict(title=title, content="今天发生了很多事", dimension="生活", tags=["日常"])
    defaults.update(overrides)
    return CreateDiaryRequest(**defaults)


# ============================================================
# 第 1 组：习惯创建 + 打卡幂等 + 连续天数 + 心情统计 + 日记创建
# ============================================================

class TestGroup1HabitCheckinMoodDiary:
    """第1组：习惯CRUD + 打卡幂等 + 连续天数 + 心情记录统计 + 日记创建。"""

    def test_create_habit_persists_to_db(self, db_session, test_user):
        """创建习惯后查库验证 name/icon/color/frequency/user_id。

        防什么：create_habit 如果漏了某个字段，习惯创建后该字段为默认值，
        前端展示异常。
        """
        svc = LifeService(db_session)
        out = svc.create_habit(test_user.id, _make_habit(
            name="每天读书", icon="book", color="#4CAF50", goal_days=100,
        ))

        assert out["name"] == "每天读书"
        assert out["status"] == "active"

        # 查库验证
        db_session.expire_all()
        in_db = db_session.get(Habit, out["id"])
        assert in_db is not None
        assert in_db.name == "每天读书"
        assert in_db.icon == "book"
        assert in_db.color == "#4CAF50"
        assert in_db.goal_days == 100
        assert in_db.user_id == test_user.id

    def test_checkin_habit_idempotent_same_day(self, db_session, test_user):
        """同一天重复打卡幂等：第二次返回已有记录，不重复创建。

        防什么：checkin_habit 如果没有幂等保护，用户多次点击打卡按钮
        会创建多条记录，连续天数计算异常。
        """
        svc = LifeService(db_session)
        habit = svc.create_habit(test_user.id, _make_habit(name="打卡习惯"))

        # 第一次打卡
        r1 = svc.checkin_habit(habit["id"])
        assert r1["checkin_date"] == date.today().isoformat()

        # 第二次打卡（同一天）
        r2 = svc.checkin_habit(habit["id"])
        assert r2["id"] == r1["id"]  # 返回同一条记录

        # 查库验证：只有一条打卡记录
        db_session.expire_all()
        count = db_session.query(HabitCheckin).filter_by(habit_id=habit["id"]).count()
        assert count == 1

    def test_checkin_streak_calculation(self, db_session, test_user):
        """连续打卡天数：今天和昨天都打卡 → streak=2；只有今天 → streak=1。

        防什么：_calc_streak 如果日期比较错误（比如用了 UTC 日期），
        午夜前后的打卡会算到错误的日期，连续天数断裂。
        """
        svc = LifeService(db_session)
        habit = svc.create_habit(test_user.id, _make_habit(name="连续打卡"))
        habit_id = habit["id"]

        # 今天和昨天都打卡
        svc.checkin_habit(habit_id, date.today())
        svc.checkin_habit(habit_id, date.today() - timedelta(days=1))

        # list_habits 返回的 current_streak
        result = svc.list_habits(test_user.id)
        assert result["list"][0]["current_streak"] == 2
        assert result["list"][0]["checked_today"] is True

        # 查库验证：两条打卡记录
        db_session.expire_all()
        count = db_session.query(HabitCheckin).filter_by(habit_id=habit_id).count()
        assert count == 2

    def test_create_mood_persists_and_stats(self, db_session, test_user):
        """创建心情记录后查库验证，get_mood_stats 返回正确的平均分和分布。

        防什么：get_mood_stats 如果日期过滤错误，会统计到范围外的记录，
        平均分不准确。
        """
        svc = LifeService(db_session)
        # 造 3 条心情记录：4分、3分、5分
        svc.create_mood(test_user.id, _make_mood(score=4, logged_date=date.today()))
        svc.create_mood(test_user.id, _make_mood(score=3, logged_date=date.today() - timedelta(days=1)))
        svc.create_mood(test_user.id, _make_mood(score=5, logged_date=date.today() - timedelta(days=2)))

        # 查库验证
        db_session.expire_all()
        count = db_session.query(MoodLog).filter_by(user_id=test_user.id).count()
        assert count == 3

        # 统计
        stats = svc.get_mood_stats(test_user.id, days=7)
        assert stats["count"] == 3
        assert stats["avg_score"] == 4.0  # (4+3+5)/3 = 4.0
        assert stats["distribution"][4] == 1
        assert stats["distribution"][3] == 1
        assert stats["distribution"][5] == 1
        assert stats["distribution"][1] == 0
        assert stats["distribution"][2] == 0

    def test_create_diary_persists_to_db(self, db_session, test_user):
        """创建日记后查库验证 title/content/dimension/diary_date/user_id。

        防什么：create_diary 如果漏了 diary_date 默认值（今天），日记日期
        会是 None，列表排序异常。
        """
        svc = LifeService(db_session)
        out = svc.create_diary(test_user.id, _make_diary(
            title="重要的一天", content="今天完成了很多事情", dimension="成长",
        ))

        assert out["title"] == "重要的一天"
        assert out["diary_date"] == date.today().isoformat()

        # 查库验证
        db_session.expire_all()
        in_db = db_session.get(Diary, out["id"])
        assert in_db is not None
        assert in_db.title == "重要的一天"
        assert in_db.content == "今天完成了很多事情"
        assert in_db.dimension == "成长"
        assert in_db.diary_date == date.today()
        assert in_db.user_id == test_user.id


# ============================================================
# 第 2 组：取消打卡 + 打卡日历 + 习惯更新删除 + 心情空统计 + 日记更新删除
# ============================================================

class TestGroup2UncheckCalendarUpdateDelete:
    """第2组：取消打卡 + 日历结构 + 习惯增量更新删除 + 心情空统计 + 日记更新删除。"""

    def test_uncheck_habit_removes_checkin(self, db_session, test_user):
        """取消打卡后，打卡记录被删除，查库验证。

        防什么：uncheck_habit 如果漏了删除，取消打卡后记录还在，
        连续天数计算错误。
        """
        svc = LifeService(db_session)
        habit = svc.create_habit(test_user.id, _make_habit(name="取消打卡"))
        habit_id = habit["id"]

        # 先打卡
        svc.checkin_habit(habit_id)
        db_session.expire_all()
        assert db_session.query(HabitCheckin).filter_by(habit_id=habit_id).count() == 1

        # 取消打卡
        svc.uncheck_habit(habit_id)
        db_session.expire_all()
        assert db_session.query(HabitCheckin).filter_by(habit_id=habit_id).count() == 0

    def test_habit_calendar_structure(self, db_session, test_user):
        """打卡日历返回正确结构：日期数=当月天数，checked 标记正确，is_today 标记。

        防什么：get_habit_calendar 如果日期计算错误（比如闰年2月），
        日历会少一天或多一天。
        """
        svc = LifeService(db_session)
        habit = svc.create_habit(test_user.id, _make_habit(name="日历习惯"))
        habit_id = habit["id"]

        # 今天打卡
        svc.checkin_habit(habit_id, date.today())

        # 获取本月日历
        today = date.today()
        cal = svc.get_habit_calendar(habit_id, today.year, today.month)

        assert cal["habit_id"] == habit_id
        assert cal["year"] == today.year
        assert cal["month"] == today.month
        assert cal["total_checkins"] == 1

        # calendar 长度 = 月初星期几偏移 + 当月天数
        days_in_month = (date(today.year, today.month + 1, 1) - timedelta(days=1)).day if today.month < 12 else 31
        first_weekday = date(today.year, today.month, 1).weekday()
        assert len(cal["calendar"]) == first_weekday + days_in_month

        # 找到今天的条目，checked=True
        today_entry = next(c for c in cal["calendar"] if c and c["is_today"])
        assert today_entry["checked"] is True

    def test_update_and_delete_habit(self, db_session, test_user):
        """更新习惯后查库验证，删除后行消失。

        防什么：update_habit 如果用了全量覆盖，未传字段会被重置为 None。
        """
        svc = LifeService(db_session)
        habit = svc.create_habit(test_user.id, _make_habit(
            name="旧名字", icon="old", color="#000000", goal_days=30,
        ))

        # 只更新 name 和 goal_days
        svc.update_habit(test_user.id, habit["id"], {"name": "新名字", "goal_days": 60})

        # 查库验证
        db_session.expire_all()
        in_db = db_session.get(Habit, habit["id"])
        assert in_db.name == "新名字"
        assert in_db.goal_days == 60
        assert in_db.icon == "old"  # 未指定字段不变
        assert in_db.color == "#000000"  # 未指定字段不变

        # 删除
        svc.delete_habit(test_user.id, habit["id"])
        db_session.expire_all()
        assert db_session.get(Habit, habit["id"]) is None

    def test_mood_stats_empty_returns_defaults(self, db_session, test_user):
        """无心情记录时，get_mood_stats 返回默认值（avg=0, count=0, trend=stable）。

        防什么：get_mood_stats 如果对空数据没有保护，会除零错误或返回
        异常结构。
        """
        svc = LifeService(db_session)
        stats = svc.get_mood_stats(test_user.id, days=30)

        assert stats["avg_score"] == 0
        assert stats["count"] == 0
        assert stats["trend"] == "stable"
        assert stats["distribution"] == {}
        assert stats["daily"] == []

    def test_update_and_delete_diary(self, db_session, test_user):
        """更新日记后查库验证，删除后行消失。

        防什么：update_diary 如果漏了 content 字段处理，日记内容无法修改。
        """
        svc = LifeService(db_session)
        diary = svc.create_diary(test_user.id, _make_diary(
            title="旧标题", content="旧内容", dimension="旧维度",
        ))

        # 只更新 title 和 content
        svc.update_diary(test_user.id, diary["id"], {"title": "新标题", "content": "新内容"})

        # 查库验证
        db_session.expire_all()
        in_db = db_session.get(Diary, diary["id"])
        assert in_db.title == "新标题"
        assert in_db.content == "新内容"
        assert in_db.dimension == "旧维度"  # 未指定字段不变

        # 删除
        svc.delete_diary(test_user.id, diary["id"])
        db_session.expire_all()
        assert db_session.get(Diary, diary["id"]) is None
