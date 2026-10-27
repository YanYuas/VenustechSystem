# ============================================================
# Identity API 生产级集成测试
#
# 标准：真数据夹具 + API操作后查库验证 + HTTP状态码 + 增量隔离
# ============================================================
from __future__ import annotations


from app.database import SessionLocal
from app.models.identity import Identity
from tests.factories import count_rows


def _db():
    return SessionLocal()


def _identity_payload(name="API身份", slug="api-identity", **overrides):
    """构造创建身份的 payload，所有字段有默认值，可覆盖。"""
    defaults = dict(
        name=name, slug=slug, color_token="primary",
        icon="star", description="API描述", sort_order=0,
    )
    defaults.update(overrides)
    return defaults


# ============================================================
# 第 1 组：Identity CRUD 的 API→查库交叉验证
# ============================================================

class TestIdentityApiGroup1CRUD:
    """第1组：列表 + 创建 + 详情 + 更新 + 软删除。"""

    def test_list_identities_via_api(self, client, default_user_id):
        """列表接口返回当前用户的身份，数量和查库一致。

        防什么：list 如果漏了 user_id 过滤，会返回所有用户的身份。
        """
        db = _db()
        try:
            db.add(Identity(user_id=default_user_id, name="身份A", slug="a"))
            db.add(Identity(user_id=default_user_id, name="身份B", slug="b"))
            db.commit()
        finally:
            db.close()

        r = client.get("/api/v1/identities")
        assert r.status_code == 200
        assert r.json()["code"] == 0
        data = r.json()["data"]
        assert len(data) == 2
        names = {i["name"] for i in data}
        assert "身份A" in names
        assert "身份B" in names

    def test_create_identity_via_api_persists_to_db(self, client, default_user_id):
        """通过 API 创建身份后，查库验证 name/slug/color_token/user_id 正确写入。

        防什么：API 层如果没正确传递字段，身份创建后字段为默认值。
        """
        r = client.post("/api/v1/identities", json=_identity_payload(
            name="新建身份", slug="new-identity", color_token="mint",
        ))
        assert r.status_code == 200
        identity_id = r.json()["data"]["id"]

        # 查库验证
        db = _db()
        try:
            in_db = db.get(Identity, identity_id)
            assert in_db is not None
            assert in_db.name == "新建身份"
            assert in_db.slug == "new-identity"
            assert in_db.color_token == "mint"
            assert in_db.user_id == default_user_id
            assert in_db.is_active is True
        finally:
            db.close()

    def test_get_identity_via_api(self, client, default_user_id):
        """详情接口返回完整字段。

        防什么：get 如果漏了 _out 转换，返回的是 ORM 对象而不是 schema。
        """
        db = _db()
        try:
            i = Identity(user_id=default_user_id, name="详情身份", slug="detail",
                         color_token="sky", icon="book")
            db.add(i)
            db.commit()
            identity_id = i.id
        finally:
            db.close()

        r = client.get(f"/api/v1/identities/{identity_id}")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["name"] == "详情身份"
        assert data["slug"] == "detail"
        assert data["color_token"] == "sky"
        assert data["icon"] == "book"
        assert data["is_active"] is True

    def test_update_identity_via_api_persists(self, client, default_user_id):
        """通过 API 更新身份后，查库验证指定字段变了，slug 不可改。

        防什么：update 如果允许修改 slug，会打断所有按 slug 的引用。
        """
        db = _db()
        try:
            i = Identity(user_id=default_user_id, name="旧名字", slug="old-slug",
                         color_token="primary")
            db.add(i)
            db.commit()
            identity_id = i.id
        finally:
            db.close()

        r = client.patch(f"/api/v1/identities/{identity_id}", json={
            "name": "新名字", "color_token": "butter",
        })
        assert r.status_code == 200
        assert r.json()["data"]["name"] == "新名字"

        # 查库验证
        db = _db()
        try:
            in_db = db.get(Identity, identity_id)
            assert in_db.name == "新名字"
            assert in_db.color_token == "butter"
            assert in_db.slug == "old-slug"  # slug 不可改
        finally:
            db.close()

    def test_delete_identity_via_api_soft_deletes(self, client, default_user_id):
        """通过 API 删除身份后，行仍在数据库但 deleted_at 非空，列表中消失。

        防什么：delete 如果是硬删除，历史记录的 identity_id 会变成悬空引用。
        """
        db = _db()
        try:
            i = Identity(user_id=default_user_id, name="待删除", slug="to-delete")
            db.add(i)
            db.commit()
            identity_id = i.id
        finally:
            db.close()

        r = client.delete(f"/api/v1/identities/{identity_id}")
        assert r.status_code == 200
        assert r.json()["code"] == 0

        # 查库：行仍在，deleted_at 非空
        db = _db()
        try:
            in_db = db.get(Identity, identity_id)
            assert in_db is not None
            assert in_db.deleted_at is not None
        finally:
            db.close()

        # 列表中消失
        r = client.get("/api/v1/identities")
        assert len(r.json()["data"]) == 0


