# ============================================================
# 资源中心 API 层测试（二期 M7）
#
# 单用户模式下无法用两个真实登录态测越权 —— 改为直接往库里插一条
# 「属于另一个用户」的记录，再请求它的 id，断言 404。
# 这批用例是 D1（IDOR）修复的**对外契约**：修复前它们会 200 且真的改到他人数据。
# ============================================================
from __future__ import annotations

import uuid

import pytest

BASE = "/api/v1/resource"


def _mk_other_user() -> str:
    from app.database import SessionLocal
    from app.models.user import User

    db = SessionLocal()
    try:
        u = User(username=f"other_{uuid.uuid4().hex[:8]}", nickname="他人")
        db.add(u)
        db.commit()
        db.refresh(u)
        return u.id
    finally:
        db.close()


def _insert_foreign(kind: str) -> str:
    """插一条属于"另一个用户"的资源，返回 id。"""
    from app.database import SessionLocal
    from app.models.resource import Domain, InboxItem, Template

    other_id = _mk_other_user()
    db = SessionLocal()
    try:
        if kind == "inbox":
            row = InboxItem(user_id=other_id, content_type="text", title="他人的收集箱项")
        elif kind == "template":
            row = Template(user_id=other_id, name="他人的模板", category="doc",
                           content="content {{x}}")
        else:
            row = Domain(user_id=other_id, name="他人的领域")
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id
    finally:
        db.close()


def _fetch(kind: str, row_id: str):
    from app.database import SessionLocal
    from app.models.resource import Domain, InboxItem, Template

    model = {"inbox": InboxItem, "template": Template, "domain": Domain}[kind]
    db = SessionLocal()
    try:
        return db.get(model, row_id)
    finally:
        db.close()


# ============================================================
# 一、收集箱 API
# ============================================================
class TestInboxApi:

    def test_create_and_get(self, client):
        r = client.post(f"{BASE}/inbox", json={"content_type": "text", "title": "随手记"})
        assert r.status_code == 200
        item_id = r.json()["data"]["id"]
        assert r.json()["data"]["status"] == "pending"

        got = client.get(f"{BASE}/inbox/{item_id}")
        assert got.status_code == 200
        assert got.json()["data"]["title"] == "随手记"

    def test_list_paginated_shape(self, client):
        client.post(f"{BASE}/inbox", json={"content_type": "text", "title": "a"})
        r = client.get(f"{BASE}/inbox")
        d = r.json()["data"]
        assert set(d) == {"list", "total", "page", "page_size"}
        assert d["total"] == 1

    def test_list_rejects_unknown_status_400(self, client):
        r = client.get(f"{BASE}/inbox", params={"status": "bogus"})
        assert r.status_code == 400
        assert r.json()["code"] == 1001

    def test_patch_title(self, client):
        item_id = client.post(f"{BASE}/inbox",
                              json={"content_type": "text", "title": "旧"}).json()["data"]["id"]
        r = client.patch(f"{BASE}/inbox/{item_id}", json={"title": "新"})
        assert r.status_code == 200 and r.json()["data"]["title"] == "新"

    def test_patch_rejects_unknown_status_400(self, client):
        item_id = client.post(f"{BASE}/inbox",
                              json={"content_type": "text"}).json()["data"]["id"]
        r = client.patch(f"{BASE}/inbox/{item_id}", json={"status": "whatever"})
        assert r.status_code == 400
        assert r.json()["code"] == 1001
        # 无副作用
        assert _fetch("inbox", item_id).status == "pending"

    def test_delete_inbox(self, client):
        item_id = client.post(f"{BASE}/inbox",
                              json={"content_type": "text"}).json()["data"]["id"]
        assert client.delete(f"{BASE}/inbox/{item_id}").status_code == 200
        assert client.get(f"{BASE}/inbox/{item_id}").status_code == 404

    def test_get_unknown_404(self, client):
        r = client.get(f"{BASE}/inbox/no-such-id")
        assert r.status_code == 404
        assert r.json()["code"] == 1002

    def test_process_invalid_action_400_not_500(self, client):
        """回归：原实现 `raise ValueError` → 未捕获 → 500。

        这条钉死「非法动作是客户端错误而非服务端错误」。
        """
        item_id = client.post(f"{BASE}/inbox",
                              json={"content_type": "text"}).json()["data"]["id"]
        r = client.post(f"{BASE}/inbox/{item_id}/process", params={"action": "explode"})
        assert r.status_code == 400
        assert r.json()["code"] == 1001
        assert "不支持的处理动作" in r.json()["message"]

    def test_process_archive(self, client):
        item_id = client.post(f"{BASE}/inbox",
                              json={"content_type": "text"}).json()["data"]["id"]
        r = client.post(f"{BASE}/inbox/{item_id}/process", params={"action": "archive"})
        assert r.status_code == 200
        assert r.json()["data"]["status"] == "archived"

    def test_batch_process_route_not_shadowed(self, client):
        """路由陷阱验证：`POST /inbox/batch-process` 必须命中批量处理器。

        `/inbox/batch-process` 与 `GET /inbox/{item_id}` 路径形状相同
        （都是两段），Starlette 会先记下 partial 匹配再继续找方法匹配的
        路由 —— 这条用例把"静态段不被动态段吞掉"钉死。
        """
        ids = [client.post(f"{BASE}/inbox",
                           json={"content_type": "text", "title": str(i)}).json()["data"]["id"]
               for i in range(3)]
        r = client.post(f"{BASE}/inbox/batch-process",
                        json={"item_ids": ids, "action": "archive"})
        assert r.status_code == 200, r.text
        d = r.json()["data"]
        assert d["total"] == 3 and d["success"] == 3
        for i in ids:
            assert _fetch("inbox", i).status == "archived"

    def test_batch_process_reports_failures(self, client):
        good = client.post(f"{BASE}/inbox",
                           json={"content_type": "text"}).json()["data"]["id"]
        r = client.post(f"{BASE}/inbox/batch-process",
                        json={"item_ids": [good, "no-such-id"], "action": "archive"})
        d = r.json()["data"]
        assert d["success"] == 1 and d["failed"] == 1

    def test_batch_process_body_contract(self, client):
        """请求体契约：`{item_ids, action}`（与前端 resource.ts 一致）。

        回归：原后端签名为裸 `item_ids: list[str]` + `action: str`，
        FastAPI 推定 body 是裸数组、action 走 query，与前端发的对象体对不上，
        该端点恒定返回「参数错误」。
        """
        # 缺 item_ids → 参数错误
        assert client.post(f"{BASE}/inbox/batch-process",
                           json={"action": "archive"}).status_code == 400
        # 空 item_ids → 被 min_length=1 拦下
        assert client.post(f"{BASE}/inbox/batch-process",
                           json={"item_ids": [], "action": "archive"}).status_code == 400
        # 非法 action 走白名单 → 400（而不是 500）
        good = client.post(f"{BASE}/inbox",
                           json={"content_type": "text"}).json()["data"]["id"]
        r = client.post(f"{BASE}/inbox/batch-process",
                        json={"item_ids": [good], "action": "explode"})
        assert r.status_code == 200
        assert r.json()["data"]["failed"] == 1  # 逐条失败被收集，不是整批 500


