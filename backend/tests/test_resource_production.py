# ============================================================
# 资源中心 Service 层测试（二期 M7：收集箱 / 模板库 / 领域库）
#
# 本轮修复的缺陷（测试即回归守护）：
#   D1 单条操作零归属校验 → IDOR（任何登录用户拿到 id 即可读改删他人数据）
#   D2 更新端点收裸 dict 直传 repo.update → mass-assignment（可改 user_id/id/use_count）
#   D3 非法 process action 抛裸 ValueError → 500，且批量场景被静默记成"失败"
#   D4 非法 status/title 等参数无白名单 → 静默写入永不生效的值
#   D5 content_type 无白名单，且模型注释 `url` 与前端/种子数据的 `link` 拼写不一致
# ============================================================
from __future__ import annotations

import pytest

from app.core.exceptions import NotFoundException, ValidationException
from app.schemas.resource import (
    CreateDomainRequest, CreateInboxItemRequest, CreateTemplateRequest,
    UpdateInboxItemRequest,
)
from app.services.resource_service import ResourceService


def _svc(db, user) -> ResourceService:
    return ResourceService(db, user.id)


def _uid(svc, user):
    return user.id if user is not None else svc.user_id


def _inbox(svc, user=None, **over):
    kw = dict(content_type="text", content="随手记", title="标题")
    kw.update(over)
    return svc.create_inbox_item(_uid(svc, user), CreateInboxItemRequest(**kw))


def _template(svc, user=None, **over):
    kw = dict(name="周报模板", category="doc", content="你好 {{name}}",
              variables=["name"])
    kw.update(over)
    return svc.create_template(_uid(svc, user), CreateTemplateRequest(**kw))


def _domain(svc, user=None, **over):
    kw = dict(name="数学", description="数学领域")
    kw.update(over)
    return svc.create_domain(_uid(svc, user), CreateDomainRequest(**kw))


# ============================================================
# 一、收集箱 CRUD
# ============================================================
class TestInboxCrud:

    def test_create_and_list(self, db_session, test_user):
        svc = _svc(db_session, test_user)
        _inbox(svc)
        page = svc.list_inbox(test_user.id)
        assert page["total"] == 1
        assert page["page"] == 1 and page["page_size"] == 20
        assert page["list"][0]["title"] == "标题"

    def test_list_filters_by_status(self, db_session, test_user):
        svc = _svc(db_session, test_user)
        a = _inbox(svc, test_user, title="待处理")
        svc.update_inbox_item(a["id"], UpdateInboxItemRequest(status="archived"))
        _inbox(svc, test_user, title="另一个待处理")
        assert svc.list_inbox(test_user.id, status="pending")["total"] == 1
        assert svc.list_inbox(test_user.id, status="archived")["total"] == 1

    def test_list_rejects_unknown_status(self, db_session, test_user):
        """status 白名单：非法值宁可报错，也不要静默返回空列表。"""
        svc = _svc(db_session, test_user)
        with pytest.raises(ValidationException) as ei:
            svc.list_inbox(test_user.id, status="bogus")
        assert "非法状态" in str(ei.value)

    def test_update_inbox_rejects_unknown_status(self, db_session, test_user):
        from app.models.resource import InboxItem

        svc = _svc(db_session, test_user)
        item = _inbox(svc, test_user)
        with pytest.raises(ValidationException):
            svc.update_inbox_item(item["id"], UpdateInboxItemRequest(status="whatever"))
        assert db_session.get(InboxItem, item["id"]).status == "pending"  # 无副作用

    def test_update_inbox_accepts_whitelisted_status(self, db_session, test_user):
        svc = _svc(db_session, test_user)
        item = _inbox(svc, test_user)
        for st in ("processed", "archived", "pending"):
            out = svc.update_inbox_item(item["id"], UpdateInboxItemRequest(status=st))
            assert out["status"] == st

    def test_update_title_only(self, db_session, test_user):
        svc = _svc(db_session, test_user)
        item = _inbox(svc, test_user, title="旧")
        out = svc.update_inbox_item(item["id"], UpdateInboxItemRequest(title="新"))
        assert out["title"] == "新"
        assert out["status"] == "pending"  # exclude_none → 未传不动

    def test_delete_inbox(self, db_session, test_user):
        from app.models.resource import InboxItem

        svc = _svc(db_session, test_user)
        item = _inbox(svc, test_user)
        svc.delete_inbox_item(item["id"])
        assert db_session.get(InboxItem, item["id"]) is None

    def test_get_unknown_inbox_404(self, db_session, test_user):
        with pytest.raises(NotFoundException):
            _svc(db_session, test_user).get_inbox_item("no-such-id")

    # ---- D5 回归：content_type 白名单（原模型注释写 url，前端与种子数据用 link）----

    def test_create_accepts_all_whitelisted_content_types(self, db_session, test_user):
        """四种合法值都能建；`link` 尤其重要 —— 它是前端实际提交的值。"""
        svc = _svc(db_session, test_user)
        for ct in ("text", "link", "image", "file"):
            assert _inbox(svc, test_user, content_type=ct)["content_type"] == ct
        assert svc.list_inbox(test_user.id)["total"] == 4

    def test_create_rejects_unknown_content_type(self, db_session, test_user):
        """回归：原实现只校验长度 1-20，`url` / 任意字符串都能入库。

        原缺陷是什么：模型注释写 `text/url/image/file`，而前端选项
        （types/resource.ts）与演示数据（demo_seed_data.INBOX_ITEMS）用的都是
        `link` —— 两端当时都没有枚举约束，写入 `url` 既不报错、也读得回来，
        但一旦该字段参与筛选或渲染分支，`url`/`link` 的拼写差就是**静默不匹配**。
        修复后非法值在写库之前就被 400 拦下。
        """
        svc = _svc(db_session, test_user)
        for bad in ("url", "video", "TEXT", "text ", "音频"):
            with pytest.raises(ValidationException) as ei:
                _inbox(svc, test_user, content_type=bad)
            assert "非法内容类型" in str(ei.value)
        # 白名单必须在落库之前生效 —— 拒绝 = 零副作用
        assert svc.list_inbox(test_user.id)["total"] == 0

    def test_create_empty_content_type_rejected_by_schema(self):
        """空串由 Pydantic `min_length=1` 拦下，进不到 Service。"""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            CreateInboxItemRequest(content_type="")


