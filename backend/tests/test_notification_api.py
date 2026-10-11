# ============================================================
# Notification API 集成测试（原缺失模块，本轮补齐）
#
# 覆盖：列表（含未读过滤/分页）、统计、创建、单条已读、全部已读。
# ============================================================
from __future__ import annotations

from app.database import SessionLocal


def _create_via_api(client, title="通知", ntype="info", content=None, **extra):
    payload = {"type": ntype, "title": title, "content": content}
    payload.update(extra)
    r = client.post("/api/v1/notifications", json=payload)
    assert r.status_code == 200, r.text
    return r.json()["data"]


def _db_count(user_id: str) -> int:
    from sqlalchemy import func, select
    from app.models.notification import Notification

    db = SessionLocal()
    try:
        return int(db.scalar(
            select(func.count()).select_from(Notification)
            .where(Notification.user_id == user_id)
        ) or 0)
    finally:
        db.close()


class TestNotificationApiGroup1ListStats:
    """第1组：列表 + 未读过滤 + 分页 + 统计。"""

    def test_list_returns_array(self, client, default_user_id):
        """空库时列表返回空数组（结构稳定，前端不炸）。"""
        r = client.get("/api/v1/notifications")
        assert r.status_code == 200
        assert r.json()["code"] == 0
        assert r.json()["data"] == []

    def test_create_then_list_matches_db(self, client, default_user_id):
        """创建后列表可见，且条数与查库一致。"""
        _create_via_api(client, title="任务已完成", ntype="success")
        _create_via_api(client, title="系统提醒", ntype="warning")

        r = client.get("/api/v1/notifications")
        assert r.status_code == 200
        data = r.json()["data"]
        assert len(data) == 2
        assert _db_count(default_user_id) == 2
        assert {n["title"] for n in data} == {"任务已完成", "系统提醒"}

    def test_unread_only_filter_via_api(self, client):
        """unread_only=true 只返回未读。"""
        n = _create_via_api(client, title="会被读掉")
        _create_via_api(client, title="保持未读")
        client.patch(f"/api/v1/notifications/{n['id']}/read", json={"read": True})

        all_items = client.get("/api/v1/notifications").json()["data"]
        unread = client.get("/api/v1/notifications", params={"unread_only": True}).json()["data"]
        assert len(all_items) == 2
        assert [x["title"] for x in unread] == ["保持未读"]

    def test_list_pagination_via_api(self, client):
        """分页参数生效。"""
        for i in range(5):
            _create_via_api(client, title=f"N{i}")
        r = client.get("/api/v1/notifications", params={"page": 1, "page_size": 2})
        assert len(r.json()["data"]) == 2
        r2 = client.get("/api/v1/notifications", params={"page": 9, "page_size": 2})
        assert r2.json()["data"] == []

    def test_stats_endpoint(self, client):
        """统计接口返回 total/unread。"""
        a = _create_via_api(client, title="A")
        _create_via_api(client, title="B")
        client.patch(f"/api/v1/notifications/{a['id']}/read", json={"read": True})

        r = client.get("/api/v1/notifications/stats")
        assert r.status_code == 200
        assert r.json()["data"] == {"total": 2, "unread": 1}

    def test_stats_zero_when_empty(self, client):
        """空库统计全 0。"""
        r = client.get("/api/v1/notifications/stats")
        assert r.json()["data"] == {"total": 0, "unread": 0}


class TestNotificationApiGroup2CreateValidation:
    """第2组：创建入参校验。"""

    def test_create_returns_created_notification(self, client, default_user_id):
        """创建返回完整字段，且 is_read 默认 False。"""
        data = _create_via_api(client, title="新通知", ntype="error", content="正文",
                               source_type="task", source_id="t-1")
        assert data["title"] == "新通知"
        assert data["type"] == "error"
        assert data["is_read"] is False
        assert data["read_at"] is None
        assert data["source_type"] == "task"
        assert _db_count(default_user_id) == 1

    def test_create_missing_title_returns_400(self, client):
        """缺少 title 返回 400 + 1001。"""
        r = client.post("/api/v1/notifications", json={"type": "info"})
        assert r.status_code == 400
        assert r.json()["code"] == 1001

    def test_create_invalid_type_returns_400(self, client, default_user_id):
        """非法 type 返回 400，且不落库。"""
        r = client.post("/api/v1/notifications", json={"type": "urgent", "title": "t"})
        assert r.status_code == 400
        assert r.json()["code"] == 1001
        assert _db_count(default_user_id) == 0

    def test_create_overlong_title_returns_400(self, client):
        """标题超长返回 400。"""
        r = client.post("/api/v1/notifications", json={"type": "info", "title": "x" * 201})
        assert r.status_code == 400


class TestNotificationApiGroup3MarkRead:
    """第3组：单条已读 / 全部已读 / 404。"""

    def test_mark_read_and_unread_via_api(self, client):
        """标记已读 → read_at 非空；再标未读 → read_at 清空。"""
        n = _create_via_api(client, title="读我")
        r = client.patch(f"/api/v1/notifications/{n['id']}/read", json={"read": True})
        assert r.status_code == 200
        assert r.json()["data"]["is_read"] is True
        assert r.json()["data"]["read_at"] is not None

        r2 = client.patch(f"/api/v1/notifications/{n['id']}/read", json={"read": False})
        assert r2.json()["data"]["is_read"] is False
        assert r2.json()["data"]["read_at"] is None

    def test_mark_read_unknown_returns_404(self, client):
        """不存在的通知返回 404 + 1002。"""
        r = client.patch("/api/v1/notifications/nope/read", json={"read": True})
        assert r.status_code == 404
        assert r.json()["code"] == 1002

    def test_mark_all_read_via_api(self, client):
        """全部已读返回标记数，之后未读为 0。"""
        for _ in range(3):
            _create_via_api(client, title="x")
        r = client.post("/api/v1/notifications/read-all")
        assert r.status_code == 200
        assert r.json()["data"]["marked"] == 3

        r2 = client.post("/api/v1/notifications/read-all")
        assert r2.json()["data"]["marked"] == 0
        assert client.get("/api/v1/notifications/stats").json()["data"]["unread"] == 0
