# ============================================================
# 加密模块测试（app/core/encryption.py）
#
# 覆盖目标：
#   1. 密钥派生：随机 salt、同参确定性、salt/password 敏感性
#   2. 加解密往返：str / bytes / JSON / 文件
#   3. **多代历史密钥回退**：轮换后旧密文仍可解；代数受 KEEP_PREVIOUS 约束
#   4. 轮换：密钥文件真的换了、新密文由新密钥产出、密钥环结构正确
#   5. 两个已修缺陷的回归断言（decrypt_file 的两处静默错误）
#
# 本文件所有用例都把 data_dir 指向 pytest 的 tmp_path，
# **绝不碰** get_settings().data_dir（那是全测试会话共用的真实临时库目录，
# 在里面轮换 key 会污染后续用例）。
# ============================================================
from __future__ import annotations

import json

import pytest

from app.core.encryption import EncryptionManager, get_encryption, init_encryption

PASSWORD = "unit-test-master-password"


@pytest.fixture()
def mgr(tmp_path):
    return EncryptionManager(tmp_path)


# ============================================================
# 一、密钥派生
# ============================================================
class TestKeyDerivation:

    def test_derive_key_is_deterministic(self):
        """同 password + 同 salt 必然派生出同一把密钥（否则重启就解不开）。"""
        salt = EncryptionManager.new_salt()
        assert EncryptionManager.derive_key(PASSWORD, salt) == \
            EncryptionManager.derive_key(PASSWORD, salt)

    def test_derive_key_differs_by_salt(self):
        """salt 不同 → 密钥不同。

        这是「随机 salt」的意义所在：硬编码全局 salt 会让相同密码在不同用户/
        不同库之间派生出相同密钥，且彩虹表可跨库复用（文件头注释的 D0 修正）。
        """
        k1 = EncryptionManager.derive_key(PASSWORD, EncryptionManager.new_salt())
        k2 = EncryptionManager.derive_key(PASSWORD, EncryptionManager.new_salt())
        assert k1 != k2

    def test_derive_key_differs_by_password(self):
        salt = EncryptionManager.new_salt()
        assert EncryptionManager.derive_key("a", salt) != \
            EncryptionManager.derive_key("b", salt)

    def test_new_salt_is_16_random_bytes(self):
        s1, s2 = EncryptionManager.new_salt(), EncryptionManager.new_salt()
        assert isinstance(s1, bytes) and len(s1) == 16
        assert s1 != s2

    def test_derived_key_is_valid_fernet_key(self):
        """派生的字节串必须能直接喂给 Fernet（base64 urlsafe，32 字节主体）。"""
        from cryptography.fernet import Fernet

        key = EncryptionManager.derive_key(PASSWORD, EncryptionManager.new_salt())
        assert len(key) == 44
        Fernet(key)  # 不抛异常即为合法密钥


# ============================================================
# 二、初始化与状态
# ============================================================
class TestInitialization:

    def test_creates_key_file_on_first_use(self, tmp_path):
        mgr = EncryptionManager(tmp_path)
        assert mgr.is_available is True
        assert (tmp_path / ".encryption_key").exists()

    def test_reopen_reuses_existing_key(self, tmp_path):
        """重新构造必须复用 key 文件，否则已有密文全部作废。"""
        token = EncryptionManager(tmp_path).encrypt("持久化验证")
        assert EncryptionManager(tmp_path).decrypt(token) == "持久化验证"

    def test_master_key_mode_writes_random_salt(self, tmp_path):
        mgr = EncryptionManager(tmp_path, master_key=PASSWORD)
        assert (tmp_path / ".encryption_key.salt").exists()
        assert not (tmp_path / ".encryption_key").exists()  # 主密钥模式不落 key 文件
        assert mgr.get_status()["has_custom_key"] is True

    def test_master_key_mode_roundtrip_across_instances(self, tmp_path):
        token = EncryptionManager(tmp_path, master_key=PASSWORD).encrypt("x")
        assert EncryptionManager(tmp_path, master_key=PASSWORD).decrypt(token) == "x"

    def test_get_status_shape(self, mgr, tmp_path):
        st = mgr.get_status()
        assert set(st) == {
            "available", "algorithm", "key_derivation", "key_file",
            "key_exists", "has_custom_key", "has_previous_key", "previous_key_count",
        }
        assert st["available"] is True
        assert st["key_exists"] is True
        assert st["has_custom_key"] is False
        assert st["key_file"] == str(tmp_path / ".encryption_key")


