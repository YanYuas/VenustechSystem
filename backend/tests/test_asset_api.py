# ============================================================
# 长期资产库 API 集成测试（原缺失模块，本轮补齐）
#
# 覆盖：SOP（CRUD + 版本 + 使用）、Prompt（CRUD + 应用 + 评分）、
#       Skill（CRUD + 使用）、项目记忆（CRUD + 轴校验）。
#
# 说明：越权（他人资产）在 API 层**无法构造** —— 一期是单用户模式，
# `get_current_user` 恒定返回 default_user，没有第二身份可 impersonate。
# 归属校验的覆盖放在 test_asset_production.py（Service 层）里做。
# 本文件着力于「路由/参数/响应契约」：PATCH 是裸 dict、rate 是查询参数、
#   apply 的请求体是变量字典本身（不是 {variables: {...}}）。
# ============================================================
from __future__ import annotations

from app.database import SessionLocal


def _db():
    return SessionLocal()


# ---------- 造数辅助（一律走 API，确保走的是真实契约） ----------

def _create_sop(client, name="周复盘 SOP", **extra):
    payload = {"name": name, "category": "review", "description": "每周日固定流程",
               "steps": [{"title": "收集数据"}], "checklist": ["导出周数据"], "tags": ["复盘"]}
    payload.update(extra)
    r = client.post("/api/v1/assets/sops", json=payload)
    assert r.status_code == 200, r.text
    assert r.json()["code"] == 0, r.json()
    return r.json()["data"]


def _create_prompt(client, name="建模拆题模板", **extra):
    payload = {"name": name, "category": "math",
               "role_setting": "你是资深数学建模手",
               "task_description": "把 {{topic}} 拆成子问题",
               "output_format": "表格", "variables": ["topic"]}
    payload.update(extra)
    r = client.post("/api/v1/assets/prompts", json=payload)
    assert r.status_code == 200, r.text
    return r.json()["data"]


def _create_skill(client, name="最小覆盖圆算法", **extra):
    payload = {"name": name, "category": "算法", "methodology": "增量化 Welzl", "tags": ["几何"]}
    payload.update(extra)
    r = client.post("/api/v1/assets/skills", json=payload)
    assert r.status_code == 200, r.text
    return r.json()["data"]


def _create_memory(client, name="论文复盘", **extra):
    payload = {"name": name, "summary": "投 CGTA", "successes": "收敛快",
               "failures": "灵敏度浅", "tags": ["科研"]}
    payload.update(extra)
    r = client.post("/api/v1/assets/memories", json=payload)
    assert r.status_code == 200, r.text
    return r.json()["data"]


class TestAssetApiSop:
    """第 1 组：SOP 列表 / 详情 / 创建 / 更新（含版本） / 使用 / 删除。"""

    def test_list_empty_shape(self, client, default_user_id):
        r = client.get("/api/v1/assets/sops")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data == {"list": [], "total": 0, "page": 1, "page_size": 20}

    def test_create_then_detail_matches_db(self, client, default_user_id):
        sop = _create_sop(client, name="周复盘 SOP")
        assert sop["version"] == 1 and sop["use_count"] == 0
        assert sop["steps"] == [{"title": "收集数据"}]

        r = client.get(f"/api/v1/assets/sops/{sop['id']}")
        assert r.status_code == 200
        assert r.json()["data"]["name"] == "周复盘 SOP"

        db = _db()
        try:
            from app.models.asset import SOP
            row = db.get(SOP, sop["id"])
            assert row is not None and row.user_id == default_user_id
        finally:
            db.close()

    def test_category_filter(self, client, default_user_id):
        _create_sop(client, name="A", category="review")
        _create_sop(client, name="B", category="reading")

        r = client.get("/api/v1/assets/sops", params={"category": "reading"})
        data = r.json()["data"]
        assert data["total"] == 1
        assert data["list"][0]["name"] == "B"

    def test_patch_with_change_note_bumps_version_and_history(self, client, default_user_id):
        """PATCH 的 change_note 是**查询参数**（api 层签名），版本历史必须记上它。"""
        sop = _create_sop(client)
        r = client.patch(f"/api/v1/assets/sops/{sop['id']}",
                         json={"name": "周复盘 SOP v2"},
                         params={"change_note": "补充决策回顾"})
        assert r.status_code == 200, r.text
        assert r.json()["data"]["version"] == 2

        hist = client.get(f"/api/v1/assets/sops/{sop['id']}/versions").json()["data"]
        assert hist["sop_id"] == sop["id"]
        assert len(hist["versions"]) == 1
        assert hist["versions"][0]["version"] == 1
        assert hist["versions"][0]["change_note"] == "补充决策回顾"
        assert hist["versions"][0]["content"]["name"] == "周复盘 SOP"

    def test_patch_ignores_non_whitelisted_fields(self, client, default_user_id):
        """回归（2026-10-11）：裸 dict 请求体不得越权改字段（user_id / id / 计数）。"""
        sop = _create_sop(client)
        r = client.patch(f"/api/v1/assets/sops/{sop['id']}", json={
            "name": "改名成功", "user_id": "someone-else", "id": "hacked",
            "use_count": 999, "version": 999,
        })
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert data["name"] == "改名成功"
        assert data["id"] == sop["id"]
        assert data["use_count"] == 0
        assert data["version"] == 2       # 服务端自增，不采信客户端

        db = _db()
        try:
            from app.models.asset import SOP
            assert db.get(SOP, sop["id"]) is not None, "主键被改成 hacked 了"
            assert db.get(SOP, sop["id"]).user_id == default_user_id
        finally:
            db.close()

    def test_use_endpoint_increments(self, client, default_user_id):
        sop = _create_sop(client)
        assert client.post(f"/api/v1/assets/sops/{sop['id']}/use").json()["data"]["use_count"] == 1
        assert client.post(f"/api/v1/assets/sops/{sop['id']}/use").json()["data"]["use_count"] == 2
        assert client.get(f"/api/v1/assets/sops/{sop['id']}").json()["data"]["use_count"] == 2

    def test_delete_then_detail_404(self, client, default_user_id):
        sop = _create_sop(client)
        assert client.delete(f"/api/v1/assets/sops/{sop['id']}").json()["code"] == 0

        r = client.get(f"/api/v1/assets/sops/{sop['id']}")
        assert r.status_code == 404
        assert r.json()["code"] == 1002

    def test_unknown_id_returns_404(self, client, default_user_id):
        for url in ("/api/v1/assets/sops/nope", "/api/v1/assets/sops/nope/versions"):
            r = client.get(url)
            assert r.status_code == 404, url
            assert r.json()["code"] == 1002

    def test_blank_name_rejected(self, client, default_user_id):
        r = client.post("/api/v1/assets/sops", json={"name": ""})
        assert r.status_code == 400
        assert r.json()["code"] == 1001


