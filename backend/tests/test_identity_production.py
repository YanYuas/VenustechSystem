# ============================================================
# Identity Service 生产级测试
#
# 业务规则：身份上限12个、slug唯一不可改、color_token白名单、
#           归档(is_active=False)而非删除、软删除清10表引用
#
# 标准：真数据夹具 + 写操作后查库验证 + 增量隔离 + 负向断言 + 防bug注释
# ============================================================
from __future__ import annotations

import pytest

from app.core.exceptions import BusinessException, NotFoundException, ValidationException
from app.models.identity import Identity
from app.schemas.identity import CreateIdentityRequest, UpdateIdentityRequest
from app.services.identity_service import IdentityService
from tests.factories import count_rows


def _make_identity(name="学生", slug="student", **overrides):
    """构造 CreateIdentityRequest，所有字段有默认值，可覆盖。"""
    defaults = dict(
        name=name, slug=slug, color_token="primary",
        icon="star", description="身份描述", sort_order=0,
    )
    defaults.update(overrides)
    return CreateIdentityRequest(**defaults)


# ============================================================
# 第 1 组：基础 CRUD
# ============================================================

class TestGroup1BasicCRUD:
    """第1组：创建 + 列表（归档过滤）+ 获取 + 更新 + 软删除。"""

    def test_create_identity_persists_to_db(self, db_session, test_user):
        """创建身份后查库验证 name/slug/color_token/icon/user_id 正确写入。

        防什么：create 如果漏了某个字段（比如 sort_order），身份创建后
        该字段为默认值，排序异常。
        """
        svc = IdentityService(db_session, test_user.id)
        out = svc.create(_make_identity(name="学生身份", slug="student", color_token="mint"))

        assert out.name == "学生身份"
        assert out.slug == "student"
        assert out.color_token == "mint"

        # 查库验证
        db_session.expire_all()
        in_db = db_session.get(Identity, out.id)
        assert in_db is not None
        assert in_db.name == "学生身份"
        assert in_db.slug == "student"
        assert in_db.color_token == "mint"
        assert in_db.icon == "star"
        assert in_db.user_id == test_user.id
        assert in_db.is_active is True
        assert in_db.deleted_at is None

    def test_list_includes_archived_by_default(self, db_session, test_user):
        """列表默认包含归档身份（is_active=False），归档不是删除。

        防什么：list 如果默认排除归档，归档身份会从筛选器消失，历史数据
        无法按身份查看。
        """
        svc = IdentityService(db_session, test_user.id)
        svc.create(_make_identity(name="活跃", slug="active"))
        archived = svc.create(_make_identity(name="归档", slug="archived"))
        svc.update(archived.id, UpdateIdentityRequest(is_active=False))

        result = svc.list()  # 默认 include_archived=True
        names = {i.name for i in result}
        assert "活跃" in names
        assert "归档" in names
        assert len(result) == 2

    def test_list_excludes_archived_when_flagged(self, db_session, test_user):
        """include_archived=False 时列表排除归档身份。

        防什么：list 的 include_archived 参数如果没正确传递给 repo，
        归档身份永远显示。
        """
        svc = IdentityService(db_session, test_user.id)
        svc.create(_make_identity(name="活跃", slug="active"))
        archived = svc.create(_make_identity(name="归档", slug="archived"))
        svc.update(archived.id, UpdateIdentityRequest(is_active=False))

        result = svc.list(include_archived=False)
        names = {i.name for i in result}
        assert "活跃" in names
        assert "归档" not in names
        assert len(result) == 1

    def test_get_returns_identity(self, db_session, test_user):
        """获取单个身份返回完整字段。

        防什么：get 如果漏了 _out 转换，返回的是 ORM 对象而不是 schema，
        前端字段不匹配。
        """
        svc = IdentityService(db_session, test_user.id)
        created = svc.create(_make_identity(name="获取测试", slug="get-test"))

        result = svc.get(created.id)
        assert result.id == created.id
        assert result.name == "获取测试"
        assert result.slug == "get-test"
        assert result.color_token == "primary"
        assert result.is_active is True

    def test_update_identity_persists_changes(self, db_session, test_user):
        """更新身份后查库验证指定字段变了，slug 不可改（UpdateIdentityRequest 无 slug 字段）。

        防什么：update 如果允许修改 slug，会打断所有按 slug 的引用（筛选器/路由）。
        """
        svc = IdentityService(db_session, test_user.id)
        created = svc.create(_make_identity(name="旧名字", slug="old-slug", color_token="primary"))

        # 更新 name 和 color_token
        svc.update(created.id, UpdateIdentityRequest(
            name="新名字", color_token="sky", icon="book",
        ))

        # 查库验证
        db_session.expire_all()
        in_db = db_session.get(Identity, created.id)
        assert in_db.name == "新名字"
        assert in_db.color_token == "sky"
        assert in_db.icon == "book"
        assert in_db.slug == "old-slug"  # slug 不可改


