# ============================================================
# 启动期自动备份（lifespan 步骤 6）行为测试（Phase9-B）
#
# `app/main.py:lifespan` 在启动时调用 `BackupService.auto_backup_if_due()`，
# 该函数是**启动链路的一部分**（配置判定 → 间隔判定 → 导出 → 保留份数修剪 →
# 任何异常都 fail-open 不阻断启动），但 Phase6 term-missing 里整段未覆盖
# （backup_service.py 164-188）。
#
# 本文件逐条钉住：
#   · 默认关闭 / 未到期跳过（不导出）；
#   · 到期导出、保留份数修剪（删最旧）、unlink 失败不致命；
#   · 导出异常 / 配置值非法 → 返回 error 且不抛（启动不被备份问题阻断）；
#   · verify 的兼容分支：旧包只有 manifest.json（无 CHECKSUM）、校验和不符。
#
# 说明：只测 auto_backup_if_due 与 verify；**不测 import_**（它会替换测试库文件）。
# 所有备份文件都建在 conftest 隔离数据目录的 backups 下，用例后清理。
# ============================================================
from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import time
import types
import uuid
import zipfile
from pathlib import Path

import pytest

from app.config import get_settings
from app.core.exceptions import ValidationException
from app.repositories import SettingRepository
from app.services.backup_service import (
    BACKUP_AUTO_KEY,
    BACKUP_INTERVAL_KEY,
    BACKUP_KEEP_KEY,
    MANIFEST_NAME,
    BackupService,
)

SQLITE_MAGIC = b"SQLite format 3" + bytes([0])


# ---------------------------------------------------------------- helpers
def _set_settings(db_session, user_id: str, **values: str) -> None:
    repo = SettingRepository(db_session)
    for key, value in values.items():
        repo.upsert(user_id, key, value)
    db_session.commit()


def _make_backup_file(directory: Path, name: str, age_hours: float) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_bytes(b"fake-backup")
    old = time.time() - age_hours * 3600
    os.utime(path, (old, old))
    return path


def _zip_bytes(db_bytes: bytes, manifest: dict | None, manifest_name: str = MANIFEST_NAME) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("app.db", db_bytes)
        if manifest is not None:
            zf.writestr(manifest_name, json.dumps(manifest, ensure_ascii=False))
    return buffer.getvalue()


@pytest.fixture()
def backup_env(db_session, test_user):
    """BackupService + **每用例独立的 backups 目录**。

    为什么不用全局 backups_dir：同一次测试会话里 backup 模块的其它用例会真的
    导出 `backup-*.zip` 到共享目录（会话结束才清空），会让「最近备份/保留份数」
    判定读到别人的文件 → 假失败。这里把实例的 settings 指向独立目录。
    """
    svc = BackupService(db_session, test_user.id)
    real_settings = svc.settings
    backups_dir = Path(get_settings().data_dir) / f"auto-backup-{uuid.uuid4().hex[:8]}"
    backups_dir.mkdir(parents=True, exist_ok=False)
    svc.settings = types.SimpleNamespace(
        backups_dir=backups_dir,
        db_path=real_settings.db_path,
        version=real_settings.version,
    )
    try:
        yield svc
    finally:
        shutil.rmtree(backups_dir, ignore_errors=True)


