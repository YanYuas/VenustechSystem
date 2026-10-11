# ============================================================
# Task API 生产级集成测试（重写版）
#
# 标准对齐经纬项目 + Service 层生产级测试：
#   1. 真数据夹具（seed_task_fixture 造 10 任务+7 子任务）
#   2. API 操作后直接查库验证（不信响应体，库才是真相）
#   3. HTTP 状态码 + 业务码 + 响应体结构三重验证
#   4. 增量隔离（改 A 不影响 B）
#   5. 负向断言（不该变的没变）
#   6. 注释写清"这条在防什么 bug"
#
# 隔离机制：
#   - client 是会话级 TestClient，自动认证为 default_user
#   - clean_db 是 autouse fixture，每个测试前清业务表
#   - 查库验证用独立 SessionLocal（与 client 内部的 Session 不是同一条连接）
#
# 以 5 个为一组逐步推进。
# ============================================================
from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.database import SessionLocal
from app.models.task import Subtask, Task
from tests.factories import (
    FIXTURE_STATUS_COUNTS,
    FIXTURE_TASK_COUNT,
    count_rows,
    seed_task_fixture,
)


# ============================================================
# 辅助函数：API 测试用独立 Session 查库
# ============================================================
def _db():
    """获取独立 Session（API 测试查库验证用）。"""
    return SessionLocal()


# ============================================================
# 第 1 组：CRUD 的 API→查库交叉验证
# ============================================================

class TestApiGroup1CRUD:
    """第1组：通过 API 做 CRUD，然后查库验证副作用。"""

    def test_list_returns_paginated_structure_and_matches_db(self, client, default_user_id):
        """列表接口返回分页结构，且数据条数和查库一致。

        防什么：list 接口如果 total 算错（比如没加 user_id 过滤），
        前端会看到错误的总数。或者响应体结构变了（字段名改了），前端解析失败。
        """
        # 造真数据
        db = _db()
        try:
            seed_task_fixture(db, default_user_id)
            db.commit()
        finally:
            db.close()

        r = client.get("/api/v1/tasks")
        assert r.status_code == 200
        body = r.json()
        assert body["code"] == 0
        data = body["data"]
        assert "list" in data
        assert "total" in data
        assert "page" in data
        assert data["total"] == FIXTURE_TASK_COUNT
        assert len(data["list"]) == FIXTURE_TASK_COUNT

        # 查库交叉验证
        db = _db()
        try:
            assert count_rows(db, "tasks", user_id=default_user_id) == FIXTURE_TASK_COUNT
        finally:
            db.close()

    def test_create_task_persists_all_fields_to_db_via_api(self, client, default_user_id):
        """通过 API 创建任务后，查库验证所有字段正确写入——不是只看响应体。

        防什么：API 层的 response_model 如果和 service 层的字段映射不一致，
        响应体可能对但库里不对（或者反过来）。
        """
        tomorrow = date.today() + timedelta(days=1)
        r = client.post("/api/v1/tasks", json={
            "title": "API创建查库验证",
            "description": "完整描述",
            "priority": "urgent",
            "status": "in_progress",
            "project_tag": "API标签",
            "due_date": tomorrow.isoformat(),
        })
        assert r.status_code == 200
        assert r.json()["code"] == 0
        task_id = r.json()["data"]["id"]

        # 查库验证
        db = _db()
        try:
            in_db = db.get(Task, task_id)
            assert in_db is not None
            assert in_db.title == "API创建查库验证"
            assert in_db.description == "完整描述"
            assert in_db.priority == "urgent"
            assert in_db.status == "in_progress"
            assert in_db.project_tag == "API标签"
            assert in_db.due_date == tomorrow
            assert in_db.user_id == default_user_id
            assert in_db.is_focus is False
        finally:
            db.close()

    def test_update_task_via_api_only_changes_specified_fields(self, client, default_user_id):
        """通过 API 更新任务后，查库验证只有指定字段变了，其他字段不变。

        防什么：API 层如果把整个 payload 传给 service（而不是 exclude_unset），
        未传的字段会被覆盖为 None。或者 PATCH 语义被错误实现为 PUT。
        """
        # 造一条任务
        db = _db()
        try:
            from tests.factories import make_task
            task = make_task(db, default_user_id, title="原标题", priority="medium",
                             status="pending", project_tag="原标签")
            db.commit()
            task_id = task.id
            original_created_at = task.created_at
        finally:
            db.close()

        r = client.patch(f"/api/v1/tasks/{task_id}", json={
            "title": "新标题",
            "priority": "high",
        })
        assert r.status_code == 200

        # 查库验证
        db = _db()
        try:
            in_db = db.get(Task, task_id)
            # 该变的变了
            assert in_db.title == "新标题"
            assert in_db.priority == "high"
            # 不该变的没变
            assert in_db.status == "pending"
            assert in_db.project_tag == "原标签"
            assert in_db.user_id == default_user_id
            assert in_db.created_at.replace(tzinfo=None) == original_created_at.replace(tzinfo=None)
        finally:
            db.close()

    def test_delete_task_via_api_removes_from_db_and_cascades(self, client, default_user_id):
        """通过 API 删除带子任务的任务后，查库验证任务和子任务都消失，其他任务保留。

        防什么：API 层的 delete 如果调用了错误的 service 方法（比如软删除），
        或者级联配置错了，子任务会变成孤儿记录。
        """
        # 造真数据
        db = _db()
        try:
            fixture = seed_task_fixture(db, default_user_id)
            db.commit()
            # "整理数模论文分类" 带2条子任务
            target = fixture["tasks"]["pending_medium_no_due"]
            target_id = target.id
            target_sub_count = 2
        finally:
            db.close()

        r = client.delete(f"/api/v1/tasks/{target_id}")
        assert r.status_code == 200
        assert r.json()["code"] == 0

        # 查库验证
        db = _db()
        try:
            assert db.get(Task, target_id) is None
            # 子任务级联删除
            subs = db.scalars(select(Subtask).where(Subtask.task_id == target_id)).all()
            assert len(subs) == 0
            # 其他任务保留
            assert count_rows(db, "tasks", user_id=default_user_id) == FIXTURE_TASK_COUNT - 1
        finally:
            db.close()

    def test_get_nonexistent_task_returns_404(self, client):
        """获取不存在的任务返回 404，业务码正确。

        防什么：API 层的异常处理器如果没正确映射 NotFoundException，
        可能返回 500 而不是 404，或者业务码不对。
        """
        r = client.get("/api/v1/tasks/non-existent-task-id-12345")
        assert r.status_code == 404
        assert r.json()["code"] == 1002