# ============================================================
# 第 2 组：业务规则校验（color_token + slug 唯一 + 越权 + 软删除）
# ============================================================

class TestGroup2BusinessRules:
    """第2组：#色值拒绝 + 未登记令牌拒绝 + 重复slug拒绝 + 越权 + 软删除。"""

    def test_create_with_hash_color_rejected(self, db_session, test_user):
        """创建时指定 # 开头的色值在 schema 层就被 pattern 校验拒绝，不产生身份。

        防什么：color_token 设计上只存设计令牌名（如 "primary"），schema 的
        pattern ^[a-z][a-z0-9-]*$ 直接拒绝 # 开头的色值，双保险。
        """
        from pydantic import ValidationError

        svc = IdentityService(db_session, test_user.id)
        with pytest.raises(ValidationError):
            # #ff0000 在构造 CreateIdentityRequest 时就被 pattern 拒绝
            svc.create(_make_identity(name="色值身份", slug="hash-color", color_token="#ff0000"))

        assert count_rows(db_session, "identities", user_id=test_user.id) == 0

    def test_create_with_unregistered_color_rejected(self, db_session, test_user):
        """创建时指定未登记的 color_token 被拒绝（白名单校验）。

        防什么：如果 color_token 没有白名单校验，任意字符串都能写入，
        前端找不到对应令牌会回退默认色，用户困惑。
        """
        svc = IdentityService(db_session, test_user.id)
        with pytest.raises(ValidationException, match="未登记的设计令牌"):
            svc.create(_make_identity(name="未登记", slug="unregistered", color_token="neon-green"))

        assert count_rows(db_session, "identities", user_id=test_user.id) == 0

    def test_create_duplicate_slug_rejected(self, db_session, test_user):
        """创建时指定已存在的 slug 被拒绝，不产生身份。

        防什么：slug 是筛选器/路由的稳定键，如果允许重复，按 slug 筛选
        会返回多个身份，逻辑混乱。
        """
        svc = IdentityService(db_session, test_user.id)
        svc.create(_make_identity(name="第一个", slug="my-slug"))

        with pytest.raises(BusinessException, match="slug 已存在"):
            svc.create(_make_identity(name="第二个", slug="my-slug"))

        # 查库：只有一条
        assert count_rows(db_session, "identities", user_id=test_user.id, slug="my-slug") == 1


# ============================================================
# 第 4 组：名称strip + 同slug不同用户 + 已删除身份get + 软删除清项目/文档 + update多字段
# ============================================================

