# ============================================================
# WorkflowService 生产级测试（原缺失模块，本轮补齐）
#
# 为什么这个模块值得单独一层测试：
#   「一键应用工作流」是一次**跨 4 张表的写操作**
#   （domains / templates / tasks / workflow_applications），
#   而且每一类创建都包在 try/except 里 —— 「静默失败」是它的默认失败模式：
#   异常被吞进 results["details"]，接口照样返回 code=0。
#
# 2026-10-11 补测时实测到两个真实缺陷，本文件均留了回归断言：
#   ① 生成的任务 status="todo"（非法状态）→ 任何流转都报 3001，任务永久卡死；
#   ② 标签 / 模板的去重查询未带 user_id → 别人有同名领域时，本用户静默不创建。
# ============================================================
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.exceptions import NotFoundException
from app.models.resource import Domain, Template
from app.models.task import Task
from app.models.workflow import Workflow, WorkflowApplication
from app.schemas.task import UpdateTaskRequest
from app.schemas.workflow import ApplyWorkflowRequest, CreateWorkflowRequest
from app.services.task_service import STATUS_TRANSITIONS, TaskService
from app.services.workflow_service import WorkflowService
from tests.factories import count_rows


# 一份「真实形态」的工作流配置：标签体系 2 个 + 文档模板 1 个 + 任务模板 2 个。
# 计数断言全部基于这份配置，改内容必须同步改期望值（形状契约）。
WF_CONFIG = {
    "tag_system": {"study": ["阅读", "笔记"]},
    "doc_templates": ["读书笔记模板"],
    "task_templates": [
        {"name": "选书", "steps": ["列书单", "定优先级"]},
        {"name": "读书", "steps": ["每天 30 分钟"]},
    ],
}
WF_TAG_COUNT = 2
WF_TEMPLATE_COUNT = 1
WF_TASK_COUNT = 2


def _svc(db) -> WorkflowService:
    return WorkflowService(db)


def _make_wf(db, **overrides) -> dict:
    """经 Service 建一条自定义工作流，返回序列化后的 dict（含 id）。"""
    payload = {"name": "读书计划", "category": "study", "config": WF_CONFIG}
    payload.update(overrides)
    return _svc(db).create_workflow("ignored", CreateWorkflowRequest(**payload))


def _make_preset(db, name: str = "预设·考研") -> Workflow:
    """预设工作流不能经 CreateWorkflowRequest 建（schema 无 is_preset 字段），直接落库。"""
    wf = Workflow(name=name, category="study", config={}, is_preset=True, is_active=True)
    db.add(wf)
    db.flush()
    return wf


def _make_domain(db, user_id: str, name: str) -> Domain:
    d = Domain(user_id=user_id, name=name, icon="🏷️", color="#8B5CF6", sort_order=0)
    db.add(d)
    db.flush()
    return d


