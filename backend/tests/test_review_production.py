# ============================================================
# ReviewService 生产级测试
#
# 标准对齐经纬项目 + task/document/folder 生产级测试：
#   1. 真数据（混合类型/日期/data字段）
#   2. 写操作后查库验证
#   3. 增量隔离
#   4. 负向断言
#   5. 注释写清"防什么bug"
#
# 注意：ReviewService(db, user_id) 构造时传入 user_id，和其他 Service 不同。
#
# 以 5 个为一组逐步推进。
# ============================================================
from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.core.exceptions import NotFoundException, ValidationException
from app.models.review import Review
from app.schemas.review import ReviewData, UpsertReviewRequest
from app.services.review_service import ReviewService
from tests.factories import count_rows


def _make_review_data(**overrides) -> ReviewData:
    """构造一份有真实内容的 ReviewData。"""
    defaults = dict(
        completed_tasks="完成了最小覆盖圆论文修订",
        unfinished_tasks="还没写灵敏度分析",
        gains="今天搞懂了 Welzl 算法的增量维护",
        reflections=[{"question": "今天最大的收获？", "answer": "增量维护的思路"}],
        tomorrow_plan="继续写论文",
        mood=4,
        energy=3,
    )
    defaults.update(overrides)
    return ReviewData(**defaults)


# ============================================================
# 第 1 组：upsert 创建/更新 + get + list + 唯一约束
# ============================================================

class TestGroup1UpsertGetList:
    """第1组：upsert 创建/更新 + 按日期获取 + 列表分页 + 唯一约束。"""

    def test_upsert_creates_new_review(self, db_session, test_user):
        """首次 upsert 创建新复盘，查库验证所有字段。

        防什么：upsert 如果漏了 create 分支，首次保存会报 NoneType 错误。
        """
        svc = ReviewService(db_session, test_user.id)
        out = svc.upsert(UpsertReviewRequest(
            type="daily", date=date(2026, 10, 10),
            data=_make_review_data(),
        ))

        assert out.type == "daily"
        assert out.review_date == date(2026, 10, 10)
        assert out.data.mood == 4

        # 查库验证
        db_session.expire_all()
        in_db = db_session.get(Review, out.id)
        assert in_db is not None
        assert in_db.user_id == test_user.id
        assert in_db.type == "daily"
        assert in_db.review_date == date(2026, 10, 10)
        assert in_db.data["mood"] == 4
        assert in_db.data["gains"] == "今天搞懂了 Welzl 算法的增量维护"

    def test_upsert_updates_existing_review(self, db_session, test_user):
        """同日期同类型第二次 upsert 更新已有复盘，不产生新行。

        防什么：upsert 如果漏了 update 分支，同日期同类型会产生重复行，
        违反唯一约束导致 IntegrityError（500）。
        """
        svc = ReviewService(db_session, test_user.id)
        first = svc.upsert(UpsertReviewRequest(
            type="daily", date=date(2026, 10, 10),
            data=_make_review_data(mood=3),
        ))

        # 同日期同类型更新
        second = svc.upsert(UpsertReviewRequest(
            type="daily", date=date(2026, 10, 10),
            data=_make_review_data(mood=5, gains="更新后的收获"),
        ))

        # id 相同（是更新，不是新建）
        assert first.id == second.id
        assert second.data.mood == 5

        # 查库：只有一条
        assert count_rows(db_session, "reviews", user_id=test_user.id) == 1
        db_session.expire_all()
        in_db = db_session.get(Review, first.id)
        assert in_db.data["mood"] == 5
        assert in_db.data["gains"] == "更新后的收获"

    def test_get_by_date_returns_review(self, db_session, test_user):
        """按日期+类型获取复盘，返回的 data 和查库一致。

        防什么：get 如果只查 id 而不查 (type, date)，按日期获取会找不到。
        """
        svc = ReviewService(db_session, test_user.id)
        svc.upsert(UpsertReviewRequest(
            type="daily", date=date(2026, 10, 10),
            data=_make_review_data(),
        ))

        out = svc.get(date(2026, 10, 10), type_="daily")
        assert out.review_date == date(2026, 10, 10)
        assert out.data.mood == 4

    def test_get_nonexistent_date_raises(self, db_session, test_user):
        """获取不存在的日期复盘抛 NotFound。

        防什么：get 如果没检查 None，review.data 会报 AttributeError（500）。
        """
        svc = ReviewService(db_session, test_user.id)
        with pytest.raises(NotFoundException, match="该日期暂无复盘"):
            svc.get(date(2026, 1, 1), type_="daily")

    def test_list_returns_paginated_and_sorted(self, db_session, test_user):
        """列表返回分页结构，按日期倒序，查库验证总数。

        防什么：list 如果漏了排序，复盘列表顺序混乱；或者 total 没加 user_id
        过滤，会看到别人的复盘数。
        """
        svc = ReviewService(db_session, test_user.id)
        # 创建3天的复盘
        for d in [date(2026, 10, 8), date(2026, 10, 9), date(2026, 10, 10)]:
            svc.upsert(UpsertReviewRequest(type="daily", date=d, data=_make_review_data()))

        result = svc.list(type_="daily", page=1, page_size=2)
        assert result.total == 3
        assert len(result.list) == 2
        # 按日期倒序
        assert result.list[0].review_date == date(2026, 10, 10)
        assert result.list[1].review_date == date(2026, 10, 9)

        # 查库交叉验证
        assert count_rows(db_session, "reviews", user_id=test_user.id) == 3


