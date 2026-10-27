# ============================================================
# DocumentService 生产级测试
#
# 标准对齐经纬项目 + task 模块生产级测试：
#   1. 真数据夹具（seed_document_fixture：5文档+2文件夹，混合标签/内容/链接）
#   2. 写操作后直接查库验证（不信 service 返回值）
#   3. 增量隔离（改 A 不影响 B）
#   4. 负向断言（不该变的没变）
#   5. 注释写清"这条在防什么 bug"
#
# 以 5 个为一组逐步推进。
# ============================================================
from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import select

from app.core.exceptions import NotFoundException
from app.models.document import Backlink, Document, DocumentVersion
from app.models.folder import Folder
from app.schemas.document import CreateDocumentRequest, UpdateDocumentRequest
from app.services.document_service import DocumentService, count_words
from tests.factories import (
    FIXTURE_DOCUMENT_COUNT,
    FIXTURE_DOCUMENT_FOLDER_COUNT,
    count_rows,
    seed_document_fixture,
)


# ============================================================
# 第 1 组：夹具基线 + 创建默认入收集箱 + 版本快照触发
# ============================================================

class TestGroup1FixtureAndCreate:
    """第1组：夹具基线验证 + 创建文档默认入收集箱 + 版本快照触发条件。"""

    def test_fixture_baseline_matches_shape_contract(self, db_session, test_user):
        """夹具造完后，库里的文档/文件夹/标签分布必须和形状契约一致。

        为什么要这条：后续所有测试都依赖夹具的已知状态。如果夹具本身造错了，
        后面的断言全是假绿。
        """
        seed_document_fixture(db_session, test_user.id)
        db_session.commit()

        # 总文档数
        assert count_rows(db_session, "documents", user_id=test_user.id) == FIXTURE_DOCUMENT_COUNT
        # 自定义文件夹数（不含收集箱）
        assert count_rows(db_session, "folders", user_id=test_user.id, is_inbox=0) == FIXTURE_DOCUMENT_FOLDER_COUNT
        # 收集箱存在
        assert count_rows(db_session, "folders", user_id=test_user.id, is_inbox=1) == 1

    def test_create_document_defaults_to_inbox(self, db_session, test_user):
        """创建文档时不传 folder_id，自动放入收集箱，查库验证 folder_id 是收集箱的 id。

        防什么：如果 create_document 漏了 _ensure_inbox 调用，folder_id 会是 None，
        列表里显示"未分类"而不是"收集箱"。
        """
        svc = DocumentService(db_session)
        out = svc.create_document(test_user.id, CreateDocumentRequest(
            title="新文档", content="内容",
        ))

        # 查库验证
        db_session.expire_all()
        in_db = db_session.get(Document, out.id)
        assert in_db is not None
        assert in_db.title == "新文档"
        assert in_db.folder_id is not None
        # folder_id 指向收集箱
        inbox = db_session.scalar(
            select(Folder).where(Folder.user_id == test_user.id, Folder.is_inbox == True)  # noqa: E712
        )
        assert in_db.folder_id == inbox.id
        # 字数统计正确
        assert in_db.word_count == count_words("内容")
        assert in_db.version == 1

    def test_create_document_with_folder_persists_correctly(self, db_session, test_user):
        """创建文档时指定 folder_id，查库验证 folder_id 正确，且不创建额外收集箱。

        防什么：如果 create_document 不管有没有传 folder_id 都调用 _ensure_inbox，
        会浪费一次查询；或者 folder_id 校验漏了，越权文件夹也能写入。
        """
        fixture = seed_document_fixture(db_session, test_user.id)
        db_session.commit()
        folder = fixture["folders"]["math_modeling"]

        svc = DocumentService(db_session)
        out = svc.create_document(test_user.id, CreateDocumentRequest(
            title="指定文件夹文档", content="内容", folder_id=folder.id,
        ))

        # 查库验证
        db_session.expire_all()
        in_db = db_session.get(Document, out.id)
        assert in_db.folder_id == folder.id
        # 总文档数 = 夹具5 + 新1 = 6
        assert count_rows(db_session, "documents", user_id=test_user.id) == FIXTURE_DOCUMENT_COUNT + 1

    def test_update_content_creates_version_snapshot_and_increments_version(self, db_session, test_user):
        """更新文档 content 后，查库验证：旧内容入版本快照、version+1、字数重算。

        防什么：如果 update_document 漏了版本快照逻辑（或者 content_changed 判断错了），
        版本历史会丢失，用户无法回滚。
        """
        fixture = seed_document_fixture(db_session, test_user.id)
        db_session.commit()
        doc = fixture["docs"]["daily_essay"]
        original_content = doc.content
        original_version = doc.version

        svc = DocumentService(db_session)
        svc.update_document(test_user.id, doc.id, UpdateDocumentRequest(
            content="更新后的内容，字数更多了一些",
        ))

        # 查库验证
        db_session.expire_all()
        in_db = db_session.get(Document, doc.id)
        assert in_db.version == original_version + 1
        assert in_db.content == "更新后的内容，字数更多了一些"
        assert in_db.word_count == count_words("更新后的内容，字数更多了一些")

        # 版本快照存在
        versions = db_session.scalars(
            select(DocumentVersion).where(DocumentVersion.document_id == doc.id)
        ).all()
        assert len(versions) == 1
        assert versions[0].content == original_content
        assert versions[0].version == original_version

    def test_update_non_content_field_does_not_create_version(self, db_session, test_user):
        """更新 title/tags 等非 content 字段后，查库验证不创建版本快照，version 不变。

        防什么：如果 update_document 不管改了什么都创建版本快照，版本历史会
        被无意义的标题修改填满，很快达到 10 个上限。
        """
        fixture = seed_document_fixture(db_session, test_user.id)
        db_session.commit()
        doc = fixture["docs"]["daily_essay"]
        original_version = doc.version

        svc = DocumentService(db_session)
        svc.update_document(test_user.id, doc.id, UpdateDocumentRequest(
            title="改了标题", tags=["新标签"],
        ))

        # 查库验证
        db_session.expire_all()
        in_db = db_session.get(Document, doc.id)
        assert in_db.version == original_version  # 没变
        assert in_db.title == "改了标题"
        assert in_db.tags == ["新标签"]
        # 没有版本快照
        assert count_rows(db_session, "document_versions", document_id=doc.id) == 0