# ================================================================
# 一、开关 / 间隔判定（启动时是否真的备份）
# ================================================================
class TestAutoBackupGating:
    def test_disabled_by_default_skips_without_export(self, backup_env, db_session, monkeypatch):
        exported = []
        monkeypatch.setattr(backup_env, "export", lambda tag=None: exported.append(tag))

        result = backup_env.auto_backup_if_due()

        assert result == {"ran": False, "reason": "auto backup disabled"}
        assert exported == []

    def test_enabled_with_no_existing_backup_runs_export(self, backup_env, monkeypatch):
        _set_settings(backup_env.db, backup_env.user_id, **{BACKUP_AUTO_KEY: "true"})
        exported = []
        monkeypatch.setattr(
            backup_env, "export",
            lambda tag=None: exported.append(tag) or {"path": "auto.zip", "size": 1},
        )

        result = backup_env.auto_backup_if_due()

        assert exported == ["auto"]
        assert result["ran"] is True
        assert result["keep"] == 7          # 默认保留 7 份
        assert result["removed"] == []
        assert result["path"] == "auto.zip"

    def test_recent_backup_skips_until_interval_elapsed(self, backup_env, monkeypatch):
        _set_settings(
            backup_env.db, backup_env.user_id,
            **{BACKUP_AUTO_KEY: "true", BACKUP_INTERVAL_KEY: "24"},
        )
        backups_dir = Path(backup_env.settings.backups_dir)
        _make_backup_file(backups_dir, "backup-recent.zip", age_hours=1.0)
        exported = []
        monkeypatch.setattr(backup_env, "export", lambda tag=None: exported.append(tag))

        result = backup_env.auto_backup_if_due()

        assert result["ran"] is False
        assert result["reason"] == "interval not elapsed"
        assert result["age_hours"] == 1.0
        assert exported == []

    def test_expired_interval_runs_export_again(self, backup_env, monkeypatch):
        _set_settings(
            backup_env.db, backup_env.user_id,
            **{BACKUP_AUTO_KEY: "true", BACKUP_INTERVAL_KEY: "24"},
        )
        backups_dir = Path(backup_env.settings.backups_dir)
        _make_backup_file(backups_dir, "backup-old.zip", age_hours=48.0)
        exported = []
        monkeypatch.setattr(
            backup_env, "export",
            lambda tag=None: exported.append(tag) or {"path": "new.zip", "size": 1},
        )

        result = backup_env.auto_backup_if_due()

        assert exported == ["auto"]
        assert result["ran"] is True

    def test_empty_config_value_falls_back_to_default(self, backup_env, monkeypatch):
        """配置行存在但值为空 → 用默认值（false → 跳过），不能崩在 int('') 上。"""
        _set_settings(
            backup_env.db, backup_env.user_id,
            **{BACKUP_AUTO_KEY: "true", BACKUP_INTERVAL_KEY: ""},
        )
        monkeypatch.setattr(backup_env, "export", lambda tag=None: {"path": "x", "size": 1})

        result = backup_env.auto_backup_if_due()
        assert result["ran"] is True          # 空值 → 默认 24h；无历史备份 → 直接跑
        assert result["keep"] == 7


