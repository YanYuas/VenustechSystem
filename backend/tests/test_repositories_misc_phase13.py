# ============================================================
# Phase13 · A 类覆盖率补缺：二/三期小仓库的语义化查询方法
#
# 背景：habit / mood / study_plan / template / inbox 的 Repository 有一批
# `list_by_user / count_by_user / list_active / ...` 便捷方法只有 service 调用，
# 部分路径（空列表、按日期区间、按分类、内置模板）此前完全没被测试覆盖。
# 本文件直接用 ORM 造数据，断言"过滤条件 + 返回值"，避免空测试。
# ============================================================
from __future__ import annotations

from datetime import date

from app.models.learning import StudyPlan
from app.models.life import Habit, HabitCheckin, MoodLog
from app.models.resource import InboxItem, Template
from app.repositories.habit_checkin_repo import HabitCheckinRepository
from app.repositories.habit_repo import HabitRepository
from app.repositories.mood_repo import MoodRepository
from app.repositories.resource_repo import InboxItemRepository
from app.repositories.study_plan_repo import StudyPlanRepository
from app.repositories.template_repo import TemplateRepository


class TestHabitRepositories:
    def test_habit_filters_by_user_and_status(self, db_session, test_user, other_user):
        db_session.add_all([
            Habit(user_id=test_user.id, name="跑步", status="active"),
            Habit(user_id=test_user.id, name="睡前阅读", status="archived"),
            Habit(user_id=other_user.id, name="别人的习惯", status="active"),
        ])
        db_session.commit()

        repo = HabitRepository(db_session)
        assert {h.name for h in repo.list_by_user(test_user.id)} == {"跑步", "睡前阅读"}
        assert repo.count_by_user(test_user.id) == 2
        assert [h.name for h in repo.list_active(test_user.id)] == ["跑步"]

    def test_habit_checkin_queries(self, db_session, test_user):
        habit = Habit(user_id=test_user.id, name="喝水")
        db_session.add(habit)
        db_session.flush()
        today = date(2026, 10, 30)
        db_session.add_all([
            HabitCheckin(habit_id=habit.id, user_id=test_user.id,
                         checkin_date=today, note="done"),
            HabitCheckin(habit_id=habit.id, user_id=test_user.id,
                         checkin_date=date(2026, 10, 29)),
        ])
        db_session.commit()

        repo = HabitCheckinRepository(db_session)
        assert repo.count_by_user(test_user.id) == 2
        assert len(repo.list_by_user(test_user.id)) == 2
        assert len(repo.list_by_habit(habit.id)) == 2
        row = repo.get_by_date(habit.id, today)
        assert row is not None and row.note == "done"
        assert repo.get_by_date(habit.id, date(2026, 10, 1)) is None

    def test_mood_repository_date_range_is_inclusive(self, db_session, test_user):
        db_session.add_all([
            MoodLog(user_id=test_user.id, score=5, logged_date=date(2026, 10, 1)),
            MoodLog(user_id=test_user.id, score=3, logged_date=date(2026, 10, 3)),
            MoodLog(user_id=test_user.id, score=4, logged_date=date(2026, 10, 5)),
        ])
        db_session.commit()

        repo = MoodRepository(db_session)
        assert repo.count_by_user(test_user.id) == 3
        assert len(repo.list_by_user(test_user.id)) == 3
        rows = repo.list_by_date_range(test_user.id, date(2026, 10, 2), date(2026, 10, 4))
        assert [r.score for r in rows] == [3]     # 只命中区间内且按日期升序


class TestPlanTemplateInboxRepositories:
    def test_study_plan_filters(self, db_session, test_user):
        db_session.add_all([
            StudyPlan(user_id=test_user.id, name="英语", status="active"),
            StudyPlan(user_id=test_user.id, name="数学", status="completed"),
        ])
        db_session.commit()

        repo = StudyPlanRepository(db_session)
        assert repo.count_by_user(test_user.id) == 2
        assert len(repo.list_by_user(test_user.id)) == 2
        assert [p.name for p in repo.list_active(test_user.id)] == ["英语"]

    def test_template_filters_by_category_and_builtin(self, db_session, test_user):
        db_session.add_all([
            Template(user_id=test_user.id, name="周报", category="doc",
                     content="x", is_builtin=False),
            Template(user_id=test_user.id, name="复盘", category="doc",
                     content="y", is_builtin=True),
            Template(user_id=test_user.id, name="表格", category="sheet", content="z"),
        ])
        db_session.commit()

        repo = TemplateRepository(db_session)
        assert repo.count_by_user(test_user.id) == 3
        assert {t.name for t in repo.list_by_category(test_user.id, "doc")} == {"周报", "复盘"}
        assert [t.name for t in repo.list_builtin()] == ["复盘"]

    def test_inbox_status_queues_and_clear_identity(self, db_session, test_user):
        db_session.add_all([
            InboxItem(user_id=test_user.id, content_type="text",
                      content="待处理", status="pending"),
            InboxItem(user_id=test_user.id, content_type="link",
                      content="已处理", status="processed"),
            InboxItem(user_id=test_user.id, content_type="text",
                      content="未归类", status="pending", identity_id="id-1"),
        ])
        db_session.commit()

        repo = InboxItemRepository(db_session)
        assert repo.count_by_user(test_user.id) == 3
        assert len(repo.list_by_user(test_user.id)) == 3
        assert [i.content for i in repo.list_pending(test_user.id)] == ["待处理", "未归类"]
        assert [i.content for i in repo.list_processed(test_user.id)] == ["已处理"]

        repo.clear_identity("id-1")
        db_session.commit()
        untouched = [i for i in repo.list_by_user(test_user.id) if i.content == "未归类"]
        assert untouched[0].identity_id is None    # 身份引用被清回「未归类」