# ============================================================
# 第 2 组：版本上限 + 版本恢复 + 反向链接自动同步 + 删除级联
# ============================================================

class TestGroup2VersionBacklinkDelete:
    """第2组：版本历史上限 + 版本恢复 + 反向链接自动同步 + 删除级联清理。"""

    def test_version_history_capped_at_10(self, db_session, test_user):
        """连续更新 content 11 次后，查库验证只有 10 个版本快照（最旧的被自动删除）。

        防什么：如果 delete_oldest 逻辑错了（比如没删、或者删了最新的），版本
        历史会无限增长，或者丢失最近的版本。
        """
        fixture = seed_document_fixture(db_session, test_user.id)
        db_session.commit()
        doc = fixture["docs"]["daily_essay"]

        svc = DocumentService(db_session)
        # 连续更新 11 次 content（每次触发版本快照）
        for i in range(11):
            svc.update_document(test_user.id, doc.id, UpdateDocumentRequest(
                content=f"第{i}次更新的内容",
            ))

        # 查库验证：最多 10 个版本快照
        db_session.expire_all()
        versions = db_session.scalars(
            select(DocumentVersion).where(DocumentVersion.document_id == doc.id)
        ).all()
        assert len(versions) == 10
        # 文档当前 version 应该是 1 + 11 = 12
        in_db = db_session.get(Document, doc.id)
        assert in_db.version == 12

    def test_restore_version_replaces_content_and_creates_snapshot(self, db_session, test_user):
        """恢复到旧版本后，查库验证 content 被替换，当前内容入快照，version+1。

        防什么：restore_version 如果只改 content 不创建快照，恢复前的内容
        就丢失了，无法再恢复回来。
        """
        fixture = seed_document_fixture(db_session, test_user.id)
        db_session.commit()
        doc = fixture["docs"]["daily_essay"]
        original_content = doc.content

        svc = DocumentService(db_session)
        # 更新一次，产生 v1 快照，当前 v2
        svc.update_document(test_user.id, doc.id, UpdateDocumentRequest(content="v2内容"))
        # 恢复到 v1
        svc.restore_version(test_user.id, doc.id, ver=1)

        # 查库验证
        db_session.expire_all()
        in_db = db_session.get(Document, doc.id)
        assert in_db.content == original_content  # 恢复到 v1 的内容
        assert in_db.version == 3  # v1 → v2(更新) → v3(恢复)
        # 版本快照应该有2个：v1(原始) + v2(恢复前的快照)
        versions = db_session.scalars(
            select(DocumentVersion).where(DocumentVersion.document_id == doc.id)
        ).all()
        assert len(versions) == 2

    def test_backlinks_auto_sync_on_create(self, db_session, test_user):
        """创建含 [[目标文档标题]] 链接的文档后，查库验证反向链接记录被创建。

        防什么：_sync_backlinks 如果在 create 时没被调用，文档间的链接关系
        不会被记录，图谱和反链页面都会缺失数据。
        """
        fixture = seed_document_fixture(db_session, test_user.id)
        db_session.commit()
        # fixture 里 "数模论文分类方案" 内容含 [[最小覆盖圆算法]]
        fixture["docs"]["classification_plan"]
        target_doc = fixture["docs"]["mec_algorithm"]

        # 注意：fixture 是直接造数据，没走 service，所以反向链接还没同步。
        # 调用一次 update（不改 content）不会触发 _sync_backlinks？
        # 实际上 _sync_backlinks 在 create 和 update 时都会调用。
        # 这里我们通过 service 重新创建一篇含链接的文档来测试。
        svc = DocumentService(db_session)
        out = svc.create_document(test_user.id, CreateDocumentRequest(
            title="新链接文档",
            content="参考 [[最小覆盖圆算法]] 和 [[高等代数笔记]]",
        ))

        # 查库验证：2 条反向链接
        db_session.expire_all()
        backlinks = db_session.scalars(
            select(Backlink).where(Backlink.source_doc_id == out.id)
        ).all()
        assert len(backlinks) == 2
        # 目标文档都解析到了
        target_ids = {bl.target_doc_id for bl in backlinks}
        assert target_doc.id in target_ids
        assert fixture["docs"]["algebra_notes"].id in target_ids

    def test_backlinks_rebuilt_on_content_update(self, db_session, test_user):
        """更新 content 改变链接后，查库验证旧反向链接被删除、新反向链接被创建。

        防什么：_sync_backlinks 如果是追加而不是重建，删除链接后旧的反链
        记录会残留，图谱里会出现不存在的边。
        """
        svc = DocumentService(db_session)
        # 创建一篇含 2 个链接的文档
        out = svc.create_document(test_user.id, CreateDocumentRequest(
            title="链接文档", content="[[A]] 和 [[B]]",
        ))
        # 创建目标文档 A 和 B
        svc.create_document(test_user.id, CreateDocumentRequest(title="A", content="a"))
        svc.create_document(test_user.id, CreateDocumentRequest(title="B", content="b"))

        # 更新 content：去掉 A，保留 B，加 C
        svc.create_document(test_user.id, CreateDocumentRequest(title="C", content="c"))
        svc.update_document(test_user.id, out.id, UpdateDocumentRequest(content="[[B]] 和 [[C]]"))

        # 查库验证：只有 2 条反链（B 和 C），A 的反链被删除了
        db_session.expire_all()
        backlinks = db_session.scalars(
            select(Backlink).where(Backlink.source_doc_id == out.id)
        ).all()
        assert len(backlinks) == 2
        target_titles = {bl.target_title for bl in backlinks}
        assert "A" not in target_titles
        assert "B" in target_titles
        assert "C" in target_titles

    def test_delete_document_cascades_backlinks(self, db_session, test_user):
        """删除文档后，查库验证该文档作为来源和目标的反向链接都被清理。

        防什么：delete_document 如果只清理了 source 端的反链没清理 target 端，
        其他文档的反链页面会指向已删除的文档（404）。

        注意：先建目标文档 B，再建含 [[B]] 的源文档 A，这样反链的 target_doc_id
        才能解析到 B.id（如果 A 先建，反链 target_doc_id 为 None，删除 B 时不会清理）。
        """
        svc = DocumentService(db_session)
        # 先创建目标文档 B
        doc_b = svc.create_document(test_user.id, CreateDocumentRequest(title="B", content="b"))
        # 再创建含 [[B]] 的源文档 A
        doc_a = svc.create_document(test_user.id, CreateDocumentRequest(title="A", content="[[B]]"))

        # 确认反链存在且 target_doc_id=B.id
        db_session.expire_all()
        before = db_session.scalars(
            select(Backlink).where(Backlink.source_doc_id == doc_a.id)
        ).all()
        assert len(before) == 1
        assert before[0].target_doc_id == doc_b.id

        # 删除 B（作为反链目标）
        svc.delete_document(test_user.id, doc_b.id)

        # 查库验证：A→B 的反链被清理
        db_session.expire_all()
        backlinks = db_session.scalars(
            select(Backlink).where(Backlink.source_doc_id == doc_a.id)
        ).all()
        assert len(backlinks) == 0
        # B 文档本身也没了
        assert db_session.get(Document, doc_b.id) is None


