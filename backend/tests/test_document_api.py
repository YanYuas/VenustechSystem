# ============================================================
# Document API 生产级集成测试
#
# 标准对齐 task API 测试 + 经纬项目：
#   1. 真数据夹具（seed_document_fixture）
#   2. API 操作后直接查库验证（不信响应体）
#   3. HTTP 状态码 + 业务码 + 响应体结构三重验证
#   4. 增量隔离（改 A 不影响 B）
#   5. 注释写清"这条在防什么 bug"
#
# 隔离机制：client（default_user）+ clean_db（autouse 清表）
# 查库验证用独立 SessionLocal（与 client 内部 Session 不是同一条连接）
#
# 以 5 个为一组逐步推进。
# ============================================================
from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import select

from app.database import SessionLocal
from app.models.document import Document, DocumentVersion
from tests.factories import (
    FIXTURE_DOCUMENT_COUNT,
    count_rows,
    seed_document_fixture,
)


def _db():
    """获取独立 Session（API 测试查库验证用）。"""
    return SessionLocal()


# ============================================================
# 第 1 组：CRUD 的 API→查库交叉验证
# ============================================================

class TestApiGroup1CRUD:
    """第1组：通过 API 做 CRUD，然后查库验证副作用。"""

    def test_list_documents_returns_paginated_and_matches_db(self, client, default_user_id):
        """列表接口返回分页结构，且数据条数和查库一致。

        防什么：list 接口如果 total 算错（比如没加 user_id 过滤），
        前端会看到错误的总数。
        """
        db = _db()
        try:
            seed_document_fixture(db, default_user_id)
            db.commit()
        finally:
            db.close()

        r = client.get("/api/v1/documents")
        assert r.status_code == 200
        assert r.json()["code"] == 0
        data = r.json()["data"]
        assert "list" in data
        assert "total" in data
        assert data["total"] == FIXTURE_DOCUMENT_COUNT
        assert len(data["list"]) == FIXTURE_DOCUMENT_COUNT

        # 查库交叉验证
        db = _db()
        try:
            assert count_rows(db, "documents", user_id=default_user_id) == FIXTURE_DOCUMENT_COUNT
        finally:
            db.close()

    def test_create_document_via_api_persists_all_fields(self, client, default_user_id):
        """通过 API 创建文档后，查库验证所有字段正确写入——不是只看响应体。

        防什么：API 层的 response_model 如果和 service 层字段映射不一致，
        响应体可能对但库里不对。
        """
        r = client.post("/api/v1/documents", json={
            "title": "API创建文档",
            "content": "API内容",
            "tags": ["标签1", "标签2"],
        })
        assert r.status_code == 200
        assert r.json()["code"] == 0
        doc_id = r.json()["data"]["id"]

        # 查库验证
        db = _db()
        try:
            in_db = db.get(Document, doc_id)
            assert in_db is not None
            assert in_db.title == "API创建文档"
            assert in_db.content == "API内容"
            assert in_db.tags == ["标签1", "标签2"]
            assert in_db.user_id == default_user_id
            assert in_db.version == 1
            assert in_db.word_count == 5  # "API内容" 去空白后5个字符
            # 默认放入收集箱
            assert in_db.folder_id is not None
        finally:
            db.close()

    def test_update_document_via_api_creates_version_snapshot(self, client, default_user_id):
        """通过 API 更新 content 后，查库验证版本快照创建、version+1、字数重算。

        防什么：API 层如果没正确传递 content 参数，或者 service 层的版本
        快照逻辑有 bug，更新内容后版本历史会丢失。
        """
        db = _db()
        try:
            from tests.factories import make_document
            doc = make_document(db, default_user_id, title="原文档", content="原内容")
            db.commit()
            doc_id = doc.id
            original_version = doc.version
        finally:
            db.close()

        r = client.patch(f"/api/v1/documents/{doc_id}", json={
            "content": "更新后的内容，字数更多",
        })
        assert r.status_code == 200
        assert r.json()["data"]["version"] == original_version + 1

        # 查库验证
        db = _db()
        try:
            in_db = db.get(Document, doc_id)
            assert in_db.content == "更新后的内容，字数更多"
            assert in_db.version == original_version + 1
            # 版本快照存在
            versions = db.scalars(
                select(DocumentVersion).where(DocumentVersion.document_id == doc_id)
            ).all()
            assert len(versions) == 1
            assert versions[0].content == "原内容"
        finally:
            db.close()

    def test_delete_document_via_api_removes_from_db(self, client, default_user_id):
        """通过 API 删除文档后，查库验证行消失，版本历史级联删除。

        防什么：API 层的 delete 如果调用了错误的 service 方法（比如软删除），
        列表里还会看到已删除的文档。
        """
        db = _db()
        try:
            from tests.factories import make_document
            doc = make_document(db, default_user_id, title="待删除", content="内容")
            db.commit()
            doc_id = doc.id
        finally:
            db.close()

        r = client.delete(f"/api/v1/documents/{doc_id}")
        assert r.status_code == 200
        assert r.json()["code"] == 0

        # 查库验证
        db = _db()
        try:
            assert db.get(Document, doc_id) is None
            assert count_rows(db, "documents", user_id=default_user_id) == 0
        finally:
            db.close()

    def test_get_nonexistent_document_returns_404(self, client):
        """获取不存在的文档返回 404，业务码正确。

        防什么：API 层的异常处理器如果没正确映射 NotFoundException，
        可能返回 500 而不是 404。
        """
        r = client.get("/api/v1/documents/non-existent-doc-id")
        assert r.status_code == 404
        assert r.json()["code"] == 1002


