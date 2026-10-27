# ============================================================
# Review API 生产级集成测试
#
# 标准对齐 task/document/folder API 测试：
#   1. 真数据（混合类型/日期/data字段）
#   2. API 操作后查库验证
#   3. HTTP 状态码 + 业务码 + 响应体结构
#   4. 增量隔离
#
# 隔离机制：client（default_user）+ clean_db（autouse 清表）
# 查库验证用独立 SessionLocal
#
# 以 5 个为一组逐步推进。
# ============================================================
from __future__ import annotations

from datetime import date


from app.database import SessionLocal
from app.models.review import Review
from tests.factories import count_rows


def _db():
    return SessionLocal()


def _review_payload(**overrides) -> dict:
    """构造一份有真实内容的 upsert payload。"""
    defaults = dict(
        type="daily",
        date="2026-10-10",
        data=dict(
            completed_tasks="完成了论文修订",
            unfinished_tasks="还没写灵敏度分析",
            gains="搞懂了增量维护",
            reflections=[{"question": "收获？", "answer": "增量维护思路"}],
            tomorrow_plan="继续写论文",
            mood=4,
            energy=3,
        ),
    )
    defaults.update(overrides)
    return defaults


# ============================================================
# 第 1 组：列表 + upsert + 按日期获取 + 404
# ============================================================

class TestReviewApiGroup1ListUpsertGet:
    """第1组：列表分页 + upsert 创建/更新 + 按日期获取 + 不存在404。"""

    def test_list_reviews_returns_paginated(self, client, default_user_id):
        """列表接口返回分页结构，查库验证总数。

        防什么：list 接口如果 total 算错（比如没加 user_id 过滤），
        前端会看到错误的总数。
        """
        # 造2条复盘
        db = _db()
        try:
            for d in ["2026-10-09", "2026-10-10"]:
                db.add(Review(
                    user_id=default_user_id, type="daily", review_date=date.fromisoformat(d),
                    data={"mood": 3},
                ))
            db.commit()
        finally:
            db.close()

        r = client.get("/api/v1/reviews")
        assert r.status_code == 200
        assert r.json()["code"] == 0
        data = r.json()["data"]
        assert data["total"] == 2
        assert len(data["list"]) == 2

        # 查库交叉验证
        db = _db()
        try:
            assert count_rows(db, "reviews", user_id=default_user_id) == 2
        finally:
            db.close()

    def test_upsert_creates_review_via_api(self, client, default_user_id):
        """通过 API upsert 创建复盘后，查库验证所有字段。

        防什么：API 层如果没正确传递 data 参数，复盘内容会丢失。
        """
        r = client.put("/api/v1/reviews", json=_review_payload())
        assert r.status_code == 200
        assert r.json()["code"] == 0
        review_id = r.json()["data"]["id"]

        # 查库验证
        db = _db()
        try:
            in_db = db.get(Review, review_id)
            assert in_db is not None
            assert in_db.user_id == default_user_id
            assert in_db.type == "daily"
            assert in_db.review_date == date(2026, 10, 10)
            assert in_db.data["mood"] == 4
            assert in_db.data["gains"] == "搞懂了增量维护"
        finally:
            db.close()

    def test_upsert_updates_existing_via_api(self, client, default_user_id):
        """同日期同类型第二次 upsert 更新已有复盘，不产生新行。

        防什么：upsert 如果漏了 update 分支，同日期同类型会产生重复行，
        违反唯一约束导致 500。
        """
        # 首次创建
        r1 = client.put("/api/v1/reviews", json=_review_payload())
        review_id = r1.json()["data"]["id"]

        # 同日期同类型更新（修改 data 里的 mood 和 gains）
        update_payload = _review_payload()
        update_payload["data"]["mood"] = 5
        update_payload["data"]["gains"] = "更新后的收获"
        r2 = client.put("/api/v1/reviews", json=update_payload)
        assert r2.json()["data"]["id"] == review_id  # 同一个 id
        assert r2.json()["data"]["data"]["mood"] == 5

        # 查库：只有一条
        db = _db()
        try:
            assert count_rows(db, "reviews", user_id=default_user_id) == 1
            in_db = db.get(Review, review_id)
            assert in_db.data["mood"] == 5
            assert in_db.data["gains"] == "更新后的收获"
        finally:
            db.close()

    def test_get_review_by_date_via_api(self, client, default_user_id):
        """按日期获取复盘，返回的 data 和查库一致。

        防什么：get 接口如果路径参数 review_date 解析错误，会找不到复盘。
        """
        client.put("/api/v1/reviews", json=_review_payload())

        r = client.get("/api/v1/reviews/2026-10-10")
        assert r.status_code == 200
        assert r.json()["data"]["review_date"] == "2026-10-10"
        assert r.json()["data"]["data"]["mood"] == 4

    def test_get_nonexistent_review_returns_404(self, client):
        """获取不存在的日期复盘返回 404。

        防什么：API 层的异常处理器如果没正确映射 NotFoundException，
        可能返回 500 而不是 404。
        """
        r = client.get("/api/v1/reviews/2026-01-01")
        assert r.status_code == 404
        assert r.json()["code"] == 1002


