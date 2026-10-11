# ============================================================
# 保险箱 Service 层测试（三期 D · 主密码 + 凭据加密）
#
# 覆盖目标（安全面，优先级最高）：
#   1. 主密码生命周期：setup / unlock / lock / change
#   2. **主密码不落盘**（无哈希、无明文可爆破）—— 本文件最重要的断言
#   3. 凭据密文只以 Fernet token 落库；明文只从 reveal_secret 一个出口出
#   4. 解锁态是硬门槛：所有凭据 CRUD / 解密 / 动作都要求解锁
#   5. 终端动作白名单：拒绝任意命令、拒绝注入字符
#   6. 归属隔离：他人凭据一律 404
#
# 安全铁律：本文件**绝不**制造「密钥文件真实存在」的场景，
# 否则 run_action 会真的 Popen 起 cmd.exe 拉起 ssh。
# ============================================================
from __future__ import annotations

import pytest

from app.core.exceptions import BusinessException, NotFoundException, ValidationException
from app.services import vault_service as vs
from app.services.vault_service import ACTION_TYPES, VaultService, _VERIFIER_PLAINTEXT

MASTER_PW = "correct-horse-battery-staple"


@pytest.fixture(autouse=True)
def _reset_vault_session():
    """每个用例前后清空解锁态。

    解锁态是**模块级进程内存全局**（`_session_keys`），clean_db 只清表，
    清不掉它 —— 不清理会导致上一个用例的解锁态泄漏到下一个用例。
    """
    vs._session_keys.clear()
    yield
    vs._session_keys.clear()


def _svc(db, user) -> VaultService:
    return VaultService(db, user.id)


def _unlocked(db, user, pw: str = MASTER_PW) -> VaultService:
    svc = _svc(db, user)
    svc.setup(pw)
    return svc


# ============================================================
# 一、主密码生命周期
# ============================================================
class TestMasterPasswordLifecycle:

    def test_status_before_setup(self, db_session, test_user):
        st = _svc(db_session, test_user).status()
        assert st["configured"] is False
        assert st["unlocked"] is False
        assert st["items_count"] == 0
        assert st["hint"]  # 未解锁时会给提示

    def test_setup_rejects_short_password(self, db_session, test_user):
        svc = _svc(db_session, test_user)
        with pytest.raises(ValidationException) as ei:
            svc.setup("1234567")  # 7 位
        assert "8" in str(ei.value)
        # 拒绝后必须**没有**留下任何配置，否则保险箱被"半初始化"卡死
        assert svc.status()["configured"] is False

    def test_setup_exactly_eight_chars_ok(self, db_session, test_user):
        st = _svc(db_session, test_user).setup("12345678")
        assert st["configured"] is True
        assert st["unlocked"] is True

    def test_setup_unlocks_immediately(self, db_session, test_user):
        svc = _svc(db_session, test_user)
        st = svc.setup(MASTER_PW)
        assert st["unlocked"] is True
        assert st["hint"] is None

    def test_setup_twice_rejected(self, db_session, test_user):
        svc = _unlocked(db_session, test_user)
        with pytest.raises(BusinessException) as ei:
            svc.setup("another-password")
        assert "已初始化" in str(ei.value)
        # 原配置未被覆盖：旧密码仍能解锁
        svc.lock()
        assert svc.unlock(MASTER_PW)["unlocked"] is True

    def test_unlock_before_setup_rejected(self, db_session, test_user):
        with pytest.raises(BusinessException) as ei:
            _svc(db_session, test_user).unlock(MASTER_PW)
        assert "尚未初始化" in str(ei.value)

    def test_unlock_wrong_password_rejected_and_stays_locked(self, db_session, test_user):
        svc = _unlocked(db_session, test_user)
        svc.lock()
        with pytest.raises(ValidationException) as ei:
            svc.unlock("wrong-password")
        assert "主密码错误" in str(ei.value)
        assert svc.status()["unlocked"] is False

    def test_unlock_correct_password(self, db_session, test_user):
        svc = _unlocked(db_session, test_user)
        svc.lock()
        assert svc.status()["unlocked"] is False
        st = svc.unlock(MASTER_PW)
        assert st["unlocked"] is True

    def test_lock_is_idempotent(self, db_session, test_user):
        svc = _unlocked(db_session, test_user)
        svc.lock()
        st = svc.lock()  # 再锁一次不应报错
        assert st["unlocked"] is False

    def test_lock_on_fresh_service_never_setup(self, db_session, test_user):
        st = _svc(db_session, test_user).lock()
        assert st["unlocked"] is False


