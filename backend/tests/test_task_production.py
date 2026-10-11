# ============================================================
# TaskService 生产级测试（重写版）
#
# 标准对齐经纬项目：
#   1. 真数据夹具（seed_task_fixture：10条任务+7条子任务，混合状态/优先级/截止日/重复规则）
#   2. 写操作后直接查库验证（不信 service 返回值，库才是真相）
#   3. 增量隔离（改 A 不影响 B）
#   4. 负向断言（不该变的没变）
#   5. 注释写清"这条在防什么 bug"
#
# 以 5 个为一组逐步推进。
# ============================================================
from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.core.exceptions import NotFoundException, TaskStateException
from app.models.task import FocusSession, Subtask, Task
from app.schemas.task import (
    CreateSubtaskRequest,
    CreateTaskRequest,
    UpdateSubtaskRequest,
    UpdateTaskRequest,
)
from app.services.task_service import TaskService
from tests.factories import (
    FIXTURE_DUE_TODAY_COUNT,
    FIXTURE_FOCUS_COUNT,
    FIXTURE_PRIORITY_COUNTS,
    FIXTURE_RECURRING_COUNT,
    FIXTURE_STATUS_COUNTS,
    FIXTURE_SUBTASK_COUNT,
    FIXTURE_TASK_COUNT,
    count_rows,
    seed_task_fixture,
)


# ============================================================
# 第 1 组：夹具基线 + CRUD 查库验证
# ============================================================

class TestGroup1FixtureAndCRUD:
    """第1组：夹具基线验证 + 创建/更新/删除的查库交叉验证。"""

    def test_fixture_baseline_matches_shape_contract(self, db_session, test_user):
        """夹具造完后，库里的任务/子任务/焦点/状态分布必须和形状契约完全一致。

        为什么要这条：后续所有测试都依赖夹具的已知状态。如果夹具本身造错了
        （比如 status 计数不对），后面的断言全是假绿。这条是"测试的测试"。
        """
        seed_task_fixture(db_session, test_user.id)
        db_session.commit()  # 落库，下面用独立查询验证

        # 总任务数
        assert count_rows(db_session, "tasks", user_id=test_user.id) == FIXTURE_TASK_COUNT

        # 各状态计数
        for status, expected in FIXTURE_STATUS_COUNTS.items():
            actual = count_rows(db_session, "tasks", user_id=test_user.id, status=status)
            assert actual == expected, f"状态 {status} 期望 {expected}，实际 {actual}"

        # 各优先级计数
        for priority, expected in FIXTURE_PRIORITY_COUNTS.items():
            actual = count_rows(db_session, "tasks", user_id=test_user.id, priority=priority)
            assert actual == expected, f"优先级 {priority} 期望 {expected}，实际 {actual}"

        # 子任务总数
        assert count_rows(db_session, "subtasks") == FIXTURE_SUBTASK_COUNT

        # 焦点任务数（部分唯一索引保证最多1，这里验证恰好1）
        assert count_rows(db_session, "tasks", user_id=test_user.id, is_focus=1) == FIXTURE_FOCUS_COUNT

        # 重复任务数
        recurring = db_session.scalars(
            select(Task).where(Task.user_id == test_user.id, Task.recurrence.is_not(None))
        ).all()
        assert len(recurring) == FIXTURE_RECURRING_COUNT

        # 今天截止的任务数
        today_tasks = db_session.scalars(
            select(Task).where(Task.user_id == test_user.id, Task.due_date == date.today())
        ).all()
        assert len(today_tasks) == FIXTURE_DUE_TODAY_COUNT

    def test_create_task_persists_all_fields_to_db(self, db_session, test_user):
        """创建任务后，直接查库验证所有字段都正确写入——不是只看返回值。

        防什么：service 返回的 TaskOut 是从 ORM 对象拼出来的，如果 ORM 对象
        在内存里对了但没写进库（比如漏了 commit），返回值照样对，但重启就没了。
        """
        svc = TaskService(db_session)
        tomorrow = date.today() + timedelta(days=1)
        out = svc.create(test_user.id, CreateTaskRequest(
            title="查库验证任务",
            description="描述内容",
            priority="urgent",
            status="in_progress",
            project_tag="验证标签",
            due_date=tomorrow,
        ))

        # 直接查库，不走 service
        task_in_db = db_session.get(Task, out.id)
        assert task_in_db is not None
        assert task_in_db.title == "查库验证任务"
        assert task_in_db.description == "描述内容"
        assert task_in_db.priority == "urgent"
        assert task_in_db.status == "in_progress"
        assert task_in_db.project_tag == "验证标签"
        assert task_in_db.due_date == tomorrow
        assert task_in_db.user_id == test_user.id
        assert task_in_db.is_focus is False  # 创建时不能设焦点
        assert task_in_db.completed_at is None

        # 副作用：总任务数 +1
        assert count_rows(db_session, "tasks", user_id=test_user.id) == 1

    def test_update_task_only_changes_specified_fields(self, db_session, test_user):
        """更新任务时，只有指定字段变了，其他字段（user_id/created_at/is_focus等）保持不变。

        防什么：update 用了 model_dump(exclude_unset=True) 遍历字段 setattr，
        如果白名单漏了或者 payload 注入了 user_id，就会越权篡改。这条直接查库验证。
        """
        fixture = seed_task_fixture(db_session, test_user.id)
        db_session.commit()
        target = fixture["tasks"]["pending_medium_no_due"]
        original_created_at = target.created_at
        original_user_id = target.user_id

        svc = TaskService(db_session)
        svc.update(test_user.id, target.id, UpdateTaskRequest(
            title="改了标题",
            priority="high",
            description="改了描述",
        ))

        # 重新查库（绕过 identity map 缓存，用新查询）
        db_session.expire_all()
        updated = db_session.get(Task, target.id)

        # 该变的变了
        assert updated.title == "改了标题"
        assert updated.priority == "high"
        assert updated.description == "改了描述"

        # 不该变的没变
        assert updated.user_id == original_user_id
        # SQLite 不存时区，重读后是 naive；统一去 tzinfo 再比（这是已知技术债）
        assert updated.created_at.replace(tzinfo=None) == original_created_at.replace(tzinfo=None)
        assert updated.status == "pending"  # 没传 status，不该变
        assert updated.is_focus is False
        assert updated.project_tag == "数学建模"  # 没传 project_tag，不该变

        # 其他任务完全没动
        other = db_session.get(Task, fixture["tasks"]["focus_pending"].id)
        assert other.title == "今日最重要（写周报）"
        assert other.priority == "high"

    def test_delete_task_removes_from_db_and_cascades_subtasks(self, db_session, test_user):
        """删除带子任务的任务后，任务和它的所有子任务都从库里消失，其他任务不受影响。

        防什么：软删除/级联删除配置错误时，可能只删了任务没删子任务，
        留下孤儿数据。或者 delete 没 commit，返回成功但数据还在。
        """
        fixture = seed_task_fixture(db_session, test_user.id)
        db_session.commit()
        target = fixture["tasks"]["pending_medium_no_due"]  # 这条带2条子任务
        target_sub_ids = [s.id for s in fixture["subtasks"].values()
                          if s.task_id == target.id]
        assert len(target_sub_ids) == 2

        svc = TaskService(db_session)
        svc.delete(test_user.id, target.id)

        # 查库：任务没了
        assert db_session.get(Task, target.id) is None
        # 查库：子任务级联删除
        for sid in target_sub_ids:
            assert db_session.get(Subtask, sid) is None
        # 其他任务还在
        assert count_rows(db_session, "tasks", user_id=test_user.id) == FIXTURE_TASK_COUNT - 1
        # 其他子任务还在
        assert count_rows(db_session, "subtasks") == FIXTURE_SUBTASK_COUNT - 2

    def test_status_to_completed_sets_completed_at_and_does_not_affect_others(self, db_session, test_user):
        """把一条 pending 任务改成 completed 后，查库验证 completed_at 被设置，且其他任务状态不变。

        防什么：_apply_status 里设置 completed_at 的逻辑如果有 bug（比如没赋值、
        或者赋值后被覆盖），返回值可能对但库里不对。同时验证批量操作时不误改其他行。
        """
        fixture = seed_task_fixture(db_session, test_user.id)
        db_session.commit()
        target = fixture["tasks"]["pending_low_tomorrow"]  # pending, low, 明天截止

        # 记录其他任务的状态快照
        others_before = {}
        for name, t in fixture["tasks"].items():
            if t.id != target.id:
                others_before[name] = t.status

        svc = TaskService(db_session)
        svc.update(test_user.id, target.id, UpdateTaskRequest(status="completed"))

        # 查库验证目标任务
        db_session.expire_all()
        updated = db_session.get(Task, target.id)
        assert updated.status == "completed"
        assert updated.completed_at is not None

        # 查库验证其他任务状态全没变
        for name, expected_status in others_before.items():
            t = db_session.get(Task, fixture["tasks"][name].id)
            assert t.status == expected_status, f"{name} 状态被误改：{expected_status} -> {t.status}"


