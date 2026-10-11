# ============================================================
# 安全 API 测试（app/api/security.py）
#
# 覆盖目标：
#   1. 信封格式与路由
#   2. **解锁门禁**：未解锁时加解密/轮换一律拒绝（补的是"进程内越权"）
#   3. 加解密端到端往返 + 坏 token 返回 400（不是 500）
#   4. 轮换真的落库（端到端，越过 Service 层直接打接口）
#   5. 审计端点：上限、信封
#
# 关键隔离：`get_encryption()` 是**全局单例**、数据目录是本测试会话共用的
# 临时目录。直接打接口会在那个目录里轮换真实密钥文件并污染后续用例，
# 因此这里 monkeypatch 掉 `get_encryption` 与 `get_settings`，把两者都指向 tmp_path。
# ============================================================
from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from app.core.encryption import EncryptionManager

PREFIX = "fernet:"


@pytest.fixture()
def enc_env(tmp_path, monkeypatch):
    """把加密数据目录与全局单例都指向本次测试独占的 tmp_path。"""
    import app.api.security as api_security
    import app.services.security_service as ss

    class _FakeSettings:
        data_dir = str(tmp_path)
        dev = True

    mgr = EncryptionManager(tmp_path)
    monkeypatch.setattr(ss, "get_settings", lambda: _FakeSettings)
    monkeypatch.setattr(api_security, "get_encryption", lambda: mgr)
    return mgr


@pytest.fixture()
def locked():
    """确保保险箱处于未解锁态（解锁态是进程内存全局，必须显式清）。"""
    from app.services import vault_service as vs

    vs._session_keys.clear()
    yield
    vs._session_keys.clear()


@pytest.fixture()
def unlocked(default_user_id):
    """伪造解锁态：解锁值就是工作密钥（vault_service 里存的是 Fernet key bytes）。

    只改进程内缓存，不碰主密码链路 —— 本文件测的是门禁「有没有」，不是保险箱本身。
    """
    from app.services import vault_service as vs

    vs._session_keys[default_user_id] = Fernet.generate_key()
    yield
    vs._session_keys.clear()


# ============================================================
# 一、状态端点
# ============================================================
class TestEncryptionStatus:

    def test_status_envelope(self, client, enc_env):
        r = client.get("/api/v1/security/status")
        assert r.status_code == 200
        body = r.json()
        assert body["code"] == 0
        assert body["data"]["available"] is True
        assert "algorithm" in body["data"]

    def test_status_reports_unavailable_without_backend(self, client, monkeypatch):
        import app.api.security as api_security

        monkeypatch.setattr(api_security, "get_encryption", lambda: None)
        body = client.get("/api/v1/security/status").json()
        assert body["data"] == {"available": False, "reason": "加密模块未初始化"}


# ============================================================
# 二、解锁门禁（本文件最重要的一组）
# ============================================================
class TestUnlockGate:

    def test_encrypt_rejected_when_locked(self, client, locked, enc_env):
        r = client.post("/api/v1/security/encrypt", json={"data": "secret"})
        assert r.status_code == 400
        assert r.json()["code"] == 1001
        assert "未解锁" in r.json()["message"]

    def test_decrypt_rejected_when_locked(self, client, locked, enc_env):
        r = client.post("/api/v1/security/decrypt", json={"token": "whatever"})
        assert r.status_code == 400
        assert "未解锁" in r.json()["message"]

    def test_rotate_rejected_when_locked(self, client, locked, enc_env):
        r = client.post("/api/v1/security/key/rotate")
        assert r.status_code == 400
        assert "未解锁" in r.json()["message"]

    def test_gate_runs_before_anything_else(self, client, locked, enc_env):
        """门禁在前：被拒时**不写审计**，也不该触碰加密后端。

        这是"补进程内越权"的设计意图 —— 任何能打到 API 的调用（含被注入的
        前端脚本）在未解锁时不得批量解密用户密钥。
        """
        client.post("/api/v1/security/encrypt", json={"data": "x"})
        assert client.get("/api/v1/security/audit").json()["data"]["items"] == []


