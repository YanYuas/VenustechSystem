# ============================================================
# 安全服务层测试（app/services/security_service.py）
#
# 覆盖目标（安全面，优先级最高）：
#   1. **rotate_key 真的重加密**（本文件最重要的回归组，见 TestRotateReallyReencrypts）
#   2. 注册表一致性：凡用全局 EncryptionManager 加密落库的列都必须登记
#   3. 不归本密钥管的密文（DPAPI / 保险箱 / 损坏值）必须跳过且不阻断
#   4. 失败整体回滚，绝不留下"半新半旧"
#   5. require_unlocked 门禁
#   6. 审计：永不抛异常、动作白名单降级、截断、AUDIT_KEEP 修剪、归属隔离
#
# 2026-10-11 本文件暴露并修复的生产缺陷（勿删，回归价值）：
#   - `_CIPHER_COLUMNS` 登记的 `users.api_key_encrypted` **从未被真正轮换**
#     （列值带 "fernet:" 前缀，旧代码拿整串去 mgr.decrypt 必然失败 → 静默跳过），
#     该列只能靠密钥环兜底，实测**第 4 次轮换后永久解不开**。
#   - `vault_items.secret_encrypted` 本不属于本服务（由保险箱主密码派生密钥管理），
#     旧代码却登记在此 → 每次都静默跳过，还在返回值里谎报"已轮换"。
# ============================================================
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.fernet import Fernet

from app.core.encryption import EncryptionManager
from app.core.exceptions import BusinessException, ValidationException
from app.models.audit import AUDIT_ACTIONS, AuditLog
from app.models.settings import Setting
from app.models.user import User
from app.services import security_service as ss
from app.services.security_service import (
    AUDIT_KEEP,
    SecurityService,
    audit,
    list_audit,
    require_unlocked,
)

FERNET_PREFIX = "fernet:"


# ============================================================
# 夹具
# ============================================================
@pytest.fixture()
def enc_dir(tmp_path, monkeypatch):
    """把 SecurityService 的加密数据目录指向 tmp_path。

    必须隔离：`rotate_key` 内部 `EncryptionManager(Path(get_settings().data_dir))`，
    不隔离就会去轮换**整个测试会话共用**的临时库目录里的真实密钥文件，
    把后续用例全部污染（且症状隐蔽 —— 只有需要解密的用例才炸）。
    """
    class _FakeSettings:
        data_dir = str(tmp_path)
        dev = True

    monkeypatch.setattr(ss, "get_settings", lambda: _FakeSettings)
    return tmp_path


@pytest.fixture(autouse=True)
def _reset_vault_session():
    """解锁态是模块级进程内存全局，clean_db 清不掉 —— 用例前后各清一次。"""
    from app.services import vault_service as vs

    vs._session_keys.clear()
    yield
    vs._session_keys.clear()


def _svc(db, user) -> SecurityService:
    return SecurityService(db, user.id)


def _fernet_token(mgr: EncryptionManager, plaintext: str) -> str:
    """复刻 `encrypt_secret()` 在非 Windows/无 DPAPI 环境下的落库格式。"""
    return FERNET_PREFIX + mgr.encrypt(plaintext).decode()


def _reopen(data_dir) -> EncryptionManager:
    return EncryptionManager(data_dir)


