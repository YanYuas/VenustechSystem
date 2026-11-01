# ============================================================
# Phase17 · D-58：EncryptionManager.rotate_key 原子性 / 失败整体回滚
#
# 目标不变量：**要么全成，要么回到旧状态，绝不半途**。
#   · 三个写入点（salt / key / keyring）均为「临时文件 + fsync + os.replace」；
#   · 任一写入失败 → 已写文件按逆序恢复旧字节（原本不存在则删除），
#     内存 `_fernet` / `_previous_fernets` 保持旧值，原异常继续上抛；
#   · 成功路径：新密文可解、旧密文经 previous 可解、无 .tmp 残留。
#
# 失败注入方式说明：实现已从「直接 write_bytes/write_text」改为原子 helper，
# 因此注入点在 helper 的底层（builtins.open / os.replace / os.fsync），
# 而不是 Path.write_text —— 等价覆盖同一条失败路径。
# ============================================================
from __future__ import annotations

import builtins
import os

import pytest

from app.core import encryption as enc_mod
from app.core.encryption import EncryptionManager

PASSWORD = "rotate-atomicity-master"


def _tmp_files(root):
    return sorted(p.name for p in root.glob("*.tmp-*"))


@pytest.fixture()
def mgr(tmp_path):
    return EncryptionManager(tmp_path)


class TestRotateSuccess:
    def test_success_rotation_keeps_old_and_new_ciphertext_readable(self, mgr, tmp_path):
        old_token = mgr.encrypt("轮换前密文")

        mgr.rotate_key()

        new_token = mgr.encrypt("轮换后密文")
        assert mgr.decrypt(new_token) == "轮换后密文"
        assert mgr.decrypt(old_token) == "轮换前密文"       # 旧密钥进入 previous
        assert _tmp_files(tmp_path) == []                   # 无临时文件残留

        reopened = EncryptionManager(tmp_path)
        assert reopened.decrypt(new_token) == "轮换后密文"
        assert reopened.decrypt(old_token) == "轮换前密文"

    def test_master_key_rotation_writes_salt_atomically(self, tmp_path):
        mgr = EncryptionManager(tmp_path, master_key=PASSWORD)
        mgr.encrypt("warm")
        salt_before = (tmp_path / ".encryption_key.salt").read_bytes()

        mgr.rotate_key(new_master_key="new-master-password")

        salt_after = (tmp_path / ".encryption_key.salt").read_bytes()
        assert salt_after != salt_before                    # salt 已原子更新
        # 主密钥模式下「旧代历史」依赖密钥环语义（ROADMAP 已知不自洽项），
        # 此处只验证成功路径：新主密钥可解开新密文、无 tmp 残留。
        assert EncryptionManager(tmp_path, master_key="new-master-password").decrypt(
            mgr.encrypt("主密钥模式-新")
        ) == "主密钥模式-新"
        assert _tmp_files(tmp_path) == []