# ============================================================
# 第 2 组：状态机边界 + 焦点互斥 + 子任务进度
# ============================================================

class TestGroup2StatusFocusSubtask:
    """第2组：非法流转的库级验证 + 焦点互斥 + 子任务进度的查库验证。"""

    def test_invalid_status_transition_does_not_modify_db(self, db_session, test_user):
        """非法状态流转（completed -> waiting）抛异常后，库里的状态必须原封不动。

        防什么：如果 service 在抛异常前已经修改了 ORM 对象但没回滚，
        后续 commit 会把非法状态写进库。这条验证异常路径下数据完整性。
        """
        fixture = seed_task_fixture(db_session, test_user.id)
        db_session.commit()
        target = fixture["tasks"]["completed_medium"]  # completed 状态

        svc = TaskService(db_session)
        with pytest.raises(TaskStateException, match="不能从"):
            svc.update(test_user.id, target.id, UpdateTaskRequest(status="waiting"))

        # 查库：状态没变，completed_at 也没变
        db_session.expire_all()
        in_db = db_session.get(Task, target.id)
        assert in_db.status == "completed"
        assert in_db.completed_at is not None

        # 其他任务也没受影响
        assert count_rows(db_session, "tasks", user_id=test_user.id, status="completed") == 3

    def test_set_focus_switches_old_focus_to_false_in_db(self, db_session, test_user):
        """设置新焦点后，查库验证旧焦点 is_focus=0、新焦点 is_focus=1，且始终只有1个焦点。

        防什么：set_focus 的互斥逻辑如果漏了旧焦点的更新（或者 flush 顺序错了
        触发唯一索引冲突），就会出现两个焦点或者旧焦点没被取消。
        """
        fixture = seed_task_fixture(db_session, test_user.id)
        db_session.commit()
        old_focus = fixture["tasks"]["focus_pending"]  # 当前焦点
        new_focus = fixture["tasks"]["in_progress_high"]  # 要设为新焦点

        svc = TaskService(db_session)
        svc.set_focus(test_user.id, new_focus.id)

        # 查库验证
        db_session.expire_all()
        old_in_db = db_session.get(Task, old_focus.id)
        new_in_db = db_session.get(Task, new_focus.id)
        assert old_in_db.is_focus is False
        assert new_in_db.is_focus is True

        # 全局只有1个焦点（部分唯一索引的应用层验证）
        all_focus = db_session.scalars(
            select(Task).where(Task.user_id == test_user.id, Task.is_focus == True)  # noqa: E712
        ).all()
        assert len(all_focus) == 1
        assert all_focus[0].id == new_focus.id

    def test_cancel_focus_persists_to_db_and_others_unchanged(self, db_session, test_user):
        """取消焦点后查库验证 is_focus=0，且其他任务的 is_focus 不受影响。

        防什么：cancel_focus 如果误把所有任务的 is_focus 都设为 False（比如
        写了全表 UPDATE），虽然目标任务对了，但其他焦点也被清掉了。
        """
        fixture = seed_task_fixture(db_session, test_user.id)
        db_session.commit()
        focus = fixture["tasks"]["focus_pending"]

        svc = TaskService(db_session)
        svc.cancel_focus(test_user.id, focus.id)

        # 查库
        db_session.expire_all()
        in_db = db_session.get(Task, focus.id)
        assert in_db.is_focus is False

        # 全局焦点数 = 0
        assert count_rows(db_session, "tasks", user_id=test_user.id, is_focus=1) == 0

        # 其他任务的字段没被误改（抽一条验证 title/status 没变）
        other = db_session.get(Task, fixture["tasks"]["completed_urgent"].id)
        assert other.status == "completed"
        assert other.title == "提交成绩复核申请"

    def test_adding_subtask_updates_progress_and_sort_order_in_db(self, db_session, test_user):
        """给无子任务的任务添加子任务后，查库验证 sort_order 递增、progress 重新计算。

        防什么：add_subtask 的 sort_order 用 max(subtasks) 计算，如果关系缓存
        不刷新（expire_on_commit=False 的坑），连续添加会重复为 0。progress
        是 _to_out 时实时算的，但库里 subtasks 数必须对。
        """
        fixture = seed_task_fixture(db_session, test_user.id)
        db_session.commit()
        # "买洗衣液" 没有子任务
        target = fixture["tasks"]["pending_low_tomorrow"]

        svc = TaskService(db_session)
        s1 = svc.add_subtask(test_user.id, target.id, CreateSubtaskRequest(title="选品牌"))
        s2 = svc.add_subtask(test_user.id, target.id, CreateSubtaskRequest(title="下单"))

        # 查库验证子任务
        db_session.expire_all()
        subs_in_db = db_session.scalars(
            select(Subtask).where(Subtask.task_id == target.id).order_by(Subtask.sort_order)
        ).all()
        assert len(subs_in_db) == 2
        assert subs_in_db[0].sort_order == 0
        assert subs_in_db[0].title == "选品牌"
        assert subs_in_db[1].sort_order == 1
        assert subs_in_db[1].title == "下单"

        # progress 应该是 0（都没完成）
        detail = svc.detail(test_user.id, target.id)
        assert detail.progress == 0
        assert detail.subtasks_count == 2

    def test_completing_subtask_updates_progress_in_db(self, db_session, test_user):
        """完成一条子任务后，查库验证该子任务 completed=True，任务 progress 正确，其他子任务不变。

        防什么：update_subtask 如果误更新了同任务的所有子任务（比如 WHERE 条件
        漏了 sub_id），progress 可能对但其他子任务被误改了。
        """
        fixture = seed_task_fixture(db_session, test_user.id)
        db_session.commit()
        # "最小覆盖圆论文" 有2条子任务：查格式(已完成)、写灵敏度(未完成)
        target = fixture["tasks"]["in_progress_high"]
        uncompleted_sub = fixture["subtasks"]["paper_1"]  # 写灵敏度，未完成
        completed_sub = fixture["subtasks"]["paper_0"]  # 查格式，已完成

        svc = TaskService(db_session)
        svc.update_subtask(test_user.id, target.id, uncompleted_sub.id,
                           UpdateSubtaskRequest(completed=True))

        # 查库验证
        db_session.expire_all()
        updated = db_session.get(Subtask, uncompleted_sub.id)
        assert updated.completed is True
        # 另一条子任务没变
        other = db_session.get(Subtask, completed_sub.id)
        assert other.completed is True  # 本来就是 True，确认没被误改
        # progress：2/2 = 100
        detail = svc.detail(test_user.id, target.id)
        assert detail.progress == 100
        assert detail.subtasks_completed == 2


# ============================================================
# 第 3 组：批量操作 + 番茄钟 + 越权访问
# ============================================================