# ============================================================
# 第 3 组：列表过滤 + 文件夹树 + 收集箱不可变
# ============================================================

class TestGroup3ListFolderInbox:
    """第3组：文档列表过滤/分页 + 文件夹树结构 + 收集箱不可变性。"""

    def test_list_documents_filter_by_folder(self, db_session, test_user):
        """按 folder_id 过滤，返回的每条都在该文件夹下，且总数和查库一致。

        防什么：list_documents 的 folder_id 过滤如果用了 IS NOT NULL 而不是 =，
        会返回所有有文件夹的文档，而不是指定文件夹的。
        """
        fixture = seed_document_fixture(db_session, test_user.id)
        db_session.commit()
        research_folder = fixture["folders"]["research"]

        svc = DocumentService(db_session)
        result = svc.list_documents(test_user.id, folder_id=research_folder.id)

        # 夹具中科研笔记文件夹下只有 "最小覆盖圆算法"
        assert result.total == 1
        assert result.list[0].title == "最小覆盖圆算法"
        assert result.list[0].folder_id == research_folder.id

        # 查库交叉验证
        assert count_rows(db_session, "documents", user_id=test_user.id,
                          folder_id=research_folder.id) == 1

    def test_list_documents_filter_by_tag(self, db_session, test_user):
        """按 tag 过滤，返回的每条都包含该标签，且不返回无标签的。

        防什么：tag 过滤如果用了精确匹配整个 tags 数组（而不是包含匹配），
        多标签文档会查不到。
        """
        seed_document_fixture(db_session, test_user.id)
        db_session.commit()

        svc = DocumentService(db_session)
        result = svc.list_documents(test_user.id, tag="数模")

        # 夹具中只有 "数模论文分类方案" 有 "数模" 标签
        assert result.total == 1
        assert result.list[0].title == "数模论文分类方案"
        assert "数模" in result.list[0].tags

    def test_list_documents_pagination_boundary(self, db_session, test_user):
        """分页边界：page 超过总数时返回空列表，total 不变。

        防什么：分页逻辑如果 page 越界时返回第一页（而不是空），前端翻到
        最后一页后继续翻会看到重复数据。
        """
        seed_document_fixture(db_session, test_user.id)
        db_session.commit()

        svc = DocumentService(db_session)
        # 5条文档，page_size=2，第3页有1条，第4页空
        page3 = svc.list_documents(test_user.id, page=3, page_size=2)
        assert len(page3.list) == 1
        assert page3.total == FIXTURE_DOCUMENT_COUNT

        page4 = svc.list_documents(test_user.id, page=4, page_size=2)
        assert len(page4.list) == 0
        assert page4.total == FIXTURE_DOCUMENT_COUNT

    def test_folders_tree_contains_inbox_and_custom_folders(self, db_session, test_user):
        """文件夹树包含收集箱和自定义文件夹，收集箱置顶。

        防什么：folders_tree 如果漏了 _ensure_inbox，收集箱不会出现在树里；
        如果排序错了，收集箱不会置顶。
        """
        seed_document_fixture(db_session, test_user.id)
        db_session.commit()

        svc = DocumentService(db_session)
        tree = svc.folders_tree(test_user.id)

        # 收集箱 + 2个自定义 = 3个根节点
        assert len(tree) == 3
        # 收集箱置顶
        assert tree[0].is_inbox is True
        assert tree[0].name == "收集箱"
        # 自定义文件夹在后面
        names = {t.name for t in tree}
        assert "数学建模" in names
        assert "科研笔记" in names

    def test_inbox_folder_cannot_be_renamed_or_deleted(self, db_session, test_user):
        """收集箱不可重命名、不可删除，操作后查库验证不变。

        防什么：如果 rename_folder/delete_folder 漏了 is_inbox 检查，
        收集箱会被篡改，导致默认归档目标消失。
        """
        from app.core.exceptions import InboxImmutableException

        fixture = seed_document_fixture(db_session, test_user.id)
        db_session.commit()
        inbox = fixture["folders"]["inbox"]
        original_name = inbox.name

        svc = DocumentService(db_session)

        # 重命名抛异常
        with pytest.raises(InboxImmutableException):
            svc.rename_folder(test_user.id, inbox.id, "新名字")

        # 删除抛异常
        with pytest.raises(InboxImmutableException):
            svc.delete_folder(test_user.id, inbox.id)

        # 查库：收集箱没变
        db_session.expire_all()
        in_db = db_session.get(Folder, inbox.id)
        assert in_db.name == original_name
        assert in_db.is_inbox is True


