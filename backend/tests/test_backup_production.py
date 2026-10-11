# ============================================================
# BackupService 生产级测试（原缺失模块，本轮补齐）
#
# 覆盖：导出 ZIP（含 SHA256 清单）/ 完整性校验（PRD F7.2）/ 导入前置校验 /
# 导入替换（隔离到临时目录）/ 数据统计 / 自动备份开关。
#
# 安全设计（重要）：
#   import_() 会**替换活动数据库文件**并 engine.dispose()。若直接对着测试库
#   调用，会当场毁掉整个测试会话的数据库。因此本文件用「桩 settings」把
#   db_path/backups_dir 指向 pytest 的 tmp_path，让真实的替换逻辑在一个
#   一次性目录里跑，既能覆盖代码又不碰活动库。
# ============================================================
from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path

import pytest

from app.config import get_settings
from app.core.exceptions import ValidationException
from app.services import backup_service as bs
from app.services.backup_service import BackupService


class _StubSettings:
    """把 data_dir 指向临时目录的 settings 桩（仅暴露服务真正用到的属性）。"""

    def __init__(self, root: Path, version: str = "0.7.0"):
        self.data_dir = root
        self.version = version

    @property
    def db_path(self) -> Path:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return self.data_dir / "app.db"

    @property
    def backups_dir(self) -> Path:
        d = self.data_dir / "backups"
        d.mkdir(parents=True, exist_ok=True)
        return d


@pytest.fixture()
def svc(db_session, test_user, tmp_path):
    """指向临时目录的 BackupService（可安全触发替换逻辑）。"""
    # 先提交，清掉 test_user 留下的未提交事务：否则 export() 里的
    # PRAGMA wal_checkpoint(TRUNCATE) 会在事务中执行而报 "database table is locked"
    db_session.commit()
    service = BackupService(db_session, test_user.id)
    stub = _StubSettings(tmp_path)
    # 放一份「像样的」SQLite 文件在桩路径上，供 export 读取
    stub.db_path.write_bytes(get_settings().db_path.read_bytes())
    service.settings = stub
    return service


def _make_zip(db_bytes: bytes, *, manifest: dict | None = "<default>",
              extra: dict[str, str] | None = None, include_manifest: bool = True) -> bytes:
    if manifest == "<default>":
        manifest = {
            "app_version": "0.7.0",
            "created_at": "2026-01-01T00:00:00",
            "user_id": None,
            "files": [{
                "name": "app.db",
                "size": len(db_bytes),
                "sha256": hashlib.sha256(db_bytes).hexdigest(),
            }],
            "algorithm": "sha256",
        }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("app.db", db_bytes)
        if include_manifest and manifest is not None:
            zf.writestr(bs.MANIFEST_NAME, json.dumps(manifest, ensure_ascii=False))
        for name, content in (extra or {}).items():
            zf.writestr(name, content)
    return buf.getvalue()


SQLITE_MAGIC = b"SQLite format 3" + bytes([0])


class TestExport:
    """导出：ZIP 结构 + 清单一致性 + 返回值。"""

    def test_export_creates_zip_with_expected_members(self, svc):
        """导出的 ZIP 必须含 app.db、MANIFEST.json 与兼容用的 manifest.json。"""
        result = svc.export()
        path = Path(result["path"])
        assert path.exists()
        with zipfile.ZipFile(path) as zf:
            names = set(zf.namelist())
        assert {"app.db", bs.MANIFEST_NAME, "manifest.json"} <= names

    def test_export_manifest_sha256_matches_db_bytes(self, svc):
        """清单里的 SHA256 必须与包内 app.db 一致（否则导入校验必然失败）。"""
        result = svc.export()
        with zipfile.ZipFile(Path(result["path"])) as zf:
            manifest = json.loads(zf.read(bs.MANIFEST_NAME))
            db_bytes = zf.read("app.db")
        assert manifest["files"][0]["sha256"] == hashlib.sha256(db_bytes).hexdigest()
        assert result["sha256"] == hashlib.sha256(db_bytes).hexdigest()
        assert result["size"] == len(db_bytes)

    def test_export_manifest_records_owner(self, svc, test_user):
        """清单记录导出者 user_id（导入时据此拒绝他人备份）。"""
        result = svc.export()
        with zipfile.ZipFile(Path(result["path"])) as zf:
            manifest = json.loads(zf.read(bs.MANIFEST_NAME))
        assert manifest["user_id"] == test_user.id

    def test_export_tag_appears_in_filename(self, svc):
        """tag 参与文件名，便于区分手动/自动备份。"""
        result = svc.export(tag="manual")
        assert "manual" in Path(result["path"]).name