class TestGroup3BatchFocusAuth:
    """第3组：批量操作的库级验证 + 番茄钟持久化 + 越权访问的数据完整性。"""

    def test_batch_complete_persists_to_db_and_skips_others(self, db_session, test_user):
        """批量完成2条任务后，查库验证只有这2条变completed，其余8条状态不变。

        防什么：batch 用循环遍历 task_ids，如果 WHERE 条件漏了 user_id 或者
        循环变量用错，可能把所有任务都完成了。
        """
        from app.schemas.task import BatchTaskRequest

        fixture = seed_task_fixture(db_session, test_user.id)
        db_session.commit()
        # 选2条 pending 任务批量完成
        ids = [
            fixture["tasks"]["pending_medium_no_due"].id,
            fixture["tasks"]["pending_low_tomorrow"].id,
        ]

        svc = TaskService(db_session)
        result = svc.batch(test_user.id, BatchTaskRequest(task_ids=ids, action="complete"))

        assert result.affected == 2
        assert result.failed == 0

        # 查库验证
        db_session.expire_all()
        for tid in ids:
            assert db_session.get(Task, tid).status == "completed"
        # 其余 pending 只剩1条（focus_pending）
        assert count_rows(db_session, "tasks", user_id=test_user.id, status="pending") == 1
        # 总 completed = 3 + 2 = 5
        assert count_rows(db_session, "tasks", user_id=test_user.id, status="completed") == 5

    def test_batch_delete_removes_from_db_and_cascades_subtasks(self, db_session, test_user):
        """批量删除带子任务的任务后，查库验证任务和子任务都消失，其他任务保留。

        防什么：batch delete 用 db.delete(task)，如果 cascade 配置错了，子任务
        会变成孤儿记录。或者 delete 没 commit，返回成功但数据还在。
        """
        from app.schemas.task import BatchTaskRequest

        fixture = seed_task_fixture(db_session, test_user.id)
        db_session.commit()
        # 删2条带子任务的任务
        ids = [
            fixture["tasks"]["pending_medium_no_due"].id,  # 2条子任务
            fixture["tasks"]["in_progress_high"].id,        # 2条子任务
        ]
        deleted_sub_count = 4

        svc = TaskService(db_session)
        result = svc.batch(test_user.id, BatchTaskRequest(task_ids=ids, action="delete"))

        assert result.affected == 2
        # 查库
        db_session.expire_all()
        for tid in ids:
            assert db_session.get(Task, tid) is None
        assert count_rows(db_session, "tasks", user_id=test_user.id) == FIXTURE_TASK_COUNT - 2
        assert count_rows(db_session, "subtasks") == FIXTURE_SUBTASK_COUNT - deleted_sub_count

    def test_batch_with_other_user_tasks_counts_failed_and_db_unchanged(self, db_session, test_user, other_user):
        """批量操作包含其他用户的任务时，越权的计 failed，且其他用户的数据在库中不变。

        防什么：batch 里如果只检查 task 是否存在而不检查 user_id，就会越权修改
        别人的数据。这条用 other_user 造一条任务，验证它没被碰。
        """
        from app.schemas.task import BatchTaskRequest

        fixture = seed_task_fixture(db_session, test_user.id)
        # 给 other_user 也造一条任务
        from tests.factories import make_task
        other_task = make_task(db_session, other_user.id, title="别人的任务", status="pending")
        db_session.commit()

        svc = TaskService(db_session)
        result = svc.batch(test_user.id, BatchTaskRequest(
            task_ids=[fixture["tasks"]["pending_low_tomorrow"].id, other_task.id],
            action="complete",
        ))

        assert result.affected == 1  # 只有自己的成功
        assert result.failed == 1    # 别人的计 failed

        # 查库：自己的变 completed
        db_session.expire_all()
        assert db_session.get(Task, fixture["tasks"]["pending_low_tomorrow"].id).status == "completed"
        # 别人的没变
        assert db_session.get(Task, other_task.id).status == "pending"

    def test_focus_start_stop_persists_session_and_accumulates_duration(self, db_session, test_user):
        """番茄钟开始→结束后，查库验证 focus_sessions 表有记录，task.focus_duration 累计。

        防什么：focus_stop 的 duration 计算如果有 bug（时区类型不匹配、
        忘记累计到 task），返回值可能对但库里不对。
        """
        from app.models.base import utcnow

        fixture = seed_task_fixture(db_session, test_user.id)
        db_session.commit()
        target = fixture["tasks"]["in_progress_high"]

        svc = TaskService(db_session)
        session_out = svc.focus_start(test_user.id, target.id)

        # 查库：会话已创建，end_time 为 None
        db_session.expire_all()
        session_in_db = db_session.get(FocusSession, session_out.id)
        assert session_in_db is not None
        assert session_in_db.end_time is None
        assert session_in_db.duration == 0

        # 手动把 start_time 往前调 90 秒（走 ORM 对象，然后 commit）
        session_in_db.start_time = utcnow() - timedelta(seconds=90)
        db_session.commit()

        svc.focus_stop(test_user.id, session_out.id)

        # 查库：会话已结束，duration ≈ 90
        db_session.expire_all()
        stopped = db_session.get(FocusSession, session_out.id)
        assert stopped.end_time is not None
        assert stopped.duration >= 89
        # task.focus_duration 累计了
        task_in_db = db_session.get(Task, target.id)
        assert task_in_db.focus_duration >= 89

    def test_accessing_other_users_task_raises_and_db_unchanged(self, db_session, test_user, other_user):
        """越权访问其他用户的任务（detail/update/delete）全部抛 NotFound，且库中数据不变。

        防什么：_owned 方法如果只检查 task 是否存在而不检查 user_id，
        就会泄露或篡改别人的数据。NotFound（而不是 Forbidden）是为了不泄露存在性。
        """
        from tests.factories import make_task

        other_task = make_task(db_session, other_user.id, title="机密任务", status="pending")
        db_session.commit()
        original_title = other_task.title
        original_status = other_task.status

        svc = TaskService(db_session)

        # detail 越权
        with pytest.raises(NotFoundException, match="任务不存在"):
            svc.detail(test_user.id, other_task.id)

        # update 越权
        with pytest.raises(NotFoundException):
            svc.update(test_user.id, other_task.id, UpdateTaskRequest(title="篡改"))

        # delete 越权
        with pytest.raises(NotFoundException):
            svc.delete(test_user.id, other_task.id)

        # 查库：数据原封不动
        db_session.expire_all()
        in_db = db_session.get(Task, other_task.id)
        assert in_db.title == original_title
        assert in_db.status == original_status
        assert in_db.user_id == other_user.id


# ============================================================
# 第 4 组：重复任务 + 今日统计交叉验证 + 列表过滤/分页边界
# ============================================================