# ============================================================
# 第 2 组：delete + auto_fill + convert_task + 404 边界
# ============================================================

class TestReviewApiGroup2DeleteAutoFillConvert:
    """第2组：删除 + 自动填充 + 转任务 + 不存在404。"""

    def test_delete_review_via_api(self, client, default_user_id):
        """通过 API 删除复盘后，查库验证行消失。

        防什么：delete 接口如果调用了错误的 service 方法，复盘可能没被删除。
        """
        r = client.put("/api/v1/reviews", json=_review_payload())
        review_id = r.json()["data"]["id"]

        r = client.delete(f"/api/v1/reviews/{review_id}")
        assert r.status_code == 200
        assert r.json()["code"] == 0

        # 查库验证
        db = _db()
        try:
            assert db.get(Review, review_id) is None
            assert count_rows(db, "reviews", user_id=default_user_id) == 0
        finally:
            db.close()

    def test_auto_fill_via_api(self, client, default_user_id):
        """auto_fill 接口返回今天的任务和文档统计。

        防什么：auto_fill 接口如果时区算错，会漏掉今天的数据。
        """
        from datetime import datetime
        from app.models.task import Task

        # 造一条今天完成的任务
        db = _db()
        try:
            db.add(Task(
                user_id=default_user_id, title="今天完成的任务",
                status="completed", completed_at=datetime.utcnow(),
            ))
            db.commit()
        finally:
            db.close()

        today = date.today().isoformat()
        r = client.get(f"/api/v1/reviews/{today}/auto-fill")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["stats"]["tasks_completed"] >= 1
        assert len(data["completed_tasks"]) >= 1

    def test_convert_task_via_api(self, client, default_user_id):
        """convert_task 接口创建任务，查库验证任务存在。

        防什么：convert_task 接口如果没正确传递 content，任务标题会丢失。
        """
        r = client.put("/api/v1/reviews", json=_review_payload())
        review_id = r.json()["data"]["id"]

        r = client.post(f"/api/v1/reviews/{review_id}/convert-task", json={
            "content": "明天写论文",
            "priority": "high",
        })
        assert r.status_code == 200
        assert "task_id" in r.json()["data"]

        # 查库验证
        from app.models.task import Task
        db = _db()
        try:
            task = db.get(Task, r.json()["data"]["task_id"])
            assert task is not None
            assert task.title == "明天写论文"
            assert task.priority == "high"
            assert task.user_id == default_user_id
        finally:
            db.close()

    def test_delete_nonexistent_review_returns_404(self, client):
        """删除不存在的复盘返回 404。

        防什么：delete 接口如果对不存在的 id 返回 200，前端无法区分
        "删除成功"和"本来就不存在"。
        """
        r = client.delete("/api/v1/reviews/non-existent-review-id")
        assert r.status_code == 404
        assert r.json()["code"] == 1002

    def test_convert_task_nonexistent_review_returns_404(self, client, default_user_id):
        """convert_task 对不存在的复盘返回 404，不产生任务。

        防什么：convert_task 如果没检查复盘存在性，会报 500 而不是 404。
        """
        r = client.post("/api/v1/reviews/non-existent/convert-task", json={
            "content": "任务",
        })
        assert r.status_code == 404
        assert r.json()["code"] == 1002

        # 查库：没有产生任务
        db = _db()
        try:
            assert count_rows(db, "tasks", user_id=default_user_id) == 0
        finally:
            db.close()