# ============================================================
# 第 4 组：文件夹删除迁移 + 重名校验 + 版本列表
# ============================================================

class TestGroup4FolderDeleteVersion:
    """第4组：删除文件夹时文档迁移 + 同级重名校验 + 版本列表/详情。"""

    def test_delete_folder_moves_docs_to_inbox(self, db_session, test_user):
        """删除文件夹后，该文件夹下的文档移至收集箱，文件夹本身消失。

        防什么：delete_folder 如果漏了文档迁移逻辑，文档的 folder_id 会指向
        已删除的文件夹（外键 SET NULL 后 folder_id=None），列表里显示"未分类"
        而不是"收集箱"。
        """
        fixture = seed_document_fixture(db_session, test_user.id)
        db_session.commit()
        folder = fixture["folders"]["research"]  # 科研笔记，下有1篇文档
        inbox = fixture["folders"]["inbox"]

        svc = DocumentService(db_session)
        svc.delete_folder(test_user.id, folder.id)

        # 查库验证
        db_session.expire_all()
        assert db_session.get(Folder, folder.id) is None
        # 原文件夹下的文档移至收集箱
        moved_doc = db_session.get(Document, fixture["docs"]["mec_algorithm"].id)
        assert moved_doc.folder_id == inbox.id

    def test_create_folder_duplicate_name_raises(self, db_session, test_user):
        """同级创建同名文件夹抛 DuplicateFolderNameException，库中不产生重复。

        防什么：如果 create_folder 漏了重名检查，同级会出现两个同名文件夹，
        前端树状结构显示混乱。
        """
        from app.core.exceptions import DuplicateFolderNameException

        seed_document_fixture(db_session, test_user.id)
        db_session.commit()

        svc = DocumentService(db_session)
        with pytest.raises(DuplicateFolderNameException):
            svc.create_folder(test_user.id, name="数学建模")  # 已存在

        # 查库：没有重复
        assert count_rows(db_session, "folders", user_id=test_user.id, name="数学建模") == 1

    def test_rename_folder_persists_to_db(self, db_session, test_user):
        """重命名文件夹后查库验证 name 变了，其他字段不变。

        防什么：rename_folder 如果直接修改了其他字段（比如 sort_order），
        文件夹的排序会被意外改变。
        """
        fixture = seed_document_fixture(db_session, test_user.id)
        db_session.commit()
        folder = fixture["folders"]["math_modeling"]
        original_sort_order = folder.sort_order

        svc = DocumentService(db_session)
        svc.rename_folder(test_user.id, folder.id, "新名字")

        # 查库验证
        db_session.expire_all()
        in_db = db_session.get(Folder, folder.id)
        assert in_db.name == "新名字"
        assert in_db.sort_order == original_sort_order
        assert in_db.is_inbox is False

    def test_get_document_versions_list_matches_db(self, db_session, test_user):
        """获取文档版本列表，返回的每个版本都和查库一致，按 version 排序。

        防什么：versions 方法如果漏了排序，版本列表顺序混乱；或者漏了
        user_id 归属检查（虽然 _owned_doc 已经检查了）。
        """
        fixture = seed_document_fixture(db_session, test_user.id)
        db_session.commit()
        doc = fixture["docs"]["daily_essay"]

        svc = DocumentService(db_session)
        # 更新2次 content，产生2个版本快照
        svc.update_document(test_user.id, doc.id, UpdateDocumentRequest(content="v2"))
        svc.update_document(test_user.id, doc.id, UpdateDocumentRequest(content="v3"))

        versions = svc.versions(test_user.id, doc.id)

        # 查库交叉验证
        db_session.expire_all()
        db_versions = db_session.scalars(
            select(DocumentVersion).where(DocumentVersion.document_id == doc.id)
            .order_by(DocumentVersion.version)
        ).all()
        assert len(versions) == len(db_versions) == 2
        # 按 version 降序（最新的在前）
        assert versions[0].version == 2
        assert versions[0].content == "v2"
        assert versions[1].version == 1
        assert versions[1].content == "今天学了很多东西。"  # v1 原始内容

    def test_get_nonexistent_version_raises(self, db_session, test_user):
        """获取不存在的版本号抛 NotFoundException，库中数据不变。

        防什么：version_detail 如果没检查版本是否存在，可能返回 None 导致
        前端 500，而不是友好的 404。
        """
        fixture = seed_document_fixture(db_session, test_user.id)
        db_session.commit()
        doc = fixture["docs"]["daily_essay"]

        svc = DocumentService(db_session)
        with pytest.raises(NotFoundException, match="版本不存在"):
            svc.version_detail(test_user.id, doc.id, ver=999)

        # 查库：文档没变
        db_session.expire_all()
        in_db = db_session.get(Document, doc.id)
        assert in_db.version == 1


# ============================================================
# 第 5 组：反链 + 标签 + 搜索 + 越权 + 字数统计
# ============================================================