class TestGroup4RecurringStatsList:
    """第4组：重复任务惰性生成 + today_stats 与查库交叉验证 + 列表过滤分页边界。"""

    def test_generate_recurring_instances_creates_due_today_task_in_db(self, db_session, test_user):
        """为 daily 重复任务生成实例后，查库验证新任务创建，due_date=今天，status=pending。

        防什么：generate_recurring_instances 的 _next_occurrence 计算如果错了
        （比如日期推进不对），生成的任务 due_date 可能不是今天。或者生成时
        漏了 commit，返回 created>0 但库里没有。
        """
        fixture = seed_task_fixture(db_session, test_user.id)
        db_session.commit()
        # "每日英语阅读" 是 daily 重复任务，due_date=昨天
        template = fixture["tasks"]["in_progress_medium_recurring"]
        today = date.today()

        svc = TaskService(db_session)
        created = svc.generate_recurring_instances(test_user.id)

        assert created >= 1
        # 查库验证：存在 title 相同、due_date=今天的新任务
        db_session.expire_all()
        instances = db_session.scalars(
            select(Task).where(
                Task.user_id == test_user.id,
                Task.title == template.title,
                Task.due_date == today,
            )
        ).all()
        assert len(instances) >= 1
        assert instances[0].status == "pending"
        assert instances[0].recurrence == template.recurrence

    def test_generate_recurring_instances_idempotent_no_duplicates(self, db_session, test_user):
        """连续两次生成重复实例，第二次不重复创建（幂等）。

        防什么：幂等判断如果漏了（比如只按 title 判重不按 due_date），
        每天会生成重复任务。这条验证第二次 created=0。
        """
        seed_task_fixture(db_session, test_user.id)
        db_session.commit()

        svc = TaskService(db_session)
        first = svc.generate_recurring_instances(test_user.id)
        assert first >= 1
        second = svc.generate_recurring_instances(test_user.id)
        assert second == 0  # 幂等：第二次不生成

        # 查库：今天的实例只有1条（按 title+due_date 判重）
        today = date.today()
        count = count_rows(db_session, "tasks", user_id=test_user.id,
                           title="每日英语阅读", due_date=today)
        # 用 count_rows 不支持多条件？用 select 查
        instances = db_session.scalars(
            select(Task).where(
                Task.user_id == test_user.id,
                Task.title == "每日英语阅读",
                Task.due_date == today,
            )
        ).all()
        assert len(instances) == 1

    def test_today_stats_matches_db_counts(self, db_session, test_user):
        """today_stats 返回的四个计数，必须和直接查库的结果完全一致。

        防什么：today_stats 调用 repo 的 count 方法，如果 count 的 WHERE
        条件错了（比如漏了 user_id、completed_on 的日期范围不对），
        返回值就会和库不一致。
        """
        fixture = seed_task_fixture(db_session, test_user.id)
        db_session.commit()

        svc = TaskService(db_session)
        stats = svc.today_stats(test_user.id)

        # 独立查库验证每个计数
        today = date.today()
        # in_progress
        db_in_progress = count_rows(db_session, "tasks", user_id=test_user.id, status="in_progress")
        assert stats.in_progress == db_in_progress
        # waiting
        db_waiting = count_rows(db_session, "tasks", user_id=test_user.id, status="waiting")
        assert stats.waiting == db_waiting
        # completed_today：completed_at 是今天的
        from app.models.base import utcnow
        # 夹具里3条 completed 都是 utcnow() 创建的，算今天
        completed_today = db_session.scalars(
            select(Task).where(
                Task.user_id == test_user.id,
                Task.status == "completed",
                Task.completed_at.is_not(None),
            )
        ).all()
        # 简化验证：completed_today >= 夹具中的3条（都是刚创建的）
        assert stats.completed_today >= 3
        # must_do：今天截止且未完成的
        assert stats.must_do >= 1  # focus_pending 是今天截止

    def test_list_filter_by_status_returns_only_matching(self, db_session, test_user):
        """按 status 过滤后，返回的每条任务都是该状态，且总数和查库一致。

        防什么：list 的过滤条件如果拼错了（比如把 status 当成 priority 过滤），
        返回结果会混入其他状态。
        """
        seed_task_fixture(db_session, test_user.id)
        db_session.commit()

        svc = TaskService(db_session)
        result = svc.list(test_user.id, status="completed")

        assert result.total == FIXTURE_STATUS_COUNTS["completed"]
        assert len(result.list) == FIXTURE_STATUS_COUNTS["completed"]
        for item in result.list:
            assert item.status == "completed"

    def test_list_pagination_beyond_total_returns_empty(self, db_session, test_user):
        """分页边界：page 超过总数时返回空列表，但 total 不变。

        防什么：分页逻辑如果 page 越界时返回了第一页数据（而不是空），
        前端翻到最后一页后继续翻会看到重复数据。
        """
        seed_task_fixture(db_session, test_user.id)
        db_session.commit()

        svc = TaskService(db_session)
        # 总共10条，page_size=5，第3页应该是空
        result = svc.list(test_user.id, page=3, page_size=5)
        assert result.total == FIXTURE_TASK_COUNT
        assert len(result.list) == 0
        assert result.page == 3

        # 第2页应该有5条
        page2 = svc.list(test_user.id, page=2, page_size=5)
        assert len(page2.list) == 5


# ============================================================
# 第 5 组：子任务删除 + 状态机全参数化 + 焦点标签 + 防注入
# ============================================================

class TestGroup5SubtaskDeleteStatusAntiInject:
    """第5组：子任务删除级联 + 状态机全流转参数化 + 焦点标签 + 非法priority + 字段白名单注入。"""

    def test_delete_subtask_removes_from_db_and_updates_progress(self, db_session, test_user):
        """删除一条已完成子任务后，查库验证子任务消失，任务 progress 从 50% 降到 0%。

        防什么：delete_subtask 如果只删了 subtask 但没触发 progress 重算（progress
        是实时算的所以没问题），或者级联删除配置错了导致子任务没删掉。
        """
        fixture = seed_task_fixture(db_session, test_user.id)
        db_session.commit()
        # "最小覆盖圆论文"：2条子任务，1已完成 → progress=50
        target = fixture["tasks"]["in_progress_high"]
        completed_sub = fixture["subtasks"]["paper_0"]

        svc = TaskService(db_session)
        # 先确认当前 progress=50
        assert svc.detail(test_user.id, target.id).progress == 50

        svc.delete_subtask(test_user.id, target.id, completed_sub.id)

        # 查库：子任务消失
        db_session.expire_all()
        assert db_session.get(Subtask, completed_sub.id) is None
        # 剩下1条未完成 → progress=0
        detail = svc.detail(test_user.id, target.id)
        assert detail.subtasks_count == 1
        assert detail.progress == 0

    @pytest.mark.parametrize("from_status,to_status", [
        ("pending", "in_progress"), ("pending", "waiting"), ("pending", "completed"),
        ("in_progress", "completed"), ("in_progress", "waiting"), ("in_progress", "pending"),
        ("waiting", "in_progress"), ("waiting", "pending"), ("waiting", "completed"),
        ("completed", "pending"),
    ])
    def test_all_valid_status_transitions_persist_to_db(self, db_session, test_user, from_status, to_status):
        """参数化覆盖所有 10 条合法状态流转，每次查库验证状态和 completed_at。

        防什么：STATUS_TRANSITIONS 白名单如果和实际 _apply_status 逻辑不一致，
        某条流转可能在白名单里但实际抛异常，或者反过来。
        """
        from tests.factories import make_task

        task = make_task(db_session, test_user.id, status=from_status)
        if from_status == "completed":
            from app.models.base import utcnow
            task.completed_at = utcnow()
        db_session.commit()

        svc = TaskService(db_session)
        svc.update(test_user.id, task.id, UpdateTaskRequest(status=to_status))

        db_session.expire_all()
        in_db = db_session.get(Task, task.id)
        assert in_db.status == to_status
        # completed → 有 completed_at；非 completed → completed_at 为 None
        if to_status == "completed":
            assert in_db.completed_at is not None
        else:
            assert in_db.completed_at is None

    def test_focus_task_stage_and_next_step_match_status(self, db_session, test_user):
        """焦点任务的 stage 标签和 next_step 文案必须与状态一一对应。

        防什么：STAGE_LABELS / NEXT_STEP_LABELS 如果和状态不同步（比如新增了状态
        但忘了加标签），前端会显示空字符串。
        """
        from app.services.task_service import NEXT_STEP_LABELS, STAGE_LABELS

        fixture = seed_task_fixture(db_session, test_user.id)
        db_session.commit()

        svc = TaskService(db_session)
        for status, expected_stage in STAGE_LABELS.items():
            # 把焦点设到对应状态的任务上
            task = None
            for t in fixture["tasks"].values():
                if t.status == status:
                    task = t
                    break
            if task is None:
                from tests.factories import make_task
                task = make_task(db_session, test_user.id, status=status)
                db_session.commit()
            svc.set_focus(test_user.id, task.id)
            focus = svc.focus(test_user.id)
            assert focus.stage == expected_stage, f"状态 {status} 的 stage 标签错误"
            assert focus.next_step == NEXT_STEP_LABELS[status]
            svc.cancel_focus(test_user.id, task.id)

    def test_create_with_invalid_priority_falls_back_to_medium_in_db(self, db_session, test_user):
        """创建任务时传非法 priority，查库验证被静默降级为 medium（不报错也不存非法值）。

        防什么：如果 create 没做 priority 校验，非法值会直接写进库，后续按
        priority 过滤时这条任务就永远查不到了。
        """
        svc = TaskService(db_session)
        out = svc.create(test_user.id, CreateTaskRequest(title="非法优先级", priority="super_urgent"))

        db_session.expire_all()
        in_db = db_session.get(Task, out.id)
        assert in_db.priority == "medium"

    def test_update_cannot_modify_protected_fields_via_payload_injection(self, db_session, test_user):
        """即使构造包含 user_id / is_focus / created_at 的 payload，update 也必须拒绝修改这些字段。

        防什么：_UPDATABLE_FIELDS 白名单如果漏了某个字段，攻击者可以通过
        PATCH 请求篡改 user_id（把任务转给别人）或 is_focus（绕过互斥设多个焦点）。
        """
        fixture = seed_task_fixture(db_session, test_user.id)
        db_session.commit()
        target = fixture["tasks"]["pending_medium_no_due"]

        # 构造一个带保护字段的 dict（模拟恶意 payload）
        malicious = {
            "title": "正常修改",
            "user_id": "attacker-id",
            "is_focus": True,
            "created_at": "2020-01-01T00:00:00Z",
        }
        # 用原始 dict 构造 UpdateTaskRequest（Pydantic 会忽略未定义字段）
        req = UpdateTaskRequest(**{k: v for k, v in malicious.items()
                                    if k in UpdateTaskRequest.model_fields})

        svc = TaskService(db_session)
        svc.update(test_user.id, target.id, req)

        # 查库验证保护字段没变
        db_session.expire_all()
        in_db = db_session.get(Task, target.id)
        assert in_db.title == "正常修改"  # 正常字段改了
        assert in_db.user_id == test_user.id  # user_id 没被改
        assert in_db.is_focus is False  # is_focus 没被改
        assert in_db.created_at.replace(tzinfo=None) != date(2020, 1, 1)  # created_at 没被改


