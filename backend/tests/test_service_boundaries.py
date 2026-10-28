# ============================================================
# Phase5 · service 边界分支测试 + ADR-0008 端到端 null 语义
#
# 覆盖缺口（Phase5 基线）：
#   app/api/workspace.py 76.3% / app/services/workspace_service.py 23.3%
#   app/services/sync/adapters.py 0.0% / app/services/ai/ai_service.py 24.2%
#   app/services/avatar_service.py 30.8% / app/core/plugin_manager.py 69.1%
#
# 约定：只走 conftest fixtures（client / default_user_id / db_session / test_user）；
# 文件系统操作全部落在 VENUSTECH_TEST_DATA_DIR 内并在用例结束后清理。
# ============================================================
from __future__ import annotations

from dataclasses import FrozenInstanceError

import asyncio
import json
import shutil
import time
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.config import get_settings
from app.core import plugin_manager as pm
from app.core.exceptions import NotFoundException
from app.services.ai import AIService
from app.services.ai.client import MockLLMClient, get_llm_client
from app.services.avatar_service import AvatarService
from app.services.sync import adapters as sync_adapters
from app.services.sync.adapters import (
    LocalDirAdapter,
    RemoteObject,
    SyncAdapter,
    available_adapters,
    get_adapter,
    register_adapter,
)


def _data_dir() -> Path:
    return Path(get_settings().data_dir)


def _ok(resp) -> dict:
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["code"] == 0, body
    return body["data"]


def _tmp_dir(prefix: str) -> Path:
    path = _data_dir() / f"{prefix}-{uuid.uuid4().hex[:8]}"
    path.mkdir(parents=True, exist_ok=False)
    return path


# ================================================================
# 一、workspace API / service 边界
# ================================================================
class TestWorkspaceBoundaries:
    def test_status_defaults_to_disabled(self, client):
        data = _ok(client.get("/api/v1/workspace/status"))
        assert data["enabled"] is False
        assert data["roots_count"] >= 0
        assert isinstance(data["terminal"], str)

    def test_register_relative_path_rejected(self, client):
        resp = client.post("/api/v1/workspace/roots", json={"path": "relative/dir"})
        body = resp.json()
        assert resp.status_code == 400
        assert "必须是绝对路径" in body["message"]

    def test_register_empty_path_rejected_by_schema(self, client):
        resp = client.post("/api/v1/workspace/roots", json={"path": ""})
        assert resp.status_code == 400
        assert resp.json()["code"] == 1001

    def test_register_missing_directory_rejected(self, client):
        missing = _data_dir() / f"missing-{uuid.uuid4().hex[:8]}"
        resp = client.post("/api/v1/workspace/roots", json={"path": str(missing)})
        assert resp.status_code == 400
        assert "目录不存在" in resp.json()["message"]

    def test_register_filesystem_root_rejected(self, client):
        root = Path.cwd().anchor  # Windows: "D:\\"；POSIX: "/"
        resp = client.post("/api/v1/workspace/roots", json={"path": root})
        assert resp.status_code == 400
        assert "文件系统根" in resp.json()["message"]

    def test_register_valid_dir_and_duplicate_rejected(self, client):
        directory = _tmp_dir("ws-root")
        try:
            data = _ok(client.post("/api/v1/workspace/roots", json={"path": str(directory)}))
            assert Path(data["path"]) == directory.resolve()
            assert data["enabled"] is True
            assert isinstance(data["scan_status"], str)  # 未扫描时为 "never"
            assert data["file_count"] == 0

            again = client.post("/api/v1/workspace/roots", json={"path": str(directory)})
            assert again.status_code == 400
            assert "该路径已登记" in again.json()["message"]

            roots = _ok(client.get("/api/v1/workspace/roots"))
            assert any(r["id"] == data["id"] for r in roots)
        finally:
            shutil.rmtree(directory, ignore_errors=True)

    def test_update_unknown_root_returns_404(self, client):
        resp = client.patch(f"/api/v1/workspace/roots/{uuid.uuid4()}", json={"label": "x"})
        assert resp.status_code == 404
        assert resp.json()["code"] == 1002
        assert "工作区根不存在" in resp.json()["message"]

    def test_delete_unknown_root_returns_404(self, client):
        resp = client.delete(f"/api/v1/workspace/roots/{uuid.uuid4()}")
        assert resp.status_code == 404
        assert resp.json()["code"] == 1002

    def test_list_files_unknown_root_returns_404(self, client):
        resp = client.get("/api/v1/workspace/files", params={"root_id": str(uuid.uuid4())})
        assert resp.status_code == 404
        assert resp.json()["code"] == 1002

    def test_scan_disabled_root_rejected(self, client):
        directory = _tmp_dir("ws-disabled")
        try:
            root = _ok(client.post("/api/v1/workspace/roots", json={"path": str(directory)}))
            _ok(client.patch(f"/api/v1/workspace/roots/{root['id']}", json={"enabled": False}))
            resp = client.post(f"/api/v1/workspace/roots/{root['id']}/scan")
            assert resp.status_code == 400
            assert "根已停用" in resp.json()["message"]
        finally:
            shutil.rmtree(directory, ignore_errors=True)

    def test_open_terminal_outside_enabled_roots_rejected(self, client):
        _ok(client.put("/api/v1/workspace/enabled", json={"enabled": True}))
        outside = _tmp_dir("ws-outside")
        try:
            resp = client.post("/api/v1/workspace/open-terminal", json={"path": str(outside)})
            assert resp.status_code == 400
            assert "安全白名单拦截" in resp.json()["message"]
        finally:
            shutil.rmtree(outside, ignore_errors=True)