class TestAssetApiPrompt:
    """第 2 组：Prompt 模板 —— 应用（变量替换）与评分（查询参数 + 范围校验）。"""

    def test_apply_renders_and_counts(self, client, default_user_id):
        prompt = _create_prompt(client)
        # 请求体就是变量字典本身（不是 {variables: {...}}）
        r = client.post(f"/api/v1/assets/prompts/{prompt['id']}/apply", json={"topic": "最小覆盖圆"})
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert "把 最小覆盖圆 拆成子问题" in data["rendered"]
        assert data["rendered"].startswith("# 角色设定\n你是资深数学建模手")
        assert data["variables_used"] == ["topic"]
        assert data["use_count"] == 1
        assert data["prompt_id"] == prompt["id"]

    def test_apply_with_empty_body(self, client, default_user_id):
        """变量为空字典也应可应用（占位符原样保留，计数照加）。"""
        prompt = _create_prompt(client)
        r = client.post(f"/api/v1/assets/prompts/{prompt['id']}/apply", json={})
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert "{{topic}}" in data["rendered"]
        assert data["variables_used"] == []
        assert data["use_count"] == 1

    def test_rate_uses_query_param(self, client, default_user_id):
        """评分是查询参数 `?rating=`（前端 api 层就是这么拼的），不是请求体。"""
        prompt = _create_prompt(client)
        r = client.post(f"/api/v1/assets/prompts/{prompt['id']}/rate", params={"rating": 4})
        assert r.status_code == 200, r.text
        assert r.json()["data"]["rating"] == 4.0

        r = client.post(f"/api/v1/assets/prompts/{prompt['id']}/rate", params={"rating": 2})
        assert r.json()["data"]["rating"] == 3.0     # (4+2)/2

    def test_rate_out_of_range_rejected(self, client, default_user_id):
        """回归（2026-10-11）：评分此前无范围约束，0 / 9 / -99 都能写进库。

        现在由 `Query(..., ge=1, le=5)` 拦在入口：400 + 1001，
        且**不得留下任何写入痕迹**（rating 保持未评分）。
        """
        prompt = _create_prompt(client)
        for bad in (0, 6, -1, 100):
            r = client.post(f"/api/v1/assets/prompts/{prompt['id']}/rate", params={"rating": bad})
            assert r.status_code == 400, f"rating={bad} 未被拦下: {r.text}"
            assert r.json()["code"] == 1001

        assert client.get(f"/api/v1/assets/prompts/{prompt['id']}").json()["data"]["rating"] is None

    def test_rate_missing_param_rejected(self, client, default_user_id):
        prompt = _create_prompt(client)
        r = client.post(f"/api/v1/assets/prompts/{prompt['id']}/rate")
        assert r.status_code == 400
        assert r.json()["code"] == 1001

    def test_patch_cannot_fake_rating_or_use_count(self, client, default_user_id):
        prompt = _create_prompt(client)
        r = client.patch(f"/api/v1/assets/prompts/{prompt['id']}",
                         json={"description": "新说明", "rating": 5, "use_count": 88})
        data = r.json()["data"]
        assert data["description"] == "新说明"
        assert data["rating"] is None
        assert data["use_count"] == 0

    def test_delete_then_404(self, client, default_user_id):
        prompt = _create_prompt(client)
        assert client.delete(f"/api/v1/assets/prompts/{prompt['id']}").json()["code"] == 0
        assert client.get(f"/api/v1/assets/prompts/{prompt['id']}").status_code == 404


