# ============================================================
# Phase19 · D-66：主密钥模式密钥轮换语义
#
# 选定语义（威胁模型：主密钥是「唯一秘密」；磁盘上只允许出现 salt，绝不允许
# 出现当前/历史 key 明文；salt 是公开参数，不构成秘密泄漏）：
#   · 同 master 轮换（new_master_key=None）：新 salt + 当前 master 派生新 key；
#     把旧 salt 归档进 keyring `previous_salts`，旧代密钥由 `master + 旧 salt`
#     重新派生 —— 因此同实例 / reload / 新实例（同 master）都能解旧密文。
#   · 换 master（new_master_key 显式给出）：新 salt + 新 master 派生。旧密文无法
#     由新 master 重派生，**必须由服务层先全量重加密**（SecurityService.rotate_key
#     的生产流程就是先解密全部→换 key→再全部重加密）；直接调用 manager 换 master
#     不保证旧密文可解。本实例内存保留旧 fernet 供同进程过渡，但不落盘。
#   · 随机密钥模式（未设 master）行为与历史完全一致（既有测试保护）。
# ============================================================
from __future__ import annotations

import base64
import builtins
import json

import pytest

from app.core import encryption as enc_mod
from app.core.encryption import EncryptionManager

PASSWORD = "p19-master-rotation"
NEW_PASSWORD = "p19-master-rotation-new"


def _ring(tmp_path) -> dict:
    path = tmp_path / ".encryption_keys.json"
    assert path.is_file()
    return json.loads(path.read_text(encoding="utf-8"))


def _tmp_files(root):
    return sorted(p.name for p in root.glob("*.tmp-*"))


def _no_key_material_in_ring(ring: dict, mgr: EncryptionManager, salt: bytes) -> None:
    """主密钥模式下 keyring 只能有 salt 历史，不能有任何 key 明文。"""
    assert "current" not in ring
    assert "previous_keys" not in ring or ring["previous_keys"] == []

    current_key = mgr.derive_key(PASSWORD, salt)
    blob = json.dumps(ring, ensure_ascii=False)
    assert current_key.decode() not in blob
    assert base64.b64encode(current_key).decode() not in blob
    for item in ring.get("previous_salts") or []:
        decoded = base64.b64decode(item.encode("ascii"), validate=True)
        assert len(decoded) == 16          # 只允许 16 字节 salt


class TestMasterSameKeyRotation:
    def test_old_and_new_ciphertext_survive_rotation_same_instance(self, tmp_path):
        mgr = EncryptionManager(tmp_path, master_key=PASSWORD)
        old_token = mgr.encrypt("轮换前-主密钥模式")

        mgr.rotate_key()                         # new_master_key=None → 同 master 轮换
        new_token = mgr.encrypt("轮换后-主密钥模式")

        assert mgr.decrypt(old_token) == "轮换前-主密钥模式"
        assert mgr.decrypt(new_token) == "轮换后-主密钥模式"
        assert _tmp_files(tmp_path) == []
        assert not (tmp_path / ".encryption_key").exists()   # 不落 key 文件

    def test_reload_and_new_instance_can_decrypt_old_and_new(self, tmp_path):
        mgr = EncryptionManager(tmp_path, master_key=PASSWORD)
        old_token = mgr.encrypt("旧密文")
        mgr.rotate_key()
        new_token = mgr.encrypt("新密文")

        mgr.reload()                             # 从磁盘重读（salt 历史 + master 重派生）
        assert mgr.decrypt(old_token) == "旧密文"
        assert mgr.decrypt(new_token) == "新密文"

        reopened = EncryptionManager(tmp_path, master_key=PASSWORD)
        assert reopened.decrypt(old_token) == "旧密文"
        assert reopened.decrypt(new_token) == "新密文"
        assert reopened.get_status()["previous_key_count"] == 1

    def test_keyring_contains_only_salt_history_no_key_material(self, tmp_path):
        mgr = EncryptionManager(tmp_path, master_key=PASSWORD)
        mgr.encrypt("warm")
        mgr.rotate_key()

        ring = _ring(tmp_path)
        salt_before_rotation = base64.b64decode(ring["previous_salts"][0].encode())
        assert ring.get("mode") == "master"
        assert len(ring["previous_salts"]) == 1
        # keyring 中只允许 16 字节 salt；当前/历史 key 明文都不允许出现
        current_salt = (tmp_path / ".encryption_key.salt").read_bytes()
        _no_key_material_in_ring(ring, mgr, current_salt)
        assert salt_before_rotation != current_salt
        assert not (tmp_path / ".encryption_key").exists()
        assert _tmp_files(tmp_path) == []

    def test_previous_key_count_matches_salt_history(self, tmp_path):
        mgr = EncryptionManager(tmp_path, master_key=PASSWORD)
        for _ in range(3):
            mgr.rotate_key()

        ring = _ring(tmp_path)
        assert mgr.get_status()["previous_key_count"] == len(ring["previous_salts"]) == 3

    def test_keep_previous_cap_and_old_generation_becomes_unreadable(self, tmp_path):
        mgr = EncryptionManager(tmp_path, master_key=PASSWORD)
        token_gen0 = mgr.encrypt("第 0 代（轮换前）")
        tokens = []
        for gen in range(1, EncryptionManager.KEEP_PREVIOUS + 2):   # +2 次越过上限
            mgr.rotate_key()
            tokens.append(mgr.encrypt(f"第 {gen} 代"))

        assert mgr.get_status()["previous_key_count"] <= EncryptionManager.KEEP_PREVIOUS
        assert len(_ring(tmp_path)["previous_salts"]) <= EncryptionManager.KEEP_PREVIOUS

        # 最近 KEEP_PREVIOUS 代仍可解；超出上限的第 0 代如实不可解
        for token in tokens[-EncryptionManager.KEEP_PREVIOUS:]:
            assert mgr.decrypt(token).startswith("第 ")
        with pytest.raises(ValueError, match="解密失败"):
            mgr.decrypt(token_gen0)