# ============================================================
# 第 2 组：delete + 越权 + identity 校验
# ============================================================

class TestGroup2DeleteAuthIdentity:
    """第2组：删除持久化 + 越权删除 + identity_id 校验。"""

    def test_delete_removes_review(self, db_session, test_user):
        """删除复盘后查库验证行消失。

        防什么：delete 如果用了软删除而列表不过滤 deleted_at，已删除的
        复盘还会出现在列表里。
        """
        svc = ReviewService(db_session, test_user.id)
        out = svc.upsert(UpsertReviewRequest(
            type="daily", date=date(2026, 10, 10), data=_make_review_data(),
        ))

        svc.delete(out.id)

        # 查库验证
        db_session.expire_all()
        assert db_session.get(Review, out.id) is None
        assert count_rows(db_session, "reviews", user_id=test_user.id) == 0

    def test_delete_nonexistent_raises(self, db_session, test_user):
        """删除不存在的复盘抛 NotFound。

        防什么：delete 如果没检查 None，self.repo.delete(None) 会报
        AttributeError（500）。
        """
        svc = ReviewService(db_session, test_user.id)
        with pytest.raises(NotFoundException, match="复盘不存在"):
            svc.delete("non-existent-review-id")

    def test_delete_other_users_review_raises(self, db_session, test_user, other_user):
        """删除其他用户的复盘抛 NotFound，库中复盘仍在。

        防什么：delete 如果只检查存在性而不检查 user_id，用户可以删除
        别人的复盘。
        """
        # 直接造其他用户的复盘
        other_review = Review(
            user_id=other_user.id, type="daily", review_date=date(2026, 10, 10),
            data={"mood": 3},
        )
        db_session.add(other_review)
        db_session.commit()

        svc = ReviewService(db_session, test_user.id)
        with pytest.raises(NotFoundException, match="复盘不存在"):
            svc.delete(other_review.id)

        # 查库：复盘仍在
        db_session.expire_all()
        assert db_session.get(Review, other_review.id) is not None

    def test_upsert_with_invalid_identity_raises(self, db_session, test_user):
        """upsert 时指定不存在的 identity_id 抛 ValidationException，库中不产生脏数据。

        防什么：identity_id 是应用层关联（无外键），如果不校验，不存在的
        identity_id 会直接写进库，后续按 identity 过滤时变成孤儿。
        """
        svc = ReviewService(db_session, test_user.id)
        with pytest.raises(ValidationException, match="身份不存在"):
            svc.upsert(UpsertReviewRequest(
                type="daily", date=date(2026, 10, 10),
                identity_id="non-existent-identity",
                data=_make_review_data(),
            ))

        assert count_rows(db_session, "reviews", user_id=test_user.id) == 0

    def test_upsert_with_other_users_identity_raises(self, db_session, test_user, other_user):
        """upsert 时指定其他用户的 identity_id 抛 ValidationException。

        防什么：_validated_identity_id 如果只检查存在性而不检查归属，
        用户可以把复盘关联到别人的身份下。
        """
        from app.models.identity import Identity

        other_identity = Identity(
            user_id=other_user.id, name="他人身份", slug="other",
            color_token="primary", icon="star", is_active=True,
        )
        db_session.add(other_identity)
        db_session.commit()

        svc = ReviewService(db_session, test_user.id)
        with pytest.raises(ValidationException, match="身份不存在"):
            svc.upsert(UpsertReviewRequest(
                type="daily", date=date(2026, 10, 10),
                identity_id=other_identity.id,
                data=_make_review_data(),
            ))

        assert count_rows(db_session, "reviews", user_id=test_user.id) == 0