# ============================================================
# 一、注册表一致性（把铁律落成检查）
# ============================================================
class TestCipherColumnRegistry:

    def test_every_model_encrypted_column_is_registered_or_exempt(self):
        """凡模型里命名为 `*_encrypted` 的列，必须登记进轮换表或被显式豁免。

        这是本模块最重要的一条"铁律落成脚本"：`_CIPHER_COLUMNS` 漏登记
        不会报错、不会失败，只会让该列在若干次轮换后**永久解不开**
        （密钥环只留 KEEP_PREVIOUS 代）。所以此处用源码级扫描把它顶住 ——
        新增一个加密列而不登记，本用例立刻变红。

        豁免必须带理由，且理由必须指向真正管理该密钥的代码位置。
        """
        # 豁免表：不归全局 EncryptionManager 管的加密列 → 原因
        exempt = {
            # 由**保险箱主密码**派生的独立 Fernet 加密（vault_service._require_fernet），
            # 其轮换在 VaultService.change_password 中完成，与全局密钥无关。
            ("vault_items", "secret_encrypted"): "VaultService.change_password",
        }
        registered = {(t, c) for t, c in ss._CIPHER_COLUMNS}

        found = _scan_encrypted_model_columns()
        # 先证明扫描器真的在工作：否则"未处理的列"恒为空集 → 本用例变成永真断言。
        assert found, "扫描器没扫到任何 *_encrypted 列，本守护形同虚设"
        assert {("users", "api_key_encrypted"), ("vault_items", "secret_encrypted")} <= found

        unhandled = {pair for pair in found if pair not in registered and pair not in exempt}
        assert not unhandled, (
            f"以下加密列既未登记进 _CIPHER_COLUMNS，也未在豁免表中说明原因：{unhandled}。"
            f"若由全局密钥加密 → 必须登记，否则密钥轮换后永久解不开；"
            f"若由别处密钥管理 → 请加入 exempt 并写明理由。"
        )

    def test_rows_of_resolves_every_registered_table(self, db_session, test_user):
        """`_CIPHER_COLUMNS` 里的每张表，`_rows_of` 都必须能取到行。

        登记了表却取不到行 = 该表密文在轮换中被静默漏掉（等价于没登记）。
        这条防的是"注册表与 `_rows_of` 分支脱节"。
        """
        svc = _svc(db_session, test_user)
        for table, _column in ss._CIPHER_COLUMNS:
            rows = svc._rows_of(table)
            assert rows, f"表 {table} 已登记但 _rows_of 取不到任何行（落进了兜底分支？）"

    def test_rows_of_unknown_table_returns_empty(self, db_session, test_user):
        assert _svc(db_session, test_user)._rows_of("no_such_table") == []

    def test_vault_items_not_registered(self):
        """回归断言：`vault_items` 曾被错误登记。

        它的密文由保险箱主密码派生的独立密钥加密，用全局密钥**必然解不开**，
        旧代码因此每次都静默跳过，却在返回值里谎报"已轮换"。
        """
        assert ("vault_items", "secret_encrypted") not in {
            (t, c) for t, c in ss._CIPHER_COLUMNS
        }


def _scan_encrypted_model_columns() -> set[tuple[str, str]]:
    """扫描全部模型，返回 (表名, 列名) 中列名含 'encrypted' 的集合。"""
    import app.models as models

    found: set[tuple[str, str]] = set()
    for name in dir(models):
        obj = getattr(models, name)
        table = getattr(obj, "__table__", None)
        if table is None:
            continue
        for column in table.columns:
            if "encrypted" in column.name:
                found.add((table.name, column.name))
    return found