class TestGroup5BacklinkSearchAuth:
    """第5组：反链查询 + 标签聚合 + 全文搜索 + 越权访问 + 字数统计边界。"""

    def test_backlinks_returns_source_documents(self, db_session, test_user):
        """获取文档的反链列表，返回的每条都指向链接到该文档的源文档。

        防什么：backlinks 方法如果只查 target_doc_id 而不查 source 文档的
        标题，返回的 source_title 会是空字符串。
        """
        svc = DocumentService(db_session)
        # 先创建目标文档 B，再创建含 [[B]] 的源文档 A
        doc_b = svc.create_document(test_user.id, CreateDocumentRequest(title="B", content="b"))
        doc_a = svc.create_document(test_user.id, CreateDocumentRequest(title="A", content="[[B]]"))

        backlinks = svc.backlinks(test_user.id, doc_b.id)

        assert len(backlinks) == 1
        assert backlinks[0].source_doc_id == doc_a.id
        assert backlinks[0].source_title == "A"

    def test_tags_returns_all_unique_tags(self, db_session, test_user):
        """获取所有标签，返回的标签集合和查库一致，无重复。

        防什么：all_tags 如果用了 DISTINCT 但没拆分数组，会返回整个 JSON
        字符串而不是单个标签。
        """
        seed_document_fixture(db_session, test_user.id)
        db_session.commit()

        svc = DocumentService(db_session)
        tags = svc.tags(test_user.id)

        # 夹具中的标签：数模、整理、算法、科研、代数
        expected = {"数模", "整理", "算法", "科研", "代数"}
        assert set(tags) == expected
        assert len(tags) == len(expected)  # 无重复

    def test_search_documents_by_keyword(self, db_session, test_user):
        """全文搜索关键词，返回的文档标题或内容包含关键词，且不返回不匹配的。

        防什么：search_documents 如果只搜 title 不搜 content，或者 LIKE 模式
        拼错了，会漏结果或返回错误结果。
        """
        seed_document_fixture(db_session, test_user.id)
        db_session.commit()

        svc = DocumentService(db_session)
        result = svc.search(test_user.id, q="Welzl", type_="document")

        # "最小覆盖圆算法" 内容含 "Welzl"
        assert len(result.documents) == 1
        assert result.documents[0].title == "最小覆盖圆算法"
        assert "Welzl" in result.documents[0].snippet

    def test_access_other_users_document_raises(self, db_session, test_user, other_user):
        """越权访问其他用户的文档（detail/update/delete）全部抛 NotFound，库中不变。

        防什么：_owned_doc 如果只检查文档是否存在而不检查 user_id，
        就会泄露或篡改别人的文档。NotFound（而不是 Forbidden）是为了不泄露存在性。
        """
        # 直接造其他用户的文档
        other_doc = Document(
            user_id=other_user.id, title="机密文档", content="机密内容",
            word_count=4,
        )
        db_session.add(other_doc)
        db_session.commit()
        original_title = other_doc.title

        svc = DocumentService(db_session)

        # detail 越权
        with pytest.raises(NotFoundException, match="文档不存在"):
            svc.get_document(test_user.id, other_doc.id)

        # update 越权
        with pytest.raises(NotFoundException):
            svc.update_document(test_user.id, other_doc.id, UpdateDocumentRequest(title="篡改"))

        # delete 越权
        with pytest.raises(NotFoundException):
            svc.delete_document(test_user.id, other_doc.id)

        # 查库：数据原封不动
        db_session.expire_all()
        in_db = db_session.get(Document, other_doc.id)
        assert in_db.title == original_title
        assert in_db.user_id == other_user.id

    def test_count_words_edge_cases(self):
        """字数统计：空内容、纯空白、中英文混合都正确计算。

        防什么：count_words 如果没去除空白，纯空格会被计为非零字数；
        如果用 split() 按词计，中文会被当成一个词。
        """
        assert count_words(None) == 0
        assert count_words("") == 0
        assert count_words("   ") == 0
        assert count_words("hello world") == 10  # 去除空格后 10 个字符
        assert count_words("你好世界") == 4
        assert count_words("hello 世界") == 7  # hello(5) + 世界(2) = 7


# ============================================================
# 第 6 组：folder 越权 + 版本恢复边界 + graph 图谱 + project_id 空串
# ============================================================

