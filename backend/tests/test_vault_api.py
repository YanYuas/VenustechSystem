# ============================================================
# 保险箱 API 层测试（三期 D）
#
# API 层特殊性（务必先读）：
#   1. 一期是**单用户模式**（get_current_user 恒返回 default_user），
#      所以 API 层无法用两个真实登录态测越权 —— 改为直接往库里插一条
#      「属于另一个用户」的记录，再请求它的 id，断言 404。
#   2. `_session_keys` 是**进程内存全局**，而 clean_db 只清表。
#      不手动清它，上一个用例的解锁态会泄漏进下一个用例（default_user.id 固定）。
# ============================================================
from __future__ import annotations

import uuid

import pytest

MASTER = "correct-horse-battery-staple"
NEW_MASTER = "another-strong-master-pw"

BASE = "/api/v1/vault"


@pytest.fixture(autouse=True)
def _reset_vault_session():
    """清空解锁态（进程内存全局，clean_db 清不掉）。"""
    from app.services import vault_service as vs

    vs._session_keys.clear()
    yield
    vs._session_keys.clear()


@pytest.fixture()
def unlocked(client):
    """开箱即用的已解锁保险箱。"""
    r = client.put(f"{BASE}/setup", json={"master_password": MASTER})
    assert r.status_code == 200 and r.json()["code"] == 0
    return client


def _mk_other_user() -> str:
    """在库里造一个"另一个用户"，返回其 id（用于越权场景）。"""
    from app.database import SessionLocal
    from app.models.user import User

    db = SessionLocal()
    try:
        u = User(username=f"other_{uuid.uuid4().hex[:8]}", nickname="他人")
        db.add(u)
        db.commit()
        db.refresh(u)
        return u.id
    finally:
        db.close()


# ============================================================
# 状态与主密码
# ============================================================
class TestMasterPasswordApi:

    def test_status_initially_unconfigured(self, client):
        r = client.get(f"{BASE}/status")
        assert r.status_code == 200
        d = r.json()["data"]
        assert d["configured"] is False
        assert d["unlocked"] is False

    def test_setup_short_password_rejected_by_pydantic(self, client):
        """Pydantic min_length=8 在进入 Service 之前就拦下。

        注意项目约定：RequestValidationError 被统一映射为 **400 + code 1001**
        （见 main.py 的 validation_exception_handler），不是 FastAPI 默认的 422。
        """
        r = client.put(f"{BASE}/setup", json={"master_password": "1234567"})
        assert r.status_code == 400
        assert r.json()["code"] == 1001
        assert "参数错误" in r.json()["message"]

    def test_setup_then_status_unlocked(self, unlocked):
        d = unlocked.get(f"{BASE}/status").json()["data"]
        assert d["configured"] is True
        assert d["unlocked"] is True
        assert d["hint"] is None

    def test_setup_twice_409(self, unlocked):
        r = unlocked.put(f"{BASE}/setup", json={"master_password": "yet-another-pw"})
        assert r.status_code == 409
        assert r.json()["code"] == 3001

    def test_lock_then_unlock_roundtrip(self, unlocked):
        assert unlocked.post(f"{BASE}/lock").json()["data"]["unlocked"] is False
        assert unlocked.get(f"{BASE}/status").json()["data"]["unlocked"] is False
        r = unlocked.post(f"{BASE}/unlock", json={"master_password": MASTER})
        assert r.status_code == 200
        assert r.json()["data"]["unlocked"] is True

    def test_unlock_wrong_password_400(self, unlocked):
        unlocked.post(f"{BASE}/lock")
        r = unlocked.post(f"{BASE}/unlock", json={"master_password": "wrong-password"})
        assert r.status_code == 400
        assert r.json()["code"] == 1001

    def test_unlock_before_setup_409(self, client):
        r = client.post(f"{BASE}/unlock", json={"master_password": MASTER})
        assert r.status_code == 409
        assert r.json()["code"] == 3001

    def test_status_does_not_require_unlock(self, unlocked):
        unlocked.post(f"{BASE}/lock")
        assert unlocked.get(f"{BASE}/status").status_code == 200

    def test_change_password_flow(self, unlocked):
        r = unlocked.post(f"{BASE}/change-password",
                          json={"old_password": MASTER, "new_password": NEW_MASTER})
        assert r.status_code == 200 and r.json()["data"]["unlocked"] is True
        unlocked.post(f"{BASE}/lock")
        assert unlocked.post(f"{BASE}/unlock",
                             json={"master_password": MASTER}).status_code == 400
        assert unlocked.post(f"{BASE}/unlock",
                             json={"master_password": NEW_MASTER}).status_code == 200

    def test_change_password_short_new_rejected(self, unlocked):
        r = unlocked.post(f"{BASE}/change-password",
                          json={"old_password": MASTER, "new_password": "short"})
        assert r.status_code == 400
        assert r.json()["code"] == 1001

    def test_change_password_wrong_old_400(self, unlocked):
        r = unlocked.post(f"{BASE}/change-password",
                          json={"old_password": "nope", "new_password": NEW_MASTER})
        assert r.status_code == 400
        assert r.json()["code"] == 1001