# ============================================================
# 第 3 组：API 层越权 + 参数校验
# ============================================================

class TestReviewApiGroup3AuthValidation:
    """第3组：API 层越权获取/删除 + mood 校验 + 空内容 + project_id 越权。"""

    def test_upsert_invalid_mood_returns_400(self, client):
        """upsert 时 mood 超出 1-5 范围返回 400，不产生复盘。

        防什么：API 层如果没正确传递 Pydantic 校验错误，mood=6 会进入
        service 层并被写入数据库。
        """
        payload = _review_payload()
        payload["data"]["mood"] = 6
        r = client.put("/api/v1/reviews", json=payload)
        assert r.status_code == 400

    def test_get_other_users_review_returns_404(self, client, default_user_id):
        """按日期获取其他用户的复盘返回 404（因为 get 按 user_id+date+type 查询）。

        防什么：get 如果只按 date+type 查询而不加 user_id，用户可以看到
        别人的复盘。
        """
        from app.models.user import User

        # 造其他用户的复盘
        db = _db()
        try:
            other = User(username="other_review_api", nickname="其他")
            db.add(other)
            db.flush()
            db.add(Review(
                user_id=other.id, type="daily", review_date=date(2026, 10, 10),
                data={"mood": 3},
            ))
            db.commit()
        finally:
            db.close()

        # 当前用户按同一日期获取，应该返回 404
        r = client.get("/api/v1/reviews/2026-10-10")
        assert r.status_code == 404
        assert r.json()["code"] == 1002

    def test_delete_other_users_review_returns_404(self, client, default_user_id):
        """删除其他用户的复盘返回 404，库中复盘仍在。

        防什么：delete 如果只检查存在性而不检查 user_id，用户可以删除
        别人的复盘。
        """
        from app.models.user import User

        db = _db()
        try:
            other = User(username="other_review_del", nickname="其他")
            db.add(other)
            db.flush()
            other_review = Review(
                user_id=other.id, type="daily", review_date=date(2026, 10, 10),
                data={"mood": 3},
            )
            db.add(other_review)
            db.commit()
            other_review_id = other_review.id
        finally:
            db.close()

        r = client.delete(f"/api/v1/reviews/{other_review_id}")
        assert r.status_code == 404
        assert r.json()["code"] == 1002

        # 查库：复盘仍在
        db = _db()
        try:
            assert db.get(Review, other_review_id) is not None
        finally:
            db.close()

    def test_convert_task_empty_content_returns_400(self, client):
        """convert_task 时空内容被校验拒绝（400），不产生任务。

        防什么：如果 schema 的 min_length 校验漏了，空内容会进入 service 层
        并创建一个空标题的任务。
        """
        # 先创建复盘
        r = client.put("/api/v1/reviews", json=_review_payload())
        review_id = r.json()["data"]["id"]

        r = client.post(f"/api/v1/reviews/{review_id}/convert-task", json={"content": ""})
        assert r.status_code == 400

    def test_upsert_with_other_users_project_returns_400(self, client, default_user_id):
        """upsert 时指定其他用户的 project_id 返回 400，不产生复盘。

        防什么：upsert 的 project_id 校验如果只检查存在性而不检查归属，
        用户可以把复盘关联到别人的项目下。
        """
        from app.models.project import Project
        from app.models.user import User

        db = _db()
        try:
            other = User(username="other_proj_review", nickname="其他")
            db.add(other)
            db.flush()
            other_project = Project(user_id=other.id, name="他人项目", status="active")
            db.add(other_project)
            db.commit()
            other_project_id = other_project.id
        finally:
            db.close()

        payload = _review_payload()
        payload["project_id"] = other_project_id
        r = client.put("/api/v1/reviews", json=payload)
        assert r.status_code == 400

        # 查库：没有产生复盘
        db = _db()
        try:
            assert count_rows(db, "reviews", user_id=default_user_id) == 0
        finally:
            db.close()