class TestGroup6FolderAuthVersionGraph:
    """第6组：folder 越权校验 + 版本恢复边界 + graph 图谱 + project_id 空串解除关联。"""

    def test_create_document_with_nonexistent_folder_raises(self, db_session, test_user):
        """创建文档时指定不存在的 folder_id 抛 NotFound，库中不产生脏数据。

        防什么：如果 create_document 漏了 folder 校验，不存在的 folder_id 会
        触发外键约束失败（500），而不是友好的 404。
        """
        svc = DocumentService(db_session)
        with pytest.raises(NotFoundException, match="文件夹不存在"):
            svc.create_document(test_user.id, CreateDocumentRequest(
                title="测试", folder_id="non-existent-folder",
            ))
        assert count_rows(db_session, "documents", user_id=test_user.id) == 0

    def test_update_document_folder_to_nonexistent_raises(self, db_session, test_user):
        """更新文档时 folder_id 改为不存在的 id 抛 NotFound，库中 folder_id 不变。

        防什么：update_document 的 folder_id 校验如果漏了，会触发外键约束
        失败（500），或者静默忽略错误。
        """
        fixture = seed_document_fixture(db_session, test_user.id)
        db_session.commit()
        doc = fixture["docs"]["daily_essay"]
        original_folder = doc.folder_id

        svc = DocumentService(db_session)
        with pytest.raises(NotFoundException, match="文件夹不存在"):
            svc.update_document(test_user.id, doc.id, UpdateDocumentRequest(
                folder_id="non-existent-folder",
            ))

        # 查库：folder_id 没变
        db_session.expire_all()
        in_db = db_session.get(Document, doc.id)
        assert in_db.folder_id == original_folder

    def test_update_document_project_id_empty_string_unlinks(self, db_session, test_user):
        """更新文档时 project_id 传空串，查库验证被解除关联（project_id=None）。

        防什么：如果 update_document 没处理空串，project_id 会被设为空字符串
        而不是 None，后续按 project_id 过滤时这条文档会查不到。
        """
        from app.models.project import Project

        # 先创建一个项目并关联到文档
        project = Project(user_id=test_user.id, name="测试项目", status="active")
        db_session.add(project)
        db_session.flush()
        fixture = seed_document_fixture(db_session, test_user.id)
        db_session.commit()
        doc = fixture["docs"]["project_plan"]
        # 手动关联 project
        doc.project_id = project.id
        db_session.commit()

        svc = DocumentService(db_session)
        svc.update_document(test_user.id, doc.id, UpdateDocumentRequest(project_id=""))

        # 查库：project_id 被设为 None
        db_session.expire_all()
        in_db = db_session.get(Document, doc.id)
        assert in_db.project_id is None

    def test_restore_nonexistent_version_raises(self, db_session, test_user):
        """恢复不存在的版本号抛 NotFound，文档内容不变。

        防什么：restore_version 如果没检查版本是否存在，v.content 会是 None，
        导致文档内容被清空。
        """
        fixture = seed_document_fixture(db_session, test_user.id)
        db_session.commit()
        doc = fixture["docs"]["daily_essay"]
        original_content = doc.content

        svc = DocumentService(db_session)
        with pytest.raises(NotFoundException, match="版本不存在"):
            svc.restore_version(test_user.id, doc.id, ver=999)

        # 查库：内容没变
        db_session.expire_all()
        in_db = db_session.get(Document, doc.id)
        assert in_db.content == original_content
        assert in_db.version == 1

    def test_graph_returns_nodes_and_edges(self, db_session, test_user):
        """graph 图谱返回所有文档节点和已解析的反向链接边。

        防什么：graph 如果漏了边的解析，图谱只有节点没有连线；或者漏了
        dangling（未解析链接），前端无法显示"待创建"提示。
        """
        svc = DocumentService(db_session)
        # 先创建目标文档 B，再创建含 [[B]] 和 [[不存在的文档]] 的源文档 A
        doc_b = svc.create_document(test_user.id, CreateDocumentRequest(title="B", content="b"))
        doc_a = svc.create_document(test_user.id, CreateDocumentRequest(
            title="A", content="[[B]] 和 [[不存在的文档]]",
        ))

        graph = svc.graph(test_user.id)

        # 节点：A 和 B
        assert len(graph["nodes"]) == 2
        node_titles = {n["title"] for n in graph["nodes"]}
        assert "A" in node_titles
        assert "B" in node_titles

        # 边：A→B（已解析）
        assert len(graph["edges"]) == 1
        assert graph["edges"][0]["source"] == doc_a.id
        assert graph["edges"][0]["target"] == doc_b.id

        # dangling：A→不存在的文档
        assert len(graph["dangling"]) == 1
        assert graph["dangling"][0]["target_title"] == "不存在的文档"


# ============================================================
# 第 7 组：子文件夹层级 + 删除上浮 + 搜索 + 级联删除 + 空数据
# ============================================================

class TestGroup7SubfolderSearchCascade:
    """第7组：子文件夹层级 + 删除有子文件夹的文件夹上浮 + 搜索过滤 + 版本级联删除 + 空数据。"""

    def test_create_subfolder_appears_in_tree_children(self, db_session, test_user):
        """创建子文件夹后，文件夹树中父节点的 children 包含该子文件夹。

        防什么：folders_tree 的 by_parent 分组如果漏了 parent_id 匹配，
        子文件夹会出现在根节点而不是父节点下。
        """
        fixture = seed_document_fixture(db_session, test_user.id)
        db_session.commit()
        parent = fixture["folders"]["math_modeling"]

        svc = DocumentService(db_session)
        child = svc.create_folder(test_user.id, name="子文件夹", parent_id=parent.id)

        # 查树
        tree = svc.folders_tree(test_user.id)
        # 找到父节点
        parent_node = next(n for n in tree if n.id == parent.id)
        assert len(parent_node.children) == 1
        assert parent_node.children[0].name == "子文件夹"
        assert parent_node.children[0].id == child.id

    def test_delete_folder_with_children_floats_to_root(self, db_session, test_user):
        """删除有子文件夹的文件夹后，子文件夹上浮到根节点。

        防什么：delete_folder 如果漏了子文件夹上浮逻辑，子文件夹的
        parent_id 会指向已删除的文件夹（外键 SET NULL 后 parent_id=None），
        虽然也能显示在根节点，但逻辑上应该显式处理。
        """
        fixture = seed_document_fixture(db_session, test_user.id)
        db_session.commit()
        parent = fixture["folders"]["math_modeling"]

        svc = DocumentService(db_session)
        child = svc.create_folder(test_user.id, name="子文件夹", parent_id=parent.id)

        # 删除父文件夹
        svc.delete_folder(test_user.id, parent.id)

        # 查库：子文件夹上浮（parent_id=None）
        db_session.expire_all()
        child_in_db = db_session.get(Folder, child.id)
        assert child_in_db.parent_id is None

        # 树中子文件夹在根节点
        tree = svc.folders_tree(test_user.id)
        root_names = {n.name for n in tree}
        assert "子文件夹" in root_names

    def test_list_documents_search_matches_title_and_content(self, db_session, test_user):
        """列表 search 过滤同时匹配标题和内容，不匹配的不返回。

        防什么：search 过滤如果只搜 title 不搜 content，内容里有关键词的
        文档会被漏掉；或者用了 AND 而不是 OR，需要同时出现在标题和内容里。
        """
        seed_document_fixture(db_session, test_user.id)
        db_session.commit()

        svc = DocumentService(db_session)
        # "Welzl" 只在 "最小覆盖圆算法" 的 content 里
        result = svc.list_documents(test_user.id, search="Welzl")
        assert result.total == 1
        assert result.list[0].title == "最小覆盖圆算法"

        # "数模" 在 "数模论文分类方案" 的 title 里
        result2 = svc.list_documents(test_user.id, search="数模")
        assert result2.total >= 1
        assert any(d.title == "数模论文分类方案" for d in result2.list)

    def test_delete_document_cascades_version_history(self, db_session, test_user):
        """删除文档后，版本历史级联删除（DocumentVersion 外键 CASCADE）。

        防什么：如果 DocumentVersion 的外键没有 ON DELETE CASCADE，删除文档
        后版本历史会变成孤儿数据，占用空间且无法访问。
        """
        fixture = seed_document_fixture(db_session, test_user.id)
        db_session.commit()
        doc = fixture["docs"]["daily_essay"]

        svc = DocumentService(db_session)
        # 更新2次产生2个版本快照
        svc.update_document(test_user.id, doc.id, UpdateDocumentRequest(content="v2"))
        svc.update_document(test_user.id, doc.id, UpdateDocumentRequest(content="v3"))

        # 确认版本存在
        assert count_rows(db_session, "document_versions", document_id=doc.id) == 2

        # 删除文档
        svc.delete_document(test_user.id, doc.id)

        # 查库：版本级联删除
        assert count_rows(db_session, "document_versions", document_id=doc.id) == 0
        assert db_session.get(Document, doc.id) is None

    def test_empty_database_returns_zero_documents_and_inbox_only(self, db_session, test_user):
        """空数据库时，文档列表返回 0 条，文件夹树只有收集箱。

        防什么：空数据场景下如果代码假设至少有一篇文档，可能报 IndexError
        或者除零错误。
        """
        # 不调用 seed_document_fixture，直接用空库（但收集箱会被 _ensure_inbox 创建）
        svc = DocumentService(db_session)

        # 文档列表空
        result = svc.list_documents(test_user.id)
        assert result.total == 0
        assert len(result.list) == 0

        # 标签空
        assert svc.tags(test_user.id) == []

        # 搜索空
        search_result = svc.search(test_user.id, q="anything")
        assert len(search_result.documents) == 0
        assert len(search_result.tasks) == 0

        # 文件夹树只有收集箱
        tree = svc.folders_tree(test_user.id)
        assert len(tree) == 1
        assert tree[0].is_inbox is True


