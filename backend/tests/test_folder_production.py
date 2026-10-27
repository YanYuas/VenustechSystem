# ============================================================
# Folder Service 生产级测试
#
# Folder 的业务逻辑在 DocumentService 里（folders_tree/create_folder/
# rename_folder/delete_folder），但需要系统性覆盖。
#
# 标准对齐经纬项目 + task/document 生产级测试：
#   1. 真数据（混合层级/排序/收集箱）
#   2. 写操作后查库验证
#   3. 增量隔离
#   4. 负向断言
#   5. 注释写清"防什么bug"
#
# 以 5 个为一组逐步推进。
# ============================================================
from __future__ import annotations

import pytest

from app.core.exceptions import DuplicateFolderNameException, InboxImmutableException, NotFoundException
from app.models.folder import Folder
from app.services.document_service import DocumentService
from tests.factories import count_rows


# ============================================================
# 第 1 组：创建 + 收集箱自动创建 + 重名 + parent 校验
# ============================================================

class TestGroup1CreateInboxDuplicate:
    """第1组：空库自动建收集箱 + 创建文件夹 + 重名检查 + parent 校验。"""

    def test_empty_db_creates_inbox_on_first_access(self, db_session, test_user):
        """空数据库首次调用 folders_tree 自动创建收集箱，查库验证。

        防什么：_ensure_inbox 如果漏了创建逻辑，首次访问时 inbox 为 None，
        后续默认入收集箱的文档会 folder_id=None。
        """
        svc = DocumentService(db_session)
        # 首次访问，应该自动创建收集箱
        tree = svc.folders_tree(test_user.id)

        assert len(tree) == 1
        assert tree[0].is_inbox is True
        assert tree[0].name == "收集箱"

        # 查库验证
        db_session.expire_all()
        assert count_rows(db_session, "folders", user_id=test_user.id, is_inbox=1) == 1

    def test_create_folder_persists_all_fields(self, db_session, test_user):
        """创建文件夹后查库验证 name/parent_id/is_inbox/sort_order/user_id。

        防什么：create_folder 如果漏了某个字段（比如 sort_order 默认值），
        文件夹的排序会异常。
        """
        svc = DocumentService(db_session)
        out = svc.create_folder(test_user.id, name="科研笔记")

        # 查库验证
        db_session.expire_all()
        in_db = db_session.get(Folder, out.id)
        assert in_db is not None
        assert in_db.name == "科研笔记"
        assert in_db.parent_id is None
        assert in_db.is_inbox is False
        assert in_db.user_id == test_user.id
        assert in_db.sort_order == 0  # 默认值

    def test_create_folder_duplicate_name_raises(self, db_session, test_user):
        """同级创建同名文件夹抛 DuplicateFolderNameException，库中不产生重复。

        防什么：如果 create_folder 漏了重名检查，唯一索引会在 commit 时报
        IntegrityError（500），而不是友好的业务异常。
        """
        svc = DocumentService(db_session)
        svc.create_folder(test_user.id, name="数学建模")

        with pytest.raises(DuplicateFolderNameException, match="同级已存在同名文件夹"):
            svc.create_folder(test_user.id, name="数学建模")

        # 查库：只有一条
        assert count_rows(db_session, "folders", user_id=test_user.id, name="数学建模") == 1

    def test_create_folder_with_nonexistent_parent_raises(self, db_session, test_user):
        """创建子文件夹时 parent_id 不存在抛 NotFound，库中不产生脏数据。

        防什么：如果 create_folder 漏了 parent 校验，不存在的 parent_id 会
        触发外键约束失败（500）。
        """
        svc = DocumentService(db_session)
        svc.folders_tree(test_user.id)  # 先触发收集箱创建
        with pytest.raises(NotFoundException, match="父文件夹不存在"):
            svc.create_folder(test_user.id, name="子文件夹", parent_id="non-existent-parent")

        # 查库：只有收集箱
        assert count_rows(db_session, "folders", user_id=test_user.id) == 1

    def test_create_subfolder_persists_parent_id(self, db_session, test_user):
        """创建子文件夹后查库验证 parent_id 正确，且出现在父节点的 children 里。

        防什么：如果 create_folder 漏了 parent_id 传递，子文件夹会变成根文件夹。
        """
        svc = DocumentService(db_session)
        parent = svc.create_folder(test_user.id, name="父文件夹")
        child = svc.create_folder(test_user.id, name="子文件夹", parent_id=parent.id)

        # 查库验证
        db_session.expire_all()
        child_in_db = db_session.get(Folder, child.id)
        assert child_in_db.parent_id == parent.id

        # 树中父节点的 children 包含子文件夹
        tree = svc.folders_tree(test_user.id)
        parent_node = next(n for n in tree if n.id == parent.id)
        assert len(parent_node.children) == 1
        assert parent_node.children[0].name == "子文件夹"