# ============================================================
# 二、处理动作（原实现抛裸 ValueError → 500）
# ============================================================
class TestProcessInbox:

    def test_archive_sets_status_and_timestamp(self, db_session, test_user):
        from app.models.resource import InboxItem

        svc = _svc(db_session, test_user)
        item = _inbox(svc, test_user)
        r = svc.process_inbox_item(item["id"], "archive")
        assert r["status"] == "archived"
        row = db_session.get(InboxItem, item["id"])
        assert row.status == "archived"
        assert row.processed_at is not None

    def test_delete_action_removes_row(self, db_session, test_user):
        from app.models.resource import InboxItem

        svc = _svc(db_session, test_user)
        item = _inbox(svc, test_user)
        assert svc.process_inbox_item(item["id"], "delete")["status"] == "deleted"
        assert db_session.get(InboxItem, item["id"]) is None

    def test_convert_task_marks_processed(self, db_session, test_user):
        svc = _svc(db_session, test_user)
        item = _inbox(svc, test_user)
        r = svc.process_inbox_item(item["id"], "convert_task", target_id="t-1")
        assert r["status"] == "processed"
        assert r["converted_to"] == "task"
        assert r["target_id"] == "t-1"

    def test_convert_doc_marks_processed(self, db_session, test_user):
        svc = _svc(db_session, test_user)
        item = _inbox(svc, test_user)
        r = svc.process_inbox_item(item["id"], "convert_doc", target_id="d-1")
        assert r["converted_to"] == "document"

    def test_invalid_action_raises_validation_not_valueerror(self, db_session, test_user):
        """回归：原实现 `raise ValueError(...)` → 未捕获 → 500。

        现在必须是 ValidationException（400/1001），且**不是** ValueError ——
        ValueError 会被 api 层的兜底 handler 变成 500。
        """
        svc = _svc(db_session, test_user)
        item = _inbox(svc, test_user)
        with pytest.raises(ValidationException) as ei:
            svc.process_inbox_item(item["id"], "explode")
        assert "不支持的处理动作" in str(ei.value)
        assert not isinstance(ei.value, ValueError)

    def test_invalid_action_checked_before_lookup(self, db_session, test_user):
        """参数校验先于查询：非法 action 是 400，不该被 404 掩盖。"""
        svc = _svc(db_session, test_user)
        with pytest.raises(ValidationException):
            svc.process_inbox_item("no-such-id", "explode")

    def test_batch_process_collects_results(self, db_session, test_user):
        svc = _svc(db_session, test_user)
        a = _inbox(svc, test_user)
        b = _inbox(svc, test_user)
        r = svc.batch_process(test_user.id, [a["id"], b["id"]], "archive")
        assert r["total"] == 2 and r["success"] == 2 and r["failed"] == 0

    def test_batch_process_reports_per_item_error(self, db_session, test_user):
        """逐条容错：单条失败不中断整批，原因写进结果（不是吞异常）。"""
        svc = _svc(db_session, test_user)
        a = _inbox(svc, test_user)
        r = svc.batch_process(test_user.id, [a["id"], "no-such-id"], "archive")
        assert r["total"] == 2 and r["success"] == 1 and r["failed"] == 1
        failed = [x for x in r["results"] if not x["success"]][0]
        assert failed["id"] == "no-such-id"
        assert failed["error"]