# ============================================================
# 二、rotate_key 真的重加密（核心回归）
# ============================================================
class TestRotateReallyReencrypts:

    def test_api_key_ciphertext_is_actually_rewritten(self, db_session, test_user, enc_dir):
        """回归断言：修复前该列**从未**被重写（前缀导致 decrypt 必然失败）。

        判据用「密文是否变化」而不是「能否解密」：修复前靠密钥环也能解密，
        所以只看能不能解是发现不了问题的（这正是它潜伏至今的原因）。
        """
        mgr = EncryptionManager(enc_dir)
        before = _fernet_token(mgr, "sk-live-key")
        test_user.api_key_encrypted = before
        db_session.flush()

        _svc(db_session, test_user).rotate_key()

        db_session.expire_all()
        after = db_session.get(User, test_user.id).api_key_encrypted
        assert after != before, "api_key_encrypted 未被重写（轮换实际没生效）"
        assert after.startswith(FERNET_PREFIX), "前缀必须保留，否则 decrypt_secret 认不出格式"

    def test_rewritten_api_key_decryptable_via_decrypt_secret(self, db_session, test_user, enc_dir):
        """重写后的值必须仍能被业务读取路径（`decrypt_secret`）解开。"""
        mgr = EncryptionManager(enc_dir)
        test_user.api_key_encrypted = _fernet_token(mgr, "sk-round-trip")
        db_session.flush()

        _svc(db_session, test_user).rotate_key()
        db_session.expire_all()
        stored = db_session.get(User, test_user.id).api_key_encrypted

        assert stored[len(FERNET_PREFIX):] and \
            _reopen(enc_dir).decrypt(stored[len(FERNET_PREFIX):]) == "sk-round-trip"

    def test_api_key_survives_repeated_rotations(self, db_session, test_user, enc_dir):
        """**核回归**：连续轮换超过密钥环代数后，当前列值仍必须可解。

        修复前的实证：第 4 次轮换后 `解密失败：密钥不匹配或数据已损坏`
        （KEEP_PREVIOUS=5，但历史里攒了重复项，实际第 4 次就丢掉了原始密钥）。
        修复后每轮都真正重写，密钥环代数与数据可用性彻底解耦。
        """
        mgr = EncryptionManager(enc_dir)
        test_user.api_key_encrypted = _fernet_token(mgr, "sk-must-survive")
        db_session.flush()

        rounds = EncryptionManager.KEEP_PREVIOUS + 1
        for i in range(1, rounds + 1):
            _svc(db_session, test_user).rotate_key()
            db_session.expire_all()
            live = db_session.get(User, test_user.id).api_key_encrypted
            plain = _reopen(enc_dir).decrypt(live[len(FERNET_PREFIX):])
            assert plain == "sk-must-survive", f"第 {i} 次轮换后列值不可解"

    def test_global_singleton_follows_rotation(self, db_session, test_user, enc_dir, monkeypatch):
        """**端到端回归**：轮换后**应用级单例**必须能解开新密文。

        为什么前面的 `_reopen(enc_dir)` 写法测不出本缺陷：新建一个 manager
        自然会从磁盘读到新密钥。真实读取路径是 `decrypt_secret()` →
        `get_encryption()` —— main.py 启动时建的**长驻单例**，它的 `_fernet`
        只在进程启动读一次磁盘。不刷新它的症状正是最误导的那类：
        提示「密钥轮换成功」，但 API Key 当场失效，**重启服务才恢复**。
        （2026-10-11 由 smoke_backend 的往返断言先测出，本用例把它固化到单元层。）
        """
        import app.core.encryption as enc_mod
        from app.core.security import decrypt_secret, encrypt_secret

        monkeypatch.setattr(enc_mod, "_encryption_manager", EncryptionManager(enc_dir))

        token = encrypt_secret("sk-singleton-777")
        assert token.startswith(FERNET_PREFIX)
        test_user.api_key_encrypted = token
        db_session.flush()
        assert decrypt_secret(token) == "sk-singleton-777", "前置条件：轮换前应可读"

        _svc(db_session, test_user).rotate_key()

        db_session.expire_all()
        after = db_session.get(User, test_user.id).api_key_encrypted
        assert after != token, "轮换未真正重写密文"
        assert decrypt_secret(after) == "sk-singleton-777", \
            "轮换后全局单例仍用旧密钥 → API Key 失效（需刷新单例）"

    def test_deepseek_setting_is_rewritten(self, db_session, test_user, enc_dir):
        mgr = EncryptionManager(enc_dir)
        before = mgr.encrypt("ds-key-plain").decode()
        setting = Setting(user_id=test_user.id, key="assistant.deepseek_key", value=before)
        db_session.add(setting)
        db_session.flush()

        _svc(db_session, test_user).rotate_key()

        db_session.expire_all()
        after = db_session.get(Setting, setting.id).value
        assert after != before
        assert _reopen(enc_dir).decrypt(after) == "ds-key-plain"

    def test_blank_setting_value_is_skipped(self, db_session, test_user, enc_dir):
        setting = Setting(user_id=test_user.id, key="assistant.deepseek_key", value="   ")
        db_session.add(setting)
        db_session.flush()

        res = _svc(db_session, test_user).rotate_key()
        assert res["rotated"] == 0
        db_session.expire_all()
        assert db_session.get(Setting, setting.id).value == "   "

    def test_other_users_rows_untouched(self, db_session, test_user, other_user, enc_dir):
        """轮换只碰当前用户的行（归属隔离，避免把别人的密文改坏）。"""
        mgr = EncryptionManager(enc_dir)
        other_api_before = _fernet_token(mgr, "other-secret")
        other_user.api_key_encrypted = other_api_before
        other_setting = Setting(user_id=other_user.id, key="assistant.deepseek_key",
                                value=mgr.encrypt("other-ds").decode())
        other_setting_before = other_setting.value
        db_session.add(other_setting)
        db_session.flush()

        _svc(db_session, test_user).rotate_key()

        db_session.expire_all()
        assert db_session.get(User, other_user.id).api_key_encrypted == other_api_before
        assert db_session.get(Setting, other_setting.id).value == other_setting_before


