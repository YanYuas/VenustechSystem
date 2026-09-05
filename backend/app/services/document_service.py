# ============================================================
# 知识资源服务（文件夹树 + 文档 CRUD + 版本历史 + 双向链接 + 全文搜索 + 标签）
# 对齐 PRD §9 / 架构 v2.0 §8.2
# ============================================================
from __future__ import annotations

import re
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from app.core.event_bus import EVENT_DOCUMENT_SAVED, event_bus
from app.core.exceptions import DuplicateFolderNameException, InboxImmutableException, NotFoundException
from app.models.document import Backlink, Document
from app.models.folder import Folder
from app.repositories import (
    BacklinkRepository,
    DocumentRepository,
    DocumentVersionRepository,
    FolderRepository,
)
from app.schemas.common import PaginatedData
from app.schemas.document import (
    BacklinkSourceOut,
    CreateDocumentRequest,
    DocumentOut,
    DocumentVersionOut,
    SearchConversationHit,
    SearchDocumentHit,
    SearchResultOut,
    SearchTaskHit,
    UpdateDocumentRequest,
)
from app.schemas.folder import FolderOut

MAX_VERSIONS = 10
LINK_PATTERN = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]")


def count_words(text: str | None) -> int:
    """字数统计：去除空白后按字符计（PRD §9 字数）。"""
    if not text:
        return 0
    return len(re.sub(r"\s+", "", text))


