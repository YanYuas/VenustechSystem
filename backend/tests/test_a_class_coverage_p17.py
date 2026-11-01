# ============================================================
# A 类覆盖收尾（Phase17-B · 目标 missed ≤35，我的范围口径）
#
# 来源：task-63 基线 term-missing 中剔除 task-62 在途文件（core/encryption.py /
# database.py / services/task_service.py）后的 A 类缺口。本文件按 ROI 覆盖：
#   · api/workspace：scan-progress / identity skeleton 两个只读端点；
#   · api/security：rotate 失败 → 审计 ok=False + 原样重抛（500 信封）；
#   · api/vault：test-connection 的审计调用失败被吞、探测结果照常返回；
#   · project_service：里程碑不存在 404；时间线 conversation 事件；
#   · workflow_service：标签/模板创建失败被记录为 details、不中断整体应用；
#   · plugin_manager：插件模块导入失败 → load() 返回 False + exception 日志；
#   · security_service：轮换时跳过无法解密的 settings 密文（不拖垮整次轮换）；
#   · learning_service：周模式计划落任务（标题带序号、截止日对齐周起始）；
#   · models/types：StringListType 绑定 None 原样返回 None；
#   · models/settings_history：mask_value(key, None) 返回 None；
#   · api/assistant：status 端点（`_svc` 工厂接线）；
#   · growth_service：get_level 极低经验兜底为 1 级；
#   · 9 个 repository 单行语义方法 + settings upsert 复活软删行 + audit 空修剪。
#
# 已确认的 **bug-blocked** 行（不在本文件断言，只记录）：
#   project_service.py:319 `r.title` —— Review 模型没有 title 列，项目时间线在
#   存在复盘记录时必抛 AttributeError（已实测复现），属真 bug，见报告。
# ============================================================
from __future__ import annotations

import json
import logging
import types
from datetime import date

import pytest

from app.api import security as security_api
from app.core.exceptions import NotFoundException
from app.core.plugin_manager import PluginManager
from app.database import SessionLocal
from app.models.base import utcnow
from app.models.settings_history import mask_value
from app.models.types import StringListType
from app.models.vault import VaultItem
from app.repositories import (
    AuditLogRepository,
    ConversationRepository,
    DomainRepository,
    FlashcardRepository,
    ProjectMemoryRepository,
    ProjectRepository,
    PromptRepository,
    SettingRepository,
    SOPRepository,
    TaskRepository,
    TemplateRepository,
    WorkflowRepository,
)
from app.schemas.learning import ApplyPlanRequest
from app.schemas.project import MilestoneUpdate
from app.schemas.workflow import ApplyWorkflowRequest
from app.services import security_service as security_svc_mod
from app.services.learning_service import LearningService
from app.services.project_service import ProjectService
from app.services.security_service import SecurityService
from app.services.workflow_service import WorkflowService
from tests.factories import make_project_memory, make_sop, make_workspace_root


def _boom(*_args, **_kwargs):
    raise RuntimeError("probe: 故障注入")


