# ============================================================
# 备份 Repository（D-06 收口）
#
# 备份没有自己的业务表，只有一个**数据库级动作**：
# 导出/导入前必须把 WAL 落盘（checkpoint），否则直接读 app.db 文件
# 会拿到不含最新提交的旧快照。
#
# 为什么放在 Repository：PRAGMA 是 DB 访问，属于本层；service 里出现
# `text("PRAGMA ...")` 会被架构守护 R13 判为直连 ORM。
# ============================================================
from __future__ import annotations

from sqlalchemy import text

from app.repositories.base import BaseRepository


class BackupRepository(BaseRepository):
    """备份所需的数据库级操作（无业务模型）。"""

    def checkpoint_wal(self) -> None:
        """把 WAL 内容合并进主库文件（导出/替换库文件前调用）。"""
        self.db.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