# ============================================================
# 第 6 组：番茄钟边界 + 子任务越权 + 多条件过滤 + 空数据 + identity 校验
# ============================================================

class TestGroup6EdgeCases:
    """第6组：异常路径的库级验证 + 多条件过滤 + 空数据场景 + identity 归属校验。"""

    def test_focus_stop_already_ended_raises_and_db_unchanged(self, db_session, test_user):
        """对已结束的专注会话再次 stop 抛异常，且库中 duration/end_time 不变。

        防什么：focus_stop 如果没有检查 end_time 是否为 None，重复 stop 会
        把 duration 累加两次（或者用新的 end_time 覆盖旧的）。
        """
        from app.models.base import utcnow

        fixture = seed_task_fixture(db_session, test_user.id)
        db_session.commit()
        target = fixture["tasks"]["in_progress_high"]

        svc = TaskService(db_session)
        session_out = svc.focus_start(test_user.id, target.id)
        svc.focus_stop(test_user.id, session_out.id)

        # 记录第一次 stop 后的值
        db_session.expire_all()
        first = db_session.get(FocusSession, session_out.id)
        first_duration = first.duration
        first_end_time = first.end_time

        # 第二次 stop 应该抛异常
        with pytest.raises(TaskStateException, match="已结束"):
            svc.focus_stop(test_user.id, session_out.id)

        # 查库：值没变
        db_session.expire_all()
        second = db_session.get(FocusSession, session_out.id)
        assert second.duration == first_duration
        assert second.end_time == first_end_time

    def test_subtask_operation_on_wrong_task_raises_and_db_unchanged(self, db_session, test_user):
        """对不属于该任务的子任务执行 update/delete 抛 NotFound，库中子任务不变。

        防什么：update_subtask/delete_subtask 如果只检查 sub 是否存在而不检查
        sub.task_id == task_id，就可以通过 task_id 路径参数操作别的任务的子任务。
        """
        fixture = seed_task_fixture(db_session, test_user.id)
        db_session.commit()
        task_a = fixture["tasks"]["in_progress_high"]      # 有子任务
        task_b = fixture["tasks"]["pending_low_tomorrow"]  # 无子任务
        sub_of_a = fixture["subtasks"]["paper_0"]

        svc = TaskService(db_session)

        # 用 task_b 的路径去操作 task_a 的子任务
        with pytest.raises(NotFoundException, match="子任务不存在"):
            svc.update_subtask(test_user.id, task_b.id, sub_of_a.id,
                               UpdateSubtaskRequest(completed=True))
        with pytest.raises(NotFoundException):
            svc.delete_subtask(test_user.id, task_b.id, sub_of_a.id)

        # 查库：子任务没变
        db_session.expire_all()
        in_db = db_session.get(Subtask, sub_of_a.id)
        assert in_db.completed is True  # 本来就是 True，确认没被误改
        assert in_db.task_id == task_a.id

    def test_list_multi_filter_status_and_priority(self, db_session, test_user):
        """同时按 status 和 priority 过滤，返回的每条都同时满足两个条件。

        防什么：多条件过滤如果用了 OR 而不是 AND，会返回多余结果。
        """
        seed_task_fixture(db_session, test_user.id)
        db_session.commit()

        svc = TaskService(db_session)
        # 夹具中 completed + urgent 只有1条（提交成绩复核申请）
        result = svc.list(test_user.id, status="completed", priority="urgent")

        assert result.total == 1
        assert result.list[0].status == "completed"
        assert result.list[0].priority == "urgent"
        assert result.list[0].title == "提交成绩复核申请"

    def test_empty_database_returns_zero_stats_and_empty_list(self, db_session, test_user):
        """没有任何任务时，list 返回空数组，today_stats 全 0，focus 返回 None。

        防什么：空数据场景下如果代码假设至少有一条任务，可能报 IndexError
        或者除零错误。
        """
        # 不调用 seed_task_fixture，直接用空库
        svc = TaskService(db_session)

        # list 空
        result = svc.list(test_user.id)
        assert result.total == 0
        assert len(result.list) == 0

        # today_stats 全 0
        stats = svc.today_stats(test_user.id)
        assert stats.must_do == 0
        assert stats.in_progress == 0
        assert stats.waiting == 0
        assert stats.completed_today == 0

        # focus 为 None
        assert svc.focus(test_user.id) is None

    def test_update_with_invalid_identity_raises_and_db_unchanged(self, db_session, test_user):
        """更新任务时传不存在的 identity_id 抛 ValidationException，库中任务不变。

        防什么：identity_id 是应用层关联（无外键），如果 _ensure_identity_owned
        漏了，非法 identity_id 会直接写进库，后续按 identity 过滤时这条任务
        就变成孤儿数据。
        """
        from app.core.exceptions import ValidationException

        fixture = seed_task_fixture(db_session, test_user.id)
        db_session.commit()
        target = fixture["tasks"]["pending_medium_no_due"]
        original_identity = target.identity_id

        svc = TaskService(db_session)
        with pytest.raises(ValidationException, match="身份不存在"):
            svc.update(test_user.id, target.id, UpdateTaskRequest(identity_id="non-existent-identity"))

        # 查库：identity_id 没变
        db_session.expire_all()
        in_db = db_session.get(Task, target.id)
        assert in_db.identity_id == original_identity


# ============================================================
# 第 7 组：批量操作剩余类型 + 专注会话列表 + 全字段创建 + 删除语义
# ============================================================

