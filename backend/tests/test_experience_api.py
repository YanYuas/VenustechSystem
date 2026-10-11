# ============================================================
# Experience API 集成测试（S6-4 · 经历视图）
#
# 契约来源：**读实现** —— `app/api/experience.py`（参数位置全是 query）
# 与前端封装 `frontend/src/api/experience.ts`（`http.get('/experience', params)`）
# 一致：identity_id / identity_unassigned / page / page_size 都走 query。
#
# 标准：HTTP 状态码 + 统一信封 + 跨进程（真实 Session）落库交叉验证 + 参数校验
# ============================================================
from __future__ import annotations

from datetime import date

import pytest

from app.database import SessionLocal
from app.models.life import Diary
from tests.factories import (
    count_rows,
    make_identity,
    seed_four_sources,
)
from app.services.experience_service import SOURCE_LABELS

URL = "/api/v1/experience"
_SOURCE_TABLES = ("diaries", "reviews", "avatar_memories", "project_memories")


def _seed(user_id: str, **kw) -> dict:
    """在**独立真实 Session**里造数据并 commit —— 请求内的 Session 才看得见。

    API 层测试与 Service 层不同：TestClient 每个请求新建 Session（连接池），
    另一条连接上的未提交数据对它不可见，所以这里必须 commit。
    """
    db = SessionLocal()
    try:
        rows = seed_four_sources(db, user_id, **kw)
        db.commit()
        return {k: v.id for k, v in rows.items()}
    finally:
        db.close()


def _add_diaries(user_id: str, count: int) -> None:
    db = SessionLocal()
    try:
        for i in range(1, count + 1):
            db.add(Diary(user_id=user_id, title=f"日记{i:02d}", content="x",
                         diary_date=date(2026, 1, i), tags=[]))
        db.commit()
    finally:
        db.close()


# ============================================================
# 第 1 组：路由契约与响应信封
# ============================================================
class TestGroup1RouteAndEnvelope:
    """第1组：路由存在、信封格式、字段名与前端消费一致。"""

    def test_get_returns_200_with_envelope(self, client):
        """GET /experience → 200 且信封为 {code:0, message:'success', data:...}。"""
        r = client.get(URL)
        assert r.status_code == 200

        body = r.json()
        assert body["code"] == 0
        assert body["message"] == "success"
        assert "data" in body
        assert isinstance(body["timestamp"], int)

    def test_empty_db_returns_empty_timeline(self, client):
        """空库 → data.items=[] / total=0 / source_counts={}（新用户首屏不崩）。"""
        data = client.get(URL).json()["data"]

        assert data["items"] == []
        assert data["total"] == 0
        assert data["source_counts"] == {}

    def test_response_keys_match_frontend_consumption(self, client):
        """响应字段名与 ExperienceView 实际读取的键一致。

        防什么：前端 `res.items / res.total / res.source_counts` 是硬编码的；
        后端改名（例如 sourceCounts）不会被 vue-tsc 发现，只会静默空页面。
        """
        data = client.get(URL).json()["data"]
        assert set(data) == {"items", "total", "page", "page_size", "source_counts"}

    def test_default_pagination_in_response(self, client):
        """默认分页 page=1 / page_size=30 出现在响应里（前端分页器依赖）。"""
        data = client.get(URL).json()["data"]
        assert data["page"] == 1
        assert data["page_size"] == 30