# ================================================================
# 一、API 单行/防御分支
# ================================================================
class TestApiStragglers:
    def test_workspace_scan_progress_and_skeleton_endpoints(
        self, client, default_user_id, db_session, tmp_path
    ):
        ws_dir = tmp_path / "ws-root"
        ws_dir.mkdir()
        root = make_workspace_root(db_session, default_user_id, path=str(ws_dir))
        db_session.commit()

        progress = client.get(f"/api/v1/workspace/roots/{root.id}/scan-progress")
        assert progress.status_code == 200, progress.text
        body = progress.json()
        assert body["code"] == 0
        assert body["data"]["root_id"] == root.id
        assert "status" in body["data"] and "phase" in body["data"]

        skeleton = client.post(f"/api/v1/workspace/roots/{root.id}/skeleton")
        assert skeleton.status_code == 200, skeleton.text
        data = skeleton.json()["data"]
        assert set(data) == {"root_id", "created", "skipped"}   # 骨架生成结果结构

    def test_rotate_failure_is_audited_and_reraised(
        self, client, default_user_id, monkeypatch
    ):
        from app.services import vault_service

        class _RotateBoom:
            def __init__(self, db, user_id):
                pass

            def rotate_key(self, new_master_key=None):
                _boom()

        monkeypatch.setattr(security_api, "SecurityService", _RotateBoom)
        vault_service._session_keys[default_user_id] = b"unlocked"
        try:
            # 统一异常处理器返回 500 信封后，Starlette 的 ServerErrorMiddleware
            # 会把原异常重新抛出（TestClient 默认 raise_server_exceptions=True）。
            with pytest.raises(RuntimeError, match="probe: 故障注入"):
                client.post("/api/v1/security/key/rotate", json={})
        finally:
            vault_service._session_keys.pop(default_user_id, None)

        db = SessionLocal()
        try:
            rows = AuditLogRepository(db).list_user(default_user_id, limit=10)
        finally:
            db.close()
        failed = [a for a in rows if a.action == "security.rotate_key"]
        assert failed and failed[0].ok is False
        assert "probe: 故障注入" in (failed[0].detail or "")

    def test_vault_test_connection_audit_failure_is_swallowed(
        self, client, default_user_id, db_session, monkeypatch
    ):
        item = VaultItem(
            user_id=default_user_id, name="探测用 SSH", category="login",
            action_type="ssh", action_host="127.0.0.1", action_port="1",
        )
        db_session.add(item)
        db_session.commit()
        monkeypatch.setattr(security_svc_mod, "audit", _boom)

        r = client.post(f"/api/v1/vault/items/{item.id}/test-connection")

        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert data["host"] == "127.0.0.1"
        assert data["port"] == 1
        assert data["reachable"] is False      # 端口 1 拒绝连接（快速失败，不联网外网）

    def test_assistant_status_endpoint(self, client):
        r = client.get("/api/v1/assistant/status")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["code"] == 0
        assert "configured" in body["data"]


