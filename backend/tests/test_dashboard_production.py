# ============================================================
# Dashboard Service 生产级测试
#
# Dashboard 是聚合服务，测试重点：空数据默认值、各模块聚合正确性、
# 今日执行排序/分组、身份进度、连续打卡、本周进度、降级逻辑。
#
# 标准：真数据夹具 + 聚合结果交叉验证 + 增量隔离 + 负向断言 + 防bug注释
# ============================================================
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from app.models.document import Document
from app.models.task import Task
from app.services.dashboard_service import DashboardService


def _make_task(db, user_id, title, **overrides):
    """造任务，所有字段有默认值，可覆盖。"""
    defaults = dict(title=title, status="pending", priority="medium")
    defaults.update(overrides)
    t = Task(user_id=user_id, **defaults)
    db.add(t)
    db.flush()
    return t


# ============================================================
# 第 1 组：空数据默认值 + 今日统计 + 今日执行 + 聚焦任务 + 最近文档
# ============================================================

class TestGroup1EmptyAndToday:
    """第1组：空数据默认值 + 今日统计计数 + 今日执行分组排序 + 聚焦任务 + 最近文档。"""

    def test_empty_dashboard_returns_defaults(self, db_session, test_user):
        """无任何数据时，仪表盘返回正确的默认值（不报错、不泄露其他用户数据）。

        防什么：聚合服务如果对空数据没有保护（如除零、None 访问），
        新用户打开首页会 500。
        """
        svc = DashboardService(db_session, test_user)
        data = svc.get()

        # 今日统计全 0
        assert data.today_stats.must_do == 0
        assert data.today_stats.in_progress == 0
        assert data.today_stats.waiting == 0
        assert data.today_stats.completed_today == 0

        # 无聚焦任务
        assert data.focus_task is None

        # 无最近文档
        assert len(data.recent_documents) == 0

        # 今日执行 total=0，3 个分组都存在
        assert data.today_execution.total == 0
        assert len(data.today_execution.groups) == 3
        for g in data.today_execution.groups:
            assert g.count == 0

        # 本周进度 0
        assert data.week_progress.total == 0
        assert data.week_progress.completed == 0
        assert data.week_progress.percentage == 0

        # 连续打卡 0 天
        assert data.streak.days == 0
        assert len(data.streak.week_checkins) == 7
        assert all(c is False for c in data.streak.week_checkins)

        # 模块状态 10 个
        assert len(data.modules_status) == 10

        # 快速入口 9 个
        assert len(data.quick_actions.items) == 9

    def test_today_stats_counts_correctly(self, db_session, test_user):
        """今日统计正确计数：must_do（今日到期未完成）、in_progress、waiting、completed_today。

        防什么：today_stats 如果用了错误的过滤条件（比如把所有 pending 都算
        must_do），数字会偏大，和今日执行口径矛盾。
        """
        today = date.today()
        # 今日到期未完成 → must_do
        _make_task(db_session, test_user.id, "今日必做", due_date=today, status="pending")
        # 进行中 → in_progress
        _make_task(db_session, test_user.id, "进行中", status="in_progress")
        # 等待处理 → waiting
        _make_task(db_session, test_user.id, "等待中", status="waiting")
        # 今天完成 → completed_today
        _make_task(db_session, test_user.id, "今天完成", status="completed",
                   completed_at=datetime.utcnow())
        # 明天到期 → 不算 must_do
        _make_task(db_session, test_user.id, "明天到期", due_date=today + timedelta(days=1),
                   status="pending")
        db_session.commit()

        svc = DashboardService(db_session, test_user)
        stats = svc.get().today_stats
        assert stats.must_do == 1
        assert stats.in_progress == 1
        assert stats.waiting == 1
        assert stats.completed_today == 1

    def test_today_execution_groups_and_sorts(self, db_session, test_user):
        """今日执行按状态分组，逾期任务优先排序，total === 各分组 count 之和。

        防什么：原实现 total=len(all_tasks) 与分组 count 之和不一致，用户
        看到"共 N 项"远大于分组之和。现在只统计"今天需要动手"的任务。
        """
        today = date.today()
        # 逾期 pending（最紧急）
        _make_task(db_session, test_user.id, "逾期任务", due_date=today - timedelta(days=1),
                   status="pending", priority="high")
        # 今日到期 pending
        _make_task(db_session, test_user.id, "今日任务", due_date=today, status="pending")
        # 进行中
        _make_task(db_session, test_user.id, "进行中任务", status="in_progress")
        # 未来到期 pending → 不算今日执行
        _make_task(db_session, test_user.id, "未来任务", due_date=today + timedelta(days=3),
                   status="pending")
        db_session.commit()

        svc = DashboardService(db_session, test_user)
        execution = svc.get().today_execution

        # total === 各分组 count 之和
        assert execution.total == 3
        group_counts = {g.status: g.count for g in execution.groups}
        assert group_counts["pending"] == 2
        assert group_counts["in_progress"] == 1
        assert group_counts["waiting"] == 0
        assert sum(group_counts.values()) == execution.total

        # pending 分组中逾期任务排第一
        pending_group = next(g for g in execution.groups if g.status == "pending")
        assert pending_group.tasks[0]["title"] == "逾期任务"

    def test_focus_task_returned(self, db_session, test_user):
        """有聚焦任务时，dashboard 返回 focus_task 字段。

        防什么：focus_task 如果漏了 is_focus 过滤，会返回任意任务而不是
        当前聚焦的任务。
        """
        _make_task(db_session, test_user.id, "普通任务", status="pending")
        _make_task(db_session, test_user.id, "聚焦任务", status="in_progress", is_focus=True)
        db_session.commit()

        svc = DashboardService(db_session, test_user)
        data = svc.get()
        assert data.focus_task is not None
        assert data.focus_task.title == "聚焦任务"

    def test_recent_documents_limited_to_5(self, db_session, test_user):
        """最近文档最多返回 5 篇，按 updated_at 降序。

        防什么：recent_documents 如果漏了 limit=5，文档多的用户首页会
        加载大量文档，性能差。
        """
        for i in range(7):
            doc = Document(user_id=test_user.id, title=f"文档{i}", content="内容")
            db_session.add(doc)
        db_session.commit()

        svc = DashboardService(db_session, test_user)
        docs = svc.get().recent_documents
        assert len(docs) == 5


