# ============================================================
# Report API 集成测试（S6-5 · 人生报告）
#
# 契约来源：**读实现** —— `app/api/report.py` 无任何参数（GET /report），
# 前端封装 `frontend/src/api/report.ts` 也是无参 GET；ReportView 直接
# 把 `data` 渲染为单文件 HTML。
#
# 标准：HTTP 状态码 + 统一信封 + 真实 Session 落库交叉验证 + 结构完整性
# ============================================================
from __future__ import annotations

from datetime import date

import pytest

from app.database import SessionLocal
from app.models.task import Task
from app.services.growth_service import GrowthService
from tests.factories import (
    count_rows,
    make_diary,
    make_identity,
    make_task,
    seed_four_sources,
)

URL = "/api/v1/report"


def _seed(fn, user_id: str):
    """在独立真实 Session 里造数据并 commit（请求内的 Session 才可见）。"""
    db = SessionLocal()
    try:
        out = fn(db, user_id)
        db.commit()
        return out
    finally:
        db.close()


# ============================================================
# 第 1 组：路由契约与信封
# ============================================================
class TestGroup1RouteAndEnvelope:
    """第1组：无参 GET、统一信封、三轴字段齐全。"""

    def test_get_report_returns_200_with_envelope(self, client):
        """GET /report → 200 / code=0 / message=success。"""
        r = client.get(URL)
        assert r.status_code == 200

        body = r.json()
        assert body["code"] == 0
        assert body["message"] == "success"
        assert isinstance(body["timestamp"], int)

    def test_report_keys_match_frontend_consumption(self, client):
        """顶层字段名与 ReportView/ReportData 一致（改名会静默空页面）。"""
        data = client.get(URL).json()["data"]
        assert set(data) == {
            "generated_at", "nickname", "identity_axis",
            "growth_axis", "archive_axis", "recent_experience",
        }

    def test_axis_keys_are_complete(self, client):
        """三轴的子字段一个都不能少（前端按字段渲染卡片，缺字段会渲染 undefined）。"""
        data = client.get(URL).json()["data"]

        assert set(data["identity_axis"]) == {"identities", "unassigned"}
        assert set(data["identity_axis"]["unassigned"]) == {
            "tasks_open", "documents", "diaries", "reviews", "memories",
        }
        assert set(data["growth_axis"]) == {
            "level", "exp", "percent", "skills",
            "tasks_completed_total", "diaries_total", "reviews_total",
        }
        assert set(data["archive_axis"]) == {
            "workspace_enabled", "roots", "documents_total", "sops_total",
            "prompts_total", "skills_total", "project_memories_total",
            "avatar_memories_total",
        }

    def test_nickname_comes_from_current_user(self, client, default_user_id):
        """nickname 取自当前用户（单用户模式为「启明星用户」）。"""
        data = client.get(URL).json()["data"]
        assert data["nickname"] == "启明星用户"

    def test_generated_at_is_iso_string(self, client):
        """generated_at 序列化为 ISO 字符串（前端直接插进 HTML 抬头）。"""
        data = client.get(URL).json()["data"]
        assert isinstance(data["generated_at"], str)
        assert "T" in data["generated_at"]

    def test_empty_user_report_is_well_formed(self, client):
        """空库报告结构完整且计数为 0（新用户首屏）。"""
        data = client.get(URL).json()["data"]

        assert data["identity_axis"]["identities"] == []
        assert data["growth_axis"]["level"] == 1
        assert data["growth_axis"]["exp"] == 0
        assert data["archive_axis"]["workspace_enabled"] is False
        assert data["archive_axis"]["roots"] == []
        assert data["recent_experience"] == []