# ============================================================
# 三、模板库
# ============================================================
class TestTemplateCrud:

    def test_create_and_list(self, db_session, test_user):
        svc = _svc(db_session, test_user)
        _template(svc)
        page = svc.list_templates(test_user.id)
        assert page["total"] == 1
        assert page["list"][0]["name"] == "周报模板"
        assert page["list"][0]["use_count"] == 0

    def test_list_filters_by_category(self, db_session, test_user):
        svc = _svc(db_session, test_user)
        _template(svc, category="doc")
        _template(svc, name="配置", category="config", content="x")
        assert svc.list_templates(test_user.id, category="config")["total"] == 1

    def test_apply_renders_variables(self, db_session, test_user):
        svc = _svc(db_session, test_user)
        tpl = _template(svc, content="你好 {{name}}，今天是 {{day}}")
        r = svc.apply_template(tpl["id"], {"name": "衍煜", "day": "周一"})
        assert r["rendered"] == "你好 衍煜，今天是 周一"
        assert sorted(r["variables_used"]) == ["day", "name"]

    def test_apply_leaves_unknown_variable_intact(self, db_session, test_user):
        svc = _svc(db_session, test_user)
        tpl = _template(svc, content="你好 {{name}} / {{missing}}")
        r = svc.apply_template(tpl["id"], {"name": "X"})
        assert r["rendered"] == "你好 X / {{missing}}"

    def test_apply_increments_use_count(self, db_session, test_user):
        svc = _svc(db_session, test_user)
        tpl = _template(svc)
        svc.apply_template(tpl["id"], {"name": "a"})
        svc.apply_template(tpl["id"], {"name": "b"})
        listed = svc.list_templates(test_user.id)["list"][0]
        assert listed["use_count"] == 2

    def test_update_template(self, db_session, test_user):
        svc = _svc(db_session, test_user)
        tpl = _template(svc)
        out = svc.update_template(tpl["id"], {"name": "新名字", "content": "新的"})
        assert out["name"] == "新名字" and out["content"] == "新的"

    def test_update_template_ignores_non_whitelisted_fields(self, db_session, test_user):
        """D2 回归：裸 dict 直传 repo.update 时，user_id/id/use_count 可被改写。

        现在只允许 _TEMPLATE_UPDATABLE 里的字段 —— 越界键静默丢弃（不改任何东西）。
        """
        svc = _svc(db_session, test_user)
        tpl = _template(svc)
        out = svc.update_template(tpl["id"], {
            "user_id": "attacker-id",
            "id": "forged-id",
            "use_count": 9999,
            "is_builtin": True,
            "name": "合法字段",
        })
        assert out["id"] == tpl["id"]        # id 未被篡改
        assert out["use_count"] == 0         # 计数未被篡改
        assert out["is_builtin"] is False    # 未被提权为内置
        assert out["name"] == "合法字段"      # 白名单内字段正常生效

    def test_update_template_cannot_change_owner(self, db_session, test_user, other_user):
        from app.models.resource import Template

        svc = _svc(db_session, test_user)
        tpl = _template(svc)
        svc.update_template(tpl["id"], {"user_id": other_user.id})
        assert db_session.get(Template, tpl["id"]).user_id == test_user.id

    def test_delete_template(self, db_session, test_user):
        from app.models.resource import Template

        svc = _svc(db_session, test_user)
        tpl = _template(svc)
        svc.delete_template(tpl["id"])
        assert db_session.get(Template, tpl["id"]) is None


# ============================================================
# 四、领域库
# ============================================================
class TestDomainCrud:

    def test_create_and_list_ordered(self, db_session, test_user):
        svc = _svc(db_session, test_user)
        _domain(svc, name="数学")
        _domain(svc, name="音乐")
        names = [d["name"] for d in svc.list_domains(test_user.id)]
        assert set(names) == {"数学", "音乐"}

    def test_update_domain(self, db_session, test_user):
        svc = _svc(db_session, test_user)
        d = _domain(svc)
        out = svc.update_domain(d["id"], {"description": "改了", "sort_order": 5})
        assert out["description"] == "改了" and out["sort_order"] == 5

    def test_update_domain_ignores_non_whitelisted(self, db_session, test_user):
        svc = _svc(db_session, test_user)
        d = _domain(svc)
        out = svc.update_domain(d["id"], {"user_id": "attacker", "name": "合法"})
        assert out["name"] == "合法"

    def test_delete_domain(self, db_session, test_user):
        from app.models.resource import Domain

        svc = _svc(db_session, test_user)
        d = _domain(svc)
        svc.delete_domain(d["id"])
        assert db_session.get(Domain, d["id"]) is None