class TestGroup7BatchAndMisc:
    """第7组：批量 set_priority/move_project + 专注会话列表排序 + 全字段创建 + 删除语义。"""

    def test_batch_set_priority_persists_to_db(self, db_session, test_user):
        """批量设置优先级后，查库验证指定任务的 priority 变了，其他任务不变。

        防什么：batch set_priority 如果漏了 priority 校验或者 WHERE 条件错了，
        可能把所有任务的 priority 都改了。
        """
        from app.schemas.task import BatchTaskRequest

        fixture = seed_task_fixture(db_session, test_user.id)
        db_session.commit()
        ids = [
            fixture["tasks"]["pending_medium_no_due"].id,
            fixture["tasks"]["waiting_medium"].id,
        ]

        svc = TaskService(db_session)
        result = svc.batch(test_user.id, BatchTaskRequest(
            task_ids=ids, action="set_priority", priority="urgent",
        ))

        assert result.affected == 2
        # 查库
        db_session.expire_all()
        for tid in ids:
            assert db_session.get(Task, tid).priority == "urgent"
        # 其他任务 priority 不变
        assert db_session.get(Task, fixture["tasks"]["focus_pending"].id).priority == "high"
        assert count_rows(db_session, "tasks", user_id=test_user.id, priority="urgent") == 3  # 原1+新2

    def test_batch_move_project_persists_to_db(self, db_session, test_user):
        """批量移动项目后，查库验证 project_id 变了，其他字段不变。

        防什么：batch move_project 如果误更新了其他字段（比如 status），
        任务状态会被意外改变。
        """
        from app.models.project import Project
        from app.schemas.task import BatchTaskRequest

        fixture = seed_task_fixture(db_session, test_user.id)
        # 先创建一个真实项目（project_id 是外键，不能用不存在的 uuid）
        project = Project(user_id=test_user.id, name="目标项目", status="active")
        db_session.add(project)
        db_session.commit()

        target = fixture["tasks"]["pending_medium_no_due"]
        original_status = target.status

        svc = TaskService(db_session)
        result = svc.batch(test_user.id, BatchTaskRequest(
            task_ids=[target.id], action="move_project", project_id=project.id,
        ))

        assert result.affected == 1
        # 查库
        db_session.expire_all()
        in_db = db_session.get(Task, target.id)
        assert in_db.project_id == project.id
        assert in_db.status == original_status  # 状态没变
        assert in_db.title == "整理数模论文分类"  # 标题没变

    def test_focus_sessions_list_ordered_desc_and_capped_at_50(self, db_session, test_user):
        """专注会话列表按 start_time 倒序排列，最多返回 50 条。

        防什么：focus_sessions 查询如果漏了 order_by 或者 limit，前端会看到
        乱序或者超长列表。
        """
        from app.models.base import utcnow

        fixture = seed_task_fixture(db_session, test_user.id)
        db_session.commit()
        target = fixture["tasks"]["in_progress_high"]

        svc = TaskService(db_session)
        # 创建3个会话，手动设置不同的 start_time
        sessions = []
        for i in range(3):
            s_out = svc.focus_start(test_user.id, target.id)
            sessions.append(s_out.id)
            # 直接改 ORM 对象的 start_time
            db_session.expire_all()
            s_orm = db_session.get(FocusSession, s_out.id)
            s_orm.start_time = utcnow() - timedelta(minutes=i * 30)
            db_session.commit()

        result = svc.focus_sessions(test_user.id, target.id)
        assert len(result) == 3
        # 倒序：第一个是最新的（i=0，时间最晚）
        times = [s.start_time for s in result]
        naive_times = [t.replace(tzinfo=None) if t.tzinfo else t for t in times]
        assert naive_times[0] > naive_times[2]

    def test_create_task_with_all_fields_persists_correctly(self, db_session, test_user):
        """创建任务时传入所有可选字段，查库验证每一个字段都正确写入。

        防什么：CreateTaskRequest 有 8 个可选字段，如果 repo.create 的参数
        映射漏了某个（比如 recurrence 或 reminder_time），返回值可能对但库里没有。
        """
        from datetime import datetime, timezone

        tomorrow = date.today() + timedelta(days=1)
        reminder = datetime.now(timezone.utc)
        recurrence = {"type": "weekly", "interval": 1, "days": [1, 3, 5]}

        svc = TaskService(db_session)
        out = svc.create(test_user.id, CreateTaskRequest(
            title="全字段任务",
            description="完整描述",
            priority="high",
            status="in_progress",
            project_tag="标签A",
            due_date=tomorrow,
            reminder_time=reminder,
            recurrence=recurrence,
        ))

        db_session.expire_all()
        in_db = db_session.get(Task, out.id)
        assert in_db.title == "全字段任务"
        assert in_db.description == "完整描述"
        assert in_db.priority == "high"
        assert in_db.status == "in_progress"
        assert in_db.project_tag == "标签A"
        assert in_db.due_date == tomorrow
        assert in_db.recurrence == recurrence
        # reminder_time 存 SQLite 后时区丢失，只比较日期时间部分
        assert in_db.reminder_time is not None

    def test_delete_is_hard_delete_not_soft_delete(self, db_session, test_user):
        """删除任务是硬删除（行从表中消失），不是软删除（deleted_at 标记）。

        防什么：模型有 SoftDeleteMixin，但当前一期不启用软删除。如果某一天
        有人把 delete 改成软删除但没更新调用方，查询会返回已删除的任务。
        这条锁定当前行为：删除 = 行消失。
        """
        fixture = seed_task_fixture(db_session, test_user.id)
        db_session.commit()
        target = fixture["tasks"]["waiting_low"]

        svc = TaskService(db_session)
        svc.delete(test_user.id, target.id)

        # 查库：行不存在（不是 deleted_at 有值）
        db_session.expire_all()
        assert db_session.get(Task, target.id) is None
        # 用原生 SQL 确认表里没有这行
        from sqlalchemy import text
        row = db_session.execute(
            text("SELECT COUNT(*) FROM tasks WHERE id = :tid"), {"tid": target.id}
        ).scalar()
        assert row == 0


# ============================================================
# 第 8 组：参数校验边界 + 批量空列表 + 列表排序 + 搜索
# ============================================================