# ============================================================
# 二、模板库 API
# ============================================================
class TestTemplateApi:

    def _create(self, client, **over):
        body = {"name": "周报模板", "category": "doc", "content": "你好 {{name}}"}
        body.update(over)
        return client.post(f"{BASE}/templates", json=body)

    def test_create_and_list(self, client):
        assert self._create(client).status_code == 200
        d = client.get(f"{BASE}/templates").json()["data"]
        assert d["total"] == 1 and d["list"][0]["name"] == "周报模板"

    def test_apply_renders(self, client):
        tid = self._create(client, content="你好 {{name}}").json()["data"]["id"]
        r = client.post(f"{BASE}/templates/{tid}/apply", json={"name": "衍煜"})
        assert r.status_code == 200
        assert r.json()["data"]["rendered"] == "你好 衍煜"

    def test_patch_template(self, client):
        tid = self._create(client).json()["data"]["id"]
        r = client.patch(f"{BASE}/templates/{tid}", json={"name": "新模板"})
        assert r.status_code == 200 and r.json()["data"]["name"] == "新模板"

    def test_patch_cannot_mass_assign(self, client, default_user_id):
        """D2 回归：PATCH 传 user_id / use_count / is_builtin 必须被忽略。"""
        tid = self._create(client).json()["data"]["id"]
        other = _mk_other_user()
        r = client.patch(f"{BASE}/templates/{tid}", json={
            "user_id": other, "id": "forged", "use_count": 9999,
            "is_builtin": True, "name": "合法名",
        })
        assert r.status_code == 200
        assert r.json()["data"]["name"] == "合法名"
        row = _fetch("template", tid)
        assert row.user_id == default_user_id   # 所有者未被改写
        assert row.use_count == 0               # 计数未被改写
        assert row.is_builtin is False          # 未被提权
        assert row.id == tid

    def test_delete_template(self, client):
        tid = self._create(client).json()["data"]["id"]
        assert client.delete(f"{BASE}/templates/{tid}").status_code == 200
        assert client.patch(f"{BASE}/templates/{tid}",
                            json={"name": "x"}).status_code == 404


