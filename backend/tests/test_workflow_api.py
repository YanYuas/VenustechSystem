# ============================================================
# 工作流 API 集成测试（原缺失模块，本轮补齐）
#
# 覆盖：列表/预设/详情/创建/更新/删除 + 一键应用 + 应用历史。
# 额外钉住两个「路由层」容易踩的点：
#   · GET /workflows/presets 必须排在 /{workflow_id} 之前，否则会被当成 id；
#   · GET /workflows/applications/history 是**两段**路径，不会被单段
#     /{workflow_id} 吞掉（FastAPI 按注册顺序匹配）。
# ============================================================
from __future__ import annotations

from app.database import SessionLocal

WF_CONFIG = {
    "tag_system": {"study": ["阅读", "笔记"]},
    "doc_templates": ["读书笔记模板"],
    "task_templates": [{"name": "选书", "steps": ["列书单"]}],
}


def _create_wf(client, name="读书计划", category="study", config=None, **extra):
    payload = {"name": name, "category": category, "config": WF_CONFIG if config is None else config}
    payload.update(extra)
    r = client.post("/api/v1/workflows", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["code"] == 0, body
    return body["data"]


def _db_counts(table: str) -> int:
    from sqlalchemy import func, select, text

    db = SessionLocal()
    try:
        return int(db.scalar(select(func.count()).select_from(text(table))) or 0)
    finally:
        db.close()


class TestWorkflowApiCrud:
    """第 1 组：CRUD 与列表。"""

    def test_list_empty_shape(self, client, default_user_id):
        """空库返回 {list:[],total:0,...}（结构稳定，前端不炸）。"""
        r = client.get("/api/v1/workflows")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["list"] == []
        assert data["total"] == 0
        assert data["page"] == 1 and data["page_size"] == 20

    def test_presets_endpoint_not_shadowed_by_id_route(self, client, default_user_id):
        """presets 路由不会被 /{workflow_id} 抢占（返回 list 结构而非 404）。"""
        r = client.get("/api/v1/workflows/presets")
        assert r.status_code == 200
        body = r.json()
        assert body["code"] == 0
        assert isinstance(body["data"]["list"], list)
        assert all(w["is_preset"] is True for w in body["data"]["list"])

    def test_create_then_get_detail_roundtrip(self, client, default_user_id):
        """创建 → 详情：config 嵌套结构原样往返。"""
        wf = _create_wf(client, name="读书计划")
        assert wf["config"] == WF_CONFIG
        assert wf["is_preset"] is False and wf["use_count"] == 0

        r = client.get(f"/api/v1/workflows/{wf['id']}")
        assert r.status_code == 200
        detail = r.json()["data"]
        assert detail["id"] == wf["id"]
        assert detail["name"] == "读书计划"
        assert detail["config"]["task_templates"][0]["steps"] == ["列书单"]

    def test_get_unknown_returns_404_code_1002(self, client, default_user_id):
        r = client.get("/api/v1/workflows/no-such-id")
        assert r.status_code == 404
        assert r.json()["code"] == 1002

    def test_create_with_blank_name_rejected(self, client, default_user_id):
        """name 有 min_length=1 约束 → 400 / 1001，不得落库。"""
        r = client.post("/api/v1/workflows", json={"name": ""})
        assert r.status_code == 400
        assert r.json()["code"] == 1001
        assert _db_counts("workflows") == 0

    def test_patch_updates_only_given_fields(self, client, default_user_id):
        wf = _create_wf(client, name="旧名", description="保留我")
        r = client.patch(f"/api/v1/workflows/{wf['id']}", json={"name": "新名"})
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["name"] == "新名"
        assert data["description"] == "保留我"
        assert data["category"] == "study"

    def test_delete_then_detail_404(self, client, default_user_id):
        wf = _create_wf(client)
        r = client.delete(f"/api/v1/workflows/{wf['id']}")
        assert r.status_code == 200 and r.json()["code"] == 0
        assert client.get(f"/api/v1/workflows/{wf['id']}").status_code == 404
        assert _db_counts("workflows") == 0


class TestWorkflowApiApply:
    """第 2 组：一键应用 + 应用历史。"""

    def test_apply_creates_data_and_history_record(self, client, default_user_id):
        wf = _create_wf(client)
        r = client.post(f"/api/v1/workflows/{wf['id']}/apply",
                        json={"params": {"name": "考研"}})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["code"] == 0, body
        data = body["data"]
        assert data["domains_created"] == 2
        assert data["templates_created"] == 1
        assert data["tasks_created"] == 1
        assert data["details"] == []

        # 落库核对：接口说创建了几个，库里就必须有几个
        assert _db_counts("domains") == 2
        assert _db_counts("templates") == 1
        assert _db_counts("tasks") == 1

        # 使用计数 +1（前端列表上的"用过 N 次"）
        assert client.get(f"/api/v1/workflows/{wf['id']}").json()["data"]["use_count"] == 1

        # 应用历史：两段路径不被 /{workflow_id} 吞掉
        hist = client.get("/api/v1/workflows/applications/history")
        assert hist.status_code == 200, hist.text
        h = hist.json()["data"]
        assert h["total"] == 1
        record = h["list"][0]
        assert record["workflow_id"] == wf["id"]
        assert record["status"] == "completed"
        assert record["params"] == {"name": "考研"}
        assert record["id"] == data["application_id"]

    def test_apply_without_body_params_defaults_to_empty(self, client, default_user_id):
        """请求体只给 {} 时应正常应用（params 默认空字典），标题前缀回落工作流名。"""
        wf = _create_wf(client, name="读书计划")
        r = client.post(f"/api/v1/workflows/{wf['id']}/apply", json={})
        assert r.status_code == 200, r.text
        assert r.json()["data"]["tasks_created"] == 1

        r = client.get("/api/v1/tasks")
        titles = {t["title"] for t in r.json()["data"]["list"]}
        assert titles == {"[读书计划] 选书"}

    def test_apply_unknown_workflow_returns_404(self, client, default_user_id):
        r = client.post("/api/v1/workflows/no-such-id/apply", json={"params": {}})
        assert r.status_code == 404
        assert r.json()["code"] == 1002

    def test_apply_is_idempotent_for_domains_and_templates(self, client, default_user_id):
        """连点两次「应用」：标签/模板不重复，任务会重复（业务有意为之）。"""
        wf = _create_wf(client)
        client.post(f"/api/v1/workflows/{wf['id']}/apply", json={"params": {}})
        second = client.post(f"/api/v1/workflows/{wf['id']}/apply", json={"params": {}})

        assert second.json()["data"]["domains_created"] == 0
        assert second.json()["data"]["templates_created"] == 0
        assert second.json()["data"]["tasks_created"] == 1
        assert _db_counts("domains") == 2
        assert _db_counts("templates") == 1
        assert _db_counts("tasks") == 2
        assert client.get("/api/v1/workflows/applications/history").json()["data"]["total"] == 2

    def test_generated_task_is_listable_by_status(self, client, default_user_id):
        """回归（2026-10-11）：生成的任务必须能被 pending 过滤器查到。

        原缺陷任务落库为 status="todo"，而列表过滤只认白名单状态 →
        任务在界面上"创建成功但看不见"，且任何流转都报 3001。
        """
        wf = _create_wf(client)
        client.post(f"/api/v1/workflows/{wf['id']}/apply", json={"params": {}})

        r = client.get("/api/v1/tasks", params={"status": "pending"})
        assert r.status_code == 200
        titles = [t["title"] for t in r.json()["data"]["list"]]
        assert "[读书计划] 选书" in titles

        task_id = r.json()["data"]["list"][0]["id"]
        # 真实用户路径：开始做 → 完成，两步都不得被状态机拒绝
        assert client.patch(f"/api/v1/tasks/{task_id}", json={"status": "in_progress"}).json()["code"] == 0
        assert client.patch(f"/api/v1/tasks/{task_id}", json={"status": "completed"}).json()["code"] == 0

    def test_history_pagination_shape(self, client, default_user_id):
        wf = _create_wf(client, config={})
        for _ in range(3):
            client.post(f"/api/v1/workflows/{wf['id']}/apply", json={"params": {}})

        r = client.get("/api/v1/workflows/applications/history", params={"page": 1, "page_size": 2})
        data = r.json()["data"]
        assert data["total"] == 3
        assert len(data["list"]) == 2
        assert set(data["list"][0]) == {
            "id", "workflow_id", "user_id", "params", "status", "result_summary", "applied_at",
        }
