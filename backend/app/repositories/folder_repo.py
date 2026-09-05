from __future__ import annotations

from sqlalchemy import func, select

from app.models.document import Document
from app.models.folder import Folder
from app.repositories.base import BaseRepository


class FolderRepository(BaseRepository[Folder]):
    model = Folder

    def list_roots(self, user_id: str) -> list[Folder]:
        q = (
            select(Folder)
            .where(Folder.user_id == user_id, Folder.parent_id.is_(None))
            .order_by(Folder.sort_order, Folder.created_at)
        )
        return list(self.db.scalars(q))

    def list_children(self, user_id: str, parent_id: str) -> list[Folder]:
        q = (
            select(Folder)
            .where(Folder.user_id == user_id, Folder.parent_id == parent_id)
            .order_by(Folder.sort_order, Folder.created_at)
        )
        return list(self.db.scalars(q))

    def list_by_user(self, user_id: str) -> list[Folder]:
        q = select(Folder).where(Folder.user_id == user_id).order_by(Folder.sort_order)
        return list(self.db.scalars(q))

    def get_inbox(self, user_id: str) -> Folder | None:
        return self.db.scalar(
            select(Folder).where(Folder.user_id == user_id, Folder.is_inbox.is_(True))
        )

    def count_documents(self, folder_id: str) -> int:
        return int(
            self.db.scalar(
                select(func.count())
                .select_from(Document)
                .where(Document.folder_id == folder_id)
            )
        )