# ================================================================
# 二、保留份数修剪 / 异常隔离（fail-open）
# ================================================================
class TestAutoBackupRetentionAndFailOpen:
    def test_keep_limit_removes_oldest(self, backup_env, monkeypatch):
        _set_settings(
            backup_env.db, backup_env.user_id,
            **{BACKUP_AUTO_KEY: "true", BACKUP_KEEP_KEY: "1", BACKUP_INTERVAL_KEY: "0"},
        )
        backups_dir = Path(backup_env.settings.backups_dir)
        _make_backup_file(backups_dir, "backup-a-oldest.zip", age_hours=72.0)
        _make_backup_file(backups_dir, "backup-b-middle.zip", age_hours=48.0)
        newest = _make_backup_file(backups_dir, "backup-c-newest.zip", age_hours=24.0)
        monkeypatch.setattr(backup_env, "export", lambda tag=None: {"path": "x", "size": 1})

        result = backup_env.auto_backup_if_due()

        assert result["keep"] == 1
        assert set(result["removed"]) == {"backup-a-oldest.zip", "backup-b-middle.zip"}
        assert [p.name for p in backups_dir.glob("backup-*.zip")] == [newest.name]

    def test_unlink_oserror_does_not_abort_pruning(self, backup_env, monkeypatch):
        _set_settings(
            backup_env.db, backup_env.user_id,
            **{BACKUP_AUTO_KEY: "true", BACKUP_KEEP_KEY: "1", BACKUP_INTERVAL_KEY: "0"},
        )
        backups_dir = Path(backup_env.settings.backups_dir)
        _make_backup_file(backups_dir, "backup-locked.zip", age_hours=72.0)
        _make_backup_file(backups_dir, "backup-removable.zip", age_hours=48.0)
        _make_backup_file(backups_dir, "backup-newest.zip", age_hours=1.0)
        monkeypatch.setattr(backup_env, "export", lambda tag=None: {"path": "x", "size": 1})

        real_unlink = Path.unlink

        def _maybe_locked(self, *args, **kwargs):
            if self.name == "backup-locked.zip":
                raise OSError("locked by antivirus")
            return real_unlink(self, *args, **kwargs)

        monkeypatch.setattr(Path, "unlink", _maybe_locked)
        result = backup_env.auto_backup_if_due()

        assert result["ran"] is True, result
        assert result["removed"] == ["backup-removable.zip"]
        assert "backup-locked.zip" not in result["removed"]

    def test_export_failure_returns_error_reason_and_logs(
        self, backup_env, monkeypatch, caplog
    ):
        import logging

        _set_settings(backup_env.db, backup_env.user_id, **{BACKUP_AUTO_KEY: "true"})

        def _boom(tag=None):
            raise RuntimeError("disk full")

        monkeypatch.setattr(backup_env, "export", _boom)
        with caplog.at_level(logging.ERROR):
            result = backup_env.auto_backup_if_due()

        assert result["ran"] is False
        assert result["reason"].startswith("error: disk full")
        assert "自动备份失败" in caplog.text      # fail-open：只记日志，不影响启动

    def test_invalid_interval_config_returns_error_instead_of_raising(self, backup_env, monkeypatch):
        _set_settings(
            backup_env.db, backup_env.user_id,
            **{BACKUP_AUTO_KEY: "true", BACKUP_INTERVAL_KEY: "not-a-number"},
        )
        exported = []
        monkeypatch.setattr(backup_env, "export", lambda tag=None: exported.append(tag))

        result = backup_env.auto_backup_if_due()   # 不得抛

        assert result["ran"] is False
        assert result["reason"].startswith("error:")
        assert "invalid literal" in result["reason"]
        assert exported == []


# ================================================================
# 三、verify 兼容分支（旧包 / 校验和不符）
# ================================================================
class TestVerifyCompatibility:
    def test_legacy_package_without_manifest_is_accepted(self, backup_env, db_session, test_user):
        """只有旧 manifest.json（无 files/SHA256）→ 接受，但 sha256_checked=False。"""
        payload = _zip_bytes(
            SQLITE_MAGIC,
            manifest={"app_version": "0.1.0", "user_id": test_user.id},
            manifest_name="manifest.json",
        )

        info = backup_env.verify(payload, "legacy.zip")

        assert info["valid"] is True
        assert info["sha256_checked"] is False      # 旧包没有 checksums
        assert info["user_id"] == test_user.id
        assert info["app_version"] == "0.1.0"

    def test_checksum_mismatch_is_rejected(self, backup_env):
        """MANIFEST 里 sha256 与 app.db 实际内容不符 → 必须拒绝（数据损坏）。"""
        wrong = hashlib.sha256(b"different").hexdigest()
        payload = _zip_bytes(
            SQLITE_MAGIC,
            manifest={
                "app_version": "0.7.0",
                "user_id": None,
                "files": [{"name": "app.db", "size": len(SQLITE_MAGIC), "sha256": wrong}],
            },
        )

        with pytest.raises(ValidationException) as ei:
            backup_env.verify(payload, "corrupt.zip")
        assert "校验和不符" in str(ei.value)

    def test_size_mismatch_is_rejected(self, backup_env):
        payload = _zip_bytes(
            SQLITE_MAGIC,
            manifest={
                "app_version": "0.7.0",
                "files": [{
                    "name": "app.db",
                    "size": len(SQLITE_MAGIC) + 99,
                    "sha256": hashlib.sha256(SQLITE_MAGIC).hexdigest(),
                }],
            },
        )

        with pytest.raises(ValidationException) as ei:
            backup_env.verify(payload, "size-bad.zip")
        assert "大小不符" in str(ei.value)
