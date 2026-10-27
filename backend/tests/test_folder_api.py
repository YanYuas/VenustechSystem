# ============================================================
# Folder API 生产级集成测试
#
# Folder API 调用 DocumentService（folders_tree/create_folder/rename_folder/delete_folder），
# 但路由在独立的 folder.py 中，需要单独覆盖。
#
# 标准：真数据夹具 + API操作后查库验证 + HTTP状态码 + 增量隔离
# ============================================================
from __future__ import annotations


from app.database import SessionLocal
from app.models.folder import Folder
from tests.factories import count_rows, seed_document_fixture


def _db():
    return SessionLocal()


# ============================================================
# 第 1 组：Folder CRUD 的 API→查库交叉验证
# ============================================================

class TestFolderApiGroup1CRUD:
    """第1组：文件夹树 + 创建 + 重命名 + 删除 + 收集箱保护。"""

    def test_folders_tree_returns_inbox_first(self, client, default_user_id):
        """文件夹树接口返回收集箱置顶，且文件夹数量和查库一致。

        防什么：folders_tree 如果漏了收集箱置顶逻辑，收集箱会和普通文件夹
        混在一起排序，用户体验混乱。
        """
        db = _db()
        try:
            seed_document_fixture(db, default_user_id)
            db.commit()
        finally:
            db.close()

        r = client.get("/api/v1/folders")
        assert r.status_code == 200
        assert r.json()["code"] == 0
        tree = r.json()["data"]
        # 收集箱置顶
        assert tree[0]["is_inbox"] is True
        assert tree[0]["name"] == "收集箱"
        # 夹具中有3个文件夹（收集箱+数学建模+科研笔记）
        assert len(tree) == 3

        # 查库交叉验证
        db = _db()
        try:
            assert count_rows(db, "folders", user_id=default_user_id) == 3
        finally:
            db.close()

    def test_create_folder_via_api_persists_to_db(self, client, default_user_id):
        """通过 API 创建文件夹后，查库验证 name/parent_id/is_inbox 正确写入。

        防什么：API 层如果没正确传递 parent_id，子文件夹会变成根文件夹。
        """
        r = client.post("/api/v1/folders", json={"name": "新文件夹"})
        assert r.status_code == 200
        assert r.json()["code"] == 0
        folder_id = r.json()["data"]["id"]

        # 查库验证
        db = _db()
        try:
            in_db = db.get(Folder, folder_id)
            assert in_db is not None
            assert in_db.name == "新文件夹"
            assert in_db.parent_id is None
            assert in_db.is_inbox is False
            assert in_db.user_id == default_user_id
        finally:
            db.close()

    def test_create_subfolder_via_api_persists_parent(self, client, default_user_id):
        """通过 API 创建子文件夹（带 parent_id），查库验证 parent_id 正确。

        防什么：create_folder 如果漏了 parent_id 校验，不存在的 parent_id 会
        触发外键约束失败（500）。
        """
        db = _db()
        try:
            fixture = seed_document_fixture(db, default_user_id)
            db.commit()
            parent_id = fixture["folders"]["math_modeling"].id
        finally:
            db.close()

        r = client.post("/api/v1/folders", json={
            "name": "子文件夹", "parent_id": parent_id,
        })
        assert r.status_code == 200
        folder_id = r.json()["data"]["id"]

        # 查库验证
        db = _db()
        try:
            in_db = db.get(Folder, folder_id)
            assert in_db.parent_id == parent_id
        finally:
            db.close()

    def test_rename_folder_via_api_persists(self, client, default_user_id):
        """通过 API 重命名文件夹后，查库验证 name 变了，其他字段不变。

        防什么：rename_folder 如果直接修改了其他字段（比如 sort_order），
        文件夹的排序会被意外改变。
        """
        db = _db()
        try:
            fixture = seed_document_fixture(db, default_user_id)
            db.commit()
            folder_id = fixture["folders"]["research"].id
            original_sort_order = fixture["folders"]["research"].sort_order
        finally:
            db.close()

        r = client.patch(f"/api/v1/folders/{folder_id}", json={"name": "新名字"})
        assert r.status_code == 200
        assert r.json()["data"]["name"] == "新名字"

        # 查库验证
        db = _db()
        try:
            in_db = db.get(Folder, folder_id)
            assert in_db.name == "新名字"
            assert in_db.sort_order == original_sort_order
            assert in_db.is_inbox is False
        finally:
            db.close()

    def test_delete_folder_via_api_moves_docs_to_inbox(self, client, default_user_id):
        """通过 API 删除文件夹后，该文件夹下的文档移至收集箱，文件夹消失。

        防什么：delete_folder 如果漏了文档迁移逻辑，文档的 folder_id 会指向
        已删除的文件夹（外键 SET NULL 后 folder_id=None），列表里显示"未分类"。
        """
        db = _db()
        try:
            fixture = seed_document_fixture(db, default_user_id)
            db.commit()
            folder_id = fixture["folders"]["research"].id  # 科研笔记，下有1篇文档
            inbox_id = fixture["folders"]["inbox"].id
        finally:
            db.close()

        r = client.delete(f"/api/v1/folders/{folder_id}")
        assert r.status_code == 200
        assert r.json()["code"] == 0

        # 查库验证
        db = _db()
        try:
            assert db.get(Folder, folder_id) is None
            # 原文件夹下的文档移至收集箱
            from app.models.document import Document
            doc_in_db = db.get(Document, fixture["docs"]["mec_algorithm"].id)
            assert doc_in_db.folder_id == inbox_id
        finally:
            db.close()


