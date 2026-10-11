# ============================================================
# Backup API 集成测试（原缺失模块，本轮补齐）
#
# 覆盖：导出、导入前校验（verify）、数据统计、非法导入被拒。
#
# 安全边界（重要）：
#   POST /api/v1/backup/import 在成功路径上会**替换活动数据库文件**并
#   engine.dispose()。在测试进程内调用它等于当场毁掉本会话的库，后续所有
#   用例都会失败。因此这里**只测它的拒绝路径**（拒绝发生在替换之前，安全）；
#   成功路径的替换逻辑已在 test_backup_production.py 用临时目录覆盖。
# ============================================================
from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

from app.database import SessionLocal


def _export_once(client) -> Path:
    r = client.post("/api/v1/backup/export")
    assert r.status_code == 200, r.text
    return Path(r.json()["data"]["path"])


def _make_invalid_zip() -> bytes:
    """不含 app.db 的 ZIP（verify 必须拒绝）。"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("readme.txt", "nothing here")
    return buf.getvalue()


def _make_no_manifest_zip() -> bytes:
    """有 app.db 但无清单（verify 必须拒绝）。"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("app.db", b"SQLite format 3" + bytes([0]) + b"x")
    return buf.getvalue()


def _make_non_sqlite_zip() -> bytes:
    """app.db 不含 SQLite 魔数（verify 必须拒绝）。"""
    payload = b"PK-not-a-db"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("app.db", payload)
        zf.writestr("MANIFEST.json", json.dumps({
            "app_version": "0.7.0", "user_id": None,
            "files": [{"name": "app.db", "size": len(payload),
                       "sha256": __import__("hashlib").sha256(payload).hexdigest()}],
        }))
    return buf.getvalue()


class TestBackupApiGroup1ExportStats:
    """第1组：导出 + 数据统计。"""

    def test_export_returns_path_size_sha(self, client):
        """导出接口返回 path/size/sha256/created_at，且文件真的落盘。"""
        r = client.post("/api/v1/backup/export")
        assert r.status_code == 200
        assert r.json()["code"] == 0
        data = r.json()["data"]
        assert Path(data["path"]).exists()
        assert data["size"] > 0
        assert len(data["sha256"]) == 64
        assert data["created_at"]

    def test_data_stats_shape(self, client):
        """统计接口返回 documents/tasks/tags/conversations 四项。"""
        r = client.get("/api/v1/data/stats")
        assert r.status_code == 200
        data = r.json()["data"]
        assert set(data.keys()) >= {"documents", "tasks", "tags", "conversations"}

    def test_data_stats_counts_created_rows(self, client, default_user_id):
        """统计值随新建数据增长，且与库内一致。"""
        client.post("/api/v1/documents", json={"title": "文档A", "content": "x"})
        client.post("/api/v1/documents", json={"title": "文档B", "content": "y"})
        client.post("/api/v1/tasks", json={"title": "任务A"})

        st = client.get("/api/v1/data/stats").json()["data"]
        assert st["documents"] == 2
        assert st["tasks"] == 1


class TestBackupApiGroup2Verify:
    """第2组：导入前完整性校验（不落盘不改库）。"""

    def test_verify_accepts_own_export(self, client):
        """对自己刚导出的包做校验：通过，且标记已做 SHA256 校验。"""
        package = _export_once(client).read_bytes()
        r = client.post("/api/v1/backup/verify",
                        files={"file": ("backup.zip", package, "application/zip")})
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["valid"] is True
        assert data["sha256_checked"] is True

    def test_verify_rejects_package_without_db(self, client):
        """缺少 app.db 的包返回 400 + 1001。"""
        r = client.post("/api/v1/backup/verify",
                        files={"file": ("bad.zip", _make_invalid_zip(), "application/zip")})
        assert r.status_code == 400
        assert r.json()["code"] == 1001

    def test_verify_rejects_package_without_manifest(self, client):
        """缺少清单的包返回 400。"""
        r = client.post("/api/v1/backup/verify",
                        files={"file": ("bad.zip", _make_no_manifest_zip(), "application/zip")})
        assert r.status_code == 400
        assert r.json()["code"] == 1001

    def test_verify_rejects_non_sqlite_payload(self, client):
        """app.db 非 SQLite 时返回 400。"""
        r = client.post("/api/v1/backup/verify",
                        files={"file": ("bad.zip", _make_non_sqlite_zip(), "application/zip")})
        assert r.status_code == 400
        assert r.json()["code"] == 1001

    def test_verify_does_not_write_anything(self, client, default_user_id):
        """校验是只读操作：不得改动数据库与业务数据。"""
        from sqlalchemy import func, select
        from app.models.document import Document

        client.post("/api/v1/documents", json={"title": "校验前", "content": "x"})

        def doc_count() -> int:
            db = SessionLocal()
            try:
                return int(db.scalar(
                    select(func.count()).select_from(Document)
                    .where(Document.user_id == default_user_id)
                ) or 0)
            finally:
                db.close()

        before = doc_count()
        client.post("/api/v1/backup/verify",
                    files={"file": ("bad.zip", _make_invalid_zip(), "application/zip")})
        assert doc_count() == before


class TestBackupApiGroup3ImportRejections:
    """第3组：非法导入在替换前被拒绝（成功路径见 service 层测试）。"""

    def test_import_rejects_non_zip(self, client):
        """非 ZIP 的导入请求返回 400。"""
        r = client.post("/api/v1/backup/import",
                        files={"file": ("x.zip", b"not a zip", "application/zip")})
        assert r.status_code == 400
        assert r.json()["code"] == 1001

    def test_import_rejects_package_without_db(self, client):
        """缺 app.db 的导入请求返回 400。"""
        r = client.post("/api/v1/backup/import",
                        files={"file": ("x.zip", _make_invalid_zip(), "application/zip")})
        assert r.status_code == 400
        assert r.json()["code"] == 1001

    def test_failed_import_keeps_data_readable(self, client, default_user_id):
        """导入失败后，原有数据仍可正常读取（活动库未被破坏）。"""
        client.post("/api/v1/documents", json={"title": "幸存文档", "content": "x"})
        client.post("/api/v1/backup/import",
                    files={"file": ("x.zip", b"garbage", "application/zip")})

        docs = client.get("/api/v1/documents").json()["data"]["list"]
        assert any(d["title"] == "幸存文档" for d in docs)