# ============================================================
# 三、返回值如实汇报
# ============================================================
class TestRotationReport:

    def test_reports_only_tables_actually_rotated(self, db_session, test_user, enc_dir):
        """回归断言：修复前返回静态清单 `['vault_items','users','settings']`，
        即使那两张表一行都没动过 —— 等于谎报。"""
        mgr = EncryptionManager(enc_dir)
        test_user.api_key_encrypted = _fernet_token(mgr, "sk-1")
        db_session.add(Setting(user_id=test_user.id, key="assistant.deepseek_key",
                               value=mgr.encrypt("ds-1").decode()))
        db_session.flush()

        res = _svc(db_session, test_user).rotate_key()

        assert res["rotated"] == 2
        assert res["tables"] == ["settings", "users"]
        assert res["details"] == {"users": 1, "settings": 1}

    def test_empty_database_reports_zero(self, db_session, test_user, enc_dir):
        res = _svc(db_session, test_user).rotate_key()
        assert res == {"rotated": 0, "tables": [], "details": {}}

    def test_reports_skipped_columns_never_claim_them(self, db_session, test_user, enc_dir):
        """只有 api_key 一条时，`tables` 不得出现 vault_items。"""
        mgr = EncryptionManager(enc_dir)
        test_user.api_key_encrypted = _fernet_token(mgr, "sk-only")
        db_session.flush()
        res = _svc(db_session, test_user).rotate_key()
        assert res["tables"] == ["users"]
        assert "vault_items" not in res["tables"]