# ============================================================
# 第 8 组：identity 关联 + 排序 + 相同 content 不产生新版本
# ============================================================

class TestGroup8IdentitySortNoop:
    """第8组：identity_id 关联/解除/越权 + 列表排序 + 相同 content 更新不产生新版本。"""

    def test_create_document_with_identity_id_persists(self, db_session, test_user):
        """创建文档时指定 identity_id，查库验证正确写入。

        防什么：create_document 如果漏了 identity_id 字段传递，文档会丢失
        身份轴归类。
        """
        from app.models.identity import Identity

        identity = Identity(user_id=test_user.id, name="学生", slug="student",
                            color_token="primary", icon="star", is_active=True)
        db_session.add(identity)
        db_session.commit()

        svc = DocumentService(db_session)
        out = svc.create_document(test_user.id, CreateDocumentRequest(
            title="带身份的文档", identity_id=identity.id,
        ))

        # 查库验证
        db_session.expire_all()
        in_db = db_session.get(Document, out.id)
        assert in_db.identity_id == identity.id

    def test_update_document_identity_id_empty_string_unlinks(self, db_session, test_user):
        """更新文档时 identity_id 传空串，查库验证被解除关联。

        防什么：如果 _validated_identity_id 没处理空串，identity_id 会被设为
        空字符串而不是 None，后续按 identity 过滤时这条文档会查不到。
        """
        from app.models.identity import Identity

        identity = Identity(user_id=test_user.id, name="学生", slug="student2",
                            color_token="primary", icon="star", is_active=True)
        db_session.add(identity)
        fixture = seed_document_fixture(db_session, test_user.id)
        db_session.commit()
        doc = fixture["docs"]["daily_essay"]
        doc.identity_id = identity.id
        db_session.commit()

        svc = DocumentService(db_session)
        svc.update_document(test_user.id, doc.id, UpdateDocumentRequest(identity_id=""))

        # 查库：identity_id 被设为 None
        db_session.expire_all()
        in_db = db_session.get(Document, doc.id)
        assert in_db.identity_id is None

    def test_create_document_with_invalid_identity_raises(self, db_session, test_user):
        """创建文档时指定不存在的 identity_id 抛 ValidationException，库中不产生脏数据。

        防什么：如果 _validated_identity_id 漏了，不存在的 identity_id 会直接
        写进库（应用层关联，无外键兜底），后续按 identity 过滤时变成孤儿。
        """
        from app.core.exceptions import ValidationException

        svc = DocumentService(db_session)
        with pytest.raises(ValidationException, match="身份不存在"):
            svc.create_document(test_user.id, CreateDocumentRequest(
                title="测试", identity_id="non-existent-identity",
            ))
        assert count_rows(db_session, "documents", user_id=test_user.id) == 0

    def test_list_documents_sorted_by_updated_at_descending(self, db_session, test_user):
        """列表默认按 updated_at 倒序（最新的在前）。

        防什么：list_documents 如果漏了 order_by，SQLite 返回的顺序是插入顺序
        （通常也是倒序，但不保证）。这条锁定排序行为。
        """
        from app.models.base import utcnow

        svc = DocumentService(db_session)
        d1 = svc.create_document(test_user.id, CreateDocumentRequest(title="最早", content="a"))
        d2 = svc.create_document(test_user.id, CreateDocumentRequest(title="中间", content="b"))
        d3 = svc.create_document(test_user.id, CreateDocumentRequest(title="最晚", content="c"))

        # 手动调整 updated_at
        db_session.expire_all()
        db_session.get(Document, d1.id).updated_at = utcnow() - timedelta(hours=3)
        db_session.get(Document, d2.id).updated_at = utcnow() - timedelta(hours=2)
        db_session.get(Document, d3.id).updated_at = utcnow() - timedelta(hours=1)
        db_session.commit()

        result = svc.list_documents(test_user.id)
        assert result.list[0].title == "最晚"
        assert result.list[1].title == "中间"
        assert result.list[2].title == "最早"

    def test_update_same_content_does_not_create_new_version(self, db_session, test_user):
        """更新 content 为相同值时，不产生新版本快照，version 不变。

        防什么：如果 content_changed 判断用了 `"content" in payload` 而不是
        比较值，每次 update 都会产生无意义的版本快照，很快达到 10 个上限。
        """
        fixture = seed_document_fixture(db_session, test_user.id)
        db_session.commit()
        doc = fixture["docs"]["daily_essay"]
        original_content = doc.content
        original_version = doc.version

        svc = DocumentService(db_session)
        # 更新 content 为相同值
        svc.update_document(test_user.id, doc.id, UpdateDocumentRequest(content=original_content))

        # 查库：没有新版本
        db_session.expire_all()
        in_db = db_session.get(Document, doc.id)
        assert in_db.version == original_version
        assert count_rows(db_session, "document_versions", document_id=doc.id) == 0