# ============================================================
# 第 3 组：auto_fill 自动数据填充
# ============================================================

class TestGroup3AutoFill:
    """第3组：auto_fill 返回今天完成的任务/未完成任务/创建的文档/逾期数。"""

    def test_auto_fill_returns_completed_tasks(self, db_session, test_user):
        """auto_fill 返回今天完成的任务，查库交叉验证数量。

        防什么：auto_fill 的 completed_at 过滤如果时区算错（用本地时间
        而不是 UTC），会漏掉或多算任务。
        """
        from datetime import datetime
        from app.models.task import Task

        today = date.today()
        # 造一条今天完成的任务
        completed = Task(
            user_id=test_user.id, title="今天完成的任务", status="completed",
            completed_at=datetime.utcnow(),
        )
        db_session.add(completed)
        # 造一条昨天完成的任务（不该返回）
        from datetime import timedelta
        yesterday_completed = Task(
            user_id=test_user.id, title="昨天完成的任务", status="completed",
            completed_at=datetime.utcnow() - timedelta(days=1),
        )
        db_session.add(yesterday_completed)
        db_session.commit()

        svc = ReviewService(db_session, test_user.id)
        result = svc.auto_fill(today, type_="daily")

        assert result.stats.tasks_completed == 1
        assert len(result.completed_tasks) == 1
        assert result.completed_tasks[0].title == "今天完成的任务"

    def test_auto_fill_returns_unfinished_due_today(self, db_session, test_user):
        """auto_fill 返回今天到期但未完成的任务。

        防什么：auto_fill 的未完成任务过滤如果漏了 due_date==today 条件，
        会返回所有未完成任务。
        """
        from app.models.task import Task

        today = date.today()
        # 今天到期未完成
        due_today = Task(
            user_id=test_user.id, title="今天到期未完成", status="pending",
            due_date=today,
        )
        db_session.add(due_today)
        # 明天到期未完成（不该返回）
        due_tomorrow = Task(
            user_id=test_user.id, title="明天到期", status="pending",
            due_date=today + timedelta(days=1),
        )
        db_session.add(due_tomorrow)
        db_session.commit()

        svc = ReviewService(db_session, test_user.id)
        result = svc.auto_fill(today, type_="daily")

        assert len(result.unfinished_tasks) == 1
        assert result.unfinished_tasks[0].title == "今天到期未完成"

    def test_auto_fill_returns_documents_created_today(self, db_session, test_user):
        """auto_fill 返回今天创建的文档。

        防什么：auto_fill 的文档过滤如果时区算错，会漏掉今天创建的文档。
        """
        from datetime import datetime
        from app.models.document import Document

        today = date.today()
        doc = Document(
            user_id=test_user.id, title="今天创建的文档", content="内容",
            word_count=2,
        )
        db_session.add(doc)
        db_session.commit()

        svc = ReviewService(db_session, test_user.id)
        result = svc.auto_fill(today, type_="daily")

        assert result.stats.documents_created == 1
        assert len(result.documents_created) == 1
        assert result.documents_created[0].title == "今天创建的文档"

    def test_auto_fill_returns_overdue_count(self, db_session, test_user):
        """auto_fill 返回逾期任务数（due_date < today 且未完成）。

        防什么：逾期统计如果漏了 status!=completed 条件，已完成的逾期
        任务也会被算进去。
        """
        from app.models.task import Task

        today = date.today()
        # 逾期未完成
        overdue = Task(
            user_id=test_user.id, title="逾期任务", status="pending",
            due_date=today - timedelta(days=2),
        )
        db_session.add(overdue)
        # 逾期但已完成（不该算逾期）
        completed_overdue = Task(
            user_id=test_user.id, title="逾期但完成了", status="completed",
            due_date=today - timedelta(days=2),
        )
        db_session.add(completed_overdue)
        db_session.commit()

        svc = ReviewService(db_session, test_user.id)
        result = svc.auto_fill(today, type_="daily")

        assert result.stats.tasks_overdue == 1

    def test_auto_fill_empty_day_returns_zeros(self, db_session, test_user):
        """没有任何数据的日期，auto_fill 返回全 0 和空列表。

        防什么：auto_fill 在空数据场景下如果假设至少有一条任务，可能报
        IndexError 或者返回 None。
        """
        today = date.today()
        svc = ReviewService(db_session, test_user.id)
        result = svc.auto_fill(today, type_="daily")

        assert result.stats.tasks_completed == 0
        assert result.stats.documents_created == 0
        assert result.stats.tasks_overdue == 0
        assert result.completed_tasks == []
        assert result.unfinished_tasks == []
        assert result.documents_created == []


