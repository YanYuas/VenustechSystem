# ============================================================
# 保险箱 service 边界测试（Phase7-D · 覆盖率补缺）
#
# 主流程（setup/unlock/CRUD/白名单）已由 test_vault_production.py 覆盖；
# 这里补 Phase6 term-missing 指出的**防御性分支**：
#   · 校验器被篡改：unlock / change_master_password 必须拒绝（数据损坏语义）；
#   · update_item 的全部可编辑字段（含身份轴）；
#   · reveal_secret 在「主密码已更换」后的解密失败分支；
#   · run_action 的防御分支（缺主机名 / 主机名被篡改）与**成功路径**的命令拼装
#     （Popen 被替换为记录器，绝不真的拉起 ssh；密钥文件用临时目录里的真文件）；
#   · 上锁态下 _require_fernet 的拒绝；
#   · test_action_connection 对存库数据的四项校验（缺 host / 非法字符 / 非数字端口 / 越界端口）。
#
# 解锁态是模块级进程内存（_session_keys），本文件用 autouse 夹具隔离。
# ============================================================
from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from app.config import get_settings
from app.core.encryption import EncryptionManager
from app.core.exceptions import BusinessException, ValidationException
from app.repositories import IdentityRepository, VaultItemRepository
from app.services import vault_service as vs
from app.services.vault_service import VaultService

MASTER_PW = "correct-horse-battery-staple"


@pytest.fixture(autouse=True)
def _reset_vault_session():
    """解锁态是进程内存全局态；clean_db 清不掉，必须显式清理。"""
    vs._session_keys.clear()
    yield
    vs._session_keys.clear()


@pytest.fixture()
def unlocked(db_session, test_user):
    svc = VaultService(db_session, test_user.id)
    svc.setup(MASTER_PW)
    return svc


def _tamper_verifier(svc: VaultService, db_session, master_pw: str = MASTER_PW) -> None:
    """把校验器改成「能用正确密钥解开、但内容不是已知常量」→ 数据被篡改。"""
    config = svc._config()
    salt = bytes.fromhex(config.salt)
    key = EncryptionManager.derive_key(master_pw, salt)
    config.verifier = Fernet(key).encrypt(b"tampered-verifier").decode()
    db_session.commit()


# ================================================================
# 一、防御性分支（校验器篡改 / 上锁态）
# ================================================================
class TestDefensiveBranches:
    def test_now_helper_returns_aware_utc(self):
        now = vs._now()
        assert now.tzinfo is not None
        assert now.utcoffset() is not None

    def test_unlock_rejects_tampered_verifier(self, unlocked, db_session):
        _tamper_verifier(unlocked, db_session)
        vs._session_keys.clear()  # 模拟进程重启（重新走 unlock）

        with pytest.raises(BusinessException) as ei:
            unlocked.unlock(MASTER_PW)
        assert "校验器异常" in str(ei.value)
        assert vs._session_keys == {}  # 篡改时不得写入解锁态

    def test_change_master_password_rejects_tampered_verifier(self, unlocked, db_session):
        _tamper_verifier(unlocked, db_session)

        with pytest.raises(BusinessException) as ei:
            unlocked.change_master_password(MASTER_PW, "new-password-2026")
        assert "校验器异常" in str(ei.value)

    def test_require_fernet_rejects_when_locked(self, db_session, test_user):
        svc = VaultService(db_session, test_user.id)
        with pytest.raises(BusinessException) as ei:
            svc._require_fernet()
        assert "保险箱已上锁" in str(ei.value)


# ================================================================
# 二、update_item 全字段 / reveal_secret 密钥失配
# ================================================================
class TestItemUpdateAndReveal:
    def test_update_item_updates_every_editable_field(self, unlocked, db_session, test_user):
        identity = IdentityRepository(db_session).create(
            user_id=test_user.id, name="工作", slug=f"vault-{uuid.uuid4().hex[:6]}",
            color_token="primary",
        )
        item = unlocked.create_item(
            name="旧名", category="login", username="old-user",
            url="https://old.example", secret="old-secret", notes="旧备注",
            identity_id=None,
        )

        updated = unlocked.update_item(
            item["id"],
            name="  新名  ", category="note", username="new-user",
            url="https://new.example", notes="新备注", identity_id=identity.id,
        )
        assert updated["name"] == "新名"          # 名称会 strip
        assert updated["category"] == "note"
        assert updated["username"] == "new-user"
        assert updated["url"] == "https://new.example"
        assert updated["notes"] == "新备注"
        assert updated["identity_id"] == identity.id

        db = db_session
        db.expire_all()
        row = VaultItemRepository(db).get(item["id"])
        assert (row.category, row.username, row.url, row.notes) == (
            "note", "new-user", "https://new.example", "新备注",
        )
        assert row.identity_id == identity.id

    def test_reveal_secret_fails_after_master_key_swapped(self, unlocked, db_session):
        item = unlocked.create_item(
            name="ssh", category="login", username=None, url=None,
            secret="my-secret", notes=None, identity_id=None,
        )
        # 模拟「主密码已被更换」：内存里的工作密钥换成另一把
        other_salt = EncryptionManager.new_salt()
        vs._session_keys[unlocked.user_id] = EncryptionManager.derive_key(
            "another-master-password", other_salt
        )

        with pytest.raises(BusinessException) as ei:
            unlocked.reveal_secret(item["id"])
        assert "解密失败" in str(ei.value)