# ================================================================
# 二、sync adapters 契约（0% 覆盖模块）
# ================================================================
class TestSyncAdapters:
    @pytest.fixture()
    def adapter_dir(self):
        directory = _tmp_dir("adapter")
        yield directory
        shutil.rmtree(directory, ignore_errors=True)

    def test_push_returns_remote_object_and_writes_bytes(self, adapter_dir):
        adapter = LocalDirAdapter(adapter_dir)
        obj = adapter.push(b'{"user_id": "u1"}', "pkg-a.json")
        assert isinstance(obj, RemoteObject)
        assert obj.key == "pkg-a.json"
        assert obj.size == len(b'{"user_id": "u1"}')
        assert obj.user_id == "u1"
        assert (adapter_dir / "pkg-a.json").read_bytes() == b'{"user_id": "u1"}'

    def test_push_same_key_is_idempotent_overwrite(self, adapter_dir):
        adapter = LocalDirAdapter(adapter_dir)
        adapter.push(b"v1", "pkg.json")
        obj = adapter.push(b"v2-longer", "pkg.json")
        assert obj.size == len(b"v2-longer")
        assert len(list(adapter_dir.glob("*.json"))) == 1
        assert adapter.pull("pkg.json") == b"v2-longer"

    def test_pull_roundtrip_and_missing_key(self, adapter_dir):
        adapter = LocalDirAdapter(adapter_dir)
        adapter.push(b"payload", "roundtrip.json")
        assert adapter.pull("roundtrip.json") == b"payload"
        with pytest.raises(KeyError):
            adapter.pull("missing.json")

    def test_list_objects_sorted_desc_and_parses_user_id(self, adapter_dir):
        adapter = LocalDirAdapter(adapter_dir)
        adapter.push(json.dumps({"user_id": "u-old"}).encode("utf-8"), "old.json")
        time.sleep(0.01)
        adapter.push(json.dumps({"user_id": "u-new"}).encode("utf-8"), "new.json")
        items = adapter.list_objects()
        assert [o.key for o in items] == ["new.json", "old.json"]
        assert items[0].user_id == "u-new"

    def test_list_objects_handles_invalid_json(self, adapter_dir):
        adapter = LocalDirAdapter(adapter_dir)
        adapter.push(b"not-json", "broken.json")
        items = adapter.list_objects()
        assert items[0].user_id is None

    def test_delete_is_idempotent(self, adapter_dir):
        adapter = LocalDirAdapter(adapter_dir)
        adapter.push(b"x", "gone.json")
        assert adapter.delete("gone.json") is True
        assert adapter.delete("gone.json") is False

    def test_constructor_creates_missing_directory(self):
        directory = _data_dir() / f"adapter-created-{uuid.uuid4().hex[:8]}"
        try:
            assert not directory.exists()
            LocalDirAdapter(directory)
            assert directory.is_dir()
        finally:
            shutil.rmtree(directory, ignore_errors=True)

    def test_register_adapter_and_get_instance(self, adapter_dir, monkeypatch):
        monkeypatch.setattr(sync_adapters, "_ADAPTERS", dict(sync_adapters._ADAPTERS))

        class MyAdapter(SyncAdapter):
            name = "phase5-custom"

            def push(self, payload, key):
                return RemoteObject(key=key, size=len(payload), modified_at="2026-01-01")

            def pull(self, key):
                return b""

            def list_objects(self):
                return []

            def delete(self, key):
                return False

        register_adapter("phase5-custom", MyAdapter)
        assert "phase5-custom" in available_adapters()
        assert isinstance(get_adapter("phase5-custom"), MyAdapter)
        assert issubclass(MyAdapter, SyncAdapter)

    def test_register_non_contract_class_rejected(self, monkeypatch):
        monkeypatch.setattr(sync_adapters, "_ADAPTERS", dict(sync_adapters._ADAPTERS))
        with pytest.raises(TypeError):
            register_adapter("bad", object)  # type: ignore[arg-type]

    def test_get_unknown_adapter_raises_value_error(self):
        with pytest.raises(ValueError) as exc:
            get_adapter("no-such-adapter")
        assert "未注册的适配器" in str(exc.value)

    def test_remote_object_is_frozen(self):
        obj = RemoteObject(key="k", size=1, modified_at="2026-01-01")
        with pytest.raises(FrozenInstanceError):
            obj.key = "other"  # type: ignore[misc]