# ============================================================
# 凭据 CRUD
# ============================================================
class TestItemsApi:

    def _create(self, client, **over):
        body = {"name": "GitHub", "category": "login", "username": "yan",
                "url": "https://github.com", "secret": "gh-token-123", "notes": "备注"}
        body.update(over)
        return client.post(f"{BASE}/items", json=body)

    def test_list_requires_unlock_409(self, unlocked):
        unlocked.post(f"{BASE}/lock")
        r = unlocked.get(f"{BASE}/items")
        assert r.status_code == 409
        assert r.json()["code"] == 3001

    def test_create_requires_unlock_409(self, client):
        r = self._create(client)
        assert r.status_code == 409
        assert r.json()["code"] == 3001

    def test_create_and_list_never_returns_secret(self, unlocked):
        r = self._create(unlocked)
        assert r.status_code == 200
        created = r.json()["data"]
        assert "secret" not in created
        assert created["has_secret"] is True

        listed = unlocked.get(f"{BASE}/items").json()["data"]
        assert len(listed) == 1
        assert "secret" not in listed[0]

    def test_reveal_returns_plaintext(self, unlocked):
        item_id = self._create(unlocked).json()["data"]["id"]
        r = unlocked.get(f"{BASE}/items/{item_id}/secret")
        assert r.status_code == 200
        assert r.json()["data"]["secret"] == "gh-token-123"

    def test_patch_updates_only_given_fields(self, unlocked):
        item_id = self._create(unlocked).json()["data"]["id"]
        r = unlocked.patch(f"{BASE}/items/{item_id}", json={"name": "GitLab"})
        assert r.status_code == 200
        d = r.json()["data"]
        assert d["name"] == "GitLab"
        assert d["username"] == "yan"          # 未传的字段不动
        assert d["has_secret"] is True

    def test_patch_rejects_invalid_category(self, unlocked):
        """category 是 Literal["login","note"] → 越界值走统一参数错误通道。"""
        item_id = self._create(unlocked).json()["data"]["id"]
        r = unlocked.patch(f"{BASE}/items/{item_id}", json={"category": "hacked"})
        assert r.status_code == 400
        assert r.json()["code"] == 1001

    def test_delete_item(self, unlocked):
        item_id = self._create(unlocked).json()["data"]["id"]
        assert unlocked.delete(f"{BASE}/items/{item_id}").status_code == 200
        assert unlocked.get(f"{BASE}/items").json()["data"] == []

    def test_get_unknown_item_404(self, unlocked):
        r = unlocked.get(f"{BASE}/items/does-not-exist/secret")
        assert r.status_code == 404
        assert r.json()["code"] == 1002

    def test_create_with_unknown_identity_400(self, unlocked):
        r = self._create(unlocked, identity_id="no-such-identity")
        assert r.status_code == 400
        assert r.json()["code"] == 1001

    def test_create_with_invalid_action_host_400(self, unlocked):
        r = self._create(unlocked, action_type="ssh", action_host="bad host; rm -rf /")
        assert r.status_code == 400
        assert r.json()["code"] == 1001

    def test_foreign_item_is_404_not_403(self, unlocked, default_user_id):
        """越权访问他人凭据：必须 404（不泄漏存在性），而不是 403。

        vault 的 `_owned_item` 本就带归属校验，这里把该行为钉死为对外契约。
        """
        from app.database import SessionLocal
        from app.models.vault import VaultItem

        other_id = _mk_other_user()
        db = SessionLocal()
        try:
            row = VaultItem(user_id=other_id, name="他人的凭据", category="login",
                            secret_encrypted=None)
            db.add(row)
            db.commit()
            foreign_item_id = row.id
        finally:
            db.close()

        assert unlocked.get(f"{BASE}/items/{foreign_item_id}/secret").status_code == 404
        assert unlocked.delete(f"{BASE}/items/{foreign_item_id}").status_code == 404
        assert unlocked.patch(f"{BASE}/items/{foreign_item_id}",
                              json={"name": "劫持"}).status_code == 404
        # 且 listing 不包含他人条目（items_count 也不含）
        assert unlocked.get(f"{BASE}/items").json()["data"] == []
        assert unlocked.get(f"{BASE}/status").json()["data"]["items_count"] == 0