# ============================================================
# 第 2 组：业务规则校验（重复slug + 越权 + 非法pattern）
# ============================================================

class TestIdentityApiGroup2ValidationAuth:
    """第2组：重复slug 400 + 越权获取/更新/删除 404 + 非法slug pattern 400。"""

    def test_create_duplicate_slug_returns_409(self, client, default_user_id):
        """创建时指定已存在的 slug 返回 409 Conflict，不产生身份。

        防什么：slug 是筛选器/路由的稳定键，BusinessException（slug已存在）
        被映射为 409 Conflict，语义正确。
        """
        client.post("/api/v1/identities", json=_identity_payload(name="第一个", slug="my-slug"))

        r = client.post("/api/v1/identities", json=_identity_payload(name="第二个", slug="my-slug"))
        assert r.status_code == 409

        # 查库：只有一条
        db = _db()
        try:
            assert count_rows(db, "identities", user_id=default_user_id, slug="my-slug") == 1
        finally:
            db.close()

    def test_get_other_users_identity_returns_404(self, client, default_user_id):
        """获取其他用户的身份返回 404，不泄露数据。

        防什么：get 如果只检查存在性而不检查 user_id，用户可以通过遍历 id
        看到别人的身份。
        """
        from app.models.user import User

        db = _db()
        try:
            other = User(username="other_id_api", nickname="其他")
            db.add(other)
            db.flush()
            other_identity = Identity(user_id=other.id, name="他人身份", slug="other")
            db.add(other_identity)
            db.commit()
            other_identity_id = other_identity.id
        finally:
            db.close()

        r = client.get(f"/api/v1/identities/{other_identity_id}")
        assert r.status_code == 404
        assert r.json()["code"] == 1002

    def test_create_invalid_slug_pattern_returns_400(self, client, default_user_id):
        """创建时指定非法 slug pattern（大写/特殊字符）返回 400，不产生身份。

        防什么：slug 的 pattern ^[a-z][a-z0-9-]*$ 确保 slug 是 URL 安全的，
        如果 schema 校验漏了，非法 slug 会破坏路由。
        """
        r = client.post("/api/v1/identities", json=_identity_payload(
            name="非法slug", slug="Invalid Slug!",
        ))
        assert r.status_code == 400

        # 查库：没有产生身份
        db = _db()
        try:
            assert count_rows(db, "identities", user_id=default_user_id) == 0
        finally:
            db.close()

    def test_update_other_users_identity_returns_404(self, client, default_user_id):
        """更新其他用户的身份返回 404，库中数据不变。

        防什么：update 如果只检查存在性而不检查 user_id，用户可以篡改
        别人的身份。
        """
        from app.models.user import User

        db = _db()
        try:
            other = User(username="other_id_update", nickname="其他")
            db.add(other)
            db.flush()
            other_identity = Identity(user_id=other.id, name="他人身份", slug="other-update")
            db.add(other_identity)
            db.commit()
            other_identity_id = other_identity.id
        finally:
            db.close()

        r = client.patch(f"/api/v1/identities/{other_identity_id}", json={"name": "篡改"})
        assert r.status_code == 404
        assert r.json()["code"] == 1002

        # 查库：名字没变
        db = _db()
        try:
            in_db = db.get(Identity, other_identity_id)
            assert in_db.name == "他人身份"
        finally:
            db.close()

    def test_delete_other_users_identity_returns_404(self, client, default_user_id):
        """删除其他用户的身份返回 404，库中身份仍在。

        防什么：delete 如果只检查存在性而不检查 user_id，用户可以删除
        别人的身份。
        """
        from app.models.user import User

        db = _db()
        try:
            other = User(username="other_id_delete", nickname="其他")
            db.add(other)
            db.flush()
            other_identity = Identity(user_id=other.id, name="他人身份", slug="other-delete")
            db.add(other_identity)
            db.commit()
            other_identity_id = other_identity.id
        finally:
            db.close()

        r = client.delete(f"/api/v1/identities/{other_identity_id}")
        assert r.status_code == 404
        assert r.json()["code"] == 1002

        # 查库：身份仍在，deleted_at 为空
        db = _db()
        try:
            in_db = db.get(Identity, other_identity_id)
            assert in_db is not None
            assert in_db.deleted_at is None
        finally:
            db.close()