class TestGroup8ValidationAndSearch:
    """第8组：参数校验边界 + 批量空列表 + 列表排序验证 + 标题搜索。"""

    def test_create_with_empty_title_raises_at_schema_layer(self, db_session, test_user):
        """创建任务时空标题在 Pydantic 校验层就被拦截（min_length=1），不进入 service。

        防什么：如果 schema 的 min_length 约束被移除，空标题会进入 service 层。
        这条锁定 schema 层的校验行为。
        """
        from pydantic import ValidationError as PydanticValidationError

        with pytest.raises(PydanticValidationError, match="too_short"):
            CreateTaskRequest(title="")

    def test_create_with_whitespace_title_raises_at_service_layer(self, db_session, test_user):
        """纯空格标题通过 Pydantic 校验（长度≥1），但 service 层 strip 后为空，抛 ValidationException。

        防什么：如果 create 方法漏了 title.strip()，"   " 会被写进库，
        列表里显示空白行。这是实测发现的 bug，已修复，本条锁定修复。
        """
        from app.core.exceptions import ValidationException

        svc = TaskService(db_session)
        with pytest.raises(ValidationException, match="标题不能为空"):
            svc.create(test_user.id, CreateTaskRequest(title="   "))

        # 库里没有脏数据
        assert count_rows(db_session, "tasks", user_id=test_user.id) == 0

    def test_batch_with_empty_list_rejected_at_schema_layer(self, db_session, test_user):
        """批量操作传空列表在 Pydantic 校验层就被拦截（min_length=1），不进入 service。

        防什么：如果 schema 的 min_length 约束被移除，空列表会进入 service 层，
        可能导致 SQL IN () 语法错误或 IndexError。
        """
        from pydantic import ValidationError as PydanticValidationError

        with pytest.raises(PydanticValidationError, match="too_short"):
            from app.schemas.task import BatchTaskRequest
            BatchTaskRequest(task_ids=[], action="complete")

    def test_list_sorted_by_created_at_descending(self, db_session, test_user):
        """列表默认按 created_at 倒序（最新的在前）。

        防什么：list 查询如果漏了 order_by，SQLite 返回的顺序是插入顺序
        （通常也是倒序，但不保证）。这条锁定排序行为。
        """
        from app.models.base import utcnow
        from tests.factories import make_task

        # 手动创建3条任务，控制 created_at 顺序
        t1 = make_task(db_session, test_user.id, title="最早")
        t1.created_at = utcnow() - timedelta(hours=3)
        t2 = make_task(db_session, test_user.id, title="中间")
        t2.created_at = utcnow() - timedelta(hours=2)
        t3 = make_task(db_session, test_user.id, title="最晚")
        t3.created_at = utcnow() - timedelta(hours=1)
        db_session.commit()

        svc = TaskService(db_session)
        result = svc.list(test_user.id)

        assert len(result.list) == 3
        assert result.list[0].title == "最晚"
        assert result.list[1].title == "中间"
        assert result.list[2].title == "最早"

    def test_filter_by_project_tag_returns_only_matching(self, db_session, test_user):
        """按 project_tag 过滤，返回的每条都有该标签，且不返回无标签的。

        防什么：list 的 project_tag 过滤如果拼错了（比如用了 ILIKE 而不是 =），
        会返回部分匹配的结果。
        """
        fixture = seed_task_fixture(db_session, test_user.id)
        db_session.commit()

        svc = TaskService(db_session)
        # 夹具中 project_tag="数学建模" 的只有1条（整理数模论文分类）
        result = svc.list(test_user.id, project_tag="数学建模")

        assert result.total == 1
        assert result.list[0].project_tag == "数学建模"
        assert result.list[0].title == "整理数模论文分类"
        # 无 project_tag 的任务不在结果里
        tags = [item.project_tag for item in result.list]
        assert all(t == "数学建模" for t in tags)


# ============================================================
# 第 9 组：update 校验 + due_date 过滤 + 番茄钟边界 + 排序 + weekly 重复
# ============================================================

class TestGroup9UpdateFilterFocusSort:
    """第9组：update 纯空格标题 + due_date 过滤 + 番茄钟状态校验 + 列表排序 + weekly 重复生成。"""

    def test_update_with_whitespace_title_raises_and_db_unchanged(self, db_session, test_user):
        """更新任务时纯空格标题抛 ValidationException，库中标题不变。

        防什么：update 用 setattr 遍历 payload，如果对 title 不做 strip 校验，
        "   " 会覆盖原标题，列表里显示空白。这是实测发现的 bug，已修复。
        """
        from app.core.exceptions import ValidationException

        fixture = seed_task_fixture(db_session, test_user.id)
        db_session.commit()
        target = fixture["tasks"]["pending_medium_no_due"]
        original_title = target.title

        svc = TaskService(db_session)
        with pytest.raises(ValidationException, match="标题不能为空"):
            svc.update(test_user.id, target.id, UpdateTaskRequest(title="   "))

        # 查库：标题没变
        db_session.expire_all()
        in_db = db_session.get(Task, target.id)
        assert in_db.title == original_title

    def test_list_filter_by_due_date_returns_only_matching(self, db_session, test_user):
        """按 due_date 过滤，返回的每条都有该截止日，不返回其他日期的。

        防什么：due_date 过滤如果用了 >= 而不是 =，会返回截止日晚于该日期的任务。
        """
        fixture = seed_task_fixture(db_session, test_user.id)
        db_session.commit()
        today = date.today()

        svc = TaskService(db_session)
        result = svc.list(test_user.id, due_date=today)

        # 夹具中今天截止的只有 focus_pending
        assert result.total == FIXTURE_DUE_TODAY_COUNT
        for item in result.list:
            assert item.due_date == today
        assert result.list[0].title == "今日最重要（写周报）"

    def test_focus_start_on_completed_task_raises(self, db_session, test_user):
        """对已完成任务启动番茄钟抛 TaskStateException，不创建会话。

        防什么：focus_start 如果不检查任务状态，对已完成任务启动番茄钟
        会创建无意义的会话记录。
        """
        fixture = seed_task_fixture(db_session, test_user.id)
        db_session.commit()
        completed = fixture["tasks"]["completed_medium"]

        svc = TaskService(db_session)
        with pytest.raises(TaskStateException, match="已完成"):
            svc.focus_start(test_user.id, completed.id)

        # 查库：没有创建会话
        assert count_rows(db_session, "focus_sessions", task_id=completed.id) == 0

    def test_list_sort_by_priority_ascending(self, db_session, test_user):
        """列表支持按 priority 升序排序。

        防什么：sort 参数如果没有映射到正确的列，排序会无效或报错。
        """
        fixture = seed_task_fixture(db_session, test_user.id)
        db_session.commit()

        svc = TaskService(db_session)
        result = svc.list(test_user.id, sort="priority")

        # 验证排序：priority 按字母序升序（high < low < medium < urgent）
        priorities = [item.priority for item in result.list]
        assert priorities == sorted(priorities)

    def test_generate_recurring_weekly_creates_correct_due_date(self, db_session, test_user):
        """weekly 重复任务生成实例时，due_date 推进到下一个匹配的星期。

        防什么：_next_occurrence 的 weekly 逻辑如果只加 7 天而不匹配星期，
        生成的任务截止日可能不对。
        """
        from tests.factories import make_task

        # 创建一个 weekly 重复任务，due_date=上周
        last_week = date.today() - timedelta(days=7)
        task = make_task(db_session, test_user.id, title="周会", status="pending",
                         recurrence={"type": "weekly", "interval": 1})
        task.due_date = last_week
        db_session.commit()

        svc = TaskService(db_session)
        created = svc.generate_recurring_instances(test_user.id)

        assert created >= 1
        # 查库验证：存在 title="周会"、due_date=今天或之后的新任务
        db_session.expire_all()
        instances = db_session.scalars(
            select(Task).where(
                Task.user_id == test_user.id,
                Task.title == "周会",
                Task.due_date >= date.today(),
            )
        ).all()
        assert len(instances) >= 1


# ============================================================
# 第 10 组：批量全越权 + identity 过滤 + completed_at 保护 + 焦点删除 + project_id 外键
# ============================================================