# ============================================================
# 二、主密码不落盘（核心安全断言）
# ============================================================
class TestMasterPasswordNeverPersisted:

    def test_verifier_decrypts_to_known_constant(self, db_session, test_user):
        from cryptography.fernet import Fernet

        from app.core.encryption import EncryptionManager
        from app.models.vault import VaultConfig

        _unlocked(db_session, test_user)
        cfg = db_session.query(VaultConfig).filter_by(user_id=test_user.id).one()
        key = EncryptionManager.derive_key(MASTER_PW, bytes.fromhex(cfg.salt))
        assert Fernet(key).decrypt(cfg.verifier.encode()).decode() == _VERIFIER_PLAINTEXT

    def test_no_column_contains_master_password(self, db_session, test_user):
        """遍历 vault_config 的**每一列**，主密码不得以任何形式出现。

        防什么：把主密码原文或哈希写进库里 —— 前者直接泄漏，后者给了
        离线爆破的第二份材料。设计上只有"派生密钥加密的已知常量"。
        """
        from sqlalchemy import inspect as sa_inspect

        from app.models.vault import VaultConfig

        _unlocked(db_session, test_user)
        cfg = db_session.query(VaultConfig).filter_by(user_id=test_user.id).one()
        for col in sa_inspect(VaultConfig).columns.keys():
            value = getattr(cfg, col)
            if value is None:
                continue
            assert MASTER_PW not in str(value), f"列 {col} 泄漏了主密码"

    def test_salt_is_random_hex_16_bytes(self, db_session, test_user, other_user):
        from app.models.vault import VaultConfig

        _svc(db_session, test_user).setup(MASTER_PW)
        _svc(db_session, other_user).setup(MASTER_PW)  # 同一密码
        rows = db_session.query(VaultConfig).all()
        salts = {r.salt for r in rows}
        assert len(salts) == 2, "相同主密码必须派生出不同 salt（防彩虹表跨库复用）"
        assert all(len(s) == 32 and bytes.fromhex(s) for s in salts)  # hex(16 bytes)

    def test_same_password_different_users_yield_different_verifier(
        self, db_session, test_user, other_user
    ):
        """salt 随机化 → 相同密码的 verifier 也不同。"""
        from app.models.vault import VaultConfig

        _svc(db_session, test_user).setup(MASTER_PW)
        _svc(db_session, other_user).setup(MASTER_PW)
        rows = db_session.query(VaultConfig).all()
        assert len({r.verifier for r in rows}) == 2


# ============================================================
# 三、解锁态是硬门槛
# ============================================================
class TestUnlockedGate:

    def test_create_requires_unlocked(self, db_session, test_user):
        svc = _svc(db_session, test_user)
        with pytest.raises(BusinessException) as ei:
            svc.create_item(name="x", category="login", username=None,
                            url=None, secret="s", notes=None, identity_id=None)
        assert "已上锁" in str(ei.value)

    def test_list_requires_unlocked(self, db_session, test_user):
        svc = _unlocked(db_session, test_user)
        svc.create_item(name="x", category="login", username=None,
                        url=None, secret="s", notes=None, identity_id=None)
        svc.lock()
        with pytest.raises(BusinessException):
            svc.list_items()

    def test_reveal_requires_unlocked(self, db_session, test_user):
        svc = _unlocked(db_session, test_user)
        item = svc.create_item(name="x", category="login", username=None,
                               url=None, secret="s", notes=None, identity_id=None)
        svc.lock()
        with pytest.raises(BusinessException):
            svc.reveal_secret(item["id"])

    def test_delete_requires_unlocked(self, db_session, test_user):
        svc = _unlocked(db_session, test_user)
        item = svc.create_item(name="x", category="login", username=None,
                               url=None, secret="s", notes=None, identity_id=None)
        svc.lock()
        with pytest.raises(BusinessException):
            svc.delete_item(item["id"])

    def test_run_action_requires_unlocked(self, db_session, test_user):
        svc = _unlocked(db_session, test_user)
        item = svc.create_item(name="x", category="login", username=None, url=None,
                               secret="/no/such/key", notes=None, identity_id=None,
                               action_type="ssh", action_host="example.com")
        svc.lock()
        with pytest.raises(BusinessException):
            svc.run_action(item["id"])