class DocumentService:
    def __init__(self, db: Session):
        self.db = db
        self.folder_repo = FolderRepository(db)
        self.doc_repo = DocumentRepository(db)
        self.ver_repo = DocumentVersionRepository(db)
        self.link_repo = BacklinkRepository(db)

    # ---------- 文件夹 ----------
    def _ensure_inbox(self, user_id: str) -> Folder:
        inbox = self.folder_repo.get_inbox(user_id)
        if inbox is None:
            inbox = self.folder_repo.create(user_id=user_id, name="收集箱", is_inbox=True, sort_order=0)
        return inbox

    def folders_tree(self, user_id: str) -> list[FolderOut]:
        inbox = self._ensure_inbox(user_id)
        all_folders = self.folder_repo.list_by_user(user_id)
        by_parent: dict[str | None, list[Folder]] = {}
        for f in all_folders:
            by_parent.setdefault(f.parent_id, []).append(f)
        for lst in by_parent.values():
            lst.sort(key=lambda f: (f.is_inbox is False, f.sort_order, f.created_at))

        def build(f: Folder) -> FolderOut:
            children = [build(c) for c in by_parent.get(f.id, [])]
            return FolderOut(
                id=f.id, name=f.name, parent_id=f.parent_id, sort_order=f.sort_order,
                is_inbox=f.is_inbox, created_at=f.created_at, updated_at=f.updated_at,
                children=children,
            )

        roots = by_parent.get(None, [])
        # 收集箱置顶
        roots.sort(key=lambda f: (f.is_inbox is False, f.sort_order, f.created_at))
        return [build(r) for r in roots]

    def create_folder(self, user_id: str, name: str, parent_id: str | None = None) -> FolderOut:
        if parent_id:
            parent = self.folder_repo.get(parent_id)
            if parent is None or parent.user_id != user_id:
                raise NotFoundException("父文件夹不存在")
        dup = [
            f for f in self.folder_repo.list_by_user(user_id)
            if f.parent_id == parent_id and f.name == name
        ]
        if dup:
            raise DuplicateFolderNameException("同级已存在同名文件夹")
        folder = self.folder_repo.create(user_id=user_id, name=name, parent_id=parent_id)
        return self._folder_out(folder)

    def rename_folder(self, user_id: str, folder_id: str, name: str) -> FolderOut:
        folder = self._owned_folder(folder_id, user_id)
        if folder.is_inbox:
            raise InboxImmutableException("收集箱不可重命名")
        folder.name = name
        self.db.commit()
        self.db.refresh(folder)
        return self._folder_out(folder)

    def delete_folder(self, user_id: str, folder_id: str) -> None:
        folder = self._owned_folder(folder_id, user_id)
        if folder.is_inbox:
            raise InboxImmutableException("收集箱不可删除")
        inbox = self._ensure_inbox(user_id)
        try:
            # 子文件夹上浮到根
            for child in self.folder_repo.list_children(user_id, folder.id):
                child.parent_id = None
            # 文档移至收集箱
            for doc in self.doc_repo.list_documents(user_id, folder_id=folder.id, limit=10000):
                doc.folder_id = inbox.id
            self.db.delete(folder)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    # ---------- 文档 ----------
    def list_documents(
        self,
        user_id: str,
        folder_id: str | None = None,
        tag: str | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
        sort: str = "-updated_at",
    ) -> PaginatedData[DocumentOut]:
        skip = (page - 1) * page_size
        docs = self.doc_repo.list_documents(
            user_id, folder_id=folder_id, tag=tag, search=search, skip=skip, limit=page_size
        )
        total = self.doc_repo.count_documents(user_id, folder_id=folder_id, tag=tag, search=search)
        # 批量预加载文件夹名，消除 N+1
        folder_ids = {d.folder_id for d in docs if d.folder_id}
        folder_map: dict[str, str] = {}
        if folder_ids:
            from sqlalchemy import select
            from app.models.folder import Folder
            rows = self.db.scalars(select(Folder).where(Folder.id.in_(folder_ids)))
            folder_map = {f.id: f.name for f in rows}
        items = [self._doc_out(d, folder_map) for d in docs]
        return PaginatedData(
            list=items,
            total=total, page=page, page_size=page_size,
        )

    def create_document(self, user_id: str, data: CreateDocumentRequest) -> DocumentOut:
        if data.folder_id is None:
            inbox = self._ensure_inbox(user_id)
            folder_id = inbox.id
        else:
            folder = self.folder_repo.get(data.folder_id)
            if folder is None or folder.user_id != user_id:
                raise NotFoundException("文件夹不存在")
            folder_id = data.folder_id
        doc = self.doc_repo.create(
            user_id=user_id,
            title=data.title,
            content=data.content,
            folder_id=folder_id,
            word_count=count_words(data.content),
            version=1,
        )
        self._sync_backlinks(user_id, doc)
        return self._doc_out(doc)

    def get_document(self, user_id: str, doc_id: str) -> DocumentOut:
        doc = self._owned_doc(doc_id, user_id)
        return self._doc_out(doc)

    def update_document(self, user_id: str, doc_id: str, data: UpdateDocumentRequest) -> DocumentOut:
        doc = self._owned_doc(doc_id, user_id)
        payload = data.model_dump(exclude_unset=True)
        content_changed = "content" in payload and payload["content"] != doc.content
        if content_changed:
            # 保存旧内容快照 → 版本 +1（PRD §9 F3.7）
            self.ver_repo.create(
                document_id=doc.id,
                content=doc.content or "",
                version=doc.version,
                word_count=count_words(doc.content),
            )
            doc.version += 1
            doc.word_count = count_words(payload["content"])
            self.ver_repo.delete_oldest(doc.id, keep=MAX_VERSIONS)
        if "title" in payload:
            doc.title = payload["title"]
        if "tags" in payload:
            doc.tags = payload["tags"] or []
        if "folder_id" in payload:
            new_fid = payload["folder_id"]
            if new_fid:
                folder = self.folder_repo.get(new_fid)
                if folder is None or folder.user_id != user_id:
                    raise NotFoundException("文件夹不存在")
            doc.folder_id = new_fid
        self.db.commit()
        self.db.refresh(doc)
        self._sync_backlinks(user_id, doc)
        if content_changed:
            event_bus.publish(EVENT_DOCUMENT_SAVED, document_id=doc.id)
        return self._doc_out(doc)

    def delete_document(self, user_id: str, doc_id: str) -> None:
        doc = self._owned_doc(doc_id, user_id)
        # 清理关联反向链接（作为来源或目标）
        for bl in self.link_repo.list_sources(doc.id):
            self.db.delete(bl)
        for bl in self.link_repo.list_targets(doc.id):
            self.db.delete(bl)
        self.db.delete(doc)
        self.db.commit()

    # ---------- 版本历史 ----------
    def versions(self, user_id: str, doc_id: str) -> list[DocumentVersionOut]:
        self._owned_doc(doc_id, user_id)
        return [
            DocumentVersionOut(
                id=v.id, document_id=v.document_id, content=v.content, version=v.version,
                word_count=v.word_count, created_at=v.created_at,
            )
            for v in self.ver_repo.list_by_document(doc_id)
        ]

    def version_detail(self, user_id: str, doc_id: str, ver: int) -> DocumentVersionOut:
        self._owned_doc(doc_id, user_id)
        v = self.ver_repo.get_by_version(doc_id, ver)
        if v is None:
            raise NotFoundException("版本不存在")
        return DocumentVersionOut(
            id=v.id, document_id=v.document_id, content=v.content, version=v.version,
            word_count=v.word_count, created_at=v.created_at,
        )

    def restore_version(self, user_id: str, doc_id: str, ver: int) -> DocumentOut:
        doc = self._owned_doc(doc_id, user_id)
        v = self.ver_repo.get_by_version(doc_id, ver)
        if v is None:
            raise NotFoundException("版本不存在")
        # 当前内容入快照，恢复目标版本
        self.ver_repo.create(
            document_id=doc.id, content=doc.content or "", version=doc.version,
            word_count=count_words(doc.content),
        )
        doc.content = v.content
        doc.word_count = v.word_count
        doc.version += 1
        self.ver_repo.delete_oldest(doc.id, keep=MAX_VERSIONS)
        self.db.commit()
        self.db.refresh(doc)
        return self._doc_out(doc)

    # ---------- 反向链接 / 标签 / 搜索 ----------
    def backlinks(self, user_id: str, doc_id: str) -> list[BacklinkSourceOut]:
        self._owned_doc(doc_id, user_id)
        result: list[BacklinkSourceOut] = []
        for bl in self.link_repo.list_targets(doc_id):
            src = self.doc_repo.get(bl.source_doc_id)
            result.append(BacklinkSourceOut(
                source_doc_id=bl.source_doc_id,
                source_title=src.title if src else bl.target_title or "",
            ))
        return result

    def tags(self, user_id: str) -> list[str]:
        return self.doc_repo.all_tags(user_id)

    def search(self, user_id: str, q: str, type_: str | None = None) -> SearchResultOut:
        result = SearchResultOut()
        keyword = q.strip()
        if not keyword:
            return result
        if type_ in (None, "task"):
            tasks = self._search_tasks(user_id, keyword)
            result.tasks = tasks
        if type_ in (None, "document"):
            result.documents = self._search_documents(user_id, keyword)
        if type_ in (None, "conversation"):
            result.conversations = self._search_conversations(user_id, keyword)
        return result

    # ---------- 内部工具 ----------
    def _search_tasks(self, user_id: str, keyword: str) -> list[SearchTaskHit]:
        from sqlalchemy import select
        from app.models.task import Task
        like = f"%{keyword}%"
        rows = self.db.scalars(
            select(Task).where(Task.user_id == user_id, Task.title.like(like)).limit(10)
        )
        return [SearchTaskHit(id=t.id, title=t.title, type="task", status=t.status) for t in rows]

    def _search_documents(self, user_id: str, keyword: str) -> list[SearchDocumentHit]:
        docs = self.doc_repo.search_documents(user_id, keyword, limit=10)
        return [
            SearchDocumentHit(
                id=d.id, title=d.title, snippet=self._snippet(d.content or "", keyword),
                updated_at=d.updated_at, type="document",
            )
            for d in docs
        ]

    def _search_conversations(self, user_id: str, keyword: str) -> list[SearchConversationHit]:
        from sqlalchemy import select
        from app.models.conversation import Conversation
        like = f"%{keyword}%"
        rows = self.db.scalars(
            select(Conversation).where(Conversation.user_id == user_id, Conversation.title.like(like)).limit(10)
        )
        return [
            SearchConversationHit(id=c.id, title=c.title or "未命名对话", updated_at=c.updated_at, type="conversation")
            for c in rows
        ]

    @staticmethod
    def _snippet(content: str, keyword: str, radius: int = 20) -> str:
        idx = content.find(keyword)
        if idx < 0:
            return content[: radius * 2]
        start = max(0, idx - radius)
        end = min(len(content), idx + len(keyword) + radius)
        prefix = "…" if start > 0 else ""
        suffix = "…" if end < len(content) else ""
        return prefix + content[start:end] + suffix

    def _sync_backlinks(self, user_id: str, doc: Document) -> None:
        """扫描文档内容中的 [[标题]] 链接，重建该文档的出链记录。

        单事务批量重建：此前每个链接一次 SELECT + 一次 INSERT（各自独立 commit），
        保存含 5 个链接的文档约产生 7 个独立事务（自动保存场景下放大明显）。
        """
        from sqlalchemy import delete, select as sa_select

        self.db.execute(delete(Backlink).where(Backlink.source_doc_id == doc.id))
        if doc.content:
            titles = list({m.group(1).strip() for m in LINK_PATTERN.finditer(doc.content)})
            if titles:
                # 一次 IN 查询解析所有目标文档
                targets = {
                    t.title: t.id
                    for t in self.db.scalars(
                        sa_select(Document).where(
                            Document.user_id == user_id,
                            Document.title.in_(titles),
                        )
                    )
                }
                for title in titles:
                    self.db.add(Backlink(
                        source_doc_id=doc.id,
                        target_doc_id=targets.get(title),
                        target_title=title,
                    ))
        self.db.commit()

    def _owned_doc(self, doc_id: str, user_id: str) -> Document:
        doc = self.doc_repo.get(doc_id)
        if doc is None or doc.user_id != user_id:
            raise NotFoundException("文档不存在")
        return doc

    def _owned_folder(self, folder_id: str, user_id: str) -> Folder:
        folder = self.folder_repo.get(folder_id)
        if folder is None or folder.user_id != user_id:
            raise NotFoundException("文件夹不存在")
        return folder

    def _folder_out(self, f: Folder) -> FolderOut:
        return FolderOut(
            id=f.id, name=f.name, parent_id=f.parent_id, sort_order=f.sort_order,
            is_inbox=f.is_inbox, created_at=f.created_at, updated_at=f.updated_at,
            children=[],
        )

    def _doc_out(self, doc: Document, folder_map: dict[str, str] | None = None) -> DocumentOut:
        folder_name = "收集箱"
        if doc.folder_id:
            if folder_map is not None:
                folder_name = folder_map.get(doc.folder_id, "收集箱")
            else:
                folder = self.folder_repo.get(doc.folder_id)
                if folder:
                    folder_name = folder.name
        return DocumentOut(
            id=doc.id,
            title=doc.title,
            content=doc.content,
            folder_id=doc.folder_id,
            folder_name=folder_name,
            tags=list(doc.tags or []),
            summary=doc.summary,
            ai_suggested_tags=list(doc.ai_suggested_tags or []),
            version=doc.version,
            word_count=doc.word_count,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
        )