# ================================================================
# 三、ADR-0008 端到端：显式 null = 清空，省略 = 不改
# ================================================================
class TestNullSemanticsEndToEnd:
    def test_task_project_id_null_clears_omitted_keeps(self, client):
        project = _ok(client.post("/api/v1/projects", json={"name": "Phase5 项目"}))
        task = _ok(
            client.post(
                "/api/v1/tasks", json={"title": "关联任务", "project_id": project["id"]}
            )
        )
        assert task["project_id"] == project["id"]

        kept = _ok(client.patch(f"/api/v1/tasks/{task['id']}", json={"title": "改名"}))
        assert kept["project_id"] == project["id"], "省略 project_id 不得解除关联"

        cleared = _ok(
            client.patch(f"/api/v1/tasks/{task['id']}", json={"project_id": None})
        )
        assert cleared["project_id"] is None, "显式 null 必须解除关联"

    def test_task_title_whitespace_only_rejected_by_service(self, client):
        task = _ok(client.post("/api/v1/tasks", json={"title": "空白校验"}))
        resp = client.patch(f"/api/v1/tasks/{task['id']}", json={"title": "   "})
        assert resp.status_code == 400
        assert "标题不能为空" in resp.json()["message"]

    def test_document_folder_id_null_clears(self, client):
        doc = _ok(client.post("/api/v1/documents", json={"title": "Phase5 文档"}))
        folder = _ok(client.post("/api/v1/folders", json={"name": "Phase5 文件夹"}))
        moved = _ok(
            client.patch(f"/api/v1/documents/{doc['id']}", json={"folder_id": folder["id"]})
        )
        assert moved["folder_id"] == folder["id"]

        cleared = _ok(
            client.patch(f"/api/v1/documents/{doc['id']}", json={"folder_id": None})
        )
        assert cleared["folder_id"] is None

    def test_project_identity_id_null_clears(self, client):
        project = _ok(client.post("/api/v1/projects", json={"name": "身份项目"}))
        identity = _ok(
            client.post(
                "/api/v1/identities", json={"name": "身份A", "slug": "identity-a"}
            )
        )
        assigned = _ok(
            client.patch(
                f"/api/v1/projects/{project['id']}", json={"identity_id": identity["id"]}
            )
        )
        assert assigned["identity_id"] == identity["id"]

        cleared = _ok(
            client.patch(f"/api/v1/projects/{project['id']}", json={"identity_id": None})
        )
        assert cleared["identity_id"] is None