# ============================================================
# 三、加解密往返
# ============================================================
class TestRoundTrip:

    def test_encrypt_decrypt_str(self, mgr):
        assert mgr.decrypt(mgr.encrypt("你好，启明星")) == "你好，启明星"

    def test_encrypt_accepts_bytes(self, mgr):
        assert mgr.decrypt(mgr.encrypt(b"raw-bytes")) == "raw-bytes"

    def test_decrypt_accepts_str_token(self, mgr):
        """从库里读回来的是 str，必须能直接解（API 层就是这么用的）。"""
        assert mgr.decrypt(mgr.encrypt("s").decode()) == "s"

    def test_encrypt_output_is_bytes_token(self, mgr):
        token = mgr.encrypt("s")
        assert isinstance(token, bytes) and token.startswith(b"gAAAAA")

    def test_same_plaintext_yields_different_tokens(self, mgr):
        """Fernet 带随机 IV：同一明文两次加密结果必须不同（否则可判断内容相同）。"""
        assert mgr.encrypt("same") != mgr.encrypt("same")

    def test_encrypt_json_roundtrip_with_unicode(self, mgr):
        obj = {"名字": "衍煜", "数值": [1, 2, 3], "嵌套": {"a": None}}
        assert mgr.decrypt_json(mgr.encrypt_json(obj)) == obj

    def test_decrypt_wrong_key_raises_valueerror(self, tmp_path):
        """密钥不匹配必须抛 ValueError（而不是把 InvalidToken 泄漏给调用方）。

        API 层 `except ValueError` 就靠这个契约把 400 返回给前端；
        若这里漏出 InvalidToken（不是 ValueError 子类），端点会变成 500。
        """
        token = EncryptionManager(tmp_path / "a").encrypt("secret")
        other = EncryptionManager(tmp_path / "b")
        with pytest.raises(ValueError, match="解密失败"):
            other.decrypt(token)

    def test_decrypt_garbage_raises_valueerror(self, mgr):
        with pytest.raises(ValueError):
            mgr.decrypt("not-a-fernet-token")

    def test_operations_raise_when_backend_missing(self, mgr, monkeypatch):
        """cryptography 缺失时必须显式报错，不能静默返回原文。"""
        monkeypatch.setattr(mgr, "_fernet", None)
        with pytest.raises(RuntimeError, match="加密模块未初始化"):
            mgr.encrypt("x")
        with pytest.raises(RuntimeError, match="加密模块未初始化"):
            mgr.decrypt("x")


# ============================================================
# 四、轮换与多代历史密钥
# ============================================================
class TestRotationAndHistory:

    def test_rotate_replaces_key_file(self, tmp_path):
        mgr = EncryptionManager(tmp_path)
        before = (tmp_path / ".encryption_key").read_bytes()
        mgr.rotate_key()
        assert (tmp_path / ".encryption_key").read_bytes() != before

    def test_rotate_keeps_old_ciphertext_readable(self, tmp_path):
        """轮换后旧密文必须仍可解（密钥环兜底）—— 这是本模块的核心不变量。"""
        mgr = EncryptionManager(tmp_path)
        token = mgr.encrypt("轮换前写入")
        mgr.rotate_key()
        assert mgr.decrypt(token) == "轮换前写入"
        assert EncryptionManager(tmp_path).decrypt(token) == "轮换前写入"

    def test_rotate_new_ciphertext_uses_new_key(self, tmp_path):
        mgr = EncryptionManager(tmp_path)
        mgr.rotate_key()
        fresh = mgr.encrypt("轮换后写入")
        assert EncryptionManager(tmp_path).decrypt(fresh) == "轮换后写入"

    def test_keyring_file_structure(self, tmp_path):
        mgr = EncryptionManager(tmp_path)
        old = (tmp_path / ".encryption_key").read_bytes().decode()
        mgr.rotate_key()
        ring = json.loads((tmp_path / ".encryption_keys.json").read_text(encoding="utf-8"))
        assert set(ring) >= {"current", "previous_keys"}
        assert ring["previous_keys"][0] == old

    def test_history_capped_at_keep_previous(self, tmp_path):
        """历史密钥代数不得超过 KEEP_PREVIOUS（否则密钥环无限膨胀）。"""
        mgr = EncryptionManager(tmp_path)
        for _ in range(EncryptionManager.KEEP_PREVIOUS + 3):
            mgr.rotate_key()
        assert len(mgr._previous_fernets) <= EncryptionManager.KEEP_PREVIOUS

    def test_stale_token_becomes_unreadable_after_history_exhausted(self, tmp_path):
        """如实钉住上限：超出 KEEP_PREVIOUS 代的陈旧密文确实解不开。

        这不是 bug，是「密钥环只留有限代」的必然结果 —— 写出来是为了让后人
        知道该上限是**有意保留**的，且任何长期落库的密文都必须被真正重写
        （见 tests/test_security_production.py 的轮换回归组）。
        """
        mgr = EncryptionManager(tmp_path)
        first = mgr.encrypt("最早写入")
        for _ in range(EncryptionManager.KEEP_PREVIOUS + 1):
            mgr.rotate_key()
        with pytest.raises(ValueError):
            EncryptionManager(tmp_path).decrypt(first)

    def test_rotate_with_new_master_key_rewrites_salt(self, tmp_path):
        """带新主密钥轮换：salt 必须重写（否则新旧密码派生同一密钥 = 没轮换）。"""
        mgr = EncryptionManager(tmp_path, master_key="old-master")
        salt_before = (tmp_path / ".encryption_key.salt").read_bytes()
        mgr.rotate_key(new_master_key="new-master")
        assert (tmp_path / ".encryption_key.salt").read_bytes() != salt_before
        # 新密钥可用：用新主密钥重新打开的管理器能解开新密文
        fresh = mgr.encrypt("轮换后的数据")
        assert EncryptionManager(tmp_path, master_key="new-master").decrypt(fresh) == "轮换后的数据"
        # 用旧主密钥打开的管理器则解不开（salt 已换，旧密钥未入密钥环）
        with pytest.raises(ValueError):
            EncryptionManager(tmp_path, master_key="old-master").decrypt(fresh)

    def test_rotate_is_noop_without_backend(self, mgr, monkeypatch):
        monkeypatch.setattr(mgr, "_fernet", None)
        assert mgr.rotate_key() is None