# ================================================================
# 三、run_action：防御分支 + 命令拼装（Popen 打桩）
# ================================================================
class _PopenRecorder:
    def __init__(self):
        self.calls: list[tuple[list[str], dict]] = []

    def __call__(self, args, **kwargs):
        self.calls.append((list(args), kwargs))
        return object()


@pytest.fixture()
def ssh_item_factory(db_session, test_user):
    """直接走 Repository 造「数据库里的 SSH 凭据」（绕过写入期校验，测读取期防御）。"""

    def _make(**overrides):
        payload = {
            "user_id": test_user.id,
            "name": "ssh-item",
            "category": "login",
            "secret_encrypted": "dummy-token",
            "action_type": "ssh",
            "action_host": "example.com",
            "action_user": None,
            "action_port": None,
        }
        payload.update(overrides)
        return VaultItemRepository(db_session).create(**payload)

    return _make


class TestRunAction:
    def test_run_action_requires_host(self, unlocked, ssh_item_factory):
        row = ssh_item_factory(action_host=None)

        with pytest.raises(ValidationException) as ei:
            unlocked.run_action(row.id)
        assert "缺少主机名" in str(ei.value)

    def test_run_action_rejects_tampered_host(self, unlocked, ssh_item_factory):
        row = ssh_item_factory(action_host="bad host!")
        with pytest.raises(BusinessException) as ei:
            unlocked.run_action(row.id)
        assert "主机名异常" in str(ei.value)

    def test_run_action_builds_whitelisted_ssh_command(self, unlocked, monkeypatch):
        key_file = Path(get_settings().data_dir) / f"vault-key-{uuid.uuid4().hex[:8]}"
        key_file.write_text("dummy-private-key", encoding="utf-8")
        try:
            item = unlocked.create_item(
                name="服务器", category="login", username=None, url=None,
                secret=str(key_file), notes=None, identity_id=None,
                action_type="ssh", action_host="example.com",
                action_user="root", action_port="2222",
            )
            recorder = _PopenRecorder()
            monkeypatch.setattr("subprocess.Popen", recorder)

            result = unlocked.run_action(item["id"])
            assert result["opened"] is True
            assert result["action"] == "ssh"

            expected = f'ssh -i "{key_file}" -p 2222 "root@example.com"'
            assert result["command"] == expected
            args, kwargs = recorder.calls[0]
            assert args == ["cmd.exe", "/K", expected]
            assert "creationflags" in kwargs

            db = unlocked.db
            db.expire_all()
            assert VaultItemRepository(db).get(item["id"]).last_accessed_at is not None
        finally:
            key_file.unlink(missing_ok=True)

    def test_run_action_without_user_or_port_uses_host_only(self, unlocked, monkeypatch):
        key_file = Path(get_settings().data_dir) / f"vault-key-{uuid.uuid4().hex[:8]}"
        key_file.write_text("dummy-private-key", encoding="utf-8")
        try:
            item = unlocked.create_item(
                name="服务器2", category="login", username=None, url=None,
                secret=str(key_file), notes=None, identity_id=None,
                action_type="ssh", action_host="example.com",
            )
            recorder = _PopenRecorder()
            monkeypatch.setattr("subprocess.Popen", recorder)

            result = unlocked.run_action(item["id"])
            assert result["command"] == f'ssh -i "{key_file}" "example.com"'
            assert "-p " not in result["command"]
        finally:
            key_file.unlink(missing_ok=True)


# ================================================================
# 四、test_action_connection 的存库数据校验（SSRF 防线）
# ================================================================
class TestProbeValidation:
    def test_probe_rejects_missing_host(self, unlocked, ssh_item_factory):
        row = ssh_item_factory(action_host="")
        with pytest.raises(ValidationException) as ei:
            unlocked.test_action_connection(row.id)
        assert "未配置主机地址" in str(ei.value)

    def test_probe_rejects_illegal_host_characters(self, unlocked, ssh_item_factory):
        row = ssh_item_factory(action_host="bad host; rm -rf /")
        with pytest.raises(ValidationException) as ei:
            unlocked.test_action_connection(row.id)
        assert "主机地址含非法字符" in str(ei.value)

    def test_probe_rejects_non_numeric_port(self, unlocked, ssh_item_factory):
        row = ssh_item_factory(action_port="abc")
        with pytest.raises(ValidationException) as ei:
            unlocked.test_action_connection(row.id)
        assert "端口必须是数字" in str(ei.value)

    def test_probe_rejects_out_of_range_port(self, unlocked, ssh_item_factory):
        row = ssh_item_factory(action_port="70000")
        with pytest.raises(ValidationException) as ei:
            unlocked.test_action_connection(row.id)
        assert "端口须在 1-65535 之间" in str(ei.value)