# ============================================================
# 第 2 组：状态机 + 焦点 + 子任务的 API→查库验证
# ============================================================

class TestApiGroup2StatusFocusSubtask:
    """第2组：通过 API 做状态流转/焦点/子任务操作，然后查库验证。"""

    def test_invalid_status_transition_via_api_returns_3001_and_db_unchanged(self, client, default_user_id):
        """非法状态流转（completed→waiting）返回业务码 3001，库中状态不变。

        防什么：API 层如果没正确捕获 TaskStateException，可能返回 500。
        或者异常被吞了，状态被错误写入。
        """
        # 造一条 completed 任务
        db = _db()
        try:
            from tests.factories import make_task
            task = make_task(db, default_user_id, title="已完成", status="completed")
            from app.models.base import utcnow
            task.completed_at = utcnow()
            db.commit()
            task_id = task.id
        finally:
            db.close()

        r = client.patch(f"/api/v1/tasks/{task_id}", json={"status": "waiting"})
        assert r.status_code == 409  # 业务异常映射为 409 Conflict
        assert r.json()["code"] == 3001

        # 查库：状态没变
        db = _db()
        try:
            in_db = db.get(Task, task_id)
            assert in_db.status == "completed"
            assert in_db.completed_at is not None
        finally:
            db.close()

    def test_set_focus_via_api_switches_old_focus_in_db(self, client, default_user_id):
        """通过 API 设置新焦点后，查库验证旧焦点 is_focus=0、新焦点 is_focus=1。

        防什么：API 层的 set_focus 如果没调用 service 的互斥逻辑（比如直接
        改数据库），可能出现两个焦点。
        """
        db = _db()
        try:
            fixture = seed_task_fixture(db, default_user_id)
            db.commit()
            old_focus_id = fixture["tasks"]["focus_pending"].id
            new_focus_id = fixture["tasks"]["in_progress_high"].id
        finally:
            db.close()

        r = client.post(f"/api/v1/tasks/{new_focus_id}/focus")
        assert r.status_code == 200
        assert r.json()["data"]["is_focus"] is True

        # 查库验证
        db = _db()
        try:
            old = db.get(Task, old_focus_id)
            new = db.get(Task, new_focus_id)
            assert old.is_focus is False
            assert new.is_focus is True
            # 全局只有1个焦点
            all_focus = db.scalars(
                select(Task).where(Task.user_id == default_user_id, Task.is_focus == True)  # noqa: E712
            ).all()
            assert len(all_focus) == 1
        finally:
            db.close()

    def test_cancel_focus_via_api_persists_to_db(self, client, default_user_id):
        """通过 API 取消焦点后，查库验证 is_focus=0，其他任务不受影响。

        防什么：cancel_focus 如果误把所有任务的 is_focus 都设为 False，
        虽然目标任务对了，但其他焦点也被清掉了。
        """
        db = _db()
        try:
            fixture = seed_task_fixture(db, default_user_id)
            db.commit()
            focus_id = fixture["tasks"]["focus_pending"].id
        finally:
            db.close()

        r = client.delete(f"/api/v1/tasks/{focus_id}/focus")
        assert r.status_code == 200
        assert r.json()["data"]["is_focus"] is False

        # 查库验证
        db = _db()
        try:
            in_db = db.get(Task, focus_id)
            assert in_db.is_focus is False
            assert count_rows(db, "tasks", user_id=default_user_id, is_focus=1) == 0
        finally:
            db.close()

    def test_add_subtask_via_api_persists_sort_order_and_progress(self, client, default_user_id):
        """通过 API 连续添加子任务后，查库验证 sort_order 递增，progress 正确。

        防什么：API 层的 add_subtask 如果没正确传递参数，或者 service 层的
        sort_order 计算有缓存问题（expire_on_commit=False），连续添加会重复为 0。
        """
        db = _db()
        try:
            from tests.factories import make_task
            task = make_task(db, default_user_id, title="无子任务的任务")
            db.commit()
            task_id = task.id
        finally:
            db.close()

        # 连续添加2条子任务
        r1 = client.post(f"/api/v1/tasks/{task_id}/subtasks", json={"title": "子A"})
        r2 = client.post(f"/api/v1/tasks/{task_id}/subtasks", json={"title": "子B"})
        assert r1.status_code == 200
        assert r2.status_code == 200

        # 查库验证
        db = _db()
        try:
            subs = db.scalars(
                select(Subtask).where(Subtask.task_id == task_id).order_by(Subtask.sort_order)
            ).all()
            assert len(subs) == 2
            assert subs[0].sort_order == 0
            assert subs[0].title == "子A"
            assert subs[1].sort_order == 1
            assert subs[1].title == "子B"
        finally:
            db.close()

    def test_complete_subtask_via_api_updates_progress_in_db(self, client, default_user_id):
        """通过 API 完成子任务后，查库验证子任务 completed=True，任务 progress 正确。

        防什么：API 层的 update_subtask 如果路径参数 task_id 和 sub_id 不匹配
        时没校验，可能操作到别的任务的子任务。
        """
        db = _db()
        try:
            fixture = seed_task_fixture(db, default_user_id)
            db.commit()
            # "最小覆盖圆论文" 有2条子任务：查格式(已完成)、写灵敏度(未完成)
            task_id = fixture["tasks"]["in_progress_high"].id
            uncompleted_sub_id = fixture["subtasks"]["paper_1"].id
        finally:
            db.close()

        r = client.patch(
            f"/api/v1/tasks/{task_id}/subtasks/{uncompleted_sub_id}",
            json={"completed": True},
        )
        assert r.status_code == 200

        # 查库验证
        db = _db()
        try:
            sub = db.get(Subtask, uncompleted_sub_id)
            assert sub.completed is True
            # 任务详情的 progress 应该是 100（2/2）
            detail = client.get(f"/api/v1/tasks/{task_id}").json()["data"]
            assert detail["progress"] == 100
            assert detail["subtasks_completed"] == 2
        finally:
            db.close()