class TestAssetApiSkill:
    """第 3 组：技能库。"""

    def test_create_defaults_and_use(self, client, default_user_id):
        skill = _create_skill(client)
        assert skill["proficiency"] == "beginner"     # 未指定时的默认熟练度
        assert skill["use_count"] == 0

        r = client.post(f"/api/v1/assets/skills/{skill['id']}/use")
        assert r.json()["data"]["use_count"] == 1

    def test_create_explicit_proficiency(self, client, default_user_id):
        skill = _create_skill(client, proficiency="expert")
        assert skill["proficiency"] == "expert"

    def test_patch_and_delete(self, client, default_user_id):
        skill = _create_skill(client)
        r = client.patch(f"/api/v1/assets/skills/{skill['id']}",
                         json={"proficiency": "intermediate", "use_count": 77})
        assert r.json()["data"]["proficiency"] == "intermediate"
        assert r.json()["data"]["use_count"] == 0     # 白名单外，忽略

        assert client.delete(f"/api/v1/assets/skills/{skill['id']}").json()["code"] == 0
        assert client.patch(f"/api/v1/assets/skills/{skill['id']}", json={"name": "x"}).status_code == 404

    def test_list_category_filter(self, client, default_user_id):
        _create_skill(client, name="算法A", category="算法")
        _create_skill(client, name="工具B", category="工具")
        data = client.get("/api/v1/assets/skills", params={"category": "工具"}).json()["data"]
        assert data["total"] == 1
        assert data["list"][0]["name"] == "工具B"


class TestAssetApiMemory:
    """第 4 组：项目记忆（身份轴 / 项目轴校验都发生在创建与更新两处）。"""

    def test_create_minimal_and_detail(self, client, default_user_id):
        memory = _create_memory(client)
        assert memory["project_id"] is None
        assert memory["identity_id"] is None
        assert memory["key_metrics"] == {}

        r = client.get(f"/api/v1/assets/memories/{memory['id']}")
        assert r.status_code == 200
        assert r.json()["data"]["summary"] == "投 CGTA"

    def test_create_with_unknown_identity_rejected(self, client, default_user_id):
        """身份轴无外键兜底 → 必须在应用层拦下，返回 1001 而不是 500。

        （他人身份在单用户模式下构造不出来，故此处只覆盖"不存在的 id"；
        跨用户归属校验在 test_asset_production.py 中用两个用户覆盖。）
        """
        r = client.post("/api/v1/assets/memories",
                        json={"name": "记忆", "identity_id": "no-such-identity"})
        assert r.status_code == 400, r.text
        assert r.json()["code"] == 1001

    def test_create_with_unknown_project_rejected(self, client, default_user_id):
        """回归（2026-10-11）：不存在的 project_id 原先撞外键 → 未捕获 → 500。

        项目轴有外键，但"外键兜底"的代价是错误信息对用户毫无意义（500 内部错误），
        所以要求提前校验并给 1001。
        """
        r = client.post("/api/v1/assets/memories",
                        json={"name": "记忆", "project_id": "no-such-project"})
        assert r.status_code == 400, r.text
        assert r.json()["code"] == 1001

    def test_patch_ignores_ownership_and_unknown_axes(self, client, default_user_id):
        memory = _create_memory(client)
        # 白名单外的字段（user_id/id）被丢弃；轴字段走校验
        r = client.patch(f"/api/v1/assets/memories/{memory['id']}", json={
            "summary": "更新后的摘要", "user_id": "someone-else", "id": "hacked",
        })
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert data["summary"] == "更新后的摘要"
        assert data["id"] == memory["id"]

        r = client.patch(f"/api/v1/assets/memories/{memory['id']}", json={"identity_id": "no-such"})
        assert r.status_code == 400
        assert r.json()["code"] == 1001

    def test_delete_then_404(self, client, default_user_id):
        memory = _create_memory(client)
        assert client.delete(f"/api/v1/assets/memories/{memory['id']}").json()["code"] == 0
        assert client.get(f"/api/v1/assets/memories/{memory['id']}").status_code == 404