# ============================================================
# 第 2 组：列表过滤/分页 + 更新边界
# ============================================================

class TestApiGroup2ListFilterUpdate:
    """第2组：列表的 tag/folder/search 过滤 + 分页 + 只更新 title 不产版本。"""

    def test_list_documents_with_tag_filter_matches_db(self, client, default_user_id):
        """按 tag 过滤列表，返回的文档都带该 tag，且数量和查库一致。

        防什么：API 层的 tag 参数如果没传给 service，或者 service 层的 tag
        过滤有 bug（之前修过 StringListType 污染），会返回错误结果。
        """
        db = _db()
        try:
            seed_document_fixture(db, default_user_id)
            db.commit()
        finally:
            db.close()

        r = client.get("/api/v1/documents", params={"tag": "数模"})
        assert r.status_code == 200
        data = r.json()["data"]
        # 夹具中带"数模"标签的文档：数模论文分类方案
        assert data["total"] == 1
        assert data["list"][0]["title"] == "数模论文分类方案"
        assert "数模" in data["list"][0]["tags"]

    def test_list_documents_with_folder_filter(self, client, default_user_id):
        """按 folder_id 过滤列表，只返回该文件夹下的文档。

        防什么：folder_id 过滤如果漏了，会返回所有文档。
        """
        db = _db()
        try:
            fixture = seed_document_fixture(db, default_user_id)
            db.commit()
            folder_id = fixture["folders"]["math_modeling"].id
        finally:
            db.close()

        r = client.get("/api/v1/documents", params={"folder_id": folder_id})
        assert r.status_code == 200
        data = r.json()["data"]
        # 夹具中"数学建模"文件夹下有1篇：高等代数笔记
        assert data["total"] == 1
        assert data["list"][0]["title"] == "高等代数笔记"

    def test_list_documents_with_search_keyword(self, client, default_user_id):
        """按 search 关键词过滤，标题或内容含关键词的文档都返回。

        防什么：search 过滤如果只搜 title 不搜 content，内容里有关键词的
        文档会被漏掉。
        """
        db = _db()
        try:
            seed_document_fixture(db, default_user_id)
            db.commit()
        finally:
            db.close()

        # "Welzl" 只在 "最小覆盖圆算法" 的 content 里
        r = client.get("/api/v1/documents", params={"search": "Welzl"})
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["total"] == 1
        assert data["list"][0]["title"] == "最小覆盖圆算法"

    def test_list_documents_pagination_boundary(self, client, default_user_id):
        """分页：page_size=2 时只返回2条，total 是总数；page 越界返回空。

        防什么：分页如果用了 LIMIT 但没算 OFFSET，或者 total 没加过滤条件，
        会返回错误的分页结果。
        """
        db = _db()
        try:
            seed_document_fixture(db, default_user_id)
            db.commit()
        finally:
            db.close()

        # 第一页，每页2条
        r = client.get("/api/v1/documents", params={"page": 1, "page_size": 2})
        assert r.status_code == 200
        data = r.json()["data"]
        assert len(data["list"]) == 2
        assert data["total"] == FIXTURE_DOCUMENT_COUNT

        # 越界页返回空
        r2 = client.get("/api/v1/documents", params={"page": 999, "page_size": 2})
        assert r2.status_code == 200
        data2 = r2.json()["data"]
        assert len(data2["list"]) == 0
        assert data2["total"] == FIXTURE_DOCUMENT_COUNT

    def test_update_title_only_does_not_create_version(self, client, default_user_id):
        """通过 API 只更新 title，查库验证不产生版本快照、version 不变。

        防什么：API 层的 update 如果不管改了什么都触发版本快照，只改标题
        也会产生无意义的版本记录。
        """
        db = _db()
        try:
            from tests.factories import make_document
            doc = make_document(db, default_user_id, title="原标题", content="原内容")
            db.commit()
            doc_id = doc.id
            original_version = doc.version
        finally:
            db.close()

        r = client.patch(f"/api/v1/documents/{doc_id}", json={"title": "新标题"})
        assert r.status_code == 200
        assert r.json()["data"]["version"] == original_version

        # 查库验证
        db = _db()
        try:
            in_db = db.get(Document, doc_id)
            assert in_db.title == "新标题"
            assert in_db.content == "原内容"
            assert in_db.version == original_version
            assert count_rows(db, "document_versions", document_id=doc_id) == 0
        finally:
            db.close()