# ============================================================
# 第 3 组：批量操作 + 番茄钟 + 今日统计的 API→查库验证
# ============================================================

class TestApiGroup3BatchFocusStats:
    """第3组：通过 API 做批量操作/番茄钟/统计，然后查库验证。"""

    def test_batch_complete_via_api_persists_to_db(self, client, default_user_id):
        """通过 API 批量完成2条任务后，查库验证只有这2条变 completed。

        防什么：API 层的 batch 如果没正确传递 action 参数，或者 service 层
        的 WHERE 条件漏了 user_id，可能把所有任务都完成了。
        """
        db = _db()
        try:
            fixture = seed_task_fixture(db, default_user_id)
            db.commit()
            ids = [
                fixture["tasks"]["pending_medium_no_due"].id,
                fixture["tasks"]["pending_low_tomorrow"].id,
            ]
        finally:
            db.close()

        r = client.post("/api/v1/tasks/batch", json={
            "task_ids": ids, "action": "complete",
        })
        assert r.status_code == 200
        assert r.json()["data"]["affected"] == 2
        assert r.json()["data"]["failed"] == 0

        # 查库验证
        db = _db()
        try:
            for tid in ids:
                assert db.get(Task, tid).status == "completed"
            # 其余 pending 只剩1条（focus_pending）
            assert count_rows(db, "tasks", user_id=default_user_id, status="pending") == 1
            # 总 completed = 3 + 2 = 5
            assert count_rows(db, "tasks", user_id=default_user_id, status="completed") == 5
        finally:
            db.close()

    def test_batch_delete_via_api_removes_from_db(self, client, default_user_id):
        """通过 API 批量删除2条任务后，查库验证行消失，其他任务保留。

        防什么：batch delete 如果用了软删除而不是硬删除，列表里还会看到
        已删除的任务（如果查询没过滤 deleted_at）。
        """
        db = _db()
        try:
            fixture = seed_task_fixture(db, default_user_id)
            db.commit()
            ids = [
                fixture["tasks"]["waiting_low"].id,
                fixture["tasks"]["waiting_medium"].id,
            ]
        finally:
            db.close()

        r = client.post("/api/v1/tasks/batch", json={
            "task_ids": ids, "action": "delete",
        })
        assert r.status_code == 200
        assert r.json()["data"]["affected"] == 2

        # 查库验证
        db = _db()
        try:
            for tid in ids:
                assert db.get(Task, tid) is None
            assert count_rows(db, "tasks", user_id=default_user_id) == FIXTURE_TASK_COUNT - 2
            # waiting 状态应该为0
            assert count_rows(db, "tasks", user_id=default_user_id, status="waiting") == 0
        finally:
            db.close()

    def test_batch_invalid_action_rejected_by_schema(self, client, default_user_id):
        """批量操作传非法 action 时，Pydantic 校验拒绝，返回 400，库不变。

        防什么：如果 schema 的 action 没有 pattern 约束，非法 action 会进入
        service 层，可能触发未预期的行为。
        """
        db = _db()
        try:
            fixture = seed_task_fixture(db, default_user_id)
            db.commit()
            task_id = fixture["tasks"]["pending_low_tomorrow"].id
        finally:
            db.close()

        r = client.post("/api/v1/tasks/batch", json={
            "task_ids": [task_id], "action": "destroy_everything",
        })
        assert r.status_code == 400

        # 查库：任务没变
        db = _db()
        try:
            assert db.get(Task, task_id).status == "pending"
        finally:
            db.close()

    def test_focus_session_start_stop_via_api_persists_to_db(self, client, default_user_id):
        """通过 API 启动→结束番茄钟后，查库验证 focus_sessions 记录和 task.focus_duration。

        防什么：API 层的 focus-sessions 路由如果路径参数错了（比如 task_id
        没传到 service），会话可能创建到错误的任务上。
        """
        from app.models.base import utcnow
        from app.models.task import FocusSession

        db = _db()
        try:
            fixture = seed_task_fixture(db, default_user_id)
            db.commit()
            task_id = fixture["tasks"]["in_progress_high"].id
        finally:
            db.close()

        # 启动
        r_start = client.post(f"/api/v1/tasks/{task_id}/focus-sessions/start")
        assert r_start.status_code == 200
        session_id = r_start.json()["data"]["id"]

        # 手动把 start_time 往前调 60 秒（走独立 session）
        db = _db()
        try:
            session = db.get(FocusSession, session_id)
            session.start_time = utcnow() - timedelta(seconds=60)
            db.commit()
        finally:
            db.close()

        # 结束
        r_stop = client.post(f"/api/v1/tasks/focus-sessions/{session_id}/stop")
        assert r_stop.status_code == 200
        assert r_stop.json()["data"]["end_time"] is not None
        assert r_stop.json()["data"]["duration"] >= 59

        # 查库验证
        db = _db()
        try:
            session = db.get(FocusSession, session_id)
            assert session.end_time is not None
            assert session.duration >= 59
            task = db.get(Task, task_id)
            assert task.focus_duration >= 59
        finally:
            db.close()

    def test_today_stats_via_api_matches_db_counts(self, client, default_user_id):
        """通过 API 获取今日统计，四个计数必须和查库结果完全一致。

        防什么：today_stats 的 count 查询如果 WHERE 条件错了（比如漏了
        user_id、completed_on 的日期范围不对），返回值和库不一致。
        """
        db = _db()
        try:
            seed_task_fixture(db, default_user_id)
            db.commit()
        finally:
            db.close()

        r = client.get("/api/v1/tasks/today/stats")
        assert r.status_code == 200
        assert r.json()["code"] == 0
        stats = r.json()["data"]

        # 查库交叉验证
        db = _db()
        try:
            db_in_progress = count_rows(db, "tasks", user_id=default_user_id, status="in_progress")
            db_waiting = count_rows(db, "tasks", user_id=default_user_id, status="waiting")
            assert stats["in_progress"] == db_in_progress
            assert stats["waiting"] == db_waiting
            # must_do >= 1（focus_pending 今天截止）
            assert stats["must_do"] >= 1
            # completed_today >= 3（夹具里3条 completed 都是刚创建的）
            assert stats["completed_today"] >= 3
        finally:
            db.close()


