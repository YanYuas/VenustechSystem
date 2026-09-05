# ============================================================
# 统一通知服务（PRD §12.4）
# - 创建通知（系统/AI/任务等来源）
# - 列表 / 未读数 / 标记已读 / 全部已读
# ============================================================
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundException
from app.models.base import utcnow
from app.models.notification import Notification
from app.repositories import NotificationRepository
from app.schemas.notification import (
    CreateNotificationRequest,
    NotificationOut,
    NotificationStats,
)


class NotificationService:
    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id
        self.repo = NotificationRepository(db)

    def list(self, unread_only: bool = False, page: int = 1, page_size: int = 50) -> list[NotificationOut]:
        skip = (page - 1) * page_size
        rows = self.repo.list_user(self.user_id, unread_only=unread_only, skip=skip, limit=page_size)
        return [self._out(n) for n in rows]

    def stats(self) -> NotificationStats:
        total = int(
            self.db.scalar(
                select(func.count()).select_from(Notification).where(Notification.user_id == self.user_id)
            )
            or 0
        )
        return NotificationStats(total=total, unread=self.repo.count_unread(self.user_id))

    def create(self, data: CreateNotificationRequest) -> NotificationOut:
        n = self.repo.create(
            user_id=self.user_id,
            type=data.type,
            title=data.title,
            content=data.content,
            source_type=data.source_type,
            source_id=data.source_id,
        )
        return self._out(n)

    def mark_read(self, notification_id: str, read: bool = True) -> NotificationOut:
        n = self.repo.get(notification_id)
        if n is None or n.user_id != self.user_id:
            raise NotFoundException("通知不存在")
        n.is_read = read
        n.read_at = utcnow() if read else None
        self.db.commit()
        self.db.refresh(n)
        return self._out(n)

    def mark_all_read(self) -> int:
        return self.repo.mark_all_read(self.user_id)

    @staticmethod
    def _out(n: Notification) -> NotificationOut:
        return NotificationOut(
            id=n.id, type=n.type, title=n.title, content=n.content,
            is_read=n.is_read, read_at=n.read_at, source_type=n.source_type,
            source_id=n.source_id, created_at=n.created_at, updated_at=n.updated_at,
        )
