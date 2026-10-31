# ============================================================
# 备份 / 数据统计服务（PRD §13.8 / 架构 v2.0 §5.6）
# - export：打包 DB + manifest 为 ZIP（不含 API Key）
# - import：校验 zip 结构（骨架阶段非破坏性，TODO 真正恢复）
# ============================================================
from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.exceptions import ValidationException
from app.core.logger import get_logger
from app.database import engine
from app.repositories import (
    BackupRepository,
    ConversationRepository,
    DocumentRepository,
    TaskRepository,
)

logger = get_logger("backup")

# 备份文件大小上限：100MB（个人数据足够，防止恶意上传）
MAX_BACKUP_SIZE = 100 * 1024 * 1024
# PRD F7.2：完整性清单文件名（与旧 manifest.json 并存兼容）
MANIFEST_NAME = "MANIFEST.json"

# 自动备份配置键（PRD F7.1：默认关闭）
BACKUP_AUTO_KEY = "backup.auto_enabled"
BACKUP_INTERVAL_KEY = "backup.interval_hours"
BACKUP_KEEP_KEY = "backup.keep"


def _rollback_failed_import(
    current_db: Path, backup_path: Path, tmp_path: Path, renamed: bool
) -> None:
    """D-46 导入失败后的自动回滚：清理 tmp；活动库缺失时从 `.bak` 恢复内容。

    用 copy 而不是 rename：保留 `.bak` 作为人工回滚点（rename 会把它消费掉）。
    回滚本身再失败时不掩盖原始异常——只记录「请手工恢复」的诊断日志。
    """
    try:
        if tmp_path.exists():
            tmp_path.unlink()
    except OSError:
        logger.warning("导入失败：临时文件清理失败（可手工删除）: {}", tmp_path)
    if renamed and not current_db.exists() and backup_path.exists():
        try:
            shutil.copy2(backup_path, current_db)
            logger.warning("导入失败，已自动从回滚副本恢复原库: {}", current_db)
        except OSError:
            logger.exception(
                "导入失败且自动回滚失败，请手工将 {} 改回 {}",
                backup_path,
                current_db,
            )


def _warn_version_mismatch(info: dict, current_version: str) -> None:
    """主版本不一致只告警、不阻断导入（与既有实现语义一致）。"""
    logger.warning(
        "备份版本 {} 与当前版本 {} 主版本号不同，可能存在兼容性问题",
        info["app_version"],
        current_version,
    )


def _cleanup_wal_files(current_db: Path) -> None:
    """清理旧连接残留的 WAL/SHM（活动库文件已被原子替换）。"""
    for suffix in (".db-wal", ".db-shm"):
        wal_file = current_db.with_suffix(suffix)
        if wal_file.exists():
            wal_file.unlink()


def _atomic_write_replace(
    current_db: Path,
    db_bytes: bytes,
    backup_path: Path,
    tmp_path: Path,
    renamed: bool,
) -> None:
    """D-46：写临时文件 → fsync → `os.replace()` 原子替换活动库。

    任一步失败都先走自动回滚（活动库可能已被改名为 `.bak`），再把原异常向上抛，
    保证 API 层的异常类型/失败语义不变。拆成独立函数便于进程内单测失败分支
    （子进程测试之外，父进程 coverage 也能覆盖成功/失败两条路径）。
    """
    try:
        with open(tmp_path, "wb") as fh:
            fh.write(db_bytes)
            fh.flush()
            os.fsync(fh.fileno())  # 尽量刷盘，缩小「崩溃留下半截库」窗口
        os.replace(tmp_path, current_db)  # 同目录同文件系统 → 原子替换
    except Exception:
        _rollback_failed_import(current_db, backup_path, tmp_path, renamed)
        raise