# ================================================================
# 二、service 降级 / 边界分支
# ================================================================
class TestServiceStragglers:
    def test_project_timeline_includes_conversation_event(self, db_session, test_user):
        project = ProjectRepository(db_session).create(user_id=test_user.id, name="时间线项目")
        db_session.commit()
        ConversationRepository(db_session).create(
            user_id=test_user.id, title="项目会话", project_id=project.id)
        db_session.commit()

        events = ProjectService(db_session).timeline(test_user.id, project.id)

        conversation_events = [e for e in events if e["type"] == "conversation"]
        assert len(conversation_events) == 1
        assert conversation_events[0]["title"] == "AI对话：项目会话"

    def test_update_milestone_unknown_is_not_found(self, db_session, test_user):
        with pytest.raises(NotFoundException, match="里程碑不存在"):
            ProjectService(db_session).update_milestone(
                test_user.id, "ghost-milestone", MilestoneUpdate())

    def test_apply_workflow_records_tag_and_template_failures(
        self, db_session, test_user, monkeypatch
    ):
        workflow = WorkflowRepository(db_session).create(
            name="故障工作流", category="study",
            is_preset=False, is_active=True,
            config={"tag_system": {"学习": ["英语"]}, "doc_templates": ["模板A"]},
        )
        db_session.commit()
        svc = WorkflowService(db_session)
        monkeypatch.setattr(svc.domain_repo, "create", _boom)
        monkeypatch.setattr(svc.template_repo, "create", _boom)

        result = svc.apply_workflow(
            test_user.id, workflow.id, ApplyWorkflowRequest(params={}))

        assert result["domains_created"] == 0
        assert result["templates_created"] == 0
        assert any("标签创建失败: 英语" in d for d in result["details"])
        assert any("模板创建失败: 模板A" in d for d in result["details"])

    def test_plugin_load_failure_returns_false_and_logs(
        self, tmp_path, caplog
    ):
        plugin_dir = tmp_path / "plugins" / "p17broken"
        plugin_dir.mkdir(parents=True)
        (plugin_dir / "plugin.json").write_text(
            json.dumps({"id": "p17broken", "name": "坏插件", "version": "1.0.0"}),
            encoding="utf-8",
        )
        (plugin_dir / "main.py").write_text(
            "raise RuntimeError('boom at import')\n", encoding="utf-8")
        PluginManager.discover(tmp_path / "plugins")
        try:
            with caplog.at_level(logging.ERROR):
                assert PluginManager.load("p17broken") is False
            assert "插件加载失败: p17broken" in caplog.text
        finally:
            PluginManager._plugins.pop("p17broken", None)
            PluginManager._instances.pop("p17broken", None)

    def test_rotate_skips_undecryptable_settings_ciphertext(
        self, db_session, test_user, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(
            security_svc_mod, "get_settings",
            lambda: types.SimpleNamespace(data_dir=tmp_path))
        monkeypatch.setattr(security_svc_mod, "get_encryption", lambda: None)
        SettingRepository(db_session).upsert(
            test_user.id, "assistant.deepseek_key", "not-a-fernet-token")
        db_session.commit()

        result = SecurityService(db_session, test_user.id).rotate_key()

        assert result["rotated"] == 0
        assert result["tables"] == []          # 坏密文被跳过，未算入任何表
        assert result["details"] == {}

    def test_learning_weekly_plan_suffix_and_week_due(self, db_session, test_user):
        start = date.today()
        result = LearningService(db_session).apply_generated_plan(
            test_user.id, ApplyPlanRequest(goal="我想学雅思", total_days=90,
                                           minutes_per_day=60))

        assert result["preview"]["weekly_mode"] is True
        tasks = TaskRepository(db_session).list_user_tasks(test_user.id)
        assert tasks
        assert any("（1）" in t.title for t in tasks)      # 同周多条加序号
        for task in tasks:
            assert task.due_date is not None
            assert (task.due_date - start).days % 7 == 0   # 截止日对齐周起始
            assert (task.due_date - start).days >= 0


# ================================================================
# 三、模型 / 工具函数 / 仓库单行方法
# ================================================================
class TestModelAndRepoStragglers:
    def test_string_list_type_binds_none_as_none(self):
        assert StringListType().process_bind_param(None, None) is None
        assert StringListType().process_bind_param(["a", "b"], None) == '["a", "b"]'

    def test_mask_value_none_returns_none(self):
        assert mask_value("assistant.deepseek_key", None) is None
        assert mask_value("assistant.deepseek_key", "sk-123456") == "sk-***"

    def test_get_level_falls_back_to_one(self):
        from app.services.growth_service import get_level

        assert get_level(-1) == 1
        assert get_level(0) == 1

    def test_repository_single_line_semantic_methods(self, db_session, test_user):
        domain = DomainRepository(db_session).create(user_id=test_user.id, name="领域A")
        workflow = WorkflowRepository(db_session).create(
            name="用户工作流", is_preset=False, is_active=True)
        template = TemplateRepository(db_session).create(
            user_id=test_user.id, name="模板A", category="doc", content="正文")
        sop = make_sop(db_session, test_user.id, name="SOP-A")
        prompt = PromptRepository(db_session).create(user_id=test_user.id, name="Prompt-A")
        card = FlashcardRepository(db_session).create(
            user_id=test_user.id, front="问", back="答")
        db_session.commit()

        assert [d.id for d in DomainRepository(db_session).list_by_user(
            test_user.id)] == [domain.id]
        assert DomainRepository(db_session).count_by_user(test_user.id) == 1
        assert [w.id for w in WorkflowRepository(db_session).list_by_user(
            test_user.id)] == [workflow.id]
        assert [t.id for t in TemplateRepository(db_session).list_by_user(
            test_user.id)] == [template.id]
        assert [s.id for s in SOPRepository(db_session).list_by_user(
            test_user.id)] == [sop.id]
        assert [p.id for p in PromptRepository(db_session).list_by_user(
            test_user.id)] == [prompt.id]
        assert [c.id for c in FlashcardRepository(db_session).list_by_user(
            test_user.id)] == [card.id]
        assert [d.id for d in DomainRepository(db_session).list_ordered(
            test_user.id)] == [domain.id]
        assert len(TemplateRepository(db_session).list_by_category(
            test_user.id, "doc")) == 1

    def test_settings_upsert_revives_soft_deleted_row(self, db_session, test_user):
        repo = SettingRepository(db_session)
        row = repo.upsert(test_user.id, "notify.task", "true")
        db_session.commit()
        row = SettingRepository(db_session).get_by_key(test_user.id, "notify.task")
        row.deleted_at = utcnow()
        db_session.commit()

        revived = repo.upsert(test_user.id, "notify.task", "false")
        db_session.commit()

        assert revived.id == row.id
        assert revived.deleted_at is None          # 软删行被复活
        assert revived.value == "false"

    def test_project_memory_list_and_audit_empty_trim(self, db_session, test_user):
        project = ProjectRepository(db_session).create(user_id=test_user.id, name="记忆项目")
        db_session.commit()
        memory = make_project_memory(db_session, test_user.id, name="项目记忆A",
                                     project_id=project.id)
        db_session.commit()

        assert [m.id for m in ProjectMemoryRepository(db_session).list_by_project(
            project.id)] == [memory.id]
        assert AuditLogRepository(db_session).delete_by_ids([]) is None