# ============================================================
# 四、凭据 CRUD 与密文落库
# ============================================================
class TestCredentialCrud:

    def _mk(self, svc, **over):
        kw = dict(name="GitHub", category="login", username="yan",
                  url="https://github.com", secret="s3cr3t-token",
                  notes="备注", identity_id=None)
        kw.update(over)
        return svc.create_item(**kw)

    def test_create_returns_no_secret_but_flags_it(self, db_session, test_user):
        svc = _unlocked(db_session, test_user)
        out = self._mk(svc)
        assert "secret" not in out          # 列表/详情一律不回明文
        assert out["has_secret"] is True
        assert out["name"] == "GitHub"

    def test_secret_stored_as_fernet_token_not_plaintext(self, db_session, test_user):
        from cryptography.fernet import Fernet

        from app.core.encryption import EncryptionManager
        from app.models.vault import VaultConfig, VaultItem

        svc = _unlocked(db_session, test_user)
        out = self._mk(svc)
        row = db_session.get(VaultItem, out["id"])
        assert row.secret_encrypted is not None
        assert "s3cr3t-token" not in row.secret_encrypted
        # Fernet token 以 gAAAAA 开头（版本字节 0x80 + 时间戳）
        assert row.secret_encrypted.startswith("gAAAAA")
        # 且**只有主密码派生密钥**能解开它（证明落库的是密文，不是别的编码）
        cfg = db_session.query(VaultConfig).filter_by(user_id=test_user.id).one()
        key = EncryptionManager.derive_key(MASTER_PW, bytes.fromhex(cfg.salt))
        assert Fernet(key).decrypt(row.secret_encrypted.encode()).decode() == "s3cr3t-token"

    def test_notes_stay_plaintext(self, db_session, test_user):
        """notes 是有意明文的（用户可选填），不应被加密 —— 钉死这个语义。"""
        from app.models.vault import VaultItem

        svc = _unlocked(db_session, test_user)
        out = self._mk(svc)
        row = db_session.get(VaultItem, out["id"])
        assert row.notes == "备注"

    def test_reveal_returns_plaintext(self, db_session, test_user):
        svc = _unlocked(db_session, test_user)
        out = self._mk(svc)
        assert svc.reveal_secret(out["id"])["secret"] == "s3cr3t-token"

    def test_reveal_updates_last_accessed_at(self, db_session, test_user):
        svc = _unlocked(db_session, test_user)
        out = self._mk(svc)
        assert out["last_accessed_at"] is None
        svc.reveal_secret(out["id"])
        assert svc.reveal_secret(out["id"])["secret"] == "s3cr3t-token"
        listed = {i["id"]: i for i in svc.list_items()}[out["id"]]
        assert listed["last_accessed_at"] is not None

    def test_item_without_secret_has_secret_false(self, db_session, test_user):
        svc = _unlocked(db_session, test_user)
        out = svc.create_item(name="纯笔记", category="note", username=None,
                              url=None, secret=None, notes="只有备注",
                              identity_id=None)
        assert out["has_secret"] is False
        assert svc.reveal_secret(out["id"])["secret"] is None

    def test_empty_string_secret_treated_as_none(self, db_session, test_user):
        svc = _unlocked(db_session, test_user)
        out = svc.create_item(name="x", category="login", username=None,
                              url=None, secret="", notes=None, identity_id=None)
        assert out["has_secret"] is False

    def test_update_replaces_secret(self, db_session, test_user):
        svc = _unlocked(db_session, test_user)
        out = self._mk(svc)
        svc.update_item(out["id"], secret="rotated-token")
        assert svc.reveal_secret(out["id"])["secret"] == "rotated-token"

    def test_update_partial_fields_only(self, db_session, test_user):
        svc = _unlocked(db_session, test_user)
        out = self._mk(svc)
        upd = svc.update_item(out["id"], name="GitHub Enterprise")
        assert upd["name"] == "GitHub Enterprise"
        # 未传的字段保持原值（PATCH 语义）
        assert upd["username"] == "yan"
        assert upd["url"] == "https://github.com"

    def test_update_clearing_secret_not_supported_by_none(self, db_session, test_user):
        """钉死已知语义：传 None 表示"不改"，不是"清空"。"""
        svc = _unlocked(db_session, test_user)
        out = self._mk(svc)
        svc.update_item(out["id"], secret=None)
        assert svc.reveal_secret(out["id"])["secret"] == "s3cr3t-token"

    def test_delete_removes_row(self, db_session, test_user):
        from app.models.vault import VaultItem

        svc = _unlocked(db_session, test_user)
        out = self._mk(svc)
        assert svc.delete_item(out["id"])["deleted"] is True
        assert db_session.get(VaultItem, out["id"]) is None

    def test_list_ordered_by_category_then_name(self, db_session, test_user):
        svc = _unlocked(db_session, test_user)
        self._mk(svc, name="zeta", category="note")
        self._mk(svc, name="alpha", category="login")
        names = [i["name"] for i in svc.list_items()]
        assert names == ["alpha", "zeta"]  # login < note

    def test_status_items_count_reflects_creation(self, db_session, test_user):
        svc = _unlocked(db_session, test_user)
        assert svc.status()["items_count"] == 0
        self._mk(svc)
        self._mk(svc, name="另一个")
        assert svc.status()["items_count"] == 2