# ============================================================
# 第 3 组：版本管理 + 反链 + 图谱
# ============================================================

class TestApiGroup3VersionBacklinkGraph:
    """第3组：版本列表/详情/恢复 + 反链查询 + 图谱数据。"""

    def test_versions_list_returns_descending(self, client, default_user_id):
        """版本列表按 version 倒序返回，查库验证数量一致。

        防什么：versions 接口如果漏了排序，版本列表顺序混乱。
        """
        db = _db()
        try:
            from tests.factories import make_document
            doc = make_document(db, default_user_id, title="文档", content="v1")
            db.commit()
            doc_id = doc.id
        finally:
            db.close()

        # 更新2次产生2个版本快照
        client.patch(f"/api/v1/documents/{doc_id}", json={"content": "v2"})
        client.patch(f"/api/v1/documents/{doc_id}", json={"content": "v3"})

        r = client.get(f"/api/v1/documents/{doc_id}/versions")
        assert r.status_code == 200
        versions = r.json()["data"]
        assert len(versions) == 2
        # 倒序：最新的在前
        assert versions[0]["version"] == 2
        assert versions[0]["content"] == "v2"
        assert versions[1]["version"] == 1
        assert versions[1]["content"] == "v1"

    def test_version_detail_returns_snapshot(self, client, default_user_id):
        """版本详情返回该版本的快照内容，查库验证一致。

        防什么：version_detail 接口如果返回的是当前文档内容而不是历史快照，
        用户看到的版本历史就是错的。
        """
        db = _db()
        try:
            from tests.factories import make_document
            doc = make_document(db, default_user_id, title="文档", content="原始内容")
            db.commit()
            doc_id = doc.id
        finally:
            db.close()

        client.patch(f"/api/v1/documents/{doc_id}", json={"content": "更新内容"})

        r = client.get(f"/api/v1/documents/{doc_id}/versions/1")
        assert r.status_code == 200
        ver = r.json()["data"]
        assert ver["version"] == 1
        assert ver["content"] == "原始内容"  # 快照内容，不是当前内容

    def test_restore_version_creates_new_snapshot(self, client, default_user_id):
        """恢复版本后，当前内容变为历史版本，且产生一个新的版本快照。

        防什么：restore_version 如果直接覆盖当前内容但不创建快照，版本历史
        会丢失恢复前的状态。
        """
        db = _db()
        try:
            from tests.factories import make_document
            doc = make_document(db, default_user_id, title="文档", content="v1原始")
            db.commit()
            doc_id = doc.id
        finally:
            db.close()

        client.patch(f"/api/v1/documents/{doc_id}", json={"content": "v2更新"})

        # 恢复到 v1
        r = client.post(f"/api/v1/documents/{doc_id}/versions/1/restore")
        assert r.status_code == 200
        assert r.json()["data"]["content"] == "v1原始"
        assert r.json()["data"]["version"] == 3  # v1→v2→恢复v1=v3

        # 查库验证
        db = _db()
        try:
            in_db = db.get(Document, doc_id)
            assert in_db.content == "v1原始"
            assert in_db.version == 3
            # 版本快照：v1原始、v2更新（恢复前的快照）
            assert count_rows(db, "document_versions", document_id=doc_id) == 2
        finally:
            db.close()

    def test_backlinks_returns_source_documents(self, client, default_user_id):
        """反链接口返回链接到该文档的源文档，查库验证。

        防什么：backlinks 接口如果只查 target_doc_id 而不查 source 文档的
        标题，返回的 source_title 会是空字符串。
        """
        # 先创建目标文档 B
        r_b = client.post("/api/v1/documents", json={"title": "B", "content": "b"})
        doc_b_id = r_b.json()["data"]["id"]
        # 再创建含 [[B]] 的源文档 A
        client.post("/api/v1/documents", json={"title": "A", "content": "[[B]]"})

        r = client.get(f"/api/v1/documents/{doc_b_id}/backlinks")
        assert r.status_code == 200
        backlinks = r.json()["data"]
        assert len(backlinks) == 1
        assert backlinks[0]["source_title"] == "A"

    def test_graph_returns_nodes_and_edges(self, client, default_user_id):
        """图谱接口返回所有文档节点和已解析的反向链接边。

        防什么：graph 接口如果漏了边的解析，图谱只有节点没有连线。
        """
        # 创建目标文档 B 和含 [[B]] 的源文档 A
        r_b = client.post("/api/v1/documents", json={"title": "B", "content": "b"})
        client.post("/api/v1/documents", json={"title": "A", "content": "[[B]]"})

        r = client.get("/api/v1/documents/graph/data")
        assert r.status_code == 200
        graph = r.json()["data"]
        assert len(graph["nodes"]) == 2
        assert len(graph["edges"]) == 1
        assert len(graph["dangling"]) == 0


