from __future__ import annotations

from sqlalchemy import func, or_, select

from app.models.document import Backlink, Document, DocumentVersion
from app.repositories.base import BaseRepository


class DocumentRepository(BaseRepository[Document]):
    model = Document

    def list_documents(
        self,
        user_id: str,
        folder_id: str | None = None,
        tag: str | None = None,
        search: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Document]:
        q = select(Document).where(Document.user_id == user_id)
        if folder_id:
            q = q.where(Document.folder_id == folder_id)
        if tag:
            q = q.where(Document.tags.like(f'%"{tag}"%'))
        if search:
            like = f"%{search}%"
            q = q.where(or_(Document.title.like(like), Document.content.like(like)))
        q = q.order_by(Document.updated_at.desc()).offset(skip).limit(limit)
        return list(self.db.scalars(q))

    def count_documents(
        self,
        user_id: str,
        folder_id: str | None = None,
        tag: str | None = None,
        search: str | None = None,
    ) -> int:
        q = select(func.count()).select_from(Document).where(Document.user_id == user_id)
        if folder_id:
            q = q.where(Document.folder_id == folder_id)
        if tag:
            q = q.where(Document.tags.like(f'%"{tag}"%'))
        if search:
            like = f"%{search}%"
            q = q.where(or_(Document.title.like(like), Document.content.like(like)))
        return int(self.db.scalar(q))

    def recent(self, user_id: str, limit: int = 3) -> list[Document]:
        q = (
            select(Document)
            .where(Document.user_id == user_id)
            .order_by(Document.updated_at.desc())
            .limit(limit)
        )
        return list(self.db.scalars(q))

    def search_documents(self, user_id: str, keyword: str, limit: int = 10) -> list[Document]:
        like = f"%{keyword}%"
        q = (
            select(Document)
            .where(
                Document.user_id == user_id,
                or_(Document.title.like(like), Document.content.like(like)),
            )
            .order_by(Document.updated_at.desc())
            .limit(limit)
        )
        return list(self.db.scalars(q))

    def all_tags(self, user_id: str) -> list[str]:
        docs = self.list_documents(user_id)
        seen: dict[str, None] = {}
        for d in docs:
            for t in (d.tags or []):
                seen[t] = None
        return list(seen.keys())

    def find_by_title(self, user_id: str, title: str) -> Document | None:
        return self.db.scalar(
            select(Document).where(Document.user_id == user_id, Document.title == title)
        )


class DocumentVersionRepository(BaseRepository[DocumentVersion]):
    model = DocumentVersion

    def list_by_document(self, document_id: str) -> list[DocumentVersion]:
        q = (
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.version.desc())
        )
        return list(self.db.scalars(q))

    def get_by_version(self, document_id: str, version: int) -> DocumentVersion | None:
        return self.db.scalar(
            select(DocumentVersion).where(
                DocumentVersion.document_id == document_id,
                DocumentVersion.version == version,
            )
        )

    def delete_oldest(self, document_id: str, keep: int) -> None:
        versions = self.list_by_document(document_id)
        for v in versions[keep:]:
            self.db.delete(v)
        self.db.commit()


class BacklinkRepository(BaseRepository[Backlink]):
    model = Backlink

    def list_targets(self, document_id: str) -> list[Backlink]:
        q = select(Backlink).where(Backlink.target_doc_id == document_id)
        return list(self.db.scalars(q))

    def list_sources(self, source_doc_id: str) -> list[Backlink]:
        q = select(Backlink).where(Backlink.source_doc_id == source_doc_id)
        return list(self.db.scalars(q))

    def delete_by_source(self, source_doc_id: str) -> None:
        for bl in self.list_sources(source_doc_id):
            self.db.delete(bl)
        self.db.commit()