# ============================================================
# 第 2 组：重命名 + 收集箱保护 + 越权
# ============================================================

class TestGroup2RenameInboxAuth:
    """第2组：重命名持久化 + 收集箱不可重命名 + 重命名无重名检查 + 越权。"""

    def test_rename_folder_persists_to_db(self, db_session, test_user):
        """重命名文件夹后查库验证 name 变了，其他字段不变。

        防什么：rename_folder 如果直接修改了其他字段（比如 sort_order），
        文件夹的排序会被意外改变。
        """
        svc = DocumentService(db_session)
        folder = svc.create_folder(test_user.id, name="原名字")
        original_sort_order = folder.sort_order

        svc.rename_folder(test_user.id, folder.id, "新名字")

        # 查库验证
        db_session.expire_all()
        in_db = db_session.get(Folder, folder.id)
        assert in_db.name == "新名字"
        assert in_db.sort_order == original_sort_order
        assert in_db.is_inbox is False

    def test_rename_inbox_raises(self, db_session, test_user):
        """重命名收集箱抛 InboxImmutableException，库中收集箱名字不变。

        防什么：如果 rename_folder 漏了收集箱保护，用户可以把收集箱改名，
        导致"收集箱"这个语义概念消失。
        """
        svc = DocumentService(db_session)
        tree = svc.folders_tree(test_user.id)
        inbox_id = tree[0].id

        with pytest.raises(InboxImmutableException, match="收集箱不可重命名"):
            svc.rename_folder(test_user.id, inbox_id, "改名后的收集箱")

        # 查库：名字没变
        db_session.expire_all()
        in_db = db_session.get(Folder, inbox_id)
        assert in_db.name == "收集箱"

    def test_rename_folder_allows_duplicate_name(self, db_session, test_user):
        """重命名为同级已存在的名字，当前不报错（记录行为，可能是待修复的 bug）。

        为什么要这条：create_folder 有重名检查，但 rename_folder 没有。
        这条测试锁定当前行为，如果未来修复了重名检查，这条会失败提醒更新。
        """
        svc = DocumentService(db_session)
        svc.create_folder(test_user.id, name="文件夹A")
        folder_b = svc.create_folder(test_user.id, name="文件夹B")

        # 把 B 改名为 "文件夹A"（和 A 同名）
        svc.rename_folder(test_user.id, folder_b.id, "文件夹A")

        # 查库：出现两个同名文件夹
        db_session.expire_all()
        count = count_rows(db_session, "folders", user_id=test_user.id, name="文件夹A")
        assert count == 2  # 当前行为：允许重名

    def test_rename_other_users_folder_raises(self, db_session, test_user, other_user):
        """重命名其他用户的文件夹抛 NotFound，库中名字不变。

        防什么：_owned_folder 如果只检查存在性而不检查归属，用户可以篡改
        别人的文件夹名。
        """
        # 直接造其他用户的文件夹
        other_folder = Folder(user_id=other_user.id, name="他人文件夹", is_inbox=False)
        db_session.add(other_folder)
        db_session.commit()

        svc = DocumentService(db_session)
        with pytest.raises(NotFoundException, match="文件夹不存在"):
            svc.rename_folder(test_user.id, other_folder.id, "篡改")

        # 查库：名字没变
        db_session.expire_all()
        in_db = db_session.get(Folder, other_folder.id)
        assert in_db.name == "他人文件夹"

    def test_rename_nonexistent_folder_raises(self, db_session, test_user):
        """重命名不存在的文件夹抛 NotFound。

        防什么：_owned_folder 如果没检查存在性，folder.name = name 会报
        AttributeError（None 没有 name 属性），导致 500。
        """
        svc = DocumentService(db_session)
        with pytest.raises(NotFoundException, match="文件夹不存在"):
            svc.rename_folder(test_user.id, "non-existent-folder", "新名字")


# ============================================================
# 第 3 组：删除 + 子文件夹上浮 + 文档迁移 + 越权
# ============================================================