# ============================================================
# 五、文件加解密
# ============================================================
class TestFileEncryption:

    def test_encrypt_decrypt_file_default_paths(self, mgr, tmp_path):
        src = tmp_path / "plain.txt"
        src.write_text("文件内容", encoding="utf-8")
        enc = mgr.encrypt_file(src)
        assert enc == tmp_path / "plain.txt.enc"
        out = mgr.decrypt_file(enc)
        assert out.read_text(encoding="utf-8") == "文件内容"

    def test_explicit_dest_paths(self, mgr, tmp_path):
        src = tmp_path / "a.bin"
        src.write_bytes(b"\x00\x01\x02")
        enc = mgr.encrypt_file(src, tmp_path / "c.enc")
        dec = mgr.decrypt_file(enc, tmp_path / "back.bin")
        assert dec.read_bytes() == b"\x00\x01\x02"

    def test_decrypt_file_falls_back_to_previous_keys(self, tmp_path):
        """回归断言（2026-10-11 修复）。

        原缺陷：`decrypt_file` 直接调 `self._fernet.decrypt()`，**绕过历史密钥
        回退**。症状：同一份密文，`decrypt()` 在轮换后仍能解开（会试 previous），
        `decrypt_file()` 却抛 InvalidToken —— 两条路径行为不一致，使用方按
        `decrypt()` 的契约写代码就会在轮换后踩坑。
        修法：统一走 `self.decrypt()`。
        """
        mgr = EncryptionManager(tmp_path)
        src = tmp_path / "old.enc"
        src.write_bytes(mgr.encrypt("轮换前的文件"))
        mgr.rotate_key()

        reopened = EncryptionManager(tmp_path)
        assert reopened.decrypt(src.read_bytes()) == "轮换前的文件"
        # 修复前这一行抛 InvalidToken
        assert reopened.decrypt_file(src, tmp_path / "old.txt").read_text(
            encoding="utf-8") == "轮换前的文件"

    def test_decrypt_file_raises_instead_of_writing_ciphertext(self, mgr, tmp_path):
        """回归断言（2026-10-11 修复）。

        原缺陷：`self._fernet.decrypt(x) if self._fernet else x` —— 后端不可用时
        `else` 分支会把**密文原样写进目标文件**当明文，静默产出垃圾文件
        （不报错、调用方以为自己拿到了明文）。
        修法：统一走 `self.decrypt()`，由它抛 RuntimeError。
        """
        src = tmp_path / "x.enc"
        src.write_bytes(mgr.encrypt("secret"))
        monkeypatch_fernet = mgr._fernet
        mgr._fernet = None
        try:
            with pytest.raises(RuntimeError, match="加密模块未初始化"):
                mgr.decrypt_file(src)
        finally:
            mgr._fernet = monkeypatch_fernet


# ============================================================
# 六、全局单例入口
# ============================================================
class TestSingletonEntrypoints:

    def test_init_then_get(self, tmp_path, monkeypatch):
        """`init_encryption` 只应影响模块全局，测试结束必须还原（否则污染其他用例）。

        不假设初始为 None —— app lifespan 也会初始化它，取决于用例执行顺序
        （本仓已吃过"单跑过、全套挂"的亏）。这里只断言"写入即可读回"这一契约。
        """
        import app.core.encryption as enc

        original = enc._encryption_manager
        monkeypatch.setattr(enc, "_encryption_manager", original)  # 登记还原

        created = init_encryption(tmp_path)
        assert get_encryption() is created
        assert created.data_dir == tmp_path

    def test_get_encryption_reflects_module_global(self, tmp_path, monkeypatch):
        import app.core.encryption as enc

        monkeypatch.setattr(enc, "_encryption_manager", "sentinel")
        assert get_encryption() == "sentinel"