class TestMasterChangeSemantics:
    def test_change_master_keeps_old_ciphertext_only_in_memory(self, tmp_path):
        old_mgr = EncryptionManager(tmp_path, master_key=PASSWORD)
        old_token = old_mgr.encrypt("换 master 前的密文")

        old_mgr.rotate_key(new_master_key=NEW_PASSWORD)
        new_token = old_mgr.encrypt("换 master 后的密文")

        # 同实例：内存保留旧 fernet → 旧密文仍可解（生产需 service 全量重加密）
        assert old_mgr.decrypt(old_token) == "换 master 前的密文"
        assert old_mgr.decrypt(new_token) == "换 master 后的密文"

        # 新 master 的新实例：只能解新密文；旧密文如实失败
        new_mgr = EncryptionManager(tmp_path, master_key=NEW_PASSWORD)
        assert new_mgr.decrypt(new_token) == "换 master 后的密文"
        with pytest.raises(ValueError, match="解密失败"):
            new_mgr.decrypt(old_token)

        # 旧 master 的新实例：磁盘上没有可重派生的旧代 → 旧密文同样失败
        stale = EncryptionManager(tmp_path, master_key=PASSWORD)
        with pytest.raises(ValueError, match="解密失败"):
            stale.decrypt(old_token)

        ring = _ring(tmp_path)
        assert ring["previous_salts"] == []          # 换 master 不归档无意义的历史 salt
        assert "current" not in ring


class TestMasterKeyringCompatibility:
    def test_legacy_random_keyring_previous_key_still_decrypts(self, tmp_path):
        from cryptography.fernet import Fernet

        legacy_key = Fernet.generate_key()
        (tmp_path / ".encryption_key").write_bytes(legacy_key)
        legacy_token = Fernet(legacy_key).encrypt(b"legacy-random-mode")
        (tmp_path / ".encryption_keys.json").write_text(
            json.dumps({"previous": legacy_key.decode()}), encoding="utf-8"
        )

        mgr = EncryptionManager(tmp_path, master_key=PASSWORD)

        assert mgr.decrypt(legacy_token) == "legacy-random-mode"
        assert mgr.get_status()["previous_key_count"] == 1
        # 兼容字段在 master 轮换时被原样保留（_legacy_keyring_fields 的赋值分支）
        mgr.rotate_key()
        ring = _ring(tmp_path)
        assert ring.get("previous", legacy_key.decode()) == legacy_key.decode()
        assert mgr.decrypt(legacy_token) == "legacy-random-mode"

    def test_invalid_previous_salts_entries_are_skipped(self, tmp_path):
        (tmp_path / ".encryption_keys.json").write_text(
            json.dumps({
                "previous_salts": ["not-base64!!", "AAAA", base64.b64encode(
                    b"\x00" * 16).decode()],
            }),
            encoding="utf-8",
        )

        mgr = EncryptionManager(tmp_path, master_key=PASSWORD)

        # 只有合法 16 字节 salt 被接受
        assert mgr.get_status()["previous_key_count"] == 1

    def test_corrupt_keyring_in_master_mode_degrades_to_empty_history(self, tmp_path):
        (tmp_path / ".encryption_keys.json").write_text("{not json", encoding="utf-8")

        mgr = EncryptionManager(tmp_path, master_key=PASSWORD)

        assert mgr.get_status()["previous_key_count"] == 0
        token = mgr.encrypt("损坏 keyring 仍可用")
        mgr.rotate_key()                     # 历史为空也要能正常轮换
        assert mgr.decrypt(token) == "损坏 keyring 仍可用"


