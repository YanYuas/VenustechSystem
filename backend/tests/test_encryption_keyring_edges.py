# ============================================================
# EncryptionManager 密钥环 / 文件权限异常分支（Phase11-C · A 类可测未测）
#
# Phase11 term-missing 里 app/core/encryption.py 有 23 行未覆盖，其中大部分是
# **本进程可安全构造**的错误分支：
#   · 80-81 / 93-94：chmod 设置权限失败 → 必须吞掉（Windows 文件系统可能不支持 POSIX 权限）
#   · 105-106 / 110-113：密钥环里存在无法解析的历史密钥 → 跳过；旧格式（单代 previous）兼容读取
#   · 213-214：rotate 时密钥环 JSON 损坏 → 跳过历史合并而不是让换钥失败
#   · 225-228：rotate 写密钥环时 chmod 失败 → 吞掉
#   · 233-234：rotate 时历史密钥无法构造 Fernet → 跳过该代
# 全部用 tmp_path 里的一次性加密目录，不触碰全局单例与真实 data_dir。
# ============================================================
from __future__ import annotations

import json
import os
import types

from cryptography.fernet import Fernet

from app.core import encryption as enc_mod
from app.core.encryption import EncryptionManager


def _write_keyring(root, payload) -> None:
    if isinstance(payload, str):
        text = payload
    else:
        text = json.dumps(payload)
    (root / ".encryption_keys.json").write_text(text, encoding="utf-8")


def _chmod_raiser():
    def _raise(*_a, **_kw):
        raise OSError("chmod not supported")

    return _raise


def _os_without_chmod(raiser):
    """只替换模块内的 os 引用：保留 urandom，注入会失败的 chmod。"""
    return types.SimpleNamespace(urandom=os.urandom, chmod=raiser)


class TestPermissionFallbacks:
    def test_master_key_salt_chmod_oserror_is_swallowed(self, tmp_path, monkeypatch):
        monkeypatch.setattr(enc_mod, "os", _os_without_chmod(_chmod_raiser()))

        mgr = EncryptionManager(tmp_path, master_key="正确的密码")

        salt = (tmp_path / ".encryption_key.salt").read_bytes()
        assert len(salt) == 16
        # 权限设置失败不影响密钥派生与加解密
        assert mgr.decrypt(mgr.encrypt("密码模式")) == "密码模式"

    def test_generated_key_file_chmod_oserror_is_swallowed(self, tmp_path, monkeypatch):
        monkeypatch.setattr(enc_mod, "os", _os_without_chmod(_chmod_raiser()))

        mgr = EncryptionManager(tmp_path)

        key_file = tmp_path / ".encryption_key"
        assert key_file.is_file() and len(key_file.read_bytes()) == 44
        # 重新打开仍复用同一密钥（证明写盘成功、只是权限位设置失败）
        assert EncryptionManager(tmp_path).decrypt(mgr.encrypt("随机密钥模式")) == "随机密钥模式"


class TestKeyringParsing:
    def test_unparseable_keyring_entries_are_skipped(self, tmp_path):
        EncryptionManager(tmp_path)  # 先产生当前密钥文件
        _write_keyring(tmp_path, {"previous_keys": ["not-a-fernet-key"], "previous": "also-bad"})

        mgr = EncryptionManager(tmp_path)

        assert mgr._previous_fernets == []          # 两个坏条目都被跳过
        assert mgr.decrypt(mgr.encrypt("当前密钥可用")) == "当前密钥可用"

    def test_legacy_single_previous_key_can_decrypt_old_ciphertext(self, tmp_path):
        old = EncryptionManager(tmp_path)
        old_token = old.encrypt("轮换前的密文")
        legacy_key = (tmp_path / ".encryption_key").read_bytes()   # 44 字节 urlsafe Fernet key
        # 模拟旧版密钥环：只有单数 previous 字段（无 previous_keys 数组）
        _write_keyring(tmp_path, {"previous": legacy_key.decode()})
        (tmp_path / ".encryption_key").write_bytes(Fernet.generate_key())  # 当前密钥换成新的

        mgr = EncryptionManager(tmp_path)

        assert len(mgr._previous_fernets) == 1
        assert mgr.decrypt(old_token) == "轮换前的密文"   # 旧密钥解密历史密文

    def test_corrupt_keyring_json_is_ignored_on_load(self, tmp_path):
        EncryptionManager(tmp_path)
        _write_keyring(tmp_path, "{not valid json")

        mgr = EncryptionManager(tmp_path)

        assert mgr._previous_fernets == []          # 损坏的密钥环归零，不影响启动
        assert mgr.is_available is True


class TestRotateKeyFallbacks:
    def test_rotate_with_corrupt_keyring_still_rotates(self, tmp_path):
        mgr = EncryptionManager(tmp_path)
        token_before = mgr.encrypt("换钥前")
        _write_keyring(tmp_path, "[broken]")

        mgr.rotate_key()

        assert mgr.decrypt(mgr.encrypt("换钥后")) == "换钥后"
        assert mgr.decrypt(token_before) == "换钥前"   # 旧密钥仍保留用于历史密文

    def test_rotate_skips_unparseable_history_keys(self, tmp_path):
        mgr = EncryptionManager(tmp_path)
        token_before = mgr.encrypt("历史密文")
        _write_keyring(tmp_path, {"previous_keys": ["garbage"]})

        mgr.rotate_key()

        # garbage 被跳过；当前旧密钥仍进入历史，历史密文可解
        assert len(mgr._previous_fernets) == 1
        assert mgr.decrypt(token_before) == "历史密文"

    def test_rotate_keyring_chmod_oserror_is_swallowed(self, tmp_path, monkeypatch):
        mgr = EncryptionManager(tmp_path)
        token_before = mgr.encrypt("chmod 失败前")
        monkeypatch.setattr(enc_mod, "os", _os_without_chmod(_chmod_raiser()))

        mgr.rotate_key()   # 不得抛 OSError

        assert mgr.decrypt(mgr.encrypt("chmod 失败后")) == "chmod 失败后"
        assert (tmp_path / ".encryption_keys.json").is_file()
        assert mgr.decrypt(token_before) == "chmod 失败前"