# ============================================================
# 三、加解密端到端
# ============================================================
class TestEncryptDecrypt:

    def test_roundtrip(self, client, unlocked, enc_env):
        enc = client.post("/api/v1/security/encrypt", json={"data": "你好"})
        assert enc.status_code == 200
        token = enc.json()["data"]["encrypted"]
        assert token.startswith("gAAAAA")

        dec = client.post("/api/v1/security/decrypt", json={"token": token})
        assert dec.status_code == 200
        assert dec.json()["data"]["decrypted"] == "你好"

    def test_decrypt_bad_token_returns_400_not_500(self, client, unlocked, enc_env):
        """坏 token 必须是 400/1001（业务异常），不能漏成 500。

        Service 层把 InvalidToken 收敛成 ValueError，API 层再 `except ValueError`
        —— 这条链路任一环断掉就会变成 500。
        """
        r = client.post("/api/v1/security/decrypt", json={"token": "not-a-token"})
        assert r.status_code == 400
        assert r.json()["code"] == 1001

    def test_missing_field_is_400(self, client, unlocked, enc_env):
        r = client.post("/api/v1/security/encrypt", json={})
        assert r.status_code == 400

    def test_unavailable_backend_uses_unified_envelope(self, client, unlocked, monkeypatch):
        """回归断言（2026-10-11 修复）：本模块曾是全仓**唯一**用裸 `HTTPException`
        的 API 文件，返回 `{"detail": ...}` 而非统一信封。

        影响是用户可见的：`frontend/src/api/http.ts` 的错误分支只读 `errBody.message`，
        不读 `detail` → 抛出时只能显示 "HTTP 503: Service Unavailable"，
        真正的原因被丢掉。改走 `ServerException` 后 message 能到达用户。
        """
        import app.api.security as api_security

        monkeypatch.setattr(api_security, "get_encryption", lambda: None)
        r = client.post("/api/v1/security/encrypt", json={"data": "x"})
        assert r.status_code == 500
        body = r.json()
        assert body["code"] == 5000
        assert "加密功能不可用" in body["message"]
        assert "detail" not in body

    def test_successful_calls_write_audit(self, client, unlocked, enc_env):
        client.post("/api/v1/security/encrypt", json={"data": "a"})
        actions = [i["action"] for i in client.get("/api/v1/security/audit")
                   .json()["data"]["items"]]
        assert "security.encrypt" in actions

    def test_failed_decrypt_writes_failed_audit(self, client, unlocked, enc_env):
        client.post("/api/v1/security/decrypt", json={"token": "bad"})
        item = client.get("/api/v1/security/audit").json()["data"]["items"][0]
        assert item["action"] == "security.decrypt"
        assert item["ok"] is False


# ============================================================
# 四、轮换端到端
# ============================================================
class TestRotateEndpoint:

    def test_rotate_returns_honest_report(self, client, unlocked, enc_env, default_user_id):
        from app.database import SessionLocal
        from app.models.user import User

        db = SessionLocal()
        try:
            db.get(User, default_user_id).api_key_encrypted = \
                PREFIX + enc_env.encrypt("sk-endpoint").decode()
            db.commit()
            before = db.get(User, default_user_id).api_key_encrypted
        finally:
            db.close()

        body = client.post("/api/v1/security/key/rotate").json()
        assert body["code"] == 0
        assert body["data"]["rotated"] == 1
        assert body["data"]["tables"] == ["users"]

        db = SessionLocal()
        try:
            after = db.get(User, default_user_id).api_key_encrypted
        finally:
            db.close()
        assert after != before
        assert EncryptionManager(enc_env.data_dir).decrypt(after[len(PREFIX):]) == "sk-endpoint"

    def test_rotate_with_empty_body(self, client, unlocked, enc_env):
        """body 可省略（`RotateRequest | None = None`）—— 前端就是这么调的。"""
        r = client.post("/api/v1/security/key/rotate")
        assert r.status_code == 200
        assert r.json()["data"]["rotated"] == 0

    def test_rotate_writes_audit(self, client, unlocked, enc_env):
        client.post("/api/v1/security/key/rotate")
        item = client.get("/api/v1/security/audit").json()["data"]["items"][0]
        assert item["action"] == "security.rotate_key"
        assert item["ok"] is True


# ============================================================
# 五、审计端点
# ============================================================
class TestAuditEndpoint:

    def test_empty_envelope(self, client, enc_env):
        body = client.get("/api/v1/security/audit").json()
        assert body["code"] == 0
        assert body["data"]["items"] == []

    def test_limit_query_param(self, client, unlocked, enc_env):
        for _ in range(3):
            client.post("/api/v1/security/encrypt", json={"data": "x"})
        body = client.get("/api/v1/security/audit?limit=2").json()
        assert len(body["data"]["items"]) == 2

    def test_limit_capped_at_200(self, client, unlocked, enc_env):
        body = client.get("/api/v1/security/audit?limit=1000").json()
        assert len(body["data"]["items"]) <= 200