class TestMasterModeAtomicRollback:
    def test_keyring_write_failure_rolls_back_salt_and_memory(self, tmp_path):
        mgr = EncryptionManager(tmp_path, master_key=PASSWORD)
        mgr.encrypt("warm")
        salt_before = (tmp_path / ".encryption_key.salt").read_bytes()
        fernet_before = mgr._fernet
        old_token = mgr.encrypt("回滚前密文")

        real_open = builtins.open

        def _failing_open(path, *args, **kwargs):
            if ".encryption_keys.json.tmp-" in str(path):
                raise RuntimeError("master keyring write boom")
            return real_open(path, *args, **kwargs)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(builtins, "open", _failing_open)
            with pytest.raises(RuntimeError, match="master keyring write boom"):
                mgr.rotate_key()

        assert (tmp_path / ".encryption_key.salt").read_bytes() == salt_before
        assert not (tmp_path / ".encryption_keys.json").exists()
        assert mgr._fernet is fernet_before
        assert mgr.decrypt(old_token) == "回滚前密文"
        assert _tmp_files(tmp_path) == []


class TestMasterDefensiveBranches:
    def test_master_chmod_oserror_is_only_logged(self, tmp_path, monkeypatch):
        import os as _os

        mgr = EncryptionManager(tmp_path, master_key=PASSWORD)
        mgr.encrypt("warm")

        def _raise_chmod(*_a, **_kw):
            raise OSError("chmod not supported")

        class _FakeOs:
            def __getattr__(self, name):
                if name == "chmod":
                    return _raise_chmod
                return getattr(_os, name)

        monkeypatch.setattr(enc_mod, "os", _FakeOs())
        mgr.rotate_key()          # 权限失败不得阻断主密钥轮换

        assert mgr.decrypt(mgr.encrypt("chmod 失败后")) == "chmod 失败后"

    def test_bad_historical_salt_derivation_is_skipped_on_load(
        self, tmp_path, monkeypatch
    ):
        mgr = EncryptionManager(tmp_path, master_key=PASSWORD)
        mgr.rotate_key()
        old_salt_b64 = _ring(tmp_path)["previous_salts"][0]
        old_salt = base64.b64decode(old_salt_b64.encode())

        real_derive = EncryptionManager.derive_key

        def _flaky_derive(password, salt):
            if salt == old_salt:
                raise ValueError("salt derivation boom")
            return real_derive(password, salt)

        monkeypatch.setattr(EncryptionManager, "derive_key", staticmethod(_flaky_derive))
        reopened = EncryptionManager(tmp_path, master_key=PASSWORD)

        assert reopened.get_status()["previous_key_count"] == 0  # 坏历史被跳过

    def test_derivation_failure_during_success_refresh_is_skipped(self, tmp_path, monkeypatch):
        mgr = EncryptionManager(tmp_path, master_key=PASSWORD)
        mgr.encrypt("warm")
        salt_before = (tmp_path / ".encryption_key.salt").read_bytes()
        real_derive = EncryptionManager.derive_key

        def _flaky_derive(password, salt):
            if salt == salt_before:
                raise ValueError("historical derivation boom")
            return real_derive(password, salt)

        monkeypatch.setattr(EncryptionManager, "derive_key", staticmethod(_flaky_derive))
        mgr.rotate_key()          # 归档 salt 的重派生失败 → 跳过该代，不影响轮换成功

        assert mgr.decrypt(mgr.encrypt("轮换后")) == "轮换后"

    def test_random_mode_rotation_preserves_previous_salts_field(self, tmp_path):
        mgr = EncryptionManager(tmp_path)
        mgr.encrypt("warm")
        (tmp_path / ".encryption_keys.json").write_text(
            json.dumps({"previous_salts": ["AAAA"]}), encoding="utf-8"
        )

        mgr.rotate_key()          # 随机模式轮换不得丢弃未知的 previous_salts 字段

        assert _ring(tmp_path)["previous_salts"] == ["AAAA"]