# ============================================================
# 五、归属隔离（防 IDOR）
# ============================================================
class TestOwnershipIsolation:

    def test_reveal_other_users_item_404(self, db_session, test_user, other_user):
        a = _unlocked(db_session, test_user)
        item = a.create_item(name="A 的凭据", category="login", username=None,
                             url=None, secret="a-secret", notes=None, identity_id=None)
        b = _unlocked(db_session, other_user)
        with pytest.raises(NotFoundException):
            b.reveal_secret(item["id"])

    def test_update_other_users_item_404(self, db_session, test_user, other_user):
        a = _unlocked(db_session, test_user)
        item = a.create_item(name="A", category="login", username=None,
                             url=None, secret=None, notes=None, identity_id=None)
        b = _unlocked(db_session, other_user)
        with pytest.raises(NotFoundException):
            b.update_item(item["id"], name="劫持")

    def test_delete_other_users_item_404_and_no_side_effect(
        self, db_session, test_user, other_user
    ):
        from app.models.vault import VaultItem

        a = _unlocked(db_session, test_user)
        item = a.create_item(name="A", category="login", username=None,
                             url=None, secret=None, notes=None, identity_id=None)
        b = _unlocked(db_session, other_user)
        with pytest.raises(NotFoundException):
            b.delete_item(item["id"])
        assert db_session.get(VaultItem, item["id"]) is not None  # 未被删除

    def test_list_only_shows_own_items(self, db_session, test_user, other_user):
        a = _unlocked(db_session, test_user)
        a.create_item(name="A", category="login", username=None,
                      url=None, secret=None, notes=None, identity_id=None)
        b = _unlocked(db_session, other_user)
        b.create_item(name="B", category="login", username=None,
                      url=None, secret=None, notes=None, identity_id=None)
        assert [i["name"] for i in a.list_items()] == ["A"]
        assert [i["name"] for i in b.list_items()] == ["B"]

    def test_unlock_is_per_user(self, db_session, test_user, other_user):
        """A 解锁不影响 B —— 解锁态按 user_id 隔离。"""
        a = _unlocked(db_session, test_user)
        b = _svc(db_session, other_user)
        assert a.status()["unlocked"] is True
        assert b.status()["unlocked"] is False


# ============================================================
# 六、身份轴关联
# ============================================================
class TestIdentityLink:

    def _identity(self, db_session, user, name="开发"):
        from app.repositories.identity_repo import IdentityRepository

        return IdentityRepository(db_session).create(
            user_id=user.id, name=name, slug=f"dev-{name}", color_token="--id-1", icon="code",
        )

    def test_link_own_identity(self, db_session, test_user):
        svc = _unlocked(db_session, test_user)
        ident = self._identity(db_session, test_user)
        out = svc.create_item(name="x", category="login", username=None, url=None,
                              secret=None, notes=None, identity_id=ident.id)
        assert out["identity_id"] == ident.id

    def test_link_unknown_identity_rejected(self, db_session, test_user):
        svc = _unlocked(db_session, test_user)
        with pytest.raises(ValidationException) as ei:
            svc.create_item(name="x", category="login", username=None, url=None,
                            secret=None, notes=None, identity_id="no-such-identity")
        assert "身份不存在" in str(ei.value)

    def test_link_other_users_identity_rejected(self, db_session, test_user, other_user):
        svc = _unlocked(db_session, test_user)
        foreign = self._identity(db_session, other_user, name="外部")
        with pytest.raises(ValidationException):
            svc.create_item(name="x", category="login", username=None, url=None,
                            secret=None, notes=None, identity_id=foreign.id)

    def test_update_to_foreign_identity_rejected_and_no_side_effect(
        self, db_session, test_user, other_user
    ):
        from app.models.vault import VaultItem

        svc = _unlocked(db_session, test_user)
        item = svc.create_item(name="x", category="login", username=None, url=None,
                               secret=None, notes=None, identity_id=None)
        foreign = self._identity(db_session, other_user)
        with pytest.raises(ValidationException):
            svc.update_item(item["id"], identity_id=foreign.id)
        assert db_session.get(VaultItem, item["id"]).identity_id is None