# ============================================================
# 第 2 组：参数校验 + 越权 + 收集箱保护
# ============================================================

class TestFolderApiGroup2ValidationAuthInbox:
    """第2组：空名称校验 + 越权创建/重命名/删除 + 收集箱保护。"""

    def test_create_folder_empty_name_returns_400(self, client):
        """创建文件夹时空名称被校验拒绝（400），不进入 service 层。

        防什么：如果 schema 的 min_length 校验漏了，空名称会进入 service 层
        并被写入数据库。
        """
        r = client.post("/api/v1/folders", json={"name": ""})
        assert r.status_code == 400

    def test_create_folder_with_other_users_parent_returns_404(self, client, default_user_id):
        """创建子文件夹时指定其他用户的 parent_id 返回 404，库中不产生脏数据。

        防什么：create_folder 的 parent 校验如果只检查存在性而不检查归属，
        用户可以在别人的文件夹下创建子文件夹。
        """
        from app.models.user import User

        db = _db()
        try:
            other = User(username="other_for_folder_api", nickname="其他")
            db.add(other)
            db.flush()
            other_folder = Folder(user_id=other.id, name="他人父文件夹", is_inbox=False)
            db.add(other_folder)
            db.commit()
            other_folder_id = other_folder.id
        finally:
            db.close()

        r = client.post("/api/v1/folders", json={
            "name": "子文件夹", "parent_id": other_folder_id,
        })
        assert r.status_code == 404
        assert r.json()["code"] == 1002

        # 先触发收集箱创建，再查库
        client.get("/api/v1/folders")
        db = _db()
        try:
            assert count_rows(db, "folders", user_id=default_user_id) == 1
        finally:
            db.close()

    def test_rename_other_users_folder_returns_404(self, client, default_user_id):
        """重命名其他用户的文件夹返回 404，库中名字不变。

        防什么：_owned_folder 如果只检查存在性而不检查归属，用户可以篡改
        别人的文件夹名。
        """
        from app.models.user import User

        db = _db()
        try:
            other = User(username="other_rename_api", nickname="其他")
            db.add(other)
            db.flush()
            other_folder = Folder(user_id=other.id, name="他人文件夹", is_inbox=False)
            db.add(other_folder)
            db.commit()
            other_folder_id = other_folder.id
        finally:
            db.close()

        r = client.patch(f"/api/v1/folders/{other_folder_id}", json={"name": "篡改"})
        assert r.status_code == 404
        assert r.json()["code"] == 1002

        # 查库：名字没变
        db = _db()
        try:
            in_db = db.get(Folder, other_folder_id)
            assert in_db.name == "他人文件夹"
        finally:
            db.close()

    def test_delete_other_users_folder_returns_404(self, client, default_user_id):
        """删除其他用户的文件夹返回 404，库中文件夹仍在。

        防什么：_owned_folder 如果只检查存在性而不检查归属，用户可以删除
        别人的文件夹。
        """
        from app.models.user import User

        db = _db()
        try:
            other = User(username="other_delete_api", nickname="其他")
            db.add(other)
            db.flush()
            other_folder = Folder(user_id=other.id, name="他人文件夹", is_inbox=False)
            db.add(other_folder)
            db.commit()
            other_folder_id = other_folder.id
        finally:
            db.close()

        r = client.delete(f"/api/v1/folders/{other_folder_id}")
        assert r.status_code == 404
        assert r.json()["code"] == 1002

        # 查库：文件夹仍在
        db = _db()
        try:
            assert db.get(Folder, other_folder_id) is not None
        finally:
            db.close()

    def test_delete_inbox_via_api_returns_error(self, client, default_user_id):
        """通过 API 删除收集箱返回错误（400/409），库中收集箱仍在。

        防什么：delete_folder 如果漏了收集箱保护，用户可以通过 API 删除
        收集箱，导致默认入收集箱的逻辑崩溃。
        """
        from sqlalchemy import select

        # 先触发收集箱创建
        client.get("/api/v1/folders")
        db = _db()
        try:
            inbox = db.scalars(
                select(Folder).where(Folder.user_id == default_user_id, Folder.is_inbox.is_(True))
            ).first()
            inbox_id = inbox.id
        finally:
            db.close()

        r = client.delete(f"/api/v1/folders/{inbox_id}")
        assert r.status_code in (400, 409)

        # 查库：收集箱仍在
        db = _db()
        try:
            assert db.get(Folder, inbox_id) is not None
        finally:
            db.close()