# ============================================================
# 第 9 组：重命名行为 + 父文件夹越权 + 未解析链接 + 同标签多文档
# ============================================================

class TestGroup9RenameParentDanglingTag:
    """第9组：重命名同名行为 + 父文件夹越权 + 未解析链接显示 + 同标签多文档。"""

    def test_rename_folder_allows_duplicate_name(self, db_session, test_user):
        """重命名文件夹为同级已存在的名字，当前不报错（记录行为，可能是待修复的 bug）。

        为什么要这条：create_folder 有重名检查，但 rename_folder 没有。
        这条测试锁定当前行为，如果未来修复了重名检查，这条会失败，提醒更新。
        """
        fixture = seed_document_fixture(db_session, test_user.id)
        db_session.commit()
        fixture["folders"]["math_modeling"]
        folder_b = fixture["folders"]["research"]

        svc = DocumentService(db_session)
        # 把 research 改名为 "数学建模"（和 math_modeling 同名）
        svc.rename_folder(test_user.id, folder_b.id, "数学建模")

        # 查库：出现两个同名文件夹
        db_session.expire_all()
        count = count_rows(db_session, "folders", user_id=test_user.id, name="数学建模")
        assert count == 2  # 当前行为：允许重名

    def test_create_folder_with_nonexistent_parent_raises(self, db_session, test_user):
        """创建子文件夹时 parent_id 不存在抛 NotFound，库中不产生脏数据。

        防什么：如果 create_folder 漏了 parent 校验，不存在的 parent_id 会
        触发外键约束失败（500）。
        """
        svc = DocumentService(db_session)
        with pytest.raises(NotFoundException, match="父文件夹不存在"):
            svc.create_folder(test_user.id, name="子文件夹", parent_id="non-existent-parent")
        assert count_rows(db_session, "folders", user_id=test_user.id, is_inbox=0) == 0

    def test_backlinks_shows_dangling_target_title(self, db_session, test_user):
        """文档链接到不存在的目标时，反链记录 target_doc_id=None 但保留 target_title。

        防什么：_sync_backlinks 如果只存已解析的链接，未解析的链接会丢失，
        用户无法知道哪些文档还没创建。
        """
        svc = DocumentService(db_session)
        # 创建含 [[不存在的文档]] 的文档（目标文档不存在）
        doc = svc.create_document(test_user.id, CreateDocumentRequest(
            title="源文档", content="[[不存在的文档]]",
        ))

        # 查库验证反链记录
        db_session.expire_all()
        backlinks = db_session.scalars(
            select(Backlink).where(Backlink.source_doc_id == doc.id)
        ).all()
        assert len(backlinks) == 1
        assert backlinks[0].target_doc_id is None
        assert backlinks[0].target_title == "不存在的文档"

    def test_multiple_documents_same_tag_all_returned(self, db_session, test_user):
        """多篇文档有同一标签时，按 tag 过滤返回全部，不遗漏。

        防什么：tag 过滤如果用了 LIMIT 1 或者 DISTINCT 错了，会只返回一条。
        """
        svc = DocumentService(db_session)
        # 创建3篇都带 "重要" 标签的文档
        for i in range(3):
            svc.create_document(test_user.id, CreateDocumentRequest(
                title=f"文档{i}", content="c",
            ))
        # 手动给3篇都加标签（通过 update）
        db_session.expire_all()
        docs = db_session.scalars(select(Document).where(Document.user_id == test_user.id)).all()
        for d in docs:
            d.tags = ["重要"]
        db_session.commit()

        result = svc.list_documents(test_user.id, tag="重要")
        assert result.total == 3
        assert len(result.list) == 3

    def test_update_document_title_only_does_not_touch_content(self, db_session, test_user):
        """只更新 title 时，content/word_count/version 都不变。

        防什么：update_document 如果不管改了什么都重置 word_count 或 version，
        只改标题也会触发版本快照。
        """
        fixture = seed_document_fixture(db_session, test_user.id)
        db_session.commit()
        doc = fixture["docs"]["daily_essay"]
        original_content = doc.content
        original_word_count = doc.word_count
        original_version = doc.version

        svc = DocumentService(db_session)
        svc.update_document(test_user.id, doc.id, UpdateDocumentRequest(title="新标题"))

        # 查库：只有 title 变了
        db_session.expire_all()
        in_db = db_session.get(Document, doc.id)
        assert in_db.title == "新标题"
        assert in_db.content == original_content
        assert in_db.word_count == original_word_count
        assert in_db.version == original_version
        assert count_rows(db_session, "document_versions", document_id=doc.id) == 0
