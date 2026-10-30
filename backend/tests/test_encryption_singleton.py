# ============================================================
# Phase7 · D-25 加密单例复用测试
#
# 目标：`ensure_encryption()` 双检锁懒初始化 + AssistantService 复用全局单例，
# 不再每次 new EncryptionManager（重复 PBKDF2 派生 + 多份实例状态）。
# ============================================================
from __future__ import annotations

from pathlib import Path

import pytest

from app.config import get_settings
from app.core import encryption
from app.core.encryption import (
    EncryptionManager,
    ensure_encryption,
    get_encryption,
    init_encryption,
)
from app.services.assistant_service import AssistantService


def _data_dir() -> Path:
    return Path(get_settings().data_dir)


@pytest.fixture()
def reset_singleton():
    saved = encryption._encryption_manager
    encryption._encryption_manager = None
    yield
    encryption._encryption_manager = saved


class TestEnsureEncryption:
    def test_lazy_initializes_when_missing(self, reset_singleton):
        assert get_encryption() is None
        manager = ensure_encryption(_data_dir())
        assert isinstance(manager, EncryptionManager)
        assert get_encryption() is manager

    def test_returns_same_instance_on_repeated_calls(self, reset_singleton):
        first = ensure_encryption(_data_dir())
        second = ensure_encryption(_data_dir())
        assert first is second

    def test_existing_singleton_wins_over_new_data_dir(self, reset_singleton):
        """已初始化后传新目录不得再创建第二套密钥库（否则加解密不对称）。"""
        first = ensure_encryption(_data_dir())
        other = _data_dir() / "another-crypto-home"
        again = ensure_encryption(other)
        assert again is first
        assert not other.exists(), "不应为已被忽略的目录创建密钥库"

    def test_init_encryption_replaces_singleton(self, reset_singleton):
        first = init_encryption(_data_dir())
        second = init_encryption(_data_dir())
        assert second is not first
        assert get_encryption() is second

    def test_ensure_encryption_is_thread_safe(self, reset_singleton):
        import threading

        results: list[EncryptionManager] = []
        barrier = threading.Barrier(4)

        def worker():
            barrier.wait()
            results.append(ensure_encryption(_data_dir()))

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(results) == 4
        assert all(r is results[0] for r in results), "并发调用应拿到同一个单例"


class TestAssistantServiceReusesSingleton:
    def test_encryption_returns_global_singleton(self, db_session, test_user, reset_singleton):
        manager = init_encryption(_data_dir())
        svc = AssistantService(db_session, test_user.id)
        assert svc._encryption() is manager
        assert get_encryption() is manager

    def test_key_roundtrip_uses_shared_singleton(self, db_session, test_user, reset_singleton):
        init_encryption(_data_dir())
        svc = AssistantService(db_session, test_user.id)
        svc.configure("sk-phase7-123456")
        assert svc._key() == "sk-phase7-123456"
        assert get_encryption() is not None