# ============================================================
# 第 4 组：convert_task 明日计划转任务
# ============================================================

class TestGroup4ConvertTask:
    """第4组：明日计划转任务 + 优先级/截止日 + 越权边界。"""

    def test_convert_task_creates_task_in_db(self, db_session, test_user):
        """convert_task 创建任务后，查库验证任务存在且标题正确。

        防什么：convert_task 如果只返回 task_id 但没实际创建任务，用户的
        明日计划会丢失。
        """
        from app.models.task import Task
        from app.schemas.review import ConvertTaskRequest

        svc = ReviewService(db_session, test_user.id)
        review = svc.upsert(UpsertReviewRequest(
            type="daily", date=date(2026, 10, 10), data=_make_review_data(),
        ))

        result = svc.convert_task(review.id, ConvertTaskRequest(content="明天写论文"))

        assert "task_id" in result
        # 查库验证
        db_session.expire_all()
        task = db_session.get(Task, result["task_id"])
        assert task is not None
        assert task.title == "明天写论文"
        assert task.user_id == test_user.id
        assert task.priority == "medium"  # 默认优先级

    def test_convert_task_with_priority(self, db_session, test_user):
        """convert_task 带优先级时，查库验证优先级正确。

        防什么：convert_task 如果忽略 priority 参数，所有转出来的任务
        都是 medium 优先级。
        """
        from app.models.task import Task
        from app.schemas.review import ConvertTaskRequest

        svc = ReviewService(db_session, test_user.id)
        review = svc.upsert(UpsertReviewRequest(
            type="daily", date=date(2026, 10, 10), data=_make_review_data(),
        ))

        result = svc.convert_task(review.id, ConvertTaskRequest(
            content="紧急任务", priority="urgent",
        ))

        db_session.expire_all()
        task = db_session.get(Task, result["task_id"])
        assert task.priority == "urgent"

    def test_convert_task_with_due_date(self, db_session, test_user):
        """convert_task 带截止日时，查库验证 due_date 正确。

        防什么：convert_task 如果忽略 due_date 参数，转出来的任务没有
        截止日，会丢失时间约束。
        """
        from app.models.task import Task
        from app.schemas.review import ConvertTaskRequest

        svc = ReviewService(db_session, test_user.id)
        review = svc.upsert(UpsertReviewRequest(
            type="daily", date=date(2026, 10, 10), data=_make_review_data(),
        ))

        tomorrow = date(2026, 10, 11)
        result = svc.convert_task(review.id, ConvertTaskRequest(
            content="明天截止的任务", due_date=tomorrow,
        ))

        db_session.expire_all()
        task = db_session.get(Task, result["task_id"])
        assert task.due_date == tomorrow

    def test_convert_task_nonexistent_review_raises(self, db_session, test_user):
        """convert_task 对不存在的复盘抛 NotFound，不产生任务。

        防什么：convert_task 如果没检查复盘存在性，review.data 会报
        AttributeError（500）。
        """
        from app.schemas.review import ConvertTaskRequest

        svc = ReviewService(db_session, test_user.id)
        with pytest.raises(NotFoundException, match="复盘不存在"):
            svc.convert_task("non-existent-review", ConvertTaskRequest(content="任务"))

        # 查库：没有产生任务
        from app.models.task import Task
        assert count_rows(db_session, "tasks", user_id=test_user.id) == 0

    def test_convert_task_other_users_review_raises(self, db_session, test_user, other_user):
        """convert_task 对其他用户的复盘抛 NotFound，不产生任务。

        防什么：convert_task 如果只检查复盘存在性而不检查归属，用户可以
        用别人的复盘创建任务（虽然任务归属自己，但语义上不对）。
        """
        from app.models.task import Task
        from app.schemas.review import ConvertTaskRequest

        # 造其他用户的复盘
        other_review = Review(
            user_id=other_user.id, type="daily", review_date=date(2026, 10, 10),
            data={"mood": 3},
        )
        db_session.add(other_review)
        db_session.commit()

        svc = ReviewService(db_session, test_user.id)
        with pytest.raises(NotFoundException, match="复盘不存在"):
            svc.convert_task(other_review.id, ConvertTaskRequest(content="任务"))

        # 查库：没有产生任务
        assert count_rows(db_session, "tasks", user_id=test_user.id) == 0