class TestGroup3DeleteFloatMigrateAuth:
    """第3组：删除持久化 + 收集箱不可删除 + 子文件夹上浮 + 文档移收集箱 + 越权。"""

    def test_delete_folder_removes_from_db(self, db_session, test_user):
        """删除文件夹后查库验证行消失，收集箱仍在。

        防什么：delete_folder 如果用了软删除而不是硬删除，文件夹列表里
        还会看到已删除的文件夹（除非 list 过滤了 deleted_at）。
        """
        svc = DocumentService(db_session)
        folder = svc.create_folder(test_user.id, name="待删除")

        svc.delete_folder(test_user.id, folder.id)

        # 查库验证
        db_session.expire_all()
        assert db_session.get(Folder, folder.id) is None
        # 收集箱仍在
        assert count_rows(db_session, "folders", user_id=test_user.id, is_inbox=1) == 1

    def test_delete_inbox_raises(self, db_session, test_user):
        """删除收集箱抛 InboxImmutableException，库中收集箱仍在。

        防什么：如果 delete_folder 漏了收集箱保护，用户可以删除收集箱，
        导致默认入收集箱的逻辑崩溃（_ensure_inbox 会重建，但用户数据可能丢）。
        """
        svc = DocumentService(db_session)
        tree = svc.folders_tree(test_user.id)
        inbox_id = tree[0].id

        with pytest.raises(InboxImmutableException, match="收集箱不可删除"):
            svc.delete_folder(test_user.id, inbox_id)

        # 查库：收集箱仍在
        db_session.expire_all()
        in_db = db_session.get(Folder, inbox_id)
        assert in_db is not None
        assert in_db.is_inbox is True

    def test_delete_folder_floats_children_to_root(self, db_session, test_user):
        """删除有子文件夹的文件夹后，子文件夹上浮到根节点（parent_id=None）。

        防什么：如果 delete_folder 漏了子文件夹上浮逻辑，子文件夹的
        parent_id 会指向已删除的文件夹（外键 SET NULL 后也是 None，
        但显式处理更可靠）。
        """
        svc = DocumentService(db_session)
        parent = svc.create_folder(test_user.id, name="父文件夹")
        child = svc.create_folder(test_user.id, name="子文件夹", parent_id=parent.id)

        svc.delete_folder(test_user.id, parent.id)

        # 查库：子文件夹上浮
        db_session.expire_all()
        child_in_db = db_session.get(Folder, child.id)
        assert child_in_db.parent_id is None

        # 树中子文件夹在根节点
        tree = svc.folders_tree(test_user.id)
        root_names = {n.name for n in tree}
        assert "子文件夹" in root_names

    def test_delete_folder_moves_docs_to_inbox(self, db_session, test_user):
        """删除文件夹后，该文件夹下的文档移至收集箱，不是 folder_id=None。

        防什么：如果 delete_folder 漏了文档迁移逻辑，文档的 folder_id 会
        指向已删除的文件夹（外键 SET NULL 后 folder_id=None），列表里
        显示"未分类"而不是"收集箱"。
        """
        from app.models.document import Document
        from tests.factories import make_document

        svc = DocumentService(db_session)
        folder = svc.create_folder(test_user.id, name="有文档的文件夹")
        doc = make_document(db_session, test_user.id, title="文档", folder_id=folder.id)
        db_session.commit()

        inbox_id = svc.folders_tree(test_user.id)[0].id
        svc.delete_folder(test_user.id, folder.id)

        # 查库：文档移至收集箱
        db_session.expire_all()
        doc_in_db = db_session.get(Document, doc.id)
        assert doc_in_db.folder_id == inbox_id

    def test_delete_other_users_folder_raises(self, db_session, test_user, other_user):
        """删除其他用户的文件夹抛 NotFound，库中文件夹仍在。

        防什么：_owned_folder 如果只检查存在性而不检查归属，用户可以删除
        别人的文件夹。
        """
        other_folder = Folder(user_id=other_user.id, name="他人文件夹", is_inbox=False)
        db_session.add(other_folder)
        db_session.commit()

        svc = DocumentService(db_session)
        with pytest.raises(NotFoundException, match="文件夹不存在"):
            svc.delete_folder(test_user.id, other_folder.id)

        # 查库：文件夹仍在
        db_session.expire_all()
        assert db_session.get(Folder, other_folder.id) is not None


# ============================================================
# 第 4 组：文件夹树排序 + 层级 + 多用户隔离
# ============================================================

