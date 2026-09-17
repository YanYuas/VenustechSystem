from __future__ import annotations

from sqlalchemy import select

from app.models.notification import Notification
from app.repositories.base import BaseRepository


class NotificationRepository(BaseRepository[Notification]):
    model = Notification

    def list_user(
        self, user_id: str, unread_only: bool = False, skip: int = 0, limit: int = 50
    ) -> list[Notification]:
        q = select(Notification).where(Notification.user_id == user_id)
        if unread_only:
            q = q.where(Notification.is_read.is_(False))
        q = q.order_by(Notification.created_at.desc()).offset(skip).limit(limit)
        return list(self.db.scalars(q))

    def count_unread(self, user_id: str) -> int:
        from sqlalchemy import func
        return int(
            self.db.scalar(
                select(func.count())
                .select_from(Notification)
                .where(Notification.user_id == user_id, Notification.is_read.is_(False))
            )
            or 0
        )

    def mark_all_read(self, user_id: str) -> int:
        from app.models.base import utcnow
        rows = self.db.scalars(
            select(Notification).where(
                Notification.user_id == user_id, Notification.is_read.is_(False)
            )
        )
        count = 0
        for n in rows:
            n.is_read = True
            n.read_at = utcnow()
            count += 1
        if count:
            self.db.commit()
        return count