# ============================================================
# 第 2 组：三轴数据（真实落库 → HTTP 读回）
# ============================================================
class TestGroup2AxesOverHttp:
    """第2组：落库数据经 HTTP 读回，三轴计数正确。"""

    def test_identity_axis_over_http(self, client, default_user_id):
        """身份行 + 该身份下的日记计数，经 HTTP 可见。"""
        def seed(db, uid):
            ident = make_identity(db, uid, name="研究生", slug="api-grad",
                                  color_token="lilac", icon="book")
            make_diary(db, uid, title="日记", identity_id=ident.id,
                       diary_date=date(2026, 1, 1))
            make_task(db, uid, title="待办", status="pending")
            return ident.id

        ident_id = _seed(seed, default_user_id)
        db = SessionLocal()
        try:
            task = db.query(Task).first()
            task.identity_id = ident_id
            db.commit()
        finally:
            db.close()

        axis = client.get(URL).json()["data"]["identity_axis"]
        row = next(r for r in axis["identities"] if r["id"] == ident_id)

        assert row["name"] == "研究生"
        assert row["color_token"] == "lilac"
        assert row["icon"] == "book"
        assert row["is_archived"] is False
        assert row["diaries"] == 1
        assert row["tasks_open"] == 1
        assert row["tasks_completed"] == 0
        assert row["documents"] == 0
        assert row["reviews"] == 0
        assert row["memories"] == 0

    def test_unassigned_bucket_over_http(self, client, default_user_id):
        """未归类桶经 HTTP 可见（identity_id 为 null 的行）。"""
        _seed(lambda db, uid: (
            make_diary(db, uid, title="无身份日记", diary_date=date(2026, 1, 1)),
            make_task(db, uid, title="无身份任务", status="pending"),
        ), default_user_id)

        un = client.get(URL).json()["data"]["identity_axis"]["unassigned"]
        assert un["diaries"] == 1
        assert un["tasks_open"] == 1
        assert un["documents"] == 0

    def test_growth_axis_reflects_award_over_http(self, client, default_user_id):
        """award 之后经 HTTP 读到的 level/exp 同步变化。"""
        def seed(db, uid):
            GrowthService(db).award(user_id=uid, source_key="api:k1",
                                    event_type="task.completed", exp=30)

        _seed(seed, default_user_id)

        g = client.get(URL).json()["data"]["growth_axis"]
        assert g["exp"] == 30
        assert g["level"] >= 1
        assert g["percent"] > 0

    def test_recent_experience_over_http(self, client, default_user_id):
        """近期经历字段完整，且 identity_name 解析为身份名（非 id）。"""
        def seed(db, uid):
            ident = make_identity(db, uid, name="科研", slug="api-res")
            seed_four_sources(db, uid, identity_id=ident.id)

        _seed(seed, default_user_id)

        recent = client.get(URL).json()["data"]["recent_experience"]
        assert len(recent) == 4
        assert set(recent[0]) == {
            "source", "source_label", "title", "identity_name", "occurred_at",
        }
        assert recent[0]["identity_name"] == "科研"
        assert recent[0]["source"] == "project_memory"

    def test_recent_experience_capped_at_ten(self, client, default_user_id):
        """HTTP 层同样只回 10 条近期经历。"""
        def seed(db, uid):
            for i in range(1, 16):
                make_diary(db, uid, title=f"日记{i:02d}", diary_date=date(2026, 1, i))

        _seed(seed, default_user_id)

        recent = client.get(URL).json()["data"]["recent_experience"]
        assert len(recent) == 10


# ============================================================
# 第 3 组：副作用与重复调用
# ============================================================
class TestGroup3SideEffects:
    """第3组：报告不是零写入（会惰性建 growth_states），业务表保持不变。"""

    def test_business_tables_unchanged_after_get(self, client, default_user_id):
        """反复 GET /report：四源/任务/文档/身份行数不变。"""
        _seed(lambda db, uid: seed_four_sources(db, uid), default_user_id)

        tables = ("diaries", "reviews", "avatar_memories", "project_memories",
                  "tasks", "documents", "identities")
        db = SessionLocal()
        try:
            before = {t: count_rows(db, t) for t in tables}
        finally:
            db.close()

        for _ in range(3):
            assert client.get(URL).status_code == 200

        db = SessionLocal()
        try:
            after = {t: count_rows(db, t) for t in tables}
        finally:
            db.close()

        assert after == before
        assert before == {
            "diaries": 1, "reviews": 1, "avatar_memories": 1, "project_memories": 1,
            "tasks": 0, "documents": 0, "identities": 0,
        }

    def test_growth_state_created_once_over_http(self, client, default_user_id):
        """首次 GET 会写入一行 growth_states，重复 GET 不再新增（幂等）。"""
        db = SessionLocal()
        try:
            assert count_rows(db, "growth_states", user_id=default_user_id) == 0
        finally:
            db.close()

        client.get(URL)
        client.get(URL)

        db = SessionLocal()
        try:
            assert count_rows(db, "growth_states", user_id=default_user_id) == 1
        finally:
            db.close()

    def test_repeated_get_is_stable(self, client, default_user_id):
        """连续两次 GET 的三轴数据一致（不因生成而漂移）。"""
        _seed(lambda db, uid: seed_four_sources(db, uid), default_user_id)

        first = client.get(URL).json()["data"]
        second = client.get(URL).json()["data"]

        for axis in ("identity_axis", "growth_axis", "archive_axis",
                     "recent_experience"):
            assert first[axis] == second[axis]

    def test_unknown_query_params_are_ignored(self, client):
        """报告端点不接参数；多余 query 被忽略而不是 400（Pydantic 默认语义）。

        防什么：前端若为打点带上 ?ts=xxx 之类，不能因此把页面打成 400。
        """
        assert client.get(URL, params={"foo": "bar"}).status_code == 200