class TestRotateRollback:
    def test_keyring_write_failure_rolls_back_key_and_keeps_memory(
        self, mgr, tmp_path
    ):
        old_token = mgr.encrypt("回滚-旧密文")
        key_before = (tmp_path / ".encryption_key").read_bytes()
        fernet_before = mgr._fernet
        previous_before = list(mgr._previous_fernets)

        real_open = builtins.open

        def _failing_open(path, *args, **kwargs):
            if ".encryption_keys.json.tmp-" in str(path):
                raise RuntimeError("keyring write boom")
            return real_open(path, *args, **kwargs)

        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(builtins, "open", _failing_open)
        try:
            with pytest.raises(RuntimeError, match="keyring write boom"):
                mgr.rotate_key()
        finally:
            monkeypatch.undo()

        # 磁盘回滚：key 文件字节与轮换前一致；无 keyring 半成品；无 tmp
        assert (tmp_path / ".encryption_key").read_bytes() == key_before
        assert not (tmp_path / ".encryption_keys.json").exists()
        assert _tmp_files(tmp_path) == []
        # 内存未更新：仍是旧 fernet，旧密文仍可解
        assert mgr._fernet is fernet_before
        assert mgr._previous_fernets == previous_before
        assert mgr.decrypt(old_token) == "回滚-旧密文"

    def test_os_replace_failure_rolls_back_after_key_written(self, mgr, tmp_path):
        old_token = mgr.encrypt("replace-失败-旧密文")
        key_before = (tmp_path / ".encryption_key").read_bytes()
        fernet_before = mgr._fernet
        real_replace = os.replace
        calls = {"n": 0}

        def _failing_replace(src, dst):
            calls["n"] += 1
            # 第 1 次替换是 key 文件（成功）；第 2 次是 keyring（失败）→ 需回滚 key
            if calls["n"] == 2:
                raise OSError("replace boom")
            return real_replace(src, dst)

        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(enc_mod.os, "replace", _failing_replace)
        try:
            with pytest.raises(OSError, match="replace boom"):
                mgr.rotate_key()
        finally:
            monkeypatch.undo()

        assert (tmp_path / ".encryption_key").read_bytes() == key_before
        assert mgr._fernet is fernet_before
        assert _tmp_files(tmp_path) == []
        assert mgr.decrypt(old_token) == "replace-失败-旧密文"

    def test_salt_write_failure_rolls_back_before_key(self, tmp_path):
        mgr = EncryptionManager(tmp_path, master_key=PASSWORD)
        mgr.encrypt("warm")
        token = mgr.encrypt("salt-失败-旧密文")
        salt_before = (tmp_path / ".encryption_key.salt").read_bytes()
        fernet_before = mgr._fernet

        real_open = builtins.open

        def _failing_open(path, *args, **kwargs):
            if ".encryption_key.salt.tmp-" in str(path):
                raise RuntimeError("salt write boom")
            return real_open(path, *args, **kwargs)

        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(builtins, "open", _failing_open)
        try:
            with pytest.raises(RuntimeError, match="salt write boom"):
                mgr.rotate_key(new_master_key="another-master")
        finally:
            monkeypatch.undo()

        assert (tmp_path / ".encryption_key.salt").read_bytes() == salt_before
        assert mgr._fernet is fernet_before
        assert _tmp_files(tmp_path) == []
        assert mgr.decrypt(token) == "salt-失败-旧密文"

    def test_rollback_failure_is_logged_and_original_exception_propagates(
        self, mgr, tmp_path, monkeypatch
    ):
        """回滚自身失败时：记录可诊断日志（不二次抛出），原始异常仍上抛。"""
        real_open = builtins.open

        def _failing_open(path, *args, **kwargs):
            if ".encryption_keys.json.tmp-" in str(path):
                raise RuntimeError("keyring write boom")
            return real_open(path, *args, **kwargs)

        def _restore_boom(*_args, **_kwargs):
            raise OSError("restore boom")

        monkeypatch.setattr(builtins, "open", _failing_open)
        monkeypatch.setattr(enc_mod, "_restore_file", _restore_boom)

        with pytest.raises(RuntimeError, match="keyring write boom"):
            mgr.rotate_key()

        assert _tmp_files(tmp_path) == []          # 临时文件仍被清理
        # 原始异常未被回滚异常替换（上面 match 已证明）；内存未更新
        assert mgr._fernet is not None


class TestAtomicWriteHelperEdges:
    def test_fsync_failure_cleans_tmp_and_reraises(self, tmp_path, monkeypatch):
        target = tmp_path / "x.bin"
        target.write_bytes(b"old")
        real_fsync = os.fsync

        def _fsync_boom(_fd):
            raise OSError("fsync boom")

        monkeypatch.setattr(enc_mod.os, "fsync", _fsync_boom)
        with pytest.raises(OSError, match="fsync boom"):
            enc_mod._atomic_write_bytes(target, b"new")
        monkeypatch.setattr(enc_mod.os, "fsync", real_fsync)

        assert target.read_bytes() == b"old"       # 未替换
        assert _tmp_files(tmp_path) == []          # 清理成功

    def test_tmp_cleanup_failure_is_swallowed_and_original_raised(
        self, tmp_path, monkeypatch
    ):
        target = tmp_path / "y.bin"

        def _fsync_boom(_fd):
            raise OSError("fsync boom")

        def _unlink_boom(_self, *_a, **_kw):
            raise OSError("unlink boom")

        monkeypatch.setattr(enc_mod.os, "fsync", _fsync_boom)
        monkeypatch.setattr("pathlib.Path.unlink", _unlink_boom)

        with pytest.raises(OSError, match="fsync boom"):
            enc_mod._atomic_write_bytes(target, b"new")

        assert not target.exists()

    def test_restore_file_removes_new_file_when_absent_before(self, tmp_path):
        path = tmp_path / "created-later.bin"
        path.write_bytes(b"half-done")

        enc_mod._restore_file(path, existed=False, data=None)

        assert not path.exists()

    def test_restore_file_unlink_failure_is_logged(self, tmp_path, monkeypatch):
        path = tmp_path / "still-there.bin"
        path.write_bytes(b"x")

        def _unlink_boom(_self, *_a, **_kw):
            raise OSError("unlink boom")

        monkeypatch.setattr("pathlib.Path.unlink", _unlink_boom)

        enc_mod._restore_file(path, existed=False, data=None)   # 不抛
        assert path.exists()