# ============================================================
# 四、跳过的密文：不归本密钥管的，跳过且不阻断
# ============================================================
class TestSkipForeignCiphertext:

    def test_dpapi_prefixed_value_is_skipped(self, db_session, test_user, enc_dir):
        """DPAPI 密文由 Windows DPAPI 自管密钥，不归本管理器管 → 跳过且不改写。"""
        test_user.api_key_encrypted = "dpapi:AAAA-not-a-fernet-token"
        db_session.flush()

        res = _svc(db_session, test_user).rotate_key()

        assert res["rotated"] == 0
        db_session.expire_all()
        assert db_session.get(User, test_user.id).api_key_encrypted == \
            "dpapi:AAAA-not-a-fernet-token"

    def test_corrupted_value_skipped_without_aborting(self, db_session, test_user, enc_dir):
        """一条坏数据不能让整次轮换回滚 —— 好的那条仍应被轮换。"""
        mgr = EncryptionManager(enc_dir)
        good_before = mgr.encrypt("ds-good").decode()
        setting = Setting(user_id=test_user.id, key="assistant.deepseek_key", value=good_before)
        db_session.add(setting)
        test_user.api_key_encrypted = "fernet:gAAAAA-corrupted"
        db_session.flush()

        res = _svc(db_session, test_user).rotate_key()

        assert res["rotated"] == 1
        assert res["tables"] == ["settings"]
        db_session.expire_all()
        assert db_session.get(User, test_user.id).api_key_encrypted == "fernet:gAAAAA-corrupted"
        assert db_session.get(Setting, setting.id).value != good_before

    def test_null_and_empty_values_skipped(self, db_session, test_user, enc_dir):
        test_user.api_key_encrypted = None
        db_session.flush()
        assert _svc(db_session, test_user).rotate_key()["rotated"] == 0

    def test_vault_item_ciphertext_untouched(self, db_session, test_user, enc_dir):
        """保险箱密文与全局密钥无关，轮换不得碰它（也不该声称碰过）。"""
        from app.models.vault import VaultItem

        vault_token = Fernet(Fernet.generate_key()).encrypt(b"vault-secret").decode()
        item = VaultItem(user_id=test_user.id, name="凭据", category="login",
                         secret_encrypted=vault_token)
        db_session.add(item)
        db_session.flush()

        res = _svc(db_session, test_user).rotate_key()

        db_session.expire_all()
        assert db_session.get(VaultItem, item.id).secret_encrypted == vault_token
        assert "vault_items" not in res["tables"]


# ============================================================
# 五、原子性：失败整体回滚
# ============================================================
class TestRotationAtomicity:

    def test_missing_backend_raises_business_exception(self, db_session, test_user, enc_dir,
                                                       monkeypatch):
        monkeypatch.setattr(EncryptionManager, "is_available",
                            property(lambda self: False))
        with pytest.raises(BusinessException, match="加密模块不可用"):
            _svc(db_session, test_user).rotate_key()

    def test_write_back_failure_rolls_back_db(self, db_session, test_user, enc_dir, monkeypatch):
        """重加密写回阶段失败 → 库必须整体回滚，不留"半新半旧"。

        注意**如实记录**：密钥文件是文件系统对象，不参与 DB 事务，不会被回滚。
        所以此时靠密钥环保住旧密文可读 —— 本用例同时断言这一点。
        """
        mgr = EncryptionManager(enc_dir)
        before = _fernet_token(mgr, "sk-atomic")
        test_user.api_key_encrypted = before
        # 必须先提交：`rotate_key` 失败时会 `db.rollback()`，那会把夹具里
        # 尚未提交的 test_user 一并回滚掉（实测 → 回查时 user 已不存在）。
        db_session.commit()

        class _BoomManager(EncryptionManager):
            def encrypt(self, data):  # noqa: ARG002
                raise RuntimeError("模拟写入阶段失败")

        monkeypatch.setattr(ss, "EncryptionManager", _BoomManager)

        with pytest.raises(BusinessException, match="密钥轮换失败，已回滚"):
            _svc(db_session, test_user).rotate_key()

        db_session.expire_all()
        assert db_session.get(User, test_user.id).api_key_encrypted == before, "库未回滚"
        # 旧密文仍可解（密钥环保住了旧密钥）—— 这正是"轮换中断不丢数据"的设计意图
        assert _reopen(enc_dir).decrypt(before[len(FERNET_PREFIX):]) == "sk-atomic"

    def test_no_master_key_argument_keeps_random_key_mode(self, db_session, test_user, enc_dir):
        res = _svc(db_session, test_user).rotate_key(new_master_key="brand-new")
        assert res["rotated"] == 0
        assert (enc_dir / ".encryption_key.salt").exists()