# ============================================================
# 第 2 组：聚合结果（真实落库 → HTTP 读回）
# ============================================================
class TestGroup2AggregationOverHttp:
    """第2组：落库数据经 HTTP 读回，语义与 Service 层一致。"""

    def test_four_sources_visible_via_api(self, client, default_user_id):
        """四源各一条 commit 后 → total=4 且计数正确。"""
        _seed(default_user_id)
        data = client.get(URL).json()["data"]

        assert data["total"] == 4
        assert data["source_counts"] == {
            "diary": 1, "review": 1, "avatar_memory": 1, "project_memory": 1,
        }

    def test_order_descending_across_sources_via_api(self, client, default_user_id):
        """HTTP 返回的顺序与 Service 一致：项目记忆→分身记忆→复盘→日记。"""
        _seed(default_user_id)
        data = client.get(URL).json()["data"]

        assert [i["source"] for i in data["items"]] == [
            "project_memory", "avatar_memory", "review", "diary",
        ]

    def test_item_fields_serialized_for_frontend(self, client, default_user_id):
        """单条 item 的字段完整、日期为 ISO 字符串（前端 dayLabel 直接 slice）。"""
        _seed(default_user_id)
        item = client.get(URL).json()["data"]["items"][0]

        assert set(item) == {
            "id", "source", "source_label", "title", "snippet",
            "identity_id", "occurred_at",
        }
        assert item["source_label"] == SOURCE_LABELS[item["source"]]
        assert isinstance(item["occurred_at"], str) and "T" in item["occurred_at"]

    def test_identity_filter_query_param(self, client, default_user_id):
        """identity_id 走 query：只返回该身份的 4 条。"""
        db = SessionLocal()
        try:
            ident = make_identity(db, default_user_id, name="身份A", slug="api-a")
            ident_id = ident.id
            db.commit()
        finally:
            db.close()
        _seed(default_user_id, identity_id=ident_id)
        _seed(default_user_id, day_offset=7)

        data = client.get(URL, params={"identity_id": ident_id}).json()["data"]
        assert data["total"] == 4
        assert all(i["identity_id"] == ident_id for i in data["items"])

    def test_identity_unassigned_query_param(self, client, default_user_id):
        """identity_unassigned=true 走 query：只返回未归类。"""
        db = SessionLocal()
        try:
            ident = make_identity(db, default_user_id, name="身份A", slug="api-a2")
            ident_id = ident.id
            db.commit()
        finally:
            db.close()
        _seed(default_user_id, identity_id=ident_id)
        _seed(default_user_id, day_offset=7)

        data = client.get(
            URL, params={"identity_unassigned": "true"}
        ).json()["data"]
        assert data["total"] == 4
        assert all(i["identity_id"] is None for i in data["items"])

    def test_pagination_over_http(self, client, default_user_id):
        """page=2 / page_size=5：items 是第 6..10 条，total 仍是 12。"""
        _add_diaries(default_user_id, 12)
        data = client.get(URL, params={"page": 2, "page_size": 5}).json()["data"]

        assert data["total"] == 12
        assert data["page"] == 2
        assert data["page_size"] == 5
        assert [i["title"] for i in data["items"]] == [
            "日记07", "日记06", "日记05", "日记04", "日记03",
        ]

    def test_source_counts_are_filtered_counts(self, client, default_user_id):
        """source_counts 只统计过滤后的集合（与 Service 层语义一致）。"""
        db = SessionLocal()
        try:
            ident = make_identity(db, default_user_id, name="身份A", slug="api-a3")
            ident_id = ident.id
            db.commit()
        finally:
            db.close()
        _seed(default_user_id, identity_id=ident_id)
        _seed(default_user_id, day_offset=7)

        data = client.get(URL, params={"identity_id": ident_id}).json()["data"]
        assert data["source_counts"] == {
            "diary": 1, "review": 1, "avatar_memory": 1, "project_memory": 1,
        }


# ============================================================
# 第 3 组：参数校验（page / page_size 边界）
# ============================================================
class TestGroup3ParamValidation:
    """第3组：非法分页参数必须 400，而不是静默返回空列表。

    背景（原缺陷）：路由签名是裸 `page: int = 1` / `page_size: int = 30`，
    没有任何范围约束。实测 `page=0` 会算成 `start=-30` → 切片为空 →
    **HTTP 200 但 items=[]**，用户看到「明明是空的但 total 有数」；
    `page_size=-1` 同理。这与项目既有约定（events/growth/logs 都用
    `Query(..., ge=, le=)`）不一致，故补上约束并在此钉成契约。
    """

    @pytest.mark.parametrize("bad_page", [0, -1, -99])
    def test_page_below_one_returns_400(self, client, bad_page):
        """page < 1 → 400 / code 1001（不是 200 空列表）。"""
        r = client.get(URL, params={"page": bad_page})
        assert r.status_code == 400
        assert r.json()["code"] == 1001

    @pytest.mark.parametrize("bad_size", [0, -1])
    def test_page_size_below_one_returns_400(self, client, bad_size):
        """page_size < 1 → 400 / code 1001。"""
        r = client.get(URL, params={"page_size": bad_size})
        assert r.status_code == 400
        assert r.json()["code"] == 1001

    def test_page_size_above_cap_returns_400(self, client):
        """page_size 超过上限(500) → 400（防单请求拉爆内存归并）。"""
        r = client.get(URL, params={"page_size": 501})
        assert r.status_code == 400
        assert r.json()["code"] == 1001

    def test_page_size_at_cap_is_accepted(self, client):
        """page_size=500 恰好在上限内 → 200（边界不误伤）。"""
        r = client.get(URL, params={"page_size": 500})
        assert r.status_code == 200

    def test_non_integer_page_returns_400(self, client):
        """page 非整数 → FastAPI 校验失败 → 项目统一映射为 400/1001（不是 422）。"""
        r = client.get(URL, params={"page": "abc"})
        assert r.status_code == 400
        assert r.json()["code"] == 1001


# ============================================================
# 第 4 组：经 HTTP 也是只读
# ============================================================
class TestGroup4ReadOnlyOverHttp:
    """第4组：HTTP 读接口不能有任何写入副作用（视图不建表铁律）。"""

    def test_http_call_does_not_write_source_rows(self, client, default_user_id):
        """反复 GET 前后四张源表行数不变。"""
        _seed(default_user_id)

        db = SessionLocal()
        try:
            before = {t: count_rows(db, t) for t in _SOURCE_TABLES}
        finally:
            db.close()

        for _ in range(3):
            assert client.get(URL).status_code == 200

        db = SessionLocal()
        try:
            after = {t: count_rows(db, t) for t in _SOURCE_TABLES}
        finally:
            db.close()

        assert after == before
        assert before == {t: 1 for t in _SOURCE_TABLES}