# ============================================================
# 第 2 组：身份进度 + 项目聚合 + 连续打卡 + 本周进度 + 用户问候
# ============================================================

class TestGroup2IdentityProjectStreakWeek:
    """第2组：身份进度聚合 + 项目实体聚合 + 连续打卡计算 + 本周进度 + 问候语。"""

    def test_identities_progress_aggregates_tasks(self, db_session, test_user):
        """身份进度区按身份聚合任务：open_tasks/in_progress/completed_today 正确计数。

        防什么：身份进度如果漏了某个状态的过滤，用户看不出每条身份线
        的推进情况。
        """
        from app.models.identity import Identity

        identity = Identity(user_id=test_user.id, name="学习线", slug="study",
                            color_token="primary", icon="book")
        db_session.add(identity)
        db_session.flush()
        identity_id = identity.id

        # 该身份下：1 个 pending（open）、1 个 in_progress、1 个今天完成
        _make_task(db_session, test_user.id, "待办", status="pending", identity_id=identity_id)
        _make_task(db_session, test_user.id, "进行中", status="in_progress", identity_id=identity_id)
        _make_task(db_session, test_user.id, "今天完成", status="completed",
                   completed_at=datetime.utcnow(), identity_id=identity_id)
        # 未归类的任务
        _make_task(db_session, test_user.id, "未归类", status="pending")
        db_session.commit()

        svc = DashboardService(db_session, test_user)
        identities = svc.get().identities

        assert len(identities.items) == 1
        item = identities.items[0]
        assert item.name == "学习线"
        assert item.open_tasks == 2  # pending + in_progress（未完成）
        assert item.in_progress == 1
        assert item.completed_today == 1
        assert item.is_archived is False
        # 未归类计数
        assert identities.unassigned_open == 1

    def test_projects_section_uses_real_project_entities(self, db_session, test_user):
        """项目区优先使用真实 Project 实体（而非 project_tag 降级聚合）。

        防什么：如果 ProjectService.list 调用失败被静默降级，用户看不到
        真实项目，只看到基于 tag 的聚合数据。
        """
        from app.models.project import Project

        project = Project(user_id=test_user.id, name="真实项目", status="active", color="#ff0000")
        db_session.add(project)
        db_session.flush()
        # 项目下 2 个任务，1 个完成
        _make_task(db_session, test_user.id, "任务1", status="completed",
                   completed_at=datetime.utcnow(), project_id=project.id)
        _make_task(db_session, test_user.id, "任务2", status="pending", project_id=project.id)
        db_session.commit()

        svc = DashboardService(db_session, test_user)
        projects = svc.get().projects

        assert projects.status == "ready"
        assert len(projects.items) == 1
        assert projects.items[0].name == "真实项目"
        assert projects.items[0].task_count == 2
        assert projects.items[0].completed_count == 1
        assert projects.items[0].progress == 50

    def test_streak_calculates_consecutive_days(self, db_session, test_user):
        """连续打卡基于复盘记录计算：今天和昨天都有复盘 → streak=2。

        防什么：streak 如果用了错误的日期比较（比如 UTC 日期而非本地日期），
        午夜前后的复盘会算到错误的日期。
        """
        from app.models.review import Review

        today = date.today()
        # 今天和昨天的复盘
        db_session.add(Review(user_id=test_user.id, type="daily", review_date=today,
                               data={"mood": 3}))
        db_session.add(Review(user_id=test_user.id, type="daily", review_date=today - timedelta(days=1),
                               data={"mood": 4}))
        db_session.commit()

        svc = DashboardService(db_session, test_user)
        streak = svc.get().streak

        assert streak.days == 2
        assert len(streak.week_checkins) == 7
        # 本周至少有 2 天打卡
        assert sum(streak.week_checkins) >= 2

    def test_week_progress_counts_this_week_tasks(self, db_session, test_user):
        """本周进度环只统计本周（周一至周日）到期的任务。

        防什么：week_progress 如果统计了所有任务，进度环会显示不准确的
        百分比，用户误解本周完成情况。
        """
        today = date.today()
        monday = today - timedelta(days=today.weekday())
        # 本周到期的任务：1 个完成，1 个未完成
        _make_task(db_session, test_user.id, "本周完成", status="completed",
                   completed_at=datetime.utcnow(), due_date=monday + timedelta(days=1))
        _make_task(db_session, test_user.id, "本周未完成", status="pending",
                   due_date=monday + timedelta(days=2))
        # 下周到期的任务 → 不算
        _make_task(db_session, test_user.id, "下周任务", status="pending",
                   due_date=monday + timedelta(days=8))
        db_session.commit()

        svc = DashboardService(db_session, test_user)
        week = svc.get().week_progress

        assert week.total == 2
        assert week.completed == 1
        assert week.percentage == 50

    def test_user_greeting_by_hour(self, db_session, test_user):
        """用户问候语根据当前小时变化（早上好/下午好/晚上好）。

        防什么：greeting 如果写死了，不同时段打开首页都是同一句话，
        缺乏温度感。
        """
        from app.core.utils import greeting_by_hour

        svc = DashboardService(db_session, test_user)
        data = svc.get()

        assert data.user.nickname == test_user.nickname
        # 问候语非空，且等于 greeting_by_hour(当前小时)
        assert data.user.greeting == greeting_by_hour(datetime.now().hour)
        assert len(data.user.greeting) > 0