# ============================================================
# 三、领域库 API
# ============================================================
class TestDomainApi:

    def test_create_and_list(self, client):
        r = client.post(f"{BASE}/domains", json={"name": "数学"})
        assert r.status_code == 200
        d = client.get(f"{BASE}/domains").json()["data"]
        assert [x["name"] for x in d] == ["数学"]

    def test_patch_domain(self, client):
        did = client.post(f"{BASE}/domains", json={"name": "数学"}).json()["data"]["id"]
        r = client.patch(f"{BASE}/domains/{did}", json={"description": "改了", "sort_order": 3})
        assert r.status_code == 200
        assert r.json()["data"]["description"] == "改了"

    def test_patch_domain_cannot_mass_assign(self, client, default_user_id):
        did = client.post(f"{BASE}/domains", json={"name": "数学"}).json()["data"]["id"]
        client.patch(f"{BASE}/domains/{did}", json={"user_id": _mk_other_user(), "name": "合法"})
        assert _fetch("domain", did).user_id == default_user_id

    def test_delete_domain(self, client):
        did = client.post(f"{BASE}/domains", json={"name": "数学"}).json()["data"]["id"]
        assert client.delete(f"{BASE}/domains/{did}").status_code == 200
        assert client.patch(f"{BASE}/domains/{did}",
                            json={"name": "x"}).status_code == 404


# ============================================================
# 四、越权访问一律 404（D1 回归 · 本文件最重要的部分）
# ============================================================
class TestIdorBlockedAtApi:
    """修复前：这些请求全部 200，且真的读到 / 改到 / 删掉他人数据。"""

    def test_get_foreign_inbox_404(self, client):
        fid = _insert_foreign("inbox")
        r = client.get(f"{BASE}/inbox/{fid}")
        assert r.status_code == 404
        assert r.json()["code"] == 1002

    def test_patch_foreign_inbox_404_no_side_effect(self, client):
        fid = _insert_foreign("inbox")
        r = client.patch(f"{BASE}/inbox/{fid}", json={"title": "劫持"})
        assert r.status_code == 404
        assert _fetch("inbox", fid).title == "他人的收集箱项"

    def test_delete_foreign_inbox_404_no_side_effect(self, client):
        fid = _insert_foreign("inbox")
        assert client.delete(f"{BASE}/inbox/{fid}").status_code == 404
        assert _fetch("inbox", fid) is not None

    def test_process_foreign_inbox_404(self, client):
        fid = _insert_foreign("inbox")
        r = client.post(f"{BASE}/inbox/{fid}/process", params={"action": "archive"})
        assert r.status_code == 404
        assert _fetch("inbox", fid).status == "pending"

    def test_apply_foreign_template_404(self, client):
        fid = _insert_foreign("template")
        r = client.post(f"{BASE}/templates/{fid}/apply", json={"x": "1"})
        assert r.status_code == 404

    def test_patch_foreign_template_404_no_side_effect(self, client):
        fid = _insert_foreign("template")
        r = client.patch(f"{BASE}/templates/{fid}", json={"name": "劫持"})
        assert r.status_code == 404
        assert _fetch("template", fid).name == "他人的模板"

    def test_delete_foreign_template_404_no_side_effect(self, client):
        fid = _insert_foreign("template")
        assert client.delete(f"{BASE}/templates/{fid}").status_code == 404
        assert _fetch("template", fid) is not None

    def test_patch_foreign_domain_404_no_side_effect(self, client):
        fid = _insert_foreign("domain")
        r = client.patch(f"{BASE}/domains/{fid}", json={"name": "劫持"})
        assert r.status_code == 404
        assert _fetch("domain", fid).name == "他人的领域"

    def test_delete_foreign_domain_404_no_side_effect(self, client):
        fid = _insert_foreign("domain")
        assert client.delete(f"{BASE}/domains/{fid}").status_code == 404
        assert _fetch("domain", fid) is not None

    def test_foreign_records_not_visible_in_lists(self, client):
        """列表必须只含自己的数据（三个库都要）。"""
        _insert_foreign("inbox")
        _insert_foreign("template")
        _insert_foreign("domain")
        assert client.get(f"{BASE}/inbox").json()["data"]["total"] == 0
        assert client.get(f"{BASE}/templates").json()["data"]["total"] == 0
        assert client.get(f"{BASE}/domains").json()["data"] == []