# ============================================================
# 七、终端动作白名单（无注入面）
# ============================================================
class TestActionWhitelist:

    def _mk(self, svc, **over):
        kw = dict(name="跳板机", category="login", username=None, url=None,
                  secret=None, notes=None, identity_id=None)
        kw.update(over)
        return svc.create_item(**kw)

    def test_action_types_are_closed_set(self):
        assert ACTION_TYPES == {"none", "ssh"}

    def test_unknown_action_type_rejected(self, db_session, test_user):
        svc = _unlocked(db_session, test_user)
        with pytest.raises(ValidationException) as ei:
            self._mk(svc, action_type="rm -rf")
        assert "不支持的动作类型" in str(ei.value)

    def test_ssh_without_host_rejected(self, db_session, test_user):
        svc = _unlocked(db_session, test_user)
        with pytest.raises(ValidationException) as ei:
            self._mk(svc, action_type="ssh", action_host=None)
        assert "主机名" in str(ei.value)

    @pytest.mark.parametrize("bad_host", [
        "host name",            # 空格
        "host;rm -rf /",        # 命令分隔符
        "host|cat /etc/passwd", # 管道
        "$(whoami)",            # 命令替换
        "host`id`",             # 反引号
        "host\nmalicious",      # 换行
        "",                     # 空
        "a" * 254,              # 超长
    ])
    def test_ssh_host_injection_rejected(self, db_session, test_user, bad_host):
        svc = _unlocked(db_session, test_user)
        with pytest.raises(ValidationException):
            self._mk(svc, action_type="ssh", action_host=bad_host)

    def test_ssh_username_injection_rejected(self, db_session, test_user):
        svc = _unlocked(db_session, test_user)
        with pytest.raises(ValidationException):
            self._mk(svc, action_type="ssh", action_host="ok.example.com",
                     action_user="u; rm -rf /")

    @pytest.mark.parametrize("bad_port", ["abc", "-1", "0", "65536", "22; ls", "1e3"])
    def test_ssh_port_out_of_whitelist_rejected(self, db_session, test_user, bad_port):
        svc = _unlocked(db_session, test_user)
        # "-1" / "22; ls" 不匹配纯数字正则 → 拒绝；
        # "0" / "65536" 是数字但越界 → 拒绝。
        with pytest.raises(ValidationException):
            self._mk(svc, action_type="ssh", action_host="ok.example.com",
                     action_port=bad_port)

    def test_ssh_valid_config_stored(self, db_session, test_user):
        svc = _unlocked(db_session, test_user)
        out = self._mk(svc, action_type="ssh", action_host="jump.example.com",
                       action_user="deploy", action_port="2222")
        assert out["action_type"] == "ssh"
        assert out["action_host"] == "jump.example.com"
        assert out["action_user"] == "deploy"
        assert out["action_port"] == "2222"

    def test_ssh_default_port_empty_is_none(self, db_session, test_user):
        svc = _unlocked(db_session, test_user)
        out = self._mk(svc, action_type="ssh", action_host="h.example.com",
                       action_port="")
        assert out["action_port"] is None

    def test_switch_back_to_none_clears_action_fields(self, db_session, test_user):
        svc = _unlocked(db_session, test_user)
        out = self._mk(svc, action_type="ssh", action_host="h.example.com",
                       action_user="u", action_port="22")
        cleared = svc.update_item(out["id"], action_type="none")
        assert cleared["action_type"] == "none"
        assert cleared["action_host"] is None
        assert cleared["action_user"] is None
        assert cleared["action_port"] is None

    def test_update_action_revalidates_whole_set(self, db_session, test_user):
        """只改 port 也要整体校验（避免半套配置落库）。"""
        svc = _unlocked(db_session, test_user)
        out = self._mk(svc, action_type="ssh", action_host="h.example.com")
        with pytest.raises(ValidationException):
            svc.update_item(out["id"], action_port="not-a-port")