class TestVerifyRejections:
    """完整性校验：所有拒绝分支（PRD F7.2，安全关键路径）。"""

    def test_accepts_valid_package(self, svc):
        """正常包通过校验，且标记已做 SHA256 校验。"""
        result = svc.export()
        info = svc.verify(Path(result["path"]).read_bytes(), "backup.zip")
        assert info["valid"] is True
        assert info["sha256_checked"] is True
        assert info["filename"] == "backup.zip"

    def test_rejects_tampered_db_bytes(self, svc):
        """包内 app.db 被改动后校验和不符，必须拒绝。

        构造方式：先生成一个哈希正确的包，再解包、篡改 app.db、原样回填清单。
        """
        original = SQLITE_MAGIC + b"original"
        package = _make_zip(original)
        with zipfile.ZipFile(io.BytesIO(package)) as zf:
            manifest = zf.read(bs.MANIFEST_NAME)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("app.db", SQLITE_MAGIC + b"CHANGED")
            zf.writestr(bs.MANIFEST_NAME, manifest)
        with pytest.raises(ValidationException):
            svc.verify(buf.getvalue(), "backup.zip")

    def test_rejects_missing_db_member(self, svc):
        """缺少 app.db 的包被拒绝。"""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr(bs.MANIFEST_NAME, json.dumps({"files": []}))
        with pytest.raises(ValidationException):
            svc.verify(buf.getvalue(), "backup.zip")

    def test_rejects_missing_manifest(self, svc):
        """既无 MANIFEST.json 也无 manifest.json 的包被拒绝。"""
        package = _make_zip(SQLITE_MAGIC, include_manifest=False)
        with pytest.raises(ValidationException):
            svc.verify(package, "backup.zip")

    def test_rejects_non_zip_bytes(self, svc):
        """非 ZIP 字节流被拒绝（不得抛未捕获异常）。"""
        with pytest.raises(ValidationException):
            svc.verify(b"this is definitely not a zip file", "backup.zip")

    def test_rejects_non_sqlite_payload(self, svc):
        """app.db 不含 SQLite 魔数时拒绝（防止塞入任意文件）。"""
        package = _make_zip(b"PK\x03\x04-not-sqlite")
        with pytest.raises(ValidationException):
            svc.verify(package, "backup.zip")

    def test_rejects_foreign_user_package(self, svc):
        """清单 user_id 指向他人时拒绝导入。"""
        package = _make_zip(SQLITE_MAGIC, manifest={
            "app_version": "0.7.0", "user_id": "someone-else",
            "files": [{"name": "app.db", "size": len(SQLITE_MAGIC),
                       "sha256": hashlib.sha256(SQLITE_MAGIC).hexdigest()}],
        })
        with pytest.raises(ValidationException):
            svc.verify(package, "backup.zip")

    def test_rejects_oversize_package(self, svc, monkeypatch):
        """超过大小上限的包被拒绝（防止恶意上传打满磁盘）。"""
        monkeypatch.setattr(bs, "MAX_BACKUP_SIZE", 10)
        with pytest.raises(ValidationException):
            svc.verify(b"x" * 100, "backup.zip")

    def test_version_mismatch_is_reported_not_rejected(self, svc):
        """主版本号不一致只做提示，不拒绝（跨版本迁移仍需允许导入）。"""
        package = _make_zip(SQLITE_MAGIC, manifest={
            "app_version": "9.9.9", "user_id": None,
            "files": [{"name": "app.db", "size": len(SQLITE_MAGIC),
                       "sha256": hashlib.sha256(SQLITE_MAGIC).hexdigest()}],
        })
        info = svc.verify(package, "backup.zip")
        assert info["valid"] is True
        assert info["version_mismatch"] is True


class TestImport:
    """导入：先校验后替换；失败路径绝不触碰活动库。"""

    def test_import_rejects_invalid_package(self, svc):
        """非法包在替换前即被拒绝。"""
        with pytest.raises(ValidationException):
            svc.import_(b"not-a-zip", "backup.zip")

    def test_import_failure_leaves_live_db_intact(self, db_session, test_user, svc):
        """导入被拒绝时，活动数据库不得被改动。

        防什么：若「先替换后校验」，一次恶意导入就能毁掉用户数据。
        """
        from tests.factories import make_document

        make_document(db_session, test_user.id, title="导入失败前存在")
        db_session.commit()

        with pytest.raises(ValidationException):
            svc.import_(b"garbage", "backup.zip")

        from app.models.document import Document
        from sqlalchemy import select
        rows = db_session.scalars(
            select(Document).where(Document.user_id == test_user.id)
        ).all()
        assert [d.title for d in rows] == ["导入失败前存在"]

    def test_import_valid_package_swaps_temp_db_and_keeps_rollback_copy(self, svc):
        """合法包导入到「桩目录」：写回 db 文件、保留 .bak 回滚副本、要求重启。"""
        result = svc.export()
        package = Path(result["path"]).read_bytes()
        original_bytes = svc.settings.db_path.read_bytes()

        info = svc.import_(package, "backup.zip")
        assert info["success"] is True
        assert info["restart_required"] is True

        # 新库字节 == 包内 app.db
        assert svc.settings.db_path.read_bytes() == original_bytes
        # 原库被改名保留，可回滚
        baks = list(svc.settings.data_dir.glob("app.db.bak.*"))
        assert len(baks) == 1
        assert baks[0].read_bytes() == original_bytes


class TestStatsAndAutoBackup:
    """数据统计 + 自动备份开关。"""

    def test_stats_counts_owned_rows(self, db_session, test_user, svc):
        """统计返回本人 documents/tasks/conversations 计数与标签并集。"""
        from tests.factories import make_document, make_task

        make_document(db_session, test_user.id, title="d1", tags=["数学", "整理"])
        make_document(db_session, test_user.id, title="d2", tags=["整理"])
        make_task(db_session, test_user.id, title="t1")
        db_session.commit()

        st = svc.stats()
        assert st["documents"] == 2
        assert st["tasks"] == 1
        assert st["tags"] == 2  # {数学, 整理}
        assert st["conversations"] == 0

    def test_stats_excludes_other_users(self, db_session, test_user, other_user, svc):
        """统计不串用户。"""
        from tests.factories import make_document

        make_document(db_session, other_user.id, title="别人的")
        db_session.commit()
        assert svc.stats()["documents"] == 0

    def test_auto_backup_disabled_by_default(self, svc):
        """默认关闭自动备份（PRD F7.1），返回明确原因而非报错。"""
        info = svc.auto_backup_if_due()
        assert info["ran"] is False
        assert "disabled" in info["reason"]