class TestWorkflowCrud:
    """工作流 CRUD 与列表语义。"""

    def test_create_persists_and_returns_shape(self, db_session):
        """创建后落库，返回结构含全部契约字段（前端依赖 config/is_active/use_count）。"""
        out = _make_wf(db_session)

        assert set(out) >= {
            "id", "name", "description", "icon", "category", "scenario",
            "config", "is_preset", "is_active", "use_count",
            "created_at", "updated_at",
        }
        assert out["name"] == "读书计划"
        assert out["category"] == "study"
        assert out["is_preset"] is False
        assert out["is_active"] is True
        assert out["use_count"] == 0
        # config 是 JSON 列，必须原样往返（嵌套 dict/list 不得被压平）
        assert out["config"] == WF_CONFIG

        assert count_rows(db_session, "workflows", id=out["id"]) == 1
        row = db_session.get(Workflow, out["id"])
        assert row.config["task_templates"][0]["steps"] == ["列书单", "定优先级"]

    def test_list_filters_out_inactive(self, db_session):
        """list_workflows 只返回 is_active=True 的（停用即从列表消失，但详情仍可取）。"""
        a = _make_wf(db_session, name="A")
        b = _make_wf(db_session, name="B")
        _svc(db_session).update_workflow(b["id"], {"is_active": False})

        visible = _svc(db_session).list_workflows()["list"]
        assert [w["name"] for w in visible] == ["A"]
        # 停用不等于删除：详情仍应可读
        assert _svc(db_session).get_workflow(b["id"])["is_active"] is False
        assert a["id"] != b["id"]

    def test_list_category_filter_and_pagination(self, db_session):
        """分类筛选与分页计数一致（total 来自 SQL COUNT，不受 page_size 影响）。"""
        for i in range(3):
            _make_wf(db_session, name=f"学习{i}", category="study")
        _make_wf(db_session, name="写作", category="writing")

        got = _svc(db_session).list_workflows(category="study", page=1, page_size=2)
        assert got["total"] == 3
        assert len(got["list"]) == 2
        assert got["page"] == 1 and got["page_size"] == 2
        assert all(w["category"] == "study" for w in got["list"])

    def test_list_presets_only_returns_presets(self, db_session):
        """预设列表与自定义列表互不混入。"""
        _make_preset(db_session, name="预设·考研")
        _make_wf(db_session, name="我建的")

        presets = _svc(db_session).list_presets()
        assert presets["total"] == 1
        assert presets["list"][0]["name"] == "预设·考研"
        assert presets["list"][0]["is_preset"] is True

    def test_get_unknown_raises_404(self, db_session):
        with pytest.raises(NotFoundException):
            _svc(db_session).get_workflow("no-such-workflow")

    def test_update_partial_does_not_touch_other_fields(self, db_session):
        """PATCH 语义：只改传入字段，未传字段保持原值。"""
        wf = _make_wf(db_session, description="原描述")
        out = _svc(db_session).update_workflow(wf["id"], {"name": "读书计划 v2"})

        assert out["name"] == "读书计划 v2"
        assert out["description"] == "原描述"
        assert out["category"] == "study"
        assert out["config"] == WF_CONFIG

    def test_update_cannot_clear_field_with_none(self, db_session):
        """契约说明（非缺陷，但必须写下来）：

        更新走 `{k: v for k, v in data.items() if v is not None}` 过滤，
        因此 **无法用 null 把字段清空** —— 想清空只能传空串。
        这里把当前语义钉死，避免以后有人"顺手改成 dict.get"而静默改变 API 行为。
        """
        wf = _make_wf(db_session, description="不该被清掉")
        out = _svc(db_session).update_workflow(wf["id"], {"description": None, "name": "改名"})

        assert out["name"] == "改名"
        assert out["description"] == "不该被清掉"

    def test_delete_removes_row(self, db_session):
        wf = _make_wf(db_session)
        _svc(db_session).delete_workflow(wf["id"])

        assert count_rows(db_session, "workflows", id=wf["id"]) == 0
        with pytest.raises(NotFoundException):
            _svc(db_session).get_workflow(wf["id"])

    def test_delete_unknown_raises_404(self, db_session):
        with pytest.raises(NotFoundException):
            _svc(db_session).delete_workflow("no-such-workflow")