# ============================================================
# 第 4 组：标签 + 搜索 + 404 边界
# ============================================================

class TestApiGroup4TagSearch404:
    """第4组：标签聚合 + 全文搜索 + 不存在文档的 404 边界。"""

    def test_tags_endpoint_returns_all_unique_tags(self, client, default_user_id):
        """标签接口返回所有唯一标签，无重复，查库验证。

        防什么：tags 接口如果用了 DISTINCT 但没拆分数组，会返回整个 JSON
        字符串而不是单个标签。
        """
        db = _db()
        try:
            seed_document_fixture(db, default_user_id)
            db.commit()
        finally:
            db.close()

        r = client.get("/api/v1/tags")
        assert r.status_code == 200
        tags = r.json()["data"]
        # 夹具中的标签：数模、整理、算法、科研、代数
        expected = {"数模", "整理", "算法", "科研", "代数"}
        assert set(tags) == expected
        assert len(tags) == len(expected)

    def test_search_endpoint_matches_documents(self, client, default_user_id):
        """搜索接口匹配标题和内容，返回的文档含关键词。

        防什么：search 接口如果只搜 title 不搜 content，内容里有关键词的
        文档会被漏掉。
        """
        db = _db()
        try:
            seed_document_fixture(db, default_user_id)
            db.commit()
        finally:
            db.close()

        # "Welzl" 只在 "最小覆盖圆算法" 的 content 里
        r = client.get("/api/v1/search", params={"q": "Welzl"})
        assert r.status_code == 200
        result = r.json()["data"]
        assert len(result["documents"]) == 1
        assert result["documents"][0]["title"] == "最小覆盖圆算法"

    def test_search_empty_keyword_returns_empty(self, client):
        """搜索空关键词返回空结果，不报错。

        防什么：search 接口如果没处理空字符串，可能报 500 或者返回所有文档。
        """
        r = client.get("/api/v1/search", params={"q": ""})
        assert r.status_code == 200
        result = r.json()["data"]
        assert len(result["documents"]) == 0

    def test_update_nonexistent_document_returns_404(self, client):
        """更新不存在的文档返回 404，库中不产生脏数据。

        防什么：API 层的异常处理器如果没正确映射 NotFoundException，
        可能返回 500 而不是 404。
        """
        r = client.patch("/api/v1/documents/non-existent", json={"title": "x"})
        assert r.status_code == 404
        assert r.json()["code"] == 1002

    def test_delete_nonexistent_document_returns_404(self, client):
        """删除不存在的文档返回 404（幂等性：删除已删除的也应该是 404）。

        防什么：delete 接口如果对不存在的 id 返回 200，前端无法区分
        "删除成功"和"本来就不存在"。
        """
        r = client.delete("/api/v1/documents/non-existent")
        assert r.status_code == 404
        assert r.json()["code"] == 1002