# ============================================================
# 第 5 组：多类型 + 过滤 + project_id + data 完整性
# ============================================================

class TestGroup5TypeFilterProjectData:
    """第5组：同日期不同类型 + type 过滤 + project_id 更新 + identity 空串 + data 完整持久化。"""

    def test_upsert_different_types_same_date_are_separate(self, db_session, test_user):
        """同日期不同类型（daily/weekly）是两条独立复盘，互不影响。

        防什么：upsert 的唯一约束如果漏了 type，同日期不同类型会互相
        覆盖。
        """
        svc = ReviewService(db_session, test_user.id)
        daily = svc.upsert(UpsertReviewRequest(
            type="daily", date=date(2026, 10, 10),
            data=_make_review_data(mood=4),
        ))
        weekly = svc.upsert(UpsertReviewRequest(
            type="weekly", date=date(2026, 10, 10),
            data=_make_review_data(mood=5),
        ))

        # 是两条不同的复盘
        assert daily.id != weekly.id
        assert daily.type == "daily"
        assert weekly.type == "weekly"

        # 查库：两条
        assert count_rows(db_session, "reviews", user_id=test_user.id) == 2

        # 各自获取正确
        assert svc.get(date(2026, 10, 10), "daily").data.mood == 4
        assert svc.get(date(2026, 10, 10), "weekly").data.mood == 5

    def test_list_filter_by_type(self, db_session, test_user):
        """列表按 type 过滤，只返回对应类型的复盘。

        防什么：list 的 type_ 过滤如果漏了，会返回所有类型的复盘。
        """
        svc = ReviewService(db_session, test_user.id)
        svc.upsert(UpsertReviewRequest(type="daily", date=date(2026, 10, 10), data=_make_review_data()))
        svc.upsert(UpsertReviewRequest(type="weekly", date=date(2026, 10, 10), data=_make_review_data()))

        daily_result = svc.list(type_="daily")
        assert daily_result.total == 1
        assert daily_result.list[0].type == "daily"

        weekly_result = svc.list(type_="weekly")
        assert weekly_result.total == 1
        assert weekly_result.list[0].type == "weekly"

        # 不过滤返回全部
        all_result = svc.list()
        assert all_result.total == 2

    def test_upsert_updates_project_id(self, db_session, test_user):
        """upsert 更新时修改 project_id，查库验证。

        防什么：upsert 的 update 分支如果漏了 project_id 处理，更新时
        project_id 不会变。
        """
        from app.models.project import Project

        project = Project(user_id=test_user.id, name="测试项目", status="active")
        db_session.add(project)
        db_session.commit()

        svc = ReviewService(db_session, test_user.id)
        # 首次创建不带 project_id
        review = svc.upsert(UpsertReviewRequest(
            type="daily", date=date(2026, 10, 10), data=_make_review_data(),
        ))
        assert review.project_id is None

        # 更新时带上 project_id
        updated = svc.upsert(UpsertReviewRequest(
            type="daily", date=date(2026, 10, 10),
            project_id=project.id,
            data=_make_review_data(),
        ))
        assert updated.project_id == project.id

        # 查库验证
        db_session.expire_all()
        in_db = db_session.get(Review, review.id)
        assert in_db.project_id == project.id

    def test_upsert_identity_id_empty_string_unlinks(self, db_session, test_user):
        """upsert 时 identity_id 传空串，查库验证被解除关联（None）。

        防什么：_validated_identity_id 如果没处理空串，identity_id 会被
        设为空字符串而不是 None，后续按 identity 过滤时查不到。
        """
        from app.models.identity import Identity

        identity = Identity(
            user_id=test_user.id, name="学生", slug="student",
            color_token="primary", icon="star", is_active=True,
        )
        db_session.add(identity)
        db_session.commit()

        svc = ReviewService(db_session, test_user.id)
        # 首次创建带 identity_id
        review = svc.upsert(UpsertReviewRequest(
            type="daily", date=date(2026, 10, 10),
            identity_id=identity.id,
            data=_make_review_data(),
        ))
        assert review.identity_id == identity.id

        # 更新时传空串解除关联
        updated = svc.upsert(UpsertReviewRequest(
            type="daily", date=date(2026, 10, 10),
            identity_id="",
            data=_make_review_data(),
        ))
        assert updated.identity_id is None

        # 查库验证
        db_session.expire_all()
        in_db = db_session.get(Review, review.id)
        assert in_db.identity_id is None

    def test_upsert_data_fields_all_persist(self, db_session, test_user):
        """upsert 后查库验证 data 的所有字段都正确持久化。

        防什么：data 是 JSON 字段，如果某个字段没被序列化（比如 reflections
        的嵌套结构），会丢失数据。
        """
        svc = ReviewService(db_session, test_user.id)
        data = _make_review_data(
            completed_tasks="任务1、任务2",
            unfinished_tasks="任务3",
            gains="收获很大",
            reflections=[
                {"question": "Q1", "answer": "A1"},
                {"question": "Q2", "answer": "A2"},
            ],
            tomorrow_plan="明天继续",
            mood=5,
            energy=4,
        )
        out = svc.upsert(UpsertReviewRequest(
            type="daily", date=date(2026, 10, 10), data=data,
        ))

        # 查库验证 data 完整
        db_session.expire_all()
        in_db = db_session.get(Review, out.id)
        assert in_db.data["completed_tasks"] == "任务1、任务2"
        assert in_db.data["unfinished_tasks"] == "任务3"
        assert in_db.data["gains"] == "收获很大"
        assert len(in_db.data["reflections"]) == 2
        assert in_db.data["reflections"][0]["question"] == "Q1"
        assert in_db.data["tomorrow_plan"] == "明天继续"
        assert in_db.data["mood"] == 5
        assert in_db.data["energy"] == 4