class TestApplyWorkflowEngine:
    """一键应用引擎：跨 4 张表的写操作。"""

    def test_apply_creates_everything_and_records_history(self, db_session, test_user):
        """一次应用：标签 + 模板 + 任务全部落地，并写一条应用历史。

        断言全部对齐真实落库行数（不是只看返回的计数）——
        返回计数与实际行数不一致正是这类"批量创建"最容易出的问题。
        """
        wf = _make_wf(db_session)
        res = _svc(db_session).apply_workflow(
            test_user.id, wf["id"], ApplyWorkflowRequest(params={"name": "考研"})
        )

        assert res["workflow_name"] == "读书计划"
        assert res["domains_created"] == WF_TAG_COUNT
        assert res["templates_created"] == WF_TEMPLATE_COUNT
        assert res["tasks_created"] == WF_TASK_COUNT
        assert res["details"] == [], f"不应有静默失败: {res['details']}"

        # —— 落库核对（返回计数 ↔ 真实行数必须一致）——
        assert count_rows(db_session, "domains", user_id=test_user.id) == WF_TAG_COUNT
        assert count_rows(db_session, "templates", user_id=test_user.id) == WF_TEMPLATE_COUNT
        assert count_rows(db_session, "tasks", user_id=test_user.id) == WF_TASK_COUNT

        domain_names = {d.name for d in db_session.scalars(
            select(Domain).where(Domain.user_id == test_user.id))}
        assert domain_names == {"阅读", "笔记"}

        # —— 任务形态：标题带项目名前缀、状态合法、描述含步骤链 ——
        tasks = list(db_session.scalars(select(Task).where(Task.user_id == test_user.id)))
        titles = {t.title for t in tasks}
        assert titles == {"[考研] 选书", "[考研] 读书"}
        pick = next(t for t in tasks if t.title.endswith("选书"))
        assert pick.status == "pending"
        assert pick.priority == "medium"
        assert pick.project_tag == "study"          # 取工作流 category
        assert "由「读书计划」工作流自动创建" in pick.description
        assert "步骤: 列书单 → 定优先级" in pick.description

        # —— 使用计数 + 应用历史 ——
        wf_row = db_session.get(Workflow, wf["id"])
        assert wf_row.use_count == 1
        apps = list(db_session.scalars(
            select(WorkflowApplication).where(WorkflowApplication.user_id == test_user.id)))
        assert len(apps) == 1
        assert apps[0].status == "completed"
        assert apps[0].params == {"name": "考研"}
        assert res["application_id"] == apps[0].id
        assert res["summary"] == apps[0].result_summary
        assert "创建2个标签" in apps[0].result_summary
        assert "1个模板" in apps[0].result_summary
        assert "2个任务" in apps[0].result_summary

    def test_generated_tasks_pass_the_state_machine(self, db_session, test_user):
        """回归（2026-10-11）：生成的任务必须能正常流转，不得 3001 永久卡死。

        原缺陷：任务以 status="todo" 落库。"todo" 不在 STATUS_TRANSITIONS 中，
        `STATUS_TRANSITIONS.get("todo", set())` 是空集 → 任何流转都被判非法
        （BusinessException 3001），且按状态过滤的列表永远查不到这些任务。

        这条测试刻意走**用户真实路径**（应用 → 开始做 → 完成），而不是只断言
        `status == "pending"` 字符串 —— 后者在状态机常量表改名后依然会通过。
        """
        wf = _make_wf(db_session)
        _svc(db_session).apply_workflow(test_user.id, wf["id"], ApplyWorkflowRequest())

        tasks = list(db_session.scalars(select(Task).where(Task.user_id == test_user.id)))
        assert len(tasks) == WF_TASK_COUNT
        # 前置：状态必须是状态机认识的键（空集即意味着卡死）
        for t in tasks:
            assert t.status in STATUS_TRANSITIONS
            assert STATUS_TRANSITIONS[t.status], f"{t.status} 无可达状态"

        task_svc = TaskService(db_session)
        for t in tasks:
            task_svc.update(test_user.id, t.id, UpdateTaskRequest(status="in_progress"))
            task_svc.update(test_user.id, t.id, UpdateTaskRequest(status="completed"))
            db_session.refresh(t)
            assert t.status == "completed"

    def test_task_title_prefix_defaults_to_workflow_name(self, db_session, test_user):
        """未传 params.name 时，前缀回落为工作流名（前端不传参数也不会得到空标题）。"""
        wf = _make_wf(db_session)
        _svc(db_session).apply_workflow(test_user.id, wf["id"], ApplyWorkflowRequest())

        titles = {t.title for t in db_session.scalars(
            select(Task).where(Task.user_id == test_user.id))}
        assert titles == {"[读书计划] 选书", "[读书计划] 读书"}

    def test_task_title_prefix_prefers_project_name(self, db_session, test_user):
        """params 同时给 name / project_name 时，name 优先。"""
        wf = _make_wf(db_session)
        _svc(db_session).apply_workflow(
            test_user.id, wf["id"],
            ApplyWorkflowRequest(params={"name": "考研", "project_name": "备用名"}),
        )
        titles = {t.title for t in db_session.scalars(
            select(Task).where(Task.user_id == test_user.id))}
        assert titles == {"[考研] 选书", "[考研] 读书"}

    def test_apply_twice_does_not_duplicate_domains_or_templates(self, db_session, test_user):
        """幂等性：标签 / 模板按名字去重，任务不去重（每次应用都要新任务）。"""
        wf = _make_wf(db_session)
        first = _svc(db_session).apply_workflow(test_user.id, wf["id"], ApplyWorkflowRequest())
        second = _svc(db_session).apply_workflow(test_user.id, wf["id"], ApplyWorkflowRequest())

        assert first["domains_created"] == WF_TAG_COUNT
        assert second["domains_created"] == 0
        assert second["templates_created"] == 0
        assert second["tasks_created"] == WF_TASK_COUNT  # 任务不去重（有意为之）

        assert count_rows(db_session, "domains", user_id=test_user.id) == WF_TAG_COUNT
        assert count_rows(db_session, "templates", user_id=test_user.id) == WF_TEMPLATE_COUNT
        assert count_rows(db_session, "tasks", user_id=test_user.id) == WF_TASK_COUNT * 2
        assert db_session.get(Workflow, wf["id"]).use_count == 2
        # 历史每次应用都记一条（供"最近用过什么工作流"回溯）
        assert count_rows(db_session, "workflow_applications", user_id=test_user.id) == 2

    def test_dedup_is_scoped_per_user(self, db_session, test_user, other_user):
        """回归（2026-10-11）：去重必须带 user_id，否则会被**别人的同名数据**挡住。

        原缺陷：`domain_repo.list(name=tag)` / `template_repo.list(name=name)`
        是不带 user_id 的全局查询。只要库里任何一个人已有同名领域（如"阅读"），
        当前用户应用工作流时 domains_created 就会是 0 —— 标签静默不创建、无报错。
        """
        _make_domain(db_session, other_user.id, "阅读")   # 别人已经有"阅读"
        other_tpl = Template(user_id=other_user.id, name="读书笔记模板",
                             category="study", content="x", variables=[])
        db_session.add(other_tpl)
        db_session.flush()

        wf = _make_wf(db_session)
        res = _svc(db_session).apply_workflow(test_user.id, wf["id"], ApplyWorkflowRequest())

        assert res["domains_created"] == WF_TAG_COUNT, f"被他人同名标签挡住: {res['details']}"
        assert res["templates_created"] == WF_TEMPLATE_COUNT
        mine = {d.name for d in db_session.scalars(
            select(Domain).where(Domain.user_id == test_user.id))}
        assert mine == {"阅读", "笔记"}
        # 他人数据不得被改写 / 删除
        assert count_rows(db_session, "domains", user_id=other_user.id) == 1
        assert count_rows(db_session, "templates", user_id=other_user.id) == 1

    def test_apply_with_empty_config_creates_nothing_but_still_records(self, db_session, test_user):
        """空配置工作流：不创建任何东西，但不能报错，且仍要记使用次数与历史。"""
        wf = _make_wf(db_session, config={})
        res = _svc(db_session).apply_workflow(test_user.id, wf["id"], ApplyWorkflowRequest())

        assert res["domains_created"] == 0
        assert res["templates_created"] == 0
        assert res["tasks_created"] == 0
        assert res["details"] == []
        assert db_session.get(Workflow, wf["id"]).use_count == 1
        assert count_rows(db_session, "workflow_applications", user_id=test_user.id) == 1

    def test_broken_task_template_is_reported_not_swallowed(self, db_session, test_user):
        """失败可见性：坏模板被 try/except 吞掉，但必须留下 details 证据。

        `tpl['name']` 取不到会 KeyError；该异常被 `except Exception` 捕获。
        若只断言「接口成功」，用户会在"应用成功但什么都没生成"里迷路 ——
        所以这里断言错误被写进 details（这是该模块唯一的失败信号通道）。
        """
        wf = _make_wf(db_session, config={
            "task_templates": [{"name": "正常的", "steps": []}, {"steps": ["缺 name 键"]}],
        })
        res = _svc(db_session).apply_workflow(test_user.id, wf["id"], ApplyWorkflowRequest())

        assert res["tasks_created"] == 1
        assert len(res["details"]) == 1
        assert "任务创建失败" in res["details"][0]
        # 一条失败不阻断其余写入与历史记录
        assert count_rows(db_session, "workflow_applications", user_id=test_user.id) == 1

    def test_apply_unknown_workflow_raises_404(self, db_session, test_user):
        with pytest.raises(NotFoundException):
            _svc(db_session).apply_workflow(test_user.id, "no-such-wf", ApplyWorkflowRequest())