class BackupService:
    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id
        self.settings = get_settings()
        self.task_repo = TaskRepository(db)
        self.doc_repo = DocumentRepository(db)
        self.conv_repo = ConversationRepository(db)
        self.backup_repo = BackupRepository(db)

    def export(self, tag: str | None = None) -> dict:
        """导出全量备份 ZIP（DB + SHA256 清单，不含 API Key）。

        PRD F7.2：包内写 MANIFEST.json（文件清单 + SHA256 + 导出时间 +
        user_id），导入前据此校验完整性；旧 manifest.json 同时保留，
        便于旧版本读取。
        """
        backup_dir = self.settings.backups_dir
        stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        name = f"backup-{stamp}" + (f"-{tag}" if tag else "") + ".zip"
        zip_path = backup_dir / name
        # 数据入库后先 checkpoint，保证 WAL 落盘
        self.backup_repo.checkpoint_wal()
        self.db.commit()
        db_bytes = self.settings.db_path.read_bytes()
        created_at = datetime.now().isoformat()
        files = [{
            "name": "app.db",
            "size": len(db_bytes),
            "sha256": hashlib.sha256(db_bytes).hexdigest(),
        }]
        manifest = {
            "app_version": self.settings.version,
            "created_at": created_at,
            "user_id": self.user_id,
            "files": files,
            "algorithm": "sha256",
        }
        legacy = {
            "app_version": self.settings.version,
            "created_at": created_at,
            "user_id": self.user_id,
        }
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("app.db", db_bytes)
            zf.writestr(MANIFEST_NAME, json.dumps(manifest, ensure_ascii=False, indent=2))
            zf.writestr("manifest.json", json.dumps(legacy, ensure_ascii=False, indent=2))
        logger.info("备份已导出: {}（{} 字节，sha256 已记录）", zip_path, len(db_bytes))
        return {"path": str(zip_path), "size": len(db_bytes),
                "sha256": files[0]["sha256"], "created_at": created_at}

    def verify(self, file_bytes: bytes, filename: str) -> dict:
        """校验备份包完整性（PRD F7.2，**不落盘不改库**）。

        顺序：大小 → zip 结构 → 清单 → 逐文件 SHA256 → 用户归属 → SQLite 魔数。
        任一不通过即抛 ValidationException。
        """
        if len(file_bytes) > MAX_BACKUP_SIZE:
            raise ValidationException(
                f"备份文件过大（上限 {MAX_BACKUP_SIZE // 1024 // 1024}MB）"
            )
        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
                names = zf.namelist()
                if "app.db" not in names:
                    raise ValueError("缺少 app.db")
                if MANIFEST_NAME in names:
                    manifest = json.loads(zf.read(MANIFEST_NAME))
                elif "manifest.json" in names:
                    manifest = json.loads(zf.read("manifest.json"))  # 旧包无校验清单
                else:
                    raise ValueError("缺少清单文件")
                for item in manifest.get("files") or []:
                    data = zf.read(item["name"])
                    if item.get("size") is not None and len(data) != item["size"]:
                        raise ValidationException("备份文件不完整或已损坏（大小不符）")
                    if hashlib.sha256(data).hexdigest() != item.get("sha256"):
                        raise ValidationException("备份文件不完整或已损坏（校验和不符）")
                db_bytes = zf.read("app.db")
        except zipfile.BadZipFile as exc:
            raise ValidationException("备份文件不是有效的 ZIP 包") from exc
        except (ValueError, json.JSONDecodeError) as exc:
            raise ValidationException(f"备份文件不完整或已损坏: {exc}") from exc

        owner = manifest.get("user_id")
        if owner and owner != self.user_id:
            raise ValidationException("备份属于其他用户，拒绝导入")

        magic = b"SQLite format 3" + bytes([0])
        if not db_bytes.startswith(magic):
            raise ValidationException("备份包中的 app.db 不是有效的 SQLite 数据库文件")

        backup_version = manifest.get("app_version", "0.0.0")
        return {
            "valid": True,
            "filename": filename,
            "app_version": backup_version,
            "created_at": manifest.get("created_at"),
            "user_id": owner,
            "files": [f.get("name") for f in (manifest.get("files") or [{"name": "app.db"}])],
            "sha256_checked": bool(manifest.get("files")),
            "version_mismatch": backup_version.split(".")[0] != self.settings.version.split(".")[0],
        }

    def auto_backup_if_due(self) -> dict:
        """按需自动备份（PRD F7.1）：默认关闭，间隔/保留份数可配。

        失败不抛异常——启动流程不能被备份问题阻断。
        """
        from app.repositories import SettingRepository as SettingsRepository

        try:
            repo = SettingsRepository(self.db)

            def _cfg(key: str, default: str) -> str:
                # BaseRepository.get 是单键读取（2 参），此处用 get_by_key + 默认值
                row = repo.get_by_key(self.user_id, key)
                if row is None or row.value in (None, ""):
                    return default
                return str(row.value)

            enabled = _cfg(BACKUP_AUTO_KEY, "false").lower() == "true"
            if not enabled:
                return {"ran": False, "reason": "auto backup disabled"}
            interval_h = int(_cfg(BACKUP_INTERVAL_KEY, "24"))
            keep = max(1, int(_cfg(BACKUP_KEEP_KEY, "7")))

            existing = sorted(self.settings.backups_dir.glob("backup-*.zip"))
            if existing:
                newest = max(b.stat().st_mtime for b in existing)
                age_h = (datetime.now().timestamp() - newest) / 3600
                if age_h < interval_h:
                    return {"ran": False, "reason": "interval not elapsed",
                            "age_hours": round(age_h, 1)}

            result = self.export(tag="auto")
            after = sorted(self.settings.backups_dir.glob("backup-*.zip"),
                           key=lambda b: b.stat().st_mtime, reverse=True)
            removed = []
            for old in after[keep:]:
                try:
                    old.unlink()
                    removed.append(old.name)
                except OSError:
                    continue
            return {"ran": True, **result, "removed": removed, "keep": keep}
        except Exception as exc:  # noqa: BLE001 - 备份失败不得阻断启动
            logger.exception("自动备份失败")
            return {"ran": False, "reason": f"error: {exc}"}

    def import_(self, file_bytes: bytes, filename: str) -> dict:
        """从备份包恢复数据库：校验 → 备份当前库 → 替换 → 标记需重启。

        当前数据库会被重命名为 app.db.bak.{timestamp}，可回滚。
        替换前 dispose 引擎连接，避免旧连接句柄继续指向被改名的文件。
        """
        # 1–4. 完整性 + 用户归属 + SQLite 魔数校验（PRD F7.2，统一走 verify）
        info = self.verify(file_bytes, filename)
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
            db_bytes = zf.read("app.db")
        manifest = {"app_version": info["app_version"], "user_id": info["user_id"]}
        if info["version_mismatch"]:
            _warn_version_mismatch(info, self.settings.version)

        # 1. 先 checkpoint，确保当前 WAL 落盘
        self.backup_repo.checkpoint_wal()
        self.db.commit()

        # 2. 释放引擎持有的连接句柄：否则旧连接仍指向改名后的旧文件，
        #    「需重启」窗口期内的读写会落到备份文件且破坏 WAL 状态
        engine.dispose()

        # 3. 备份当前数据库
        # D-47：时间戳带毫秒 + 短 uuid —— 同秒内连续两次恢复不会因 `.bak` 同名
        # 在 Windows 上 FileExistsError，也不会在 POSIX 上覆盖上一个回滚点。
        current_db = self.settings.db_path
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19]
        backup_path = current_db.with_suffix(f".db.bak.{stamp}_{uuid4().hex[:6]}")
        renamed = False
        if current_db.exists():
            current_db.rename(backup_path)
            renamed = True

        # 4. D-46：写临时文件 + os.replace 原子替换。
        #    临时文件与活动库同目录（同文件系统），os.replace 才是原子的：
        #    不会出现「活动库缺失 / 半截文件」的中间态；崩溃时最多留一个 .tmp，
        #    原库仍完整躺在 .bak 里；失败自动回滚（见 _atomic_write_replace）。
        tmp_path = current_db.with_suffix(
            f".db.import-{os.getpid()}-{uuid4().hex[:8]}.tmp"
        )
        _atomic_write_replace(current_db, db_bytes, backup_path, tmp_path, renamed)

        # 5. 清理 WAL/SHM 文件（旧连接的残留）
        _cleanup_wal_files(current_db)

        logger.warning(
            "数据库已从备份恢复: {}，版本={}，原库备份={}，需重启应用生效",
            filename,
            manifest.get("app_version"),
            backup_path.name,
        )
        return {
            "success": True,
            "restart_required": True,
            "backup_of_original": str(backup_path),
            "manifest_version": manifest.get("app_version"),
        }

    def stats(self) -> dict:
        # D-06：计数/最近文档全部经各域 Repository（备份服务是聚合读）
        doc_count = self.doc_repo.count_by_user(self.user_id)
        task_count = self.task_repo.count_user(self.user_id)
        conv_count = self.conv_repo.count_by_user(self.user_id)
        # 标签数：取最近500篇文档统计（避免全量扫描）
        recent_docs = self.doc_repo.recent(self.user_id, limit=500)
        tags: set[str] = set()
        for d in recent_docs:
            tags.update(d.tags or [])
        return {
            "documents": doc_count,
            "tasks": task_count,
            "tags": len(tags),
            "conversations": conv_count,
        }
