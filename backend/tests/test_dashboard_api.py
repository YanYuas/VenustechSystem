# ============================================================
# Dashboard API 生产级集成测试
#
# Dashboard 只有一个端点 GET /dashboard，测试重点：返回结构完整、
# 数据和查库交叉验证、week_progress/streak 字段存在（验证 bug 修复）。
# ============================================================
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from app.database import SessionLocal
from app.models.task import Task
from tests.factories import count_rows


def _db():
    return SessionLocal()


# ============================================================
# 第 1 组：Dashboard API 结构 + 数据验证 + bug修复验证
# ============================================================

class TestDashboardApiGroup1StructureData:
    """第1组：返回200 + 完整结构 + 任务数据交叉验证 + 空用户默认值 + week_progress/streak字段。"""

    def test_dashboard_api_returns_200(self, client):
        """仪表盘接口返回 200，code=0。

        防什么：聚合服务如果某个模块报错未捕获，整个仪表盘会 500。
        """
        r = client.get("/api/v1/dashboard")
        assert r.status_code == 200
        assert r.json()["code"] == 0

    def test_dashboard_api_complete_structure(self, client):
        """仪表盘返回完整的字段结构（所有 16 个顶级字段都存在）。

        防什么：如果 DashboardDataOut 缺少某个字段（如 week_progress/streak），
        前端对应组件会报错或显示空白。
        """
        r = client.get("/api/v1/dashboard")
        data = r.json()["data"]

        required_fields = [
            "focus_task", "today_stats", "recent_documents", "user",
            "today_execution", "projects", "identities", "resource_center",
            "learning", "life", "assets", "quick_actions", "week_progress",
            "streak", "ai_assistant", "modules_status",
        ]
        for field in required_fields:
            assert field in data, f"缺少字段: {field}"

        # today_stats 子字段
        for sub in ["must_do", "in_progress", "waiting", "completed_today"]:
            assert sub in data["today_stats"]

        # today_execution 有 3 个分组
        assert len(data["today_execution"]["groups"]) == 3

        # modules_status 有 10 个模块
        assert len(data["modules_status"]) == 10

        # quick_actions 有 9 个入口
        assert len(data["quick_actions"]["items"]) == 9

    def test_dashboard_api_with_tasks_cross_check(self, client, default_user_id):
        """有任务时，API 返回的今日统计和查库交叉验证。

        防什么：API 层如果返回了缓存或错误的数据，今日统计和实际数据库
        不一致。
        """
        today = date.today()
        db = _db()
        try:
            db.add(Task(user_id=default_user_id, title="今日必做", status="pending",
                        due_date=today))
            db.add(Task(user_id=default_user_id, title="进行中", status="in_progress"))
            db.add(Task(user_id=default_user_id, title="今天完成", status="completed",
                        completed_at=datetime.utcnow()))
            db.commit()
        finally:
            db.close()

        r = client.get("/api/v1/dashboard")
        stats = r.json()["data"]["today_stats"]
        assert stats["must_do"] == 1
        assert stats["in_progress"] == 1
        assert stats["completed_today"] == 1

        # 查库交叉验证
        db = _db()
        try:
            assert count_rows(db, "tasks", user_id=default_user_id) == 3
        finally:
            db.close()

    def test_dashboard_api_empty_user_defaults(self, client):
        """空用户（无任何数据）返回正确的默认值，不报错。

        防什么：新用户首次打开仪表盘，如果聚合服务对空数据没有保护，
        会 500 或显示异常。
        """
        r = client.get("/api/v1/dashboard")
        data = r.json()["data"]

        assert data["focus_task"] is None
        assert data["today_stats"]["must_do"] == 0
        assert data["today_stats"]["completed_today"] == 0
        assert len(data["recent_documents"]) == 0
        assert data["today_execution"]["total"] == 0
        assert data["week_progress"]["total"] == 0
        assert data["streak"]["days"] == 0
        assert len(data["projects"]["items"]) == 0
        assert len(data["identities"]["items"]) == 0

    def test_dashboard_api_week_progress_and_streak_fields(self, client, default_user_id):
        """API 返回 week_progress 和 streak 字段（验证 DashboardDataOut 缺字段 bug 已修复）。

        防什么：之前 DashboardDataOut 缺少这两个字段，service 传入的参数
        被 Pydantic 静默忽略，前端看不到本周进度环和连续打卡徽章。
        """
        # 造一个本周完成的任务
        today = date.today()
        monday = today - timedelta(days=today.weekday())
        db = _db()
        try:
            db.add(Task(user_id=default_user_id, title="本周完成", status="completed",
                        completed_at=datetime.utcnow(), due_date=monday + timedelta(days=1)))
            db.commit()
        finally:
            db.close()

        r = client.get("/api/v1/dashboard")
        data = r.json()["data"]

        # week_progress 字段存在且有数据
        assert "week_progress" in data
        assert data["week_progress"]["total"] >= 1
        assert data["week_progress"]["completed"] >= 1
        assert "percentage" in data["week_progress"]

        # streak 字段存在
        assert "streak" in data
        assert "days" in data["streak"]
        assert "week_checkins" in data["streak"]
        assert len(data["streak"]["week_checkins"]) == 7