class TestApplicationHistory:
    """应用历史列表：按用户隔离 + 分页。"""

    def test_history_isolated_per_user(self, db_session, test_user, other_user):
        wf = _make_wf(db_session)
        _svc(db_session).apply_workflow(test_user.id, wf["id"], ApplyWorkflowRequest())
        _svc(db_session).apply_workflow(other_user.id, wf["id"], ApplyWorkflowRequest())

        mine = _svc(db_session).list_applications(test_user.id)
        assert mine["total"] == 1
        assert mine["list"][0]["user_id"] == test_user.id

        theirs = _svc(db_session).list_applications(other_user.id)
        assert theirs["total"] == 1
        assert theirs["list"][0]["user_id"] == other_user.id

    def test_history_pagination_and_shape(self, db_session, test_user):
        wf = _make_wf(db_session, config={})
        for _ in range(3):
            _svc(db_session).apply_workflow(test_user.id, wf["id"], ApplyWorkflowRequest())

        page1 = _svc(db_session).list_applications(test_user.id, page=1, page_size=2)
        assert page1["total"] == 3
        assert len(page1["list"]) == 2
        assert set(page1["list"][0]) == {
            "id", "workflow_id", "user_id", "params", "status", "result_summary", "applied_at",
        }
        page2 = _svc(db_session).list_applications(test_user.id, page=2, page_size=2)
        assert len(page2["list"]) == 1
        # 两页不重复
        ids = {a["id"] for a in page1["list"]} | {a["id"] for a in page2["list"]}
        assert len(ids) == 3