class TestGroup4TreeSortIsolation:
    """第4组：收集箱置顶 + sort_order 排序 + 多层级树 + 空库 + 多用户隔离。"""

    def test_folders_tree_inbox_always_first(self, db_session, test_user):
        """无论创建顺序如何，收集箱始终在树的第一个位置。

        防什么：folders_tree 的收集箱置顶逻辑如果漏了，收集箱会和普通
        文件夹混在一起排序，用户找不到默认入口。
        """
        svc = DocumentService(db_session)
        # 先创建普通文件夹，再访问树（收集箱是 _ensure_inbox 时创建的）
        svc.create_folder(test_user.id, name="AAA 应该排前面的文件夹")
        svc.create_folder(test_user.id, name="ZZZ 应该排后面的文件夹")

        tree = svc.folders_tree(test_user.id)
        assert tree[0].is_inbox is True
        assert tree[0].name == "收集箱"

    def test_folders_tree_sorted_by_sort_order(self, db_session, test_user):
        """同级文件夹按 sort_order 排序，sort_order 小的在前。

        防什么：folders_tree 的排序如果漏了 sort_order，文件夹顺序会
        按 created_at 排序，用户手动调整的顺序失效。
        """
        svc = DocumentService(db_session)
        f1 = svc.create_folder(test_user.id, name="第一个")
        f2 = svc.create_folder(test_user.id, name="第二个")
        f3 = svc.create_folder(test_user.id, name="第三个")

        # 手动调整 sort_order：f3=0, f1=1, f2=2
        db_session.expire_all()
        db_session.get(Folder, f1.id).sort_order = 1
        db_session.get(Folder, f2.id).sort_order = 2
        db_session.get(Folder, f3.id).sort_order = 0
        db_session.commit()

        tree = svc.folders_tree(test_user.id)
        # 收集箱之后，按 sort_order 排序
        names = [n.name for n in tree if not n.is_inbox]
        assert names == ["第三个", "第一个", "第二个"]

    def test_folders_tree_three_level_nesting(self, db_session, test_user):
        """三层嵌套文件夹的树结构正确：根→子→孙。

        防什么：folders_tree 的递归 build 如果层级处理有误，深层子文件夹
        会丢失或者出现在错误的层级。
        """
        svc = DocumentService(db_session)
        root = svc.create_folder(test_user.id, name="根")
        child = svc.create_folder(test_user.id, name="子", parent_id=root.id)
        svc.create_folder(test_user.id, name="孙", parent_id=child.id)

        tree = svc.folders_tree(test_user.id)
        root_node = next(n for n in tree if n.name == "根")
        assert len(root_node.children) == 1
        assert root_node.children[0].name == "子"
        assert len(root_node.children[0].children) == 1
        assert root_node.children[0].children[0].name == "孙"

    def test_folders_tree_empty_db_only_inbox(self, db_session, test_user):
        """空数据库时，文件夹树只有收集箱一个节点。

        防什么：空数据场景下如果代码假设至少有一个普通文件夹，可能报
        IndexError 或者除零错误。
        """
        svc = DocumentService(db_session)
        tree = svc.folders_tree(test_user.id)
        assert len(tree) == 1
        assert tree[0].is_inbox is True
        assert len(tree[0].children) == 0

    def test_folders_tree_isolates_between_users(self, db_session, test_user, other_user):
        """A 用户的文件夹树不包含 B 用户的文件夹。

        防什么：folders_tree 的 list_by_user 如果漏了 user_id 过滤，
        会返回所有用户的文件夹，造成数据泄露。
        """
        # 其他用户创建文件夹
        other_folder = Folder(user_id=other_user.id, name="他人的文件夹", is_inbox=False)
        db_session.add(other_folder)
        db_session.commit()

        svc = DocumentService(db_session)
        tree = svc.folders_tree(test_user.id)
        names = {n.name for n in tree}
        assert "他人的文件夹" not in names
        # 只有收集箱
        assert len(tree) == 1


# ============================================================
# 第 5 组：边界场景
# ============================================================