# ============================================================
# 第 3 组：include_archived + 空名称 + 已删除404 + 同slug不同用户 + 名称strip
# ============================================================

class TestIdentityApiGroup3ArchivedValidationDeleted:
    """第3组：include_archived参数 + 空名称400 + 已删除身份404 + 同slug不同用户 + 名称strip。"""

    def test_list_include_archived_param(self, client, default_user_id):
        """列表接口默认包含归档（include_archived=True），显式传 false 时排除。

        防什么：Identity API 的 list 默认 include_archived=True（与 project
        不同），归档身份默认显示在筛选器里（灰显）。
        """
        # 创建身份并归档
        r = client.post("/api/v1/identities", json=_identity_payload(name="归档身份", slug="archived-api"))
        identity_id = r.json()["data"]["id"]
        client.patch(f"/api/v1/identities/{identity_id}", json={"is_active": False})

        # 默认包含归档
        r = client.get("/api/v1/identities")
        assert len(r.json()["data"]) == 1

        # include_archived=false 排除归档
        r = client.get("/api/v1/identities?include_archived=false")
        assert len(r.json()["data"]) == 0

    def test_create_empty_name_returns_400(self, client, default_user_id):
        """创建时空名称返回 400，不产生身份。

        防什么：CreateIdentityRequest.name 的 min_length=1 校验确保空名称被拒绝。
        """
        r = client.post("/api/v1/identities", json=_identity_payload(name="", slug="empty-name"))
        assert r.status_code == 400

        # 查库：没有产生身份
        db = _db()
        try:
            assert count_rows(db, "identities", user_id=default_user_id) == 0
        finally:
            db.close()

    def test_get_deleted_identity_returns_404(self, client, default_user_id):
        """获取已软删除的身份返回 404。

        防什么：如果 _get_owned 漏了 deleted_at 检查，已删除的身份仍可
        被获取，前端显示已删除的数据。
        """
        r = client.post("/api/v1/identities", json=_identity_payload(name="已删除", slug="deleted-api"))
        identity_id = r.json()["data"]["id"]
        client.delete(f"/api/v1/identities/{identity_id}")

        r = client.get(f"/api/v1/identities/{identity_id}")
        assert r.status_code == 404
        assert r.json()["code"] == 1002

    def test_same_slug_different_user_allowed_via_api(self, client, default_user_id):
        """不同用户可以使用相同的 slug（唯一约束是 user_id+slug）。

        防什么：如果唯一约束漏了 user_id，全局 slug 唯一，用户不能使用
        常见 slug。
        """
        from app.models.user import User

        # 当前用户创建
        client.post("/api/v1/identities", json=_identity_payload(name="用户A", slug="shared-api"))

        # 造其他用户（通过数据库，因为 API 只能操作当前用户）
        db = _db()
        try:
            other = User(username="other_shared_api", nickname="其他")
            db.add(other)
            db.flush()
            db.add(Identity(user_id=other.id, name="用户B", slug="shared-api"))
            db.commit()
        finally:
            db.close()

        # 查库：两条同 slug
        db = _db()
        try:
            assert count_rows(db, "identities", slug="shared-api") == 2
        finally:
            db.close()

    def test_create_name_with_spaces_stripped(self, client, default_user_id):
        """创建时名称前后空格被 strip，查库验证。

        防什么：如果 service 层漏了 name.strip()，用户输入"  学生  "会
        原样写入，列表显示有多余空格。
        """
        r = client.post("/api/v1/identities", json=_identity_payload(
            name="  带空格身份  ", slug="spaces-api",
        ))
        assert r.status_code == 200
        identity_id = r.json()["data"]["id"]
        assert r.json()["data"]["name"] == "带空格身份"

        # 查库验证
        db = _db()
        try:
            in_db = db.get(Identity, identity_id)
            assert in_db.name == "带空格身份"
        finally:
            db.close()