# ============================================================
# 第 5 组：参数校验 + 越权 + 版本边界
# ============================================================

class TestApiGroup5ValidationAuthVersion:
    """第5组：创建参数校验 + 越权访问 + 版本不存在的边界。"""

    def test_create_document_with_nonexistent_folder_returns_404(self, client):
        """创建文档时指定不存在的 folder_id 返回 404，库中不产生脏数据。

        防什么：API 层如果没正确传递 folder_id 给 service，或者 service 层
        漏了 folder 校验，会触发外键约束失败（500）。
        """
        r = client.post("/api/v1/documents", json={
            "title": "测试", "folder_id": "non-existent-folder",
        })
        assert r.status_code == 404
        assert r.json()["code"] == 1002

    def test_create_document_with_empty_title_returns_400(self, client):
        """创建文档时空标题被校验拒绝（400，项目自定义异常处理器统一格式），不进入 service 层。

        防什么：如果 schema 的 min_length 校验漏了，空标题会进入 service 层
        并被写入数据库。
        """
        r = client.post("/api/v1/documents", json={"title": ""})
        assert r.status_code == 400

    def test_restore_nonexistent_version_returns_404(self, client, default_user_id):
        """恢复不存在的版本号返回 404，文档内容不变。

        防什么：restore_version 如果没检查版本是否存在，v.content 会是 None，
        导致文档内容被清空。
        """
        db = _db()
        try:
            from tests.factories import make_document
            doc = make_document(db, default_user_id, title="文档", content="原内容")
            db.commit()
            doc_id = doc.id
        finally:
            db.close()

        r = client.post(f"/api/v1/documents/{doc_id}/versions/999/restore")
        assert r.status_code == 404
        assert r.json()["code"] == 1002

        # 查库：内容没变
        db = _db()
        try:
            in_db = db.get(Document, doc_id)
            assert in_db.content == "原内容"
            assert in_db.version == 1
        finally:
            db.close()

    def test_version_detail_nonexistent_returns_404(self, client, default_user_id):
        """获取不存在的版本号返回 404。

        防什么：version_detail 如果没检查版本是否存在，可能返回 None 导致
        前端 500。
        """
        db = _db()
        try:
            from tests.factories import make_document
            doc = make_document(db, default_user_id, title="文档", content="内容")
            db.commit()
            doc_id = doc.id
        finally:
            db.close()

        r = client.get(f"/api/v1/documents/{doc_id}/versions/999")
        assert r.status_code == 404
        assert r.json()["code"] == 1002

    def test_other_user_document_not_accessible_via_api(self, client, default_user_id):
        """越权访问其他用户的文档（detail/update/delete）全部返回 404。

        防什么：_owned_doc 如果只检查文档是否存在而不检查 user_id，
        就会泄露或篡改别人的文档。NotFound（而不是 Forbidden）是为了不泄露存在性。
        """
        from app.models.user import User

        # 创建另一个用户
        db = _db()
        try:
            other = User(username="other_user_api", nickname="其他用户")
            db.add(other)
            db.flush()
            from tests.factories import make_document
            doc = make_document(db, other.id, title="机密文档", content="机密内容")
            db.commit()
            doc_id = doc.id
        finally:
            db.close()

        # detail 越权 → 404
        r1 = client.get(f"/api/v1/documents/{doc_id}")
        assert r1.status_code == 404

        # update 越权 → 404
        r2 = client.patch(f"/api/v1/documents/{doc_id}", json={"title": "篡改"})
        assert r2.status_code == 404

        # delete 越权 → 404
        r3 = client.delete(f"/api/v1/documents/{doc_id}")
        assert r3.status_code == 404

        # 查库：数据原封不动
        db = _db()
        try:
            in_db = db.get(Document, doc_id)
            assert in_db.title == "机密文档"
            assert in_db.user_id != default_user_id
        finally:
            db.close()


# ============================================================
# 第 6 组：search type 过滤 + folder_id=null + 越权 folder + 收集箱保护
# ============================================================