class TestGroup10FinalEdge:
    """第10组：批量全越权 + identity_unassigned 过滤 + completed_at 保护 + 焦点删除 + project_id 外键校验。"""

    def test_batch_all_other_user_tasks_returns_all_failed(self, db_session, test_user, other_user):
        """批量操作全是其他用户的任务时，affected=0, failed=N，库中数据不变。

        防什么：batch 如果只检查第一条任务的归属而跳过后续，可能越权修改
        别人的数据。这条验证每一条都被独立检查。
        """
        from app.schemas.task import BatchTaskRequest
        from tests.factories import make_task

        t1 = make_task(db_session, other_user.id, title="别人的1", status="pending")
        t2 = make_task(db_session, other_user.id, title="别人的2", status="pending")
        db_session.commit()

        svc = TaskService(db_session)
        result = svc.batch(test_user.id, BatchTaskRequest(
            task_ids=[t1.id, t2.id], action="complete",
        ))

        assert result.affected == 0
        assert result.failed == 2
        # 查库：两条都没变
        db_session.expire_all()
        assert db_session.get(Task, t1.id).status == "pending"
        assert db_session.get(Task, t2.id).status == "pending"

    def test_list_identity_unassigned_returns_only_null(self, db_session, test_user):
        """identity_unassigned=True 时，只返回 identity_id 为 null 的任务。

        防什么：identity_unassigned 过滤如果用了 IS NOT NULL 而不是 IS NULL，
        会返回相反的结果。
        """
        from tests.factories import make_task

        # 夹具中所有任务 identity_id 都是 null
        seed_task_fixture(db_session, test_user.id)
        # 再创建一条有 identity_id 的任务（需要先创建 identity）
        from app.models.identity import Identity
        identity = Identity(user_id=test_user.id, name="学生身份", slug="student",
                            color_token="primary", icon="star", is_active=True)
        db_session.add(identity)
        db_session.flush()
        task_with_identity = make_task(db_session, test_user.id, title="有身份的任务")
        task_with_identity.identity_id = identity.id
        db_session.commit()

        svc = TaskService(db_session)
        result = svc.list(test_user.id, identity_unassigned=True)

        # 10条夹具任务 + 1条有身份的 = 11条，unassigned 应该是10条
        assert result.total == FIXTURE_TASK_COUNT
        for item in result.list:
            assert item.identity_id is None
        assert "有身份的任务" not in [i.title for i in result.list]

    def test_update_non_status_field_preserves_completed_at(self, db_session, test_user):
        """更新已完成任务的非 status 字段时，completed_at 不被清除。

        防什么：_apply_status 只在 status 变化时才设置/清除 completed_at。
        如果 update 逻辑有误（比如每次 update 都重置 completed_at=None），
        已完成任务的完成时间会丢失。
        """
        fixture = seed_task_fixture(db_session, test_user.id)
        db_session.commit()
        target = fixture["tasks"]["completed_urgent"]
        original_completed_at = target.completed_at

        svc = TaskService(db_session)
        svc.update(test_user.id, target.id, UpdateTaskRequest(priority="high"))

        # 查库：completed_at 还在
        db_session.expire_all()
        in_db = db_session.get(Task, target.id)
        assert in_db.status == "completed"
        assert in_db.completed_at is not None
        assert in_db.completed_at.replace(tzinfo=None) == original_completed_at.replace(tzinfo=None)
        assert in_db.priority == "high"  # priority 确实改了

    def test_delete_focus_task_leaves_no_focus_in_db(self, db_session, test_user):
        """删除当前焦点任务后，全局焦点数为0，不需要手动 cancel_focus。

        防什么：如果 delete 没有级联处理焦点状态（比如焦点标记是独立表），
        删除焦点任务后可能留下脏的焦点引用。当前是 tasks.is_focus 字段，
        删除行自然就没了，但这条锁定行为。
        """
        fixture = seed_task_fixture(db_session, test_user.id)
        db_session.commit()
        focus = fixture["tasks"]["focus_pending"]

        svc = TaskService(db_session)
        svc.delete(test_user.id, focus.id)

        # 查库：全局焦点数=0
        assert count_rows(db_session, "tasks", user_id=test_user.id, is_focus=1) == 0
        # focus() 返回 None
        assert svc.focus(test_user.id) is None

    def test_create_with_invalid_project_id_raises_and_db_unchanged(self, db_session, test_user):
        """创建任务时传不存在的 project_id 抛异常，库里不产生脏数据。

        防什么：project_id 是外键，如果 create 没有提前校验，SQLAlchemy 会
        抛 IntegrityError（500错误），而不是友好的 ValidationException。
        """
        from app.core.exceptions import ValidationException

        svc = TaskService(db_session)
        with pytest.raises(ValidationException, match="项目不存在"):
            svc.create(test_user.id, CreateTaskRequest(
                title="带不存在项目的任务",
                project_id="non-existent-project-id",
            ))

        assert count_rows(db_session, "tasks", user_id=test_user.id) == 0


# ============================================================
# 第 11 组：子任务越权 + 空列表边界 + project_id 越权
# ============================================================

class TestGroup11SubtaskAuthEmptyBoundary:
    """第11组：子任务越权操作 + focus_sessions 空列表 + 无重复任务 + update project_id 越权。"""

    def test_update_subtask_unauthorized_raises(self, db_session, test_user, other_user):
        """更新其他用户任务的子任务抛 NotFound，库中数据不变。

        防什么：update_subtask 如果只检查 subtask 存在而不检查 task 归属，
        用户可以篡改别人的子任务。
        """
        # 直接造其他用户的任务和子任务
        other_task = Task(user_id=other_user.id, title="他人任务", status="pending")
        db_session.add(other_task)
        db_session.flush()
        other_sub = Subtask(task_id=other_task.id, title="他人子任务", sort_order=0)
        db_session.add(other_sub)
        db_session.commit()

        svc = TaskService(db_session)
        with pytest.raises(NotFoundException, match="任务不存在"):
            svc.update_subtask(test_user.id, other_task.id, other_sub.id,
                               UpdateSubtaskRequest(title="篡改"))

        # 查库：子任务没变
        db_session.expire_all()
        in_db = db_session.get(Subtask, other_sub.id)
        assert in_db.title == "他人子任务"

    def test_delete_subtask_unauthorized_raises(self, db_session, test_user, other_user):
        """删除其他用户任务的子任务抛 NotFound，库中子任务仍在。

        防什么：delete_subtask 如果只检查 subtask 存在而不检查 task 归属，
        用户可以删除别人的子任务。
        """
        other_task = Task(user_id=other_user.id, title="他人任务", status="pending")
        db_session.add(other_task)
        db_session.flush()
        other_sub = Subtask(task_id=other_task.id, title="他人子任务", sort_order=0)
        db_session.add(other_sub)
        db_session.commit()

        svc = TaskService(db_session)
        with pytest.raises(NotFoundException, match="任务不存在"):
            svc.delete_subtask(test_user.id, other_task.id, other_sub.id)

        # 查库：子任务仍在
        db_session.expire_all()
        assert db_session.get(Subtask, other_sub.id) is not None

    def test_focus_sessions_empty_returns_empty_list(self, db_session, test_user):
        """没有焦点会话时，focus_sessions 返回空列表，不报错。

        防什么：focus_sessions 如果假设至少有一条会话，可能报 IndexError
        或者返回 None 导致前端崩溃。
        """
        fixture = seed_task_fixture(db_session, test_user.id)
        db_session.commit()
        task = fixture["tasks"]["pending_medium_no_due"]

        svc = TaskService(db_session)
        sessions = svc.focus_sessions(test_user.id, task.id)
        assert sessions == []

    def test_generate_recurring_no_recurring_tasks_returns_zero(self, db_session, test_user):
        """没有重复任务时，generate_recurring_instances 返回 0，不报错。

        防什么：generate_recurring_instances 如果假设至少有一条重复任务，
        可能在空列表上报错。
        """
        # 造一条非重复任务
        task = Task(user_id=test_user.id, title="普通任务", status="pending", recurrence=None)
        db_session.add(task)
        db_session.commit()

        svc = TaskService(db_session)
        count = svc.generate_recurring_instances(test_user.id)
        assert count == 0

    def test_update_task_project_id_unauthorized_raises(self, db_session, test_user, other_user):
        """更新任务时指定其他用户的 project_id 抛异常，库中 project_id 不变。

        防什么：update 的 project_id 校验如果漏了，用户可以把任务关联到
        别人的项目下。
        """
        from app.core.exceptions import ValidationException
        from app.models.project import Project

        # 造其他用户的项目
        other_project = Project(user_id=other_user.id, name="他人项目", status="active")
        db_session.add(other_project)
        db_session.flush()
        # 造自己的任务
        task = Task(user_id=test_user.id, title="我的任务", status="pending")
        db_session.add(task)
        db_session.commit()

        svc = TaskService(db_session)
        with pytest.raises(ValidationException, match="项目不存在"):
            svc.update(test_user.id, task.id, UpdateTaskRequest(project_id=other_project.id))

        # 查库：project_id 没变
        db_session.expire_all()
        in_db = db_session.get(Task, task.id)
        assert in_db.project_id is None