# ============================================================
# 五、归属隔离（D1 回归 · 防 IDOR）
# ============================================================
class TestOwnershipIsolation:
    """他人数据一律 404（不是 403）—— 不泄漏"该 id 是否存在"。"""

    def test_get_foreign_inbox_404(self, db_session, test_user, other_user):
        item = _inbox(_svc(db_session, test_user), test_user)
        with pytest.raises(NotFoundException):
            _svc(db_session, other_user).get_inbox_item(item["id"])

    def test_update_foreign_inbox_404_no_side_effect(self, db_session, test_user, other_user):
        from app.models.resource import InboxItem

        item = _inbox(_svc(db_session, test_user), test_user, title="原始")
        with pytest.raises(NotFoundException):
            _svc(db_session, other_user).update_inbox_item(
                item["id"], UpdateInboxItemRequest(title="劫持"))
        assert db_session.get(InboxItem, item["id"]).title == "原始"

    def test_delete_foreign_inbox_404_no_side_effect(self, db_session, test_user, other_user):
        from app.models.resource import InboxItem

        item = _inbox(_svc(db_session, test_user), test_user)
        with pytest.raises(NotFoundException):
            _svc(db_session, other_user).delete_inbox_item(item["id"])
        assert db_session.get(InboxItem, item["id"]) is not None

    def test_process_foreign_inbox_404(self, db_session, test_user, other_user):
        item = _inbox(_svc(db_session, test_user), test_user)
        with pytest.raises(NotFoundException):
            _svc(db_session, other_user).process_inbox_item(item["id"], "archive")

    def test_apply_foreign_template_404(self, db_session, test_user, other_user):
        tpl = _template(_svc(db_session, test_user), test_user)
        with pytest.raises(NotFoundException):
            _svc(db_session, other_user).apply_template(tpl["id"], {"name": "x"})

    def test_update_foreign_template_404(self, db_session, test_user, other_user):
        from app.models.resource import Template

        tpl = _template(_svc(db_session, test_user), test_user, name="原始模板")
        with pytest.raises(NotFoundException):
            _svc(db_session, other_user).update_template(tpl["id"], {"name": "劫持"})
        assert db_session.get(Template, tpl["id"]).name == "原始模板"

    def test_delete_foreign_template_404(self, db_session, test_user, other_user):
        from app.models.resource import Template

        tpl = _template(_svc(db_session, test_user), test_user)
        with pytest.raises(NotFoundException):
            _svc(db_session, other_user).delete_template(tpl["id"])
        assert db_session.get(Template, tpl["id"]) is not None

    def test_update_foreign_domain_404(self, db_session, test_user, other_user):
        from app.models.resource import Domain

        d = _domain(_svc(db_session, test_user), test_user, name="原始领域")
        with pytest.raises(NotFoundException):
            _svc(db_session, other_user).update_domain(d["id"], {"name": "劫持"})
        assert db_session.get(Domain, d["id"]).name == "原始领域"

    def test_delete_foreign_domain_404(self, db_session, test_user, other_user):
        from app.models.resource import Domain

        d = _domain(_svc(db_session, test_user), test_user)
        with pytest.raises(NotFoundException):
            _svc(db_session, other_user).delete_domain(d["id"])
        assert db_session.get(Domain, d["id"]) is not None

    def test_lists_are_per_user(self, db_session, test_user, other_user):
        a = _svc(db_session, test_user)
        b = _svc(db_session, other_user)
        _inbox(a, test_user)
        _template(a, test_user)
        _domain(a, test_user)
        assert b.list_inbox(other_user.id)["total"] == 0
        assert b.list_templates(other_user.id)["total"] == 0
        assert b.list_domains(other_user.id) == []


# ============================================================
# 六、向后兼容（不传 user_id 的内部调用方）
# ============================================================
class TestBackwardCompatibility:

    def test_service_without_user_id_keeps_existence_only_semantics(
        self, db_session, test_user
    ):
        """dashboard_service / assistant_service 构造时不传 user_id。

        此时单条操作退化为"只查存在性"，绝不能因此抛错 —— 否则会打断
        这两个模块的既有行为。归属校验只在面向用户的 API 路径上生效。
        """
        item = _inbox(_svc(db_session, test_user), test_user)
        legacy = ResourceService(db_session)  # 不传 user_id
        assert legacy.get_inbox_item(item["id"])["id"] == item["id"]
        assert legacy.list_inbox(test_user.id)["total"] == 1

    def test_service_with_user_id_rejects_foreign_but_accepts_own(
        self, db_session, test_user
    ):
        svc = _svc(db_session, test_user)
        item = _inbox(svc, test_user)
        assert svc.get_inbox_item(item["id"])["id"] == item["id"]