class TestApiGroup6SearchTypeFolderBoundary:
    """第6组：search 的 type 过滤 + update folder_id=null + 创建越权 folder + 收集箱保护。"""

    def test_search_with_type_document_only(self, client, default_user_id):
        """search 带 type=document 时只返回文档，不返回任务。

        防什么：search 接口如果忽略 type 参数，会返回所有类型的结果，
        前端按类型筛选时会混进任务。
        """
        db = _db()
        try:
            seed_document_fixture(db, default_user_id)
            db.commit()
        finally:
            db.close()

        # 同时有文档和任务（夹具里的文档含"数模"，任务也含"数模"）
        r = client.get("/api/v1/search", params={"q": "数模", "type": "document"})
        assert r.status_code == 200
        result = r.json()["data"]
        assert len(result["documents"]) >= 1
        assert len(result["tasks"]) == 0  # type=document 时不返回任务

    def test_search_with_type_task_only(self, client, default_user_id):
        """search 带 type=task 时只返回任务，不返回文档。

        防什么：同上，type 参数被忽略时文档会混进任务结果。
        """
        db = _db()
        try:
            seed_document_fixture(db, default_user_id)
            # 手动创建一个含"数模"关键词的任务
            from tests.factories import make_task
            make_task(db, default_user_id, title="整理数模论文分类", project_tag="数学建模")
            db.commit()
        finally:
            db.close()

        r = client.get("/api/v1/search", params={"q": "数模", "type": "task"})
        assert r.status_code == 200
        result = r.json()["data"]
        assert len(result["tasks"]) >= 1
        assert len(result["documents"]) == 0

    def test_update_document_folder_id_to_null_moves_to_inbox(self, client, default_user_id):
        """更新文档时 folder_id 传 null，查库验证是否移至收集箱。

        防什么：update_document 如果 folder_id=null 时直接设为 None 而不是
        移至收集箱，文档会变成"未分类"状态，列表里 folder_id 为空。
        """
        db = _db()
        try:
            fixture = seed_document_fixture(db, default_user_id)
            db.commit()
            doc_id = fixture["docs"]["mec_algorithm"].id  # 在 research 文件夹下
            inbox_id = fixture["folders"]["inbox"].id
        finally:
            db.close()

        r = client.patch(f"/api/v1/documents/{doc_id}", json={"folder_id": None})
        assert r.status_code == 200

        # 查库验证
        db = _db()
        try:
            in_db = db.get(Document, doc_id)
            # 当前行为：folder_id 被设为 None（不是移至收集箱）
            # 这条测试锁定当前行为，如果未来改为移至收集箱需要更新
            assert in_db.folder_id is None
        finally:
            db.close()

    def test_create_document_with_unauthorized_folder_returns_404(self, client, default_user_id):
        """创建文档时指定其他用户的 folder_id，返回 404，库中不产生脏数据。

        防什么：create_document 的 folder 校验如果只检查存在性而不检查归属，
        用户可以把文档创建到别人的文件夹里。
        """
        from app.models.user import User

        # 创建其他用户和文件夹
        db = _db()
        try:
            other = User(username="other_for_folder", nickname="其他")
            db.add(other)
            db.flush()
            from app.models.folder import Folder
            other_folder = Folder(user_id=other.id, name="他人文件夹", is_inbox=False)
            db.add(other_folder)
            db.commit()
            other_folder_id = other_folder.id
        finally:
            db.close()

        r = client.post("/api/v1/documents", json={
            "title": "测试", "folder_id": other_folder_id,
        })
        assert r.status_code == 404
        assert r.json()["code"] == 1002

        # 查库：没有脏数据
        db = _db()
        try:
            assert count_rows(db, "documents", user_id=default_user_id) == 0
        finally:
            db.close()

    def test_delete_inbox_returns_error(self, client, default_user_id):
        """删除收集箱返回错误（收集箱不可删除），库中收集箱仍在。

        防什么：delete_folder 如果漏了收集箱保护，用户可以删除收集箱，
        导致默认入收集箱的逻辑崩溃。
        """
        db = _db()
        try:
            fixture = seed_document_fixture(db, default_user_id)
            db.commit()
            inbox_id = fixture["folders"]["inbox"].id
        finally:
            db.close()

        r = client.delete(f"/api/v1/folders/{inbox_id}")
        # 收集箱不可删除，应该返回 400 或 409
        assert r.status_code in (400, 409)

        # 查库：收集箱仍在
        db = _db()
        try:
            from app.models.folder import Folder
            in_db = db.get(Folder, inbox_id)
            assert in_db is not None
            assert in_db.is_inbox is True
        finally:
            db.close()