# ============================================================
# 八、run_action 拒绝路径（绝不真的启动进程）
# ============================================================
class TestRunActionRefusals:

    def test_run_action_with_none_type_rejected(self, db_session, test_user):
        svc = _unlocked(db_session, test_user)
        item = svc.create_item(name="x", category="login", username=None, url=None,
                               secret=None, notes=None, identity_id=None)
        with pytest.raises(ValidationException) as ei:
            svc.run_action(item["id"])
        assert "未配置终端动作" in str(ei.value)

    def test_run_action_without_secret_rejected(self, db_session, test_user):
        svc = _unlocked(db_session, test_user)
        item = svc.create_item(name="x", category="login", username=None, url=None,
                               secret=None, notes=None, identity_id=None,
                               action_type="ssh", action_host="h.example.com")
        with pytest.raises(ValidationException) as ei:
            svc.run_action(item["id"])
        assert "密钥文件路径" in str(ei.value)

    def test_run_action_missing_key_file_rejected(self, db_session, test_user,
                                                  tmp_path, monkeypatch):
        """密钥文件不存在 → 拒绝。

        这是**唯一能安全触达 run_action 深处的路径**：必须先通过解锁、
        动作类型、主机名、密钥存在性四道关。这里用明确不存在的路径，
        保证不会走到 subprocess.Popen。另用 monkeypatch 兜底断言未启动进程。
        """
        import subprocess

        calls: list = []
        monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: calls.append((a, k)))
        svc = _unlocked(db_session, test_user)
        missing = tmp_path / "no-such-key-file"
        assert not missing.exists()
        item = svc.create_item(name="x", category="login", username=None, url=None,
                               secret=str(missing), notes=None, identity_id=None,
                               action_type="ssh", action_host="h.example.com")
        with pytest.raises(ValidationException) as ei:
            svc.run_action(item["id"])
        assert "密钥文件不存在" in str(ei.value)
        assert calls == [], "密钥文件缺失时绝不能启动任何进程"

    def test_run_action_other_users_item_404(self, db_session, test_user, other_user):
        a = _unlocked(db_session, test_user)
        item = a.create_item(name="x", category="login", username=None, url=None,
                             secret="/no/such", notes=None, identity_id=None,
                             action_type="ssh", action_host="h.example.com")
        b = _unlocked(db_session, other_user)
        with pytest.raises(NotFoundException):
            b.run_action(item["id"])


# ============================================================
# 九、SSH 连通性探测（只用 monkeypatch，不打真实网络）
# ============================================================
class TestActionConnectionProbe:

    def _ssh_item(self, svc, host="jump.example.com", port=None):
        return svc.create_item(name="跳板", category="login", username=None, url=None,
                               secret=None, notes=None, identity_id=None,
                               action_type="ssh", action_host=host, action_port=port)

    def _fake_conn(self, *, fail: bool):
        import contextlib

        @contextlib.contextmanager
        def _cm(address, timeout=None):
            if fail:
                raise OSError("connection refused")
            yield object()
        return _cm

    def test_non_ssh_item_rejected(self, db_session, test_user):
        svc = _unlocked(db_session, test_user)
        item = svc.create_item(name="纯凭据", category="login", username=None, url=None,
                               secret=None, notes=None, identity_id=None)
        with pytest.raises(ValidationException) as ei:
            svc.test_action_connection(item["id"])
        assert "action_type != ssh" in str(ei.value)

    def test_reachable_returns_true(self, db_session, test_user, monkeypatch):
        svc = _unlocked(db_session, test_user)
        item = self._ssh_item(svc, port="22")
        monkeypatch.setattr(vs.socket, "create_connection", self._fake_conn(fail=False))
        r = svc.test_action_connection(item["id"])
        assert r["reachable"] is True
        assert r["host"] == "jump.example.com"
        assert r["port"] == 22
        assert r["error"] is None
        assert isinstance(r["elapsed_ms"], int)

    def test_unreachable_returns_false_with_error(self, db_session, test_user, monkeypatch):
        svc = _unlocked(db_session, test_user)
        item = self._ssh_item(svc)
        monkeypatch.setattr(vs.socket, "create_connection", self._fake_conn(fail=True))
        r = svc.test_action_connection(item["id"])
        assert r["reachable"] is False
        assert "connection refused" in r["error"]
        assert r["port"] == 22  # 未配置时默认 22

    def test_probe_uses_stored_host_only(self, db_session, test_user, monkeypatch):
        """探测目标只能来自已存凭据 —— 否则就是任意 host:port 探测原语。"""
        seen: list = []

        def _spy(address, timeout=None):
            seen.append(address)
            raise OSError("nope")

        svc = _unlocked(db_session, test_user)
        item = self._ssh_item(svc, host="only-this.example.com", port="2222")
        monkeypatch.setattr(vs.socket, "create_connection", _spy)
        svc.test_action_connection(item["id"])
        assert seen == [("only-this.example.com", 2222)]

    def test_other_users_item_404(self, db_session, test_user, other_user):
        a = _unlocked(db_session, test_user)
        item = self._ssh_item(a)
        b = _unlocked(db_session, other_user)
        with pytest.raises(NotFoundException):
            b.test_action_connection(item["id"])