class TestGroup4StripMultiuserDeletedCascade:
    """第4组：名称前后空格strip + 同slug不同用户允许 + 已删除身份get抛异常 + 软删除清项目/文档 + update多字段。"""

    def test_create_name_stripped(self, db_session, test_user):
        """创建时名称前后空格被 strip，查库验证。

        防什么：如果 create 漏了 name.strip()，用户输入"  学生  "会原样
        写入，列表显示有多余空格，筛选匹配异常。
        """
        svc = IdentityService(db_session, test_user.id)
        out = svc.create(_make_identity(name="  学生身份  ", slug="stripped"))

        assert out.name == "学生身份"  # 前后空格被 strip

        db_session.expire_all()
        in_db = db_session.get(Identity, out.id)
        assert in_db.name == "学生身份"

    def test_update_name_stripped(self, db_session, test_user):
        """更新时名称前后空格被 strip，查库验证。

        防什么：update 如果漏了 name.strip()，更新后的名称会有多余空格。
        """
        svc = IdentityService(db_session, test_user.id)
        identity = svc.create(_make_identity(name="旧名字", slug="update-strip"))

        svc.update(identity.id, UpdateIdentityRequest(name="  新名字  "))

        db_session.expire_all()
        in_db = db_session.get(Identity, identity.id)
        assert in_db.name == "新名字"

    def test_same_slug_different_user_allowed(self, db_session, test_user, other_user):
        """不同用户可以使用相同的 slug（唯一约束是 user_id+slug）。

        防什么：如果唯一约束漏了 user_id，全局 slug 唯一，用户不能使用
        常见 slug（如 "work"、"study"）。
        """
        svc1 = IdentityService(db_session, test_user.id)
        svc2 = IdentityService(db_session, other_user.id)

        id1 = svc1.create(_make_identity(name="用户A的身份", slug="shared-slug"))
        id2 = svc2.create(_make_identity(name="用户B的身份", slug="shared-slug"))

        assert id1.id != id2.id
        # 查库：两条同 slug 但不同 user_id
        assert count_rows(db_session, "identities", slug="shared-slug") == 2

    def test_get_deleted_identity_raises(self, db_session, test_user):
        """获取已软删除的身份抛 NotFoundException（_get_owned 检查 deleted_at）。

        防什么：如果 _get_owned 漏了 deleted_at 检查，已删除的身份仍可
        被获取，前端显示已删除的数据。
        """
        svc = IdentityService(db_session, test_user.id)
        identity = svc.create(_make_identity(name="已删除", slug="deleted-get"))
        svc.delete(identity.id)

        with pytest.raises(NotFoundException, match="身份不存在"):
            svc.get(identity.id)

    def test_soft_delete_clears_project_and_document_refs(self, db_session, test_user):
        """软删除身份后，关联项目和文档的 identity_id 被清除为 None。

        防什么：delete 如果只清除了任务引用而漏了项目/文档，这些记录的
        identity_id 会变成悬空引用，在「按身份」和「未归类」两不靠。
        """
        from app.models.document import Document
        from app.models.project import Project

        svc = IdentityService(db_session, test_user.id)
        identity = svc.create(_make_identity(name="有项目文档身份", slug="with-proj-doc"))

        project = Project(user_id=test_user.id, name="关联项目", status="active",
                          identity_id=identity.id)
        doc = Document(user_id=test_user.id, title="关联文档", identity_id=identity.id)
        db_session.add_all([project, doc])
        db_session.commit()
        project_id, doc_id = project.id, doc.id

        svc.delete(identity.id)

        db_session.expire_all()
        assert db_session.get(Project, project_id).identity_id is None
        assert db_session.get(Document, doc_id).identity_id is None


# ============================================================
# 第 5 组：已删除身份update/delete + 列表排序 + 7个color_token + update多字段
# ============================================================