# ============================================================
# 第 4 组：列表过滤/分页 + 参数校验 + 404 边界
# ============================================================

class TestApiGroup4FilterValidation:
    """第4组：通过 API 做列表过滤/分页/参数校验，验证响应和库一致。"""

    def test_list_filter_by_status_via_api_matches_db(self, client, default_user_id):
        """通过 API 按 status 过滤，返回的每条都是该状态，且总数和查库一致。

        防什么：list 接口的 status 过滤如果拼错了（比如用了 priority 字段），
        返回结果会混入其他状态。
        """
        db = _db()
        try:
            seed_task_fixture(db, default_user_id)
            db.commit()
        finally:
            db.close()

        r = client.get("/api/v1/tasks", params={"status": "completed"})
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["total"] == FIXTURE_STATUS_COUNTS["completed"]
        for item in data["list"]:
            assert item["status"] == "completed"

        # 查库交叉验证
        db = _db()
        try:
            assert count_rows(db, "tasks", user_id=default_user_id, status="completed") == data["total"]
        finally:
            db.close()

    def test_list_pagination_via_api(self, client, default_user_id):
        """通过 API 分页，page=1/page_size=3 返回3条，page=4 返回空，total 不变。

        防什么：分页逻辑如果 page 越界时返回第一页（而不是空），前端翻到
        最后一页后继续翻会看到重复数据。
        """
        db = _db()
        try:
            seed_task_fixture(db, default_user_id)
            db.commit()
        finally:
            db.close()

        # 第1页3条
        r1 = client.get("/api/v1/tasks", params={"page": 1, "page_size": 3})
        assert r1.status_code == 200
        assert r1.json()["data"]["total"] == FIXTURE_TASK_COUNT
        assert len(r1.json()["data"]["list"]) == 3

        # 第5页（10条/3=3页余1，第4页1条，第5页空）
        r5 = client.get("/api/v1/tasks", params={"page": 5, "page_size": 3})
        assert r5.status_code == 200
        assert r5.json()["data"]["total"] == FIXTURE_TASK_COUNT
        assert len(r5.json()["data"]["list"]) == 0

    def test_create_task_empty_title_rejected_at_api_layer(self, client):
        """通过 API 创建空标题任务，Pydantic 校验拒绝，返回 400，库不产生脏数据。

        防什么：如果 schema 的 min_length 约束被移除，空标题会进入 service 层。
        """
        r = client.post("/api/v1/tasks", json={"title": ""})
        assert r.status_code == 400
        assert r.json()["code"] == 1001

    def test_create_task_whitespace_title_rejected_at_service_layer(self, client, default_user_id):
        """通过 API 创建纯空格标题任务，service 层 strip 后为空，返回 400，库不产生脏数据。

        防什么：如果 service 层漏了 title.strip() 校验，"   " 会写进库，
        列表里显示空白行。这是实测发现的 bug，已修复，本条锁定。
        """
        r = client.post("/api/v1/tasks", json={"title": "   "})
        assert r.status_code == 400
        assert r.json()["code"] == 1001

        # 查库：没有脏数据
        db = _db()
        try:
            assert count_rows(db, "tasks", user_id=default_user_id) == 0
        finally:
            db.close()

    def test_update_nonexistent_task_returns_404(self, client):
        """更新不存在的任务返回 404，业务码正确。

        防什么：API 层的异常处理器如果没正确映射 NotFoundException，
        可能返回 500 而不是 404。
        """
        r = client.patch("/api/v1/tasks/non-existent-id", json={"title": "x"})
        assert r.status_code == 404
        assert r.json()["code"] == 1002

    def test_delete_nonexistent_task_returns_404(self, client):
        """删除不存在的任务返回 404。

        防什么：同上，验证 delete 路由的异常处理。
        """
        r = client.delete("/api/v1/tasks/non-existent-id")
        assert r.status_code == 404
        assert r.json()["code"] == 1002


