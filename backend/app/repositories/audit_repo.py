# ============================================================
# 审计日志 Repository（mod-platform P1 · D-06 收口）
#
# 审计表只增不改；写入按 AUDIT_KEEP 修剪最旧记录。
# 注意：审计写入**独立提交**（业务失败也要留痕），事务由 service 闭合。
# ============================================================
from __future__ import annotations

from sqlalchemy import delete, func, select

from app.models.audit import AuditLog
from app.repositories.base import BaseRepository


class AuditLogRepository(BaseRepository[AuditLog]):
    """安全审计日志。"""

    model = AuditLog

    def create_entry(
        self,
        *,
        user_id: str,
        action: str,
        target: str | None = None,
        ok: bool = True,
        detail: str | None = None,
        ip: str | None = None,
    ) -> AuditLog:
        """追加一条审计记录（只 flush）。"""
        return self.create(
            user_id=user_id,
            action=action,
            target=target,
            ok=ok,
            detail=detail,
            ip=ip,
        )

    def list_user(self, user_id: str, limit: int = 50) -> list[AuditLog]:
        """最近的审计记录（新→旧，排除软删除）。"""
        q = (
            select(AuditLog)
            .where(AuditLog.user_id == user_id, AuditLog.deleted_at.is_(None))
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        return list(self.db.scalars(q))

    def count_user(self, user_id: str) -> int:
        return int(
            self.db.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(AuditLog.user_id == user_id)
            )
            or 0
        )

    def stale_ids(self, user_id: str, keep: int) -> list[str]:
        """超出保留上限的最旧记录 id（按 created_at 升序取前 N 条）。"""
        total = self.count_user(user_id)
        if total <= keep:
            return []
        q = (
            select(AuditLog.id)
            .where(AuditLog.user_id == user_id)
            .order_by(AuditLog.created_at.asc())
            .limit(total - keep)
        )
        return list(self.db.scalars(q))

    def delete_by_ids(self, ids: list[str]) -> None:
        """按 id 批量删除（修剪用；只 flush）。"""
        if not ids:
            return
        self.db.execute(delete(AuditLog).where(AuditLog.id.in_(ids)))
        self.db.flush()