# ============================================================
# 十、更换主密码（原地重加密全部凭据）
# ============================================================
class TestChangeMasterPassword:

    NEW_PW = "brand-new-master-pass"

    def test_change_rejects_short_new_password(self, db_session, test_user):
        svc = _unlocked(db_session, test_user)
        with pytest.raises(ValidationException):
            svc.change_master_password(MASTER_PW, "short")

    def test_change_rejects_wrong_old_password(self, db_session, test_user):
        svc = _unlocked(db_session, test_user)
        with pytest.raises(ValidationException) as ei:
            svc.change_master_password("not-the-old-one", self.NEW_PW)
        assert "原主密码错误" in str(ei.value)

    def test_change_reencrypts_existing_items(self, db_session, test_user):
        """核心回归：换密码后，**老凭据仍能解出原明文**。

        防什么：只换 verifier 而不重加密 secret_encrypted —— 换密码成功，
        但所有历史凭据永久解不开（静默数据丢失）。
        """
        svc = _unlocked(db_session, test_user)
        a = svc.create_item(name="A", category="login", username=None, url=None,
                            secret="secret-A", notes=None, identity_id=None)
        b = svc.create_item(name="B", category="login", username=None, url=None,
                            secret="secret-B", notes=None, identity_id=None)

        svc.change_master_password(MASTER_PW, self.NEW_PW)

        assert svc.reveal_secret(a["id"])["secret"] == "secret-A"
        assert svc.reveal_secret(b["id"])["secret"] == "secret-B"
        assert svc.status()["unlocked"] is True

    def test_change_invalidates_old_password(self, db_session, test_user):
        svc = _unlocked(db_session, test_user)
        svc.change_master_password(MASTER_PW, self.NEW_PW)
        svc.lock()
        with pytest.raises(ValidationException):
            svc.unlock(MASTER_PW)
        assert svc.unlock(self.NEW_PW)["unlocked"] is True

    def test_change_rotates_salt(self, db_session, test_user):
        from app.models.vault import VaultConfig

        svc = _unlocked(db_session, test_user)
        before = db_session.query(VaultConfig).filter_by(user_id=test_user.id).one().salt
        svc.change_master_password(MASTER_PW, self.NEW_PW)
        after = db_session.query(VaultConfig).filter_by(user_id=test_user.id).one().salt
        assert before != after, "换密码必须换 salt"

    def test_change_ciphertext_actually_changes(self, db_session, test_user):
        from app.models.vault import VaultItem

        svc = _unlocked(db_session, test_user)
        item = svc.create_item(name="A", category="login", username=None, url=None,
                               secret="same-secret", notes=None, identity_id=None)
        before = db_session.get(VaultItem, item["id"]).secret_encrypted
        svc.change_master_password(MASTER_PW, self.NEW_PW)
        db_session.expire_all()
        after = db_session.get(VaultItem, item["id"]).secret_encrypted
        assert before != after
        assert svc.reveal_secret(item["id"])["secret"] == "same-secret"

    def test_change_only_touches_own_items(self, db_session, test_user, other_user):
        """换 A 的密码不得影响 B 的凭据解密。"""
        a = _unlocked(db_session, test_user)
        b = _unlocked(db_session, other_user)
        b_item = b.create_item(name="B", category="login", username=None, url=None,
                               secret="b-secret", notes=None, identity_id=None)
        a.change_master_password(MASTER_PW, self.NEW_PW)
        assert b.reveal_secret(b_item["id"])["secret"] == "b-secret"
