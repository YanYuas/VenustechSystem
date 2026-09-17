# ============================================================
# 备份 / 数据统计服务（PRD §13.8 / 架构 v2.0 §5.6）
# - export：打包 DB + manifest 为 ZIP（不含 API Key）
# - import：校验 zip 结构（骨架阶段非破坏性，TODO 真正恢复）
# ============================================================
from __future__ import annotations

import io
import json
import zipfile
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.exceptions import ValidationException
from app.core.logger import get_logger
from app.database import engine
from app.models.conversation import Conversation
from app.models.document import Document
from app.models.task import Task
from app.repositories import (
    ConversationRepository,
    DocumentRepository,
    TaskRepository,
)

logger = get_logger("backup")

# 备份文件大小上限：100MB（个人数据足够，防止恶意上传）
MAX_BACKUP_SIZE = 100 * 1024 * 1024


class BackupService:
    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id
        self.settings = get_settings()
        self.task_repo = TaskRepository(db)
        self.doc_repo = DocumentRepository(db)
        self.conv_repo = ConversationRepository(db)

    def export(self) -> dict:
        """导出全量备份 ZIP（DB + manifest，不含 API Key）。"""
        backup_dir = self.settings.backups_dir
        stamp = date.today().isoformat()
        zip_path = backup_dir / f"backup-{stamp}.zip"
        manifest = {
            "app_version": self.settings.version,
            "created_at": datetime.now().isoformat(),
            "user_id": self.user_id,
        }
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # 数据入库后先 checkpoint，保证 WAL 落盘
            self.db.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
            db_file = self.settings.db_path
            zf.write(db_file, arcname="app.db")
            zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        logger.info(f"备份已导出: {zip_path}")
        return {"path": str(zip_path)}

    def import_(self, file_bytes: bytes, filename: str) -> dict:
        """从备份包恢复数据库：校验 → 备份当前库 → 替换 → 标记需重启。

        当前数据库会被重命名为 app.db.bak.{timestamp}，可回滚。
        替换前 dispose 引擎连接，避免旧连接句柄继续指向被改名的文件。
        """
        # 1. 文件大小校验
        if len(file_bytes) > MAX_BACKUP_SIZE:
            raise ValidationException(f"备份文件过大（上限 {MAX_BACKUP_SIZE // 1024 // 1024}MB）")

        # 2. 校验备份包结构
        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
                names = zf.namelist()
                if "app.db" not in names or "manifest.json" not in names:
                    raise ValueError("备份包结构不完整")
                manifest = json.loads(zf.read("manifest.json"))
                db_bytes = zf.read("app.db")
        except (zipfile.BadZipFile, ValueError, json.JSONDecodeError) as exc:
            raise ValidationException(f"备份包无效: {exc}") from exc

        # 3. 校验 app.db 是合法 SQLite 文件（防止损坏/恶意包直接覆盖用户库）
        if not db_bytes.startswith(b"SQLite format 3\x00"):
            raise ValidationException("备份包中的 app.db 不是有效的 SQLite 数据库文件")

        # 4. 版本兼容性校验（主版本号不同则警告但不阻止）
        backup_version = manifest.get("app_version", "0.0.0")
        current_version = self.settings.version
        if backup_version.split(".")[0] != current_version.split(".")[0]:
            logger.warning(
                "备份版本 %s 与当前版本 %s 主版本号不同，可能存在兼容性问题",
                backup_version, current_version,
            )

        # 1. 先 checkpoint，确保当前 WAL 落盘
        self.db.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
        self.db.commit()

        # 2. 释放引擎持有的连接句柄：否则旧连接仍指向改名后的旧文件，
        #    「需重启」窗口期内的读写会落到备份文件且破坏 WAL 状态
        engine.dispose()

        # 3. 备份当前数据库
        current_db = self.settings.db_path
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = current_db.with_suffix(f".db.bak.{timestamp}")
        if current_db.exists():
            current_db.rename(backup_path)

        # 4. 写入备份数据库
        current_db.write_bytes(db_bytes)

        # 5. 清理 WAL/SHM 文件（旧连接的残留）
        for suffix in (".db-wal", ".db-shm"):
            wal_file = current_db.with_suffix(suffix)
            if wal_file.exists():
                wal_file.unlink()

        logger.warning(
            f"数据库已从备份恢复: {filename}，版本={manifest.get('app_version')}，"
            f"原库备份={backup_path.name}，需重启应用生效"
        )
        return {
            "success": True,
            "restart_required": True,
            "backup_of_original": str(backup_path),
            "manifest_version": manifest.get("app_version"),
        }

    def stats(self) -> dict:
        doc_count = self.db.scalar(
            select(func.count()).select_from(Document).where(Document.user_id == self.user_id)
        ) or 0
        task_count = self.db.scalar(
            select(func.count()).select_from(Task).where(Task.user_id == self.user_id)
        ) or 0
        conv_count = self.db.scalar(
            select(func.count()).select_from(Conversation).where(Conversation.user_id == self.user_id)
        ) or 0
        # 标签数：取最近500篇文档统计（避免全量扫描）
        recent_docs = self.db.scalars(
            select(Document).where(Document.user_id == self.user_id).limit(500)
        )
        tags: set[str] = set()
        for d in recent_docs:
            tags.update(d.tags or [])
        return {
            "documents": doc_count,
            "tasks": task_count,
            "tags": len(tags),
            "conversations": conv_count,
        }