class TestGroup5DeletedUpdateSortColors:
    """第5组：已删除身份update/delete抛异常 + 列表排序 + 全部7个白名单令牌 + update description/sort_order。"""

    def test_update_deleted_identity_raises(self, db_session, test_user):
        """更新已软删除的身份抛 NotFoundException，数据不变。

        防什么：如果 update 漏了 deleted_at 检查，已删除的身份可以被
        复活（通过更新字段），软删除语义被破坏。
        """
        svc = IdentityService(db_session, test_user.id)
        identity = svc.create(_make_identity(name="已删除", slug="deleted-update"))
        svc.delete(identity.id)

        with pytest.raises(NotFoundException, match="身份不存在"):
            svc.update(identity.id, UpdateIdentityRequest(name="复活"))

        # 查库：名字没变，deleted_at 仍在
        db_session.expire_all()
        in_db = db_session.get(Identity, identity.id)
        assert in_db.name == "已删除"
        assert in_db.deleted_at is not None

    def test_delete_deleted_identity_raises(self, db_session, test_user):
        """删除已软删除的身份抛 NotFoundException（幂等删除应该安全，但当前实现抛异常）。

        防什么：如果 delete 漏了 deleted_at 检查，重复删除可能导致
        deleted_at 被重复设置（虽然无害，但语义不清晰）。
        """
        svc = IdentityService(db_session, test_user.id)
        identity = svc.create(_make_identity(name="已删除", slug="deleted-delete"))
        svc.delete(identity.id)

        with pytest.raises(NotFoundException, match="身份不存在"):
            svc.delete(identity.id)

    def test_list_sorted_by_sort_order(self, db_session, test_user):
        """列表按 sort_order 升序返回，sort_order 相同时按 created_at 升序。

        防什么：list_user 如果漏了 order_by，身份顺序随机，前端拖拽排序
        后刷新会乱。
        """
        svc = IdentityService(db_session, test_user.id)
        # 按倒序创建
        svc.create(_make_identity(name="第三", slug="third", sort_order=3))
        svc.create(_make_identity(name="第一", slug="first", sort_order=1))
        svc.create(_make_identity(name="第二", slug="second", sort_order=2))

        result = svc.list()
        names = [i.name for i in result]
        assert names == ["第一", "第二", "第三"]

    def test_all_7_color_tokens_accepted(self, db_session, test_user):
        """全部 7 个白名单 color_token 都能成功创建。

        防什么：如果 ALLOWED_COLOR_TOKENS 和前端 variables.scss 不同步，
        某些合法令牌会被拒绝，前端显示默认色。
        """
        from app.services.identity_service import ALLOWED_COLOR_TOKENS

        svc = IdentityService(db_session, test_user.id)
        assert len(ALLOWED_COLOR_TOKENS) == 7  # primary/mint/butter/sky/lilac/strawberry/gold

        for i, token in enumerate(ALLOWED_COLOR_TOKENS):
            out = svc.create(_make_identity(name=f"身份{i}", slug=f"color-{i}", color_token=token))
            assert out.color_token == token

        assert count_rows(db_session, "identities", user_id=test_user.id) == 7

    def test_update_description_and_sort_order(self, db_session, test_user):
        """更新 description 和 sort_order 后查库验证，其他字段不变。

        防什么：update 如果漏了 description 或 sort_order 字段处理，
        这些字段无法通过 API 修改。
        """
        svc = IdentityService(db_session, test_user.id)
        identity = svc.create(_make_identity(
            name="多字段", slug="multi-field", description="旧描述", sort_order=0,
        ))

        svc.update(identity.id, UpdateIdentityRequest(
            description="新描述", sort_order=5,
        ))

        db_session.expire_all()
        in_db = db_session.get(Identity, identity.id)
        assert in_db.description == "新描述"
        assert in_db.sort_order == 5
        assert in_db.name == "多字段"  # 未指定字段不变
        assert in_db.color_token == "primary"  # 未指定字段不变

    def test_get_other_users_identity_raises(self, db_session, test_user, other_user):
        """获取其他用户的身份抛 NotFoundException，不泄露数据。

        防什么：_get_owned 如果只检查存在性而不检查 user_id，用户可以
        通过遍历 id 看到别人的身份。
        """
        other_identity = Identity(
            user_id=other_user.id, name="他人身份", slug="other-identity",
        )
        db_session.add(other_identity)
        db_session.commit()

        svc = IdentityService(db_session, test_user.id)
        with pytest.raises(NotFoundException, match="身份不存在"):
            svc.get(other_identity.id)

    def test_soft_delete_excludes_from_list(self, db_session, test_user):
        """软删除身份后，从列表消失（deleted_at 过滤），但行仍在数据库。

        防什么：list 如果漏了 deleted_at 过滤，已删除的身份会出现在
        筛选器里，甚至被「按身份生成目录骨架」建出文件夹。
        """
        svc = IdentityService(db_session, test_user.id)
        created = svc.create(_make_identity(name="待删除", slug="to-delete"))

        svc.delete(created.id)

        # 列表中消失
        result = svc.list()
        assert len(result) == 0

        # 但行仍在数据库（软删除）
        db_session.expire_all()
        in_db = db_session.get(Identity, created.id)
        assert in_db is not None
        assert in_db.deleted_at is not None


# ============================================================
# 第 3 组：上限 + 软删除清引用 + 归档恢复 + update color + 删除后slug重用
# ============================================================