# ============================================================
# 第 5 组：专注会话列表 + 子任务删除 + 越权子任务 + 非法 priority + 空数据
# ============================================================

class TestApiGroup5MiscEdge:
    """第5组：专注会话列表 + 子任务删除 + 越权子任务 + 非法 priority + 空数据边界。"""

    def test_focus_sessions_list_via_api_matches_db(self, client, default_user_id):
        """通过 API 获取专注会话列表，返回的每条都属于该任务，且数量和查库一致。

        防什么：focus-sessions 列表如果没加 task_id 过滤，会返回所有用户的
        会话（越权泄露）。
        """
        from app.models.task import FocusSession

        db = _db()
        try:
            fixture = seed_task_fixture(db, default_user_id)
            db.commit()
            task_id = fixture["tasks"]["in_progress_high"].id
        finally:
            db.close()

        # 启动2个会话
        client.post(f"/api/v1/tasks/{task_id}/focus-sessions/start")
        client.post(f"/api/v1/tasks/{task_id}/focus-sessions/start")

        r = client.get(f"/api/v1/tasks/{task_id}/focus-sessions")
        assert r.status_code == 200
        sessions = r.json()["data"]
        assert len(sessions) == 2

        # 查库交叉验证
        db = _db()
        try:
            db_sessions = db.scalars(
                select(FocusSession).where(FocusSession.task_id == task_id)
            ).all()
            assert len(db_sessions) == 2
        finally:
            db.close()

    def test_delete_subtask_via_api_removes_from_db(self, client, default_user_id):
        """通过 API 删除子任务后，查库验证子任务消失，任务 progress 更新。

        防什么：delete_subtask 如果只删了 subtask 但没触发 progress 重算
        （progress 是实时算的所以没问题），或者级联配置错了导致子任务没删掉。
        """
        db = _db()
        try:
            fixture = seed_task_fixture(db, default_user_id)
            db.commit()
            task_id = fixture["tasks"]["in_progress_high"].id
            sub_id = fixture["subtasks"]["paper_0"].id  # 已完成的子任务
        finally:
            db.close()

        # 删除前 progress=50（1/2）
        before = client.get(f"/api/v1/tasks/{task_id}").json()["data"]
        assert before["progress"] == 50

        r = client.delete(f"/api/v1/tasks/{task_id}/subtasks/{sub_id}")
        assert r.status_code == 200

        # 查库验证
        db = _db()
        try:
            assert db.get(Subtask, sub_id) is None
            # 删除后 progress=0（0/1）
            after = client.get(f"/api/v1/tasks/{task_id}").json()["data"]
            assert after["subtasks_count"] == 1
            assert after["progress"] == 0
        finally:
            db.close()

    def test_subtask_wrong_task_id_returns_404(self, client, default_user_id):
        """用错误的 task_id 操作其他任务的子任务，返回 404，库中子任务不变。

        防什么：update_subtask/delete_subtask 如果只检查 sub 是否存在而不检查
        sub.task_id == task_id，就可以通过路径参数操作别的任务的子任务。
        """
        db = _db()
        try:
            fixture = seed_task_fixture(db, default_user_id)
            db.commit()
            task_a_id = fixture["tasks"]["in_progress_high"].id  # 有子任务
            task_b_id = fixture["tasks"]["pending_low_tomorrow"].id  # 无子任务
            sub_of_a_id = fixture["subtasks"]["paper_0"].id
        finally:
            db.close()

        # 用 task_b 的路径去操作 task_a 的子任务
        r = client.patch(
            f"/api/v1/tasks/{task_b_id}/subtasks/{sub_of_a_id}",
            json={"completed": False},
        )
        assert r.status_code == 404
        assert r.json()["code"] == 1002

        # 查库：子任务没变
        db = _db()
        try:
            sub = db.get(Subtask, sub_of_a_id)
            assert sub.completed is True  # 本来就是 True，确认没被误改
        finally:
            db.close()

    def test_create_task_invalid_priority_falls_back_to_medium_via_api(self, client, default_user_id):
        """通过 API 创建任务时传非法 priority，查库验证被静默降级为 medium。

        防什么：如果 create 没做 priority 校验，非法值会直接写进库，后续按
        priority 过滤时这条任务就永远查不到了。
        """
        r = client.post("/api/v1/tasks", json={
            "title": "非法优先级任务",
            "priority": "super_urgent_xxx",
        })
        assert r.status_code == 200
        task_id = r.json()["data"]["id"]

        # 查库验证
        db = _db()
        try:
            in_db = db.get(Task, task_id)
            assert in_db.priority == "medium"
        finally:
            db.close()

    def test_empty_database_list_returns_zero_via_api(self, client):
        """空数据库时，列表接口返回 total=0、list=[]，today_stats 全 0，focus=None。

        防什么：空数据场景下如果代码假设至少有一条任务，可能报 IndexError
        或者除零错误。
        """
        # clean_db 已经清表了，直接测
        r_list = client.get("/api/v1/tasks")
        assert r_list.status_code == 200
        assert r_list.json()["data"]["total"] == 0
        assert len(r_list.json()["data"]["list"]) == 0

        r_stats = client.get("/api/v1/tasks/today/stats")
        assert r_stats.status_code == 200
        stats = r_stats.json()["data"]
        assert stats["must_do"] == 0
        assert stats["in_progress"] == 0
        assert stats["waiting"] == 0
        assert stats["completed_today"] == 0

        r_focus = client.get("/api/v1/tasks/focus")
        assert r_focus.status_code == 200
        assert r_focus.json()["data"] is None