class TestGroup5Boundary:
    """第5组：parent 越权 + 大量子文件夹上浮 + 收集箱幂等 + 同名重命名 + 删除后重建。"""

    def test_create_folder_with_other_users_parent_raises(self, db_session, test_user, other_user):
        """创建子文件夹时指定其他用户的 parent_id 抛 NotFound，库中不产生脏数据。

        防什么：create_folder 的 parent 校验如果只检查存在性而不检查归属，
        用户可以在别人的文件夹下创建子文件夹。
        """
        other_folder = Folder(user_id=other_user.id, name="他人父文件夹", is_inbox=False)
        db_session.add(other_folder)
        db_session.commit()

        svc = DocumentService(db_session)
        svc.folders_tree(test_user.id)  # 先触发收集箱
        with pytest.raises(NotFoundException, match="父文件夹不存在"):
            svc.create_folder(test_user.id, name="子文件夹", parent_id=other_folder.id)

        # 查库：只有收集箱
        assert count_rows(db_session, "folders", user_id=test_user.id) == 1

    def test_delete_folder_with_many_children_all_floated(self, db_session, test_user):
        """删除有 10 个子文件夹的父文件夹后，所有子文件夹全部上浮到根。

        防什么：delete_folder 的子文件夹上浮如果用了 LIMIT 或者只处理
        第一层，深层或大量子文件夹会丢失。
        """
        svc = DocumentService(db_session)
        parent = svc.create_folder(test_user.id, name="父文件夹")
        child_ids = []
        for i in range(10):
            child = svc.create_folder(test_user.id, name=f"子{i}", parent_id=parent.id)
            child_ids.append(child.id)

        svc.delete_folder(test_user.id, parent.id)

        # 查库：所有子文件夹 parent_id=None
        db_session.expire_all()
        for cid in child_ids:
            child_in_db = db_session.get(Folder, cid)
            assert child_in_db.parent_id is None

        # 树中根节点有 10 个子文件夹 + 收集箱
        tree = svc.folders_tree(test_user.id)
        assert len(tree) == 11  # 1 收集箱 + 10 上浮的子文件夹

    def test_inbox_id_stable_across_calls(self, db_session, test_user):
        """多次调用 folders_tree，收集箱的 id 不变（幂等创建）。

        防什么：_ensure_inbox 如果每次都创建新的收集箱，会产生多个
        is_inbox=True 的文件夹，默认入收集箱的逻辑会混乱。
        """
        svc = DocumentService(db_session)
        tree1 = svc.folders_tree(test_user.id)
        inbox_id_1 = tree1[0].id

        tree2 = svc.folders_tree(test_user.id)
        inbox_id_2 = tree2[0].id

        assert inbox_id_1 == inbox_id_2
        # 查库：只有一个收集箱
        assert count_rows(db_session, "folders", user_id=test_user.id, is_inbox=1) == 1

    def test_rename_folder_to_same_name_no_error(self, db_session, test_user):
        """重命名为相同名字不报错，库中数据不变。

        防什么：rename_folder 如果对同名也抛异常，用户"保存"时即使没改
        名字也会报错。
        """
        svc = DocumentService(db_session)
        folder = svc.create_folder(test_user.id, name="我的文件夹")

        # 重命名为相同名字
        out = svc.rename_folder(test_user.id, folder.id, "我的文件夹")
        assert out.name == "我的文件夹"

        # 查库：没变
        db_session.expire_all()
        in_db = db_session.get(Folder, folder.id)
        assert in_db.name == "我的文件夹"

    def test_create_folder_after_delete_same_name_allowed(self, db_session, test_user):
        """删除文件夹后，同名文件夹可以重新创建（软删除后唯一索引不冲突）。

        防什么：如果唯一索引没有加 deleted_at IS NULL 条件，软删除后
        同名文件夹无法重建。当前模型用了 sqlite_where 条件，这条验证。
        """
        svc = DocumentService(db_session)
        folder = svc.create_folder(test_user.id, name="临时文件夹")
        svc.delete_folder(test_user.id, folder.id)

        # 删除后同名重建
        new_folder = svc.create_folder(test_user.id, name="临时文件夹")
        assert new_folder.name == "临时文件夹"
        assert new_folder.id != folder.id  # 是新的 id

        # 查库：只有一条未删除的
        assert count_rows(db_session, "folders", user_id=test_user.id, name="临时文件夹") == 1


# ============================================================
# 第 6 组：深度场景补充（同名不同parent + 孙文件夹上浮 + 树更新 + 文档移动 + 四层嵌套）
# ============================================================