# ============================================================
# 六、require_unlocked 门禁
# ============================================================
class TestRequireUnlocked:

    def test_locked_user_is_rejected(self, test_user):
        with pytest.raises(ValidationException, match="保险箱未解锁"):
            require_unlocked(test_user.id)

    def test_unlocked_user_passes(self, test_user):
        from app.services import vault_service as vs

        vs._session_keys[test_user.id] = Fernet.generate_key()
        # 显式断言返回值而不是只写「不抛异常」——没有断言的用例在缺陷存在时
        # 也会全绿（本仓 audit_test_quality.py 会把它判为 NO_ASSERT）。
        assert require_unlocked(test_user.id) is None

    def test_other_users_unlock_does_not_leak(self, test_user, other_user):
        from app.services import vault_service as vs

        vs._session_keys[other_user.id] = Fernet.generate_key()
        with pytest.raises(ValidationException):
            require_unlocked(test_user.id)


# ============================================================
# 七、审计
# ============================================================
class TestAudit:

    def _seed(self, db, user_id, n, *, start=0):
        rows = [
            AuditLog(user_id=user_id, action="security.encrypt", ok=True,
                     created_at=datetime(2026, 6, 1, tzinfo=timezone.utc) + timedelta(seconds=i))
            for i in range(start, start + n)
        ]
        db.add_all(rows)
        db.commit()
        return rows

    def test_audit_writes_and_reads_back(self, db_session, test_user):
        audit(db_session, test_user.id, "security.encrypt", target="api_key")
        items = list_audit(db_session, test_user.id)
        assert len(items) == 1
        assert items[0]["action"] == "security.encrypt"
        assert items[0]["target"] == "api_key"
        assert items[0]["ok"] is True

    def test_unregistered_action_degrades_to_plugin_error(self, db_session, test_user):
        """未登记动作降级归类，绝不静默丢弃（白名单防任意字符串入库）。"""
        audit(db_session, test_user.id, "totally.made.up")
        assert list_audit(db_session, test_user.id)[0]["action"] == "plugin.error"

    def test_all_whitelisted_actions_are_accepted(self, db_session, test_user):
        assert AUDIT_ACTIONS, "动作白名单不得为空"
        for action in sorted(AUDIT_ACTIONS):
            audit(db_session, test_user.id, action)
        stored = {i["action"] for i in list_audit(db_session, test_user.id, 200)}
        assert stored == set(AUDIT_ACTIONS)

    def test_target_truncated_to_200(self, db_session, test_user):
        audit(db_session, test_user.id, "security.encrypt", target="x" * 500)
        assert len(list_audit(db_session, test_user.id)[0]["target"]) == 200

    def test_detail_truncated_to_1000(self, db_session, test_user):
        audit(db_session, test_user.id, "security.encrypt", detail="y" * 5000)
        assert len(list_audit(db_session, test_user.id)[0]["detail"]) == 1000

    def test_blank_target_and_detail_become_null(self, db_session, test_user):
        audit(db_session, test_user.id, "security.encrypt", target="", detail="")
        row = list_audit(db_session, test_user.id)[0]
        assert row["target"] is None and row["detail"] is None

    def test_audit_never_raises_when_db_broken(self):
        """审计本身永不抛异常 —— 不能因为记日志把业务打断。"""
        rolled_back = []

        class _BoomDb:
            def add(self, _obj):
                raise RuntimeError("db down")

            def rollback(self):
                rolled_back.append(True)

        audit(_BoomDb(), "u1", "security.encrypt")  # 不抛异常
        assert rolled_back == [True]

    def test_audit_trims_to_keep_limit(self, db_session, test_user):
        """写入后按 AUDIT_KEEP 修剪最旧记录（原来无上限，长期持续膨胀）。"""
        self._seed(db_session, test_user.id, AUDIT_KEEP + 5)
        audit(db_session, test_user.id, "security.rotate_key")
        total = db_session.query(AuditLog).filter(AuditLog.user_id == test_user.id).count()
        assert total == AUDIT_KEEP

    def test_trim_keeps_newest(self, db_session, test_user):
        self._seed(db_session, test_user.id, AUDIT_KEEP + 5)
        audit(db_session, test_user.id, "security.rotate_key")
        # 最新那条一定还在
        newest = list_audit(db_session, test_user.id, 1)[0]
        assert newest["action"] == "security.rotate_key"

    def test_below_limit_does_not_trim(self, db_session, test_user):
        self._seed(db_session, test_user.id, 10)
        audit(db_session, test_user.id, "security.rotate_key")
        total = db_session.query(AuditLog).filter(AuditLog.user_id == test_user.id).count()
        assert total == 11

    def test_audit_rows_isolated_by_user(self, db_session, test_user, other_user):
        audit(db_session, test_user.id, "security.encrypt")
        audit(db_session, other_user.id, "security.decrypt")
        assert {i["action"] for i in list_audit(db_session, test_user.id)} == {"security.encrypt"}