# ============================================================
# 终端动作
# ============================================================
class TestActionApi:

    def _create_ssh(self, client, **over):
        body = {"name": "跳板机", "category": "login", "secret": "/no/such/key",
                "action_type": "ssh", "action_host": "jump.example.com"}
        body.update(over)
        return client.post(f"{BASE}/items", json=body)

    def test_run_action_without_action_config_400(self, unlocked):
        item_id = unlocked.post(f"{BASE}/items",
                                json={"name": "x", "category": "note"}).json()["data"]["id"]
        r = unlocked.post(f"{BASE}/items/{item_id}/run-action")
        assert r.status_code == 400
        assert r.json()["code"] == 1001

    def test_run_action_missing_key_file_400(self, unlocked):
        """密钥文件不存在 → 400，且不起进程（run_action 的 Popen 未被触达）。"""
        item_id = self._create_ssh(unlocked).json()["data"]["id"]
        r = unlocked.post(f"{BASE}/items/{item_id}/run-action")
        assert r.status_code == 400
        assert "密钥文件不存在" in r.json()["message"]

    def test_run_action_requires_unlock_409(self, unlocked):
        item_id = self._create_ssh(unlocked).json()["data"]["id"]
        unlocked.post(f"{BASE}/lock")
        assert unlocked.post(f"{BASE}/items/{item_id}/run-action").status_code == 409

    def test_test_connection_non_ssh_400(self, unlocked):
        item_id = unlocked.post(f"{BASE}/items",
                                json={"name": "x", "category": "note"}).json()["data"]["id"]
        r = unlocked.post(f"{BASE}/items/{item_id}/test-connection")
        assert r.status_code == 400
        assert "action_type != ssh" in r.json()["message"]

    def test_test_connection_reachable(self, unlocked, monkeypatch):
        """monkeypatch TCP 连接，避免测试打真实网络。"""
        import contextlib

        import app.services.vault_service as vs

        @contextlib.contextmanager
        def _ok(address, timeout=None):
            yield object()

        monkeypatch.setattr(vs.socket, "create_connection", _ok)
        item_id = self._create_ssh(unlocked, action_port="22").json()["data"]["id"]
        r = unlocked.post(f"{BASE}/items/{item_id}/test-connection")
        assert r.status_code == 200
        d = r.json()["data"]
        assert d["reachable"] is True
        assert d["host"] == "jump.example.com"
        assert d["port"] == 22

    def test_test_connection_writes_audit_log(self, unlocked, monkeypatch):
        """探测结果落审计（api 层显式调用 audit）—— 失败也必须留痕。"""
        import contextlib

        import app.services.vault_service as vs
        from app.database import SessionLocal
        from app.models.audit import AuditLog

        @contextlib.contextmanager
        def _fail(address, timeout=None):
            raise OSError("refused")
            yield  # pragma: no cover

        monkeypatch.setattr(vs.socket, "create_connection", _fail)
        item_id = self._create_ssh(unlocked, action_port="22").json()["data"]["id"]
        unlocked.post(f"{BASE}/items/{item_id}/test-connection")

        db = SessionLocal()
        try:
            rows = db.query(AuditLog).all()
        finally:
            db.close()
        assert len(rows) == 1
        assert rows[0].target == "jump.example.com:22"
        assert rows[0].ok is False