class TestGroup6DeepScenarios:
    """第6组：唯一约束边界 + 深层删除 + 树即时更新 + 文档跨文件夹移动 + 四层嵌套。"""

    def test_same_name_different_parent_allowed(self, db_session, test_user):
        """不同 parent 下的同名文件夹是允许的（唯一约束是 user+parent+name）。

        防什么：如果唯一约束漏了 parent_id，不同父文件夹下也不能有同名
        文件夹，用户体验会很差。
        """
        svc = DocumentService(db_session)
        parent_a = svc.create_folder(test_user.id, name="父A")
        parent_b = svc.create_folder(test_user.id, name="父B")

        # 在父A和父B下都创建"子文件夹"
        child_a = svc.create_folder(test_user.id, name="子文件夹", parent_id=parent_a.id)
        child_b = svc.create_folder(test_user.id, name="子文件夹", parent_id=parent_b.id)

        assert child_a.id != child_b.id
        # 查库：两条同名但不同 parent
        assert count_rows(db_session, "folders", user_id=test_user.id, name="子文件夹") == 2

    def test_delete_nested_folder_floats_grandchildren(self, db_session, test_user):
        """删除有子文件夹的文件夹后，直接子文件夹上浮到根；孙文件夹仍挂在子文件夹下。

        防什么：delete_folder 如果错误地递归删除所有后代，孙文件夹会丢失。
        正确行为：只上浮直接子文件夹，后代保持原有的层级关系。
        """
        svc = DocumentService(db_session)
        root = svc.create_folder(test_user.id, name="根")
        child = svc.create_folder(test_user.id, name="子", parent_id=root.id)
        grandchild = svc.create_folder(test_user.id, name="孙", parent_id=child.id)

        # 删除根文件夹
        svc.delete_folder(test_user.id, root.id)

        # 查库：子上浮（parent_id=None），孙仍挂在子下
        db_session.expire_all()
        assert db_session.get(Folder, child.id).parent_id is None
        assert db_session.get(Folder, grandchild.id).parent_id == child.id

        # 树中：根节点有"子"，"子"下有"孙"
        tree = svc.folders_tree(test_user.id)
        child_node = next(n for n in tree if n.name == "子")
        assert len(child_node.children) == 1
        assert child_node.children[0].name == "孙"

    def test_rename_folder_updates_tree_immediately(self, db_session, test_user):
        """重命名文件夹后，再次获取树，名字即时更新。

        防什么：folders_tree 如果有缓存（比如内存缓存），重命名后树里
        还是旧名字。当前没有缓存，这条锁定行为。
        """
        svc = DocumentService(db_session)
        folder = svc.create_folder(test_user.id, name="旧名字")

        tree_before = svc.folders_tree(test_user.id)
        assert any(n.name == "旧名字" for n in tree_before)

        svc.rename_folder(test_user.id, folder.id, "新名字")

        tree_after = svc.folders_tree(test_user.id)
        assert any(n.name == "新名字" for n in tree_after)
        assert not any(n.name == "旧名字" for n in tree_after)

    def test_move_document_between_folders(self, db_session, test_user):
        """文档从文件夹A移动到文件夹B（update folder_id），查库验证。

        防什么：document 的 update 如果漏了 folder_id 处理，文档无法
        在文件夹间移动。
        """
        from app.models.document import Document
        from app.schemas.document import UpdateDocumentRequest
        from tests.factories import make_document

        svc = DocumentService(db_session)
        folder_a = svc.create_folder(test_user.id, name="A")
        folder_b = svc.create_folder(test_user.id, name="B")
        doc = make_document(db_session, test_user.id, title="文档", folder_id=folder_a.id)
        db_session.commit()

        # 移动到 B
        svc.update_document(test_user.id, doc.id, UpdateDocumentRequest(folder_id=folder_b.id))

        # 查库验证
        db_session.expire_all()
        doc_in_db = db_session.get(Document, doc.id)
        assert doc_in_db.folder_id == folder_b.id

    def test_four_level_nesting_tree(self, db_session, test_user):
        """四层嵌套文件夹的树结构正确：根→子→孙→曾孙。

        防什么：folders_tree 的递归 build 如果深度处理有误，深层子文件夹
        会丢失或者出现在错误的层级。
        """
        svc = DocumentService(db_session)
        root = svc.create_folder(test_user.id, name="根")
        child = svc.create_folder(test_user.id, name="子", parent_id=root.id)
        grand = svc.create_folder(test_user.id, name="孙", parent_id=child.id)
        svc.create_folder(test_user.id, name="曾孙", parent_id=grand.id)

        tree = svc.folders_tree(test_user.id)
        root_node = next(n for n in tree if n.name == "根")
        assert len(root_node.children) == 1
        assert root_node.children[0].name == "子"
        assert root_node.children[0].children[0].name == "孙"
        assert root_node.children[0].children[0].children[0].name == "曾孙"
        # 曾孙没有子节点
        assert len(root_node.children[0].children[0].children[0].children) == 0