# ============================================================
# 八、list_audit 上限与过滤
# ============================================================
class TestListAudit:

    def test_returns_newest_first(self, db_session, test_user):
        """倒序取最近 N 条。

        这里显式给 created_at 递增时间戳，不依赖 `audit()` 的默认 utcnow ——
        连续三次调用可能落在同一微秒，排序会变成未定义（潜在 flaky）。
        """
        base = datetime(2026, 6, 1, tzinfo=timezone.utc)
        db_session.add_all([
            AuditLog(user_id=test_user.id, action=action, ok=True,
                     created_at=base + timedelta(seconds=i))
            for i, action in enumerate(
                ("security.encrypt", "security.decrypt", "security.rotate_key"))
        ])
        db_session.commit()
        assert [i["action"] for i in list_audit(db_session, test_user.id)] == [
            "security.rotate_key", "security.decrypt", "security.encrypt",
        ]

    def test_limit_is_capped_at_200(self, db_session, test_user):
        """limit 上限 200（防止一次拉爆审计表）。"""
        db_session.add_all([
            AuditLog(user_id=test_user.id, action="security.encrypt", ok=True,
                     created_at=datetime(2026, 6, 1, tzinfo=timezone.utc) + timedelta(seconds=i))
            for i in range(205)
        ])
        db_session.commit()
        assert len(list_audit(db_session, test_user.id, 1000)) == 200

    def test_limit_respected_below_cap(self, db_session, test_user):
        for _ in range(5):
            audit(db_session, test_user.id, "security.encrypt")
        assert len(list_audit(db_session, test_user.id, 3)) == 3

    def test_soft_deleted_rows_excluded(self, db_session, test_user):
        audit(db_session, test_user.id, "security.encrypt")
        audit(db_session, test_user.id, "security.decrypt")
        row = db_session.query(AuditLog).filter(AuditLog.action == "security.decrypt").one()
        row.deleted_at = datetime.now(timezone.utc)
        db_session.commit()
        assert {i["action"] for i in list_audit(db_session, test_user.id)} == {"security.encrypt"}

    def test_item_shape(self, db_session, test_user):
        audit(db_session, test_user.id, "security.encrypt", ok=False, detail="d", ip="127.0.0.1")
        item = list_audit(db_session, test_user.id)[0]
        assert set(item) == {"id", "action", "target", "ok", "detail", "ip", "created_at"}
        assert item["ip"] == "127.0.0.1"
        assert item["ok"] is False
        assert isinstance(item["created_at"], str)


# ============================================================
# 九、越权隔离
# ============================================================
class TestOwnership:

    def test_rotate_only_touches_own_rows(self, db_session, test_user, other_user, enc_dir):
        mgr = EncryptionManager(enc_dir)
        other_before = _fernet_token(mgr, "other-api-key")
        other_user.api_key_encrypted = other_before
        db_session.flush()

        _svc(db_session, test_user).rotate_key()

        db_session.expire_all()
        assert db_session.get(User, other_user.id).api_key_encrypted == other_before

    def test_rotating_unknown_user_is_noop(self, db_session, enc_dir):
        res = SecurityService(db_session, str(uuid.uuid4())).rotate_key()
        assert res["rotated"] == 0