class TestGroup3LimitsAndCascade:
    """第3组：12个上限 + 软删除清任务引用 + 归档恢复 + update color校验 + 删除后slug重用。"""

    def test_create_exceeds_max_identities_rejected(self, db_session, test_user):
        """创建第 13 个身份时被拒绝（上限 12 个），不产生身份。

        防什么：如果没有上限校验，用户可以创建几十个身份，筛选器爆炸，
        该合并而不是新建。
        """
        svc = IdentityService(db_session, test_user.id)
        # 造 12 个身份
        for i in range(12):
            svc.create(_make_identity(name=f"身份{i}", slug=f"identity-{i}"))

        assert count_rows(db_session, "identities", user_id=test_user.id) == 12

        # 第 13 个被拒绝
        with pytest.raises(BusinessException, match="身份数量已达上限"):
            svc.create(_make_identity(name="第13个", slug="identity-13"))

        assert count_rows(db_session, "identities", user_id=test_user.id) == 12

    def test_soft_delete_clears_task_identity_ref(self, db_session, test_user):
        """软删除身份后，关联任务的 identity_id 被清除为 None（不删除任务）。

        防什么：delete 如果漏了引用清除，任务的 identity_id 会指向已删除
        的身份（悬空引用），在「按身份」和「未归类」两个视图里都不可见。
        """
        from app.models.task import Task

        svc = IdentityService(db_session, test_user.id)
        identity = svc.create(_make_identity(name="有任务身份", slug="with-tasks"))

        # 造 2 个关联任务
        task_ids = []
        for i in range(2):
            t = Task(user_id=test_user.id, title=f"任务{i}", identity_id=identity.id)
            db_session.add(t)
            db_session.flush()
            task_ids.append(t.id)
        db_session.commit()

        svc.delete(identity.id)

        # 查库：任务还在，identity_id 为 None
        db_session.expire_all()
        for tid in task_ids:
            task = db_session.get(Task, tid)
            assert task is not None
            assert task.identity_id is None

    def test_archive_then_restore_via_update(self, db_session, test_user):
        """归档（is_active=False）后恢复（is_active=True），查库验证。

        防什么：归档不是删除，如果 update 的 is_active 处理有误，归档身份
        无法恢复。
        """
        svc = IdentityService(db_session, test_user.id)
        identity = svc.create(_make_identity(name="可归档", slug="archivable"))

        # 归档
        archived = svc.update(identity.id, UpdateIdentityRequest(is_active=False))
        assert archived.is_active is False

        # 恢复
        restored = svc.update(identity.id, UpdateIdentityRequest(is_active=True))
        assert restored.is_active is True

        # 查库验证
        db_session.expire_all()
        in_db = db_session.get(Identity, identity.id)
        assert in_db.is_active is True
        assert in_db.deleted_at is None  # 归档不是软删除

    def test_update_with_unregistered_color_rejected(self, db_session, test_user):
        """更新时指定未登记的 color_token 被拒绝，原 color_token 不变。

        防什么：update 的 color_token 校验如果漏了，非法令牌会被写入，
        前端找不到对应色值。
        """
        svc = IdentityService(db_session, test_user.id)
        identity = svc.create(_make_identity(name="颜色测试", slug="color-test", color_token="primary"))

        with pytest.raises(ValidationException, match="未登记的设计令牌"):
            svc.update(identity.id, UpdateIdentityRequest(color_token="neon-pink"))

        # 查库：color_token 没变
        db_session.expire_all()
        in_db = db_session.get(Identity, identity.id)
        assert in_db.color_token == "primary"

    def test_delete_then_same_slug_blocked_by_unique_constraint(self, db_session, test_user):
        """软删除身份后，同 slug 无法重建（唯一约束不含 deleted_at 条件）。

        这是设计决策：slug 是筛选器/路由的稳定键，软删除后保留 slug 占用，
        避免复用导致历史数据按 slug 引用混乱。与 folder 不同（folder 有
        sqlite_where 条件允许同名重建）。
        """
        from sqlalchemy.exc import IntegrityError

        svc = IdentityService(db_session, test_user.id)
        first = svc.create(_make_identity(name="第一个", slug="my-slug"))
        first_id = first.id
        svc.delete(first.id)

        # 删除后同 slug 重建被唯一约束拒绝
        with pytest.raises((BusinessException, IntegrityError)):
            svc.create(_make_identity(name="第二个", slug="my-slug"))

        # IntegrityError 后 session 需要 rollback 才能继续查询
        db_session.rollback()

        # 查库：只有一条（已删除的）
        in_db = db_session.get(Identity, first_id)
        assert in_db is not None
        assert in_db.deleted_at is not None