# ================================================================
# 四、AI / avatar / plugin 边界分支
# ================================================================
class TestAIServiceBoundaries:
    def test_summarize_missing_document_raises_not_found(self, db_session, test_user):
        svc = AIService(db_session, test_user)
        with pytest.raises(NotFoundException):
            asyncio.run(svc.summarize(str(uuid.uuid4())))

    def test_suggest_tags_missing_document_raises_not_found(self, db_session, test_user):
        svc = AIService(db_session, test_user)
        with pytest.raises(NotFoundException):
            asyncio.run(svc.suggest_tags(str(uuid.uuid4())))

    def test_get_llm_client_falls_back_to_mock_without_key(self, db_session, test_user):
        assert test_user.api_key_encrypted is None
        assert isinstance(get_llm_client(test_user), MockLLMClient)

    def test_get_llm_client_falls_back_to_mock_when_decrypt_fails(self):
        broken = SimpleNamespace(id="u1", api_key_encrypted="fernet:not-a-valid-token")
        assert isinstance(get_llm_client(broken), MockLLMClient)

    def test_mock_client_chat_and_stream_are_deterministic(self):
        client = MockLLMClient()
        resp = asyncio.run(
            client.chat([{"role": "user", "content": "你好"}])
        )
        assert "（演示模式）" in resp.content
        assert resp.tokens == 0

        async def collect():
            return [chunk async for chunk in client.stream_chat(
                [{"role": "user", "content": "流式"}]
            )]

        chunks = asyncio.run(collect())
        assert "".join(chunks) == resp.content.replace("你好", "流式")


class TestAvatarServiceBoundaries:
    def test_update_missing_memory_raises_not_found(self, db_session, test_user):
        with pytest.raises(NotFoundException):
            AvatarService(db_session).update_memory(str(uuid.uuid4()), {"title": "x"})

    def test_delete_missing_memory_raises_not_found(self, db_session, test_user):
        with pytest.raises(NotFoundException):
            AvatarService(db_session).delete_memory(str(uuid.uuid4()))

    def test_verify_missing_memory_raises_not_found(self, db_session, test_user):
        with pytest.raises(NotFoundException):
            AvatarService(db_session).verify_memory(str(uuid.uuid4()), True)


class TestPluginManagerBoundaries:
    def test_validate_permissions_rejects_denied(self):
        ok, reason = pm.validate_permissions(["exec"])
        assert ok is False
        assert "高危权限被拒绝" in reason

    def test_validate_permissions_rejects_unknown(self):
        ok, reason = pm.validate_permissions(["teleport"])
        assert ok is False
        assert "未知权限" in reason

    def test_validate_permissions_accepts_known(self):
        allowed = sorted(pm.ALLOWED_PERMISSIONS - pm.DENIED_PERMISSIONS)
        assert allowed, "ALLOWED_PERMISSIONS 不应为空"
        assert pm.validate_permissions([allowed[0]]) == (True, "")

    def test_require_permission_raises_for_undeclared(self):
        with pytest.raises(PermissionError):
            pm.require_permission("phase5-plugin", "network")

    def test_safe_call_returns_default_on_exception(self):
        def boom():
            raise RuntimeError("plugin exploded")

        assert pm.safe_call("phase5-plugin", boom, default="fallback") == "fallback"

    def test_safe_call_returns_default_on_none(self):
        assert pm.safe_call("phase5-plugin", None, default=42) == 42

    def test_safe_call_returns_default_on_timeout(self):
        def slow():
            time.sleep(0.2)
            return "too-late"

        started = time.perf_counter()
        assert pm.safe_call("phase5-plugin", slow, timeout=0.01, default="timeout") == "timeout"
        assert time.perf_counter() - started < 0.2


# ================================================================
# 五、task/subtask 边界（未找到 = 404 语义）
# ================================================================
class TestTaskSubtaskBoundaries:
    def test_update_subtask_of_wrong_task_returns_404(self, client):
        t1 = _ok(client.post("/api/v1/tasks", json={"title": "任务1"}))
        t2 = _ok(client.post("/api/v1/tasks", json={"title": "任务2"}))
        sub = _ok(client.post(f"/api/v1/tasks/{t1['id']}/subtasks", json={"title": "子任务"}))
        resp = client.patch(
            f"/api/v1/tasks/{t2['id']}/subtasks/{sub['id']}", json={"completed": True}
        )
        assert resp.status_code == 404
        assert "子任务不存在" in resp.json()["message"]

    def test_illegal_status_transition_returns_409(self, client):
        task = _ok(client.post("/api/v1/tasks", json={"title": "状态机"}))
        _ok(client.patch(f"/api/v1/tasks/{task['id']}", json={"status": "completed"}))
        resp = client.patch(f"/api/v1/tasks/{task['id']}", json={"status": "waiting"})
        assert resp.status_code == 409
        assert resp.json()["code"] == 3001