# ============================================================
# 第 6 组：schema 校验 + project_id 越权 + 非法 priority + 删除后重建
# ============================================================

class TestGroup6ValidationProjectPriority:
    """第6组：mood/energy 范围校验 + project_id 不存在/越权 + convert_task 非法 priority + 删除后重建。"""

    def test_upsert_invalid_mood_rejected_by_schema(self, db_session, test_user):
        """upsert 时 mood 超出 1-5 范围被 Pydantic 校验拒绝，不产生复盘。

        防什么：如果 schema 的 ge/le 校验漏了，mood=6 会被写入数据库，
        前端展示异常。
        """
        from pydantic import ValidationError

        svc = ReviewService(db_session, test_user.id)
        with pytest.raises(ValidationError):
            # mood=6 在构造 ReviewData 时就会被 Pydantic 拒绝
            svc.upsert(UpsertReviewRequest(
                type="daily", date=date(2026, 10, 10),
                data=ReviewData(mood=6, energy=3),
            ))

        assert count_rows(db_session, "reviews", user_id=test_user.id) == 0

    def test_upsert_project_id_nonexistent_raises(self, db_session, test_user):
        """upsert 时指定不存在的 project_id 抛**业务异常**，且不产生复盘。

        防什么：project_id 是外键，如果 upsert 没有提前校验，SQLAlchemy 会
        抛 IntegrityError（→500）而不是友好的业务异常。

        断言具体类型 ValidationException（原先写的是宽泛的 Exception，
        注释还留着"IntegrityError 或 ValidationException"——等于没断言：
        真的退化成 IntegrityError 时这条用例照样绿）。同时补上
        「副作用为零」，否则"报错但已落库半条"这种更糟的情况测不出来。
        """
        svc = ReviewService(db_session, test_user.id)
        with pytest.raises(ValidationException):
            svc.upsert(UpsertReviewRequest(
                type="daily", date=date(2026, 10, 10),
                project_id="non-existent-project",
                data=_make_review_data(),
            ))
        assert count_rows(db_session, "reviews", user_id=test_user.id) == 0

    def test_upsert_project_id_other_user_raises(self, db_session, test_user, other_user):
        """upsert 时指定其他用户的 project_id 抛 ValidationException，不产生复盘。

        防什么：upsert 如果只检查 project 存在性而不检查归属，用户可以把
        复盘关联到别人的项目下。
        """
        from app.models.project import Project

        other_project = Project(user_id=other_user.id, name="他人项目", status="active")
        db_session.add(other_project)
        db_session.commit()

        svc = ReviewService(db_session, test_user.id)
        with pytest.raises(ValidationException, match="项目不存在"):
            svc.upsert(UpsertReviewRequest(
                type="daily", date=date(2026, 10, 10),
                project_id=other_project.id,
                data=_make_review_data(),
            ))

        assert count_rows(db_session, "reviews", user_id=test_user.id) == 0

    def test_convert_task_invalid_priority_falls_back_to_medium(self, db_session, test_user):
        """convert_task 时指定非法 priority，任务被降级为 medium（不抛异常）。

        防什么：TaskService.create 对非法 priority 的处理是降级为 medium，
        这条锁定行为。如果未来改为抛异常，这条会失败提醒更新。
        """
        from app.models.task import Task
        from app.schemas.review import ConvertTaskRequest

        svc = ReviewService(db_session, test_user.id)
        review = svc.upsert(UpsertReviewRequest(
            type="daily", date=date(2026, 10, 10), data=_make_review_data(),
        ))

        result = svc.convert_task(review.id, ConvertTaskRequest(
            content="任务", priority="invalid_priority",
        ))

        # 查库：priority 被降级为 medium
        db_session.expire_all()
        task = db_session.get(Task, result["task_id"])
        assert task.priority == "medium"

    def test_delete_then_upsert_same_date_creates_new(self, db_session, test_user):
        """删除复盘后，同日期同类型 upsert 创建新的复盘（不是恢复旧的）。

        防什么：如果 delete 用了软删除而 upsert 查到了软删除的记录，可能
        会恢复旧数据而不是创建新的。当前 delete 是硬删除，这条验证。
        """
        svc = ReviewService(db_session, test_user.id)
        first = svc.upsert(UpsertReviewRequest(
            type="daily", date=date(2026, 10, 10),
            data=_make_review_data(gains="第一次的收获"),
        ))
        first_id = first.id

        svc.delete(first_id)

        # 删除后同日期重建
        second = svc.upsert(UpsertReviewRequest(
            type="daily", date=date(2026, 10, 10),
            data=_make_review_data(gains="第二次的收获"),
        ))

        assert second.id != first_id  # 是新的 id
        assert second.data.gains == "第二次的收获"

        # 查库：只有一条
        assert count_rows(db_session, "reviews", user_id=test_user.id) == 1
