from __future__ import annotations

from sqlalchemy import Text, cast, delete, func, or_, select

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
            # cast 到 Text：StringListType 的 process_bind_param 会把 LIKE 模式
            # 字符串拆成字符列表再 json.dumps，导致模式被污染。cast 后走原生 Text 比较。
            q = q.where(cast(Document.tags, Text).like(f'%"{tag}"%'))
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
            # cast 到 Text：StringListType 的 process_bind_param 会把 LIKE 模式
            # 字符串拆成字符列表再 json.dumps，导致模式被污染。cast 后走原生 Text 比较。
            q = q.where(cast(Document.tags, Text).like(f'%"{tag}"%'))
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
        # 只取 tags 列且不分页：之前复用 list_documents（默认 limit=100 + 加载全部列），
        # 文档超过 100 篇后旧文档的标签会从标签栏"消失"
        rows = self.db.scalars(select(Document.tags).where(Document.user_id == user_id))
        seen: dict[str, None] = {}
        for tags in rows:
            for t in (tags or []):
                seen[t] = None
        return list(seen.keys())

    def find_by_title(self, user_id: str, title: str) -> Document | None:
        return self.db.scalar(
            select(Document).where(Document.user_id == user_id, Document.title == title)
        )

    # ---------- D-06 收口新增：供 service 用的语义化查询 ----------

    def count_by_user(self, user_id: str) -> int:
        return self.count(user_id=user_id)

    def list_all_by_user(self, user_id: str) -> list[Document]:
        """关系图谱用：某用户全部文档节点。"""
        return list(self.db.scalars(select(Document).where(Document.user_id == user_id)))

    def title_id_map(self, user_id: str, titles: list[str]) -> dict[str, str]:
        """[[标题]] 双链解析：标题 → 文档 id（一次 IN 查询）。"""
        if not titles:
            return {}
        rows = self.db.scalars(
            select(Document).where(
                Document.user_id == user_id,
                Document.title.in_(titles),
            )
        )
        return {d.title: d.id for d in rows}

    def list_project_cards(self, project_id: str, limit: int = 50) -> list:
        """项目详情用：只取卡片字段（不拉 content 大字段），按更新时间倒序。"""
        q = (
            select(Document.id, Document.title, Document.updated_at,
                   Document.tags, Document.word_count)
            .where(Document.project_id == project_id)
            .order_by(Document.updated_at.desc())
            .limit(limit)
        )
        return list(self.db.execute(q).all())

    def list_project_documents(self, project_id: str, limit: int = 20) -> list[Document]:
        """项目时间线用：最近创建的文档。"""
        q = (
            select(Document)
            .where(Document.project_id == project_id)
            .order_by(Document.created_at.desc())
            .limit(limit)
        )
        return list(self.db.scalars(q))

    def list_all_by_project(self, project_id: str) -> list[Document]:
        """项目导出用：全量文档（不排序、不分页）。"""
        return list(
            self.db.scalars(select(Document).where(Document.project_id == project_id))
        )

    def list_created_between(self, user_id: str, start, end) -> list[Document]:
        """每日复盘自动填充：某时间段内创建的文档。"""
        q = select(Document).where(
            Document.user_id == user_id,
            Document.created_at >= start,
            Document.created_at < end,
        )
        return list(self.db.scalars(q))

    def identity_counts(self, user_id: str) -> dict[str, int]:
        """按身份分组计数（跳过未归类）。"""
        q = (
            select(Document.identity_id, func.count())
            .where(
                Document.user_id == user_id,
                Document.identity_id.is_not(None),
            )
            .group_by(Document.identity_id)
        )
        return {rid: int(count) for rid, count in self.db.execute(q).all()}

    def count_identity_unassigned(self, user_id: str) -> int:
        """未归类文档数。"""
        q = select(func.count()).select_from(Document).where(
            Document.user_id == user_id,
            Document.identity_id.is_(None),
        )
        return int(self.db.scalar(q) or 0)

    def clear_identity(self, identity_id: str) -> None:
        """把某身份的引用清回「未归类」（身份软删除时用；只 flush）。"""
        self.nullify("identity_id", identity_id=identity_id)

    def clear_project(self, project_id: str) -> None:
        """解除文档与项目的关联（项目删除时用；只 flush）。"""
        self.nullify("project_id", project_id=project_id)


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
        """裁剪超出的旧版本（只 flush；事务由调用方闭合）。"""
        versions = self.list_by_document(document_id)
        for v in versions[keep:]:
            self.db.delete(v)
        self.db.flush()


class BacklinkRepository(BaseRepository[Backlink]):
    model = Backlink

    def list_targets(self, document_id: str) -> list[Backlink]:
        q = select(Backlink).where(Backlink.target_doc_id == document_id)
        return list(self.db.scalars(q))

    def list_sources(self, source_doc_id: str) -> list[Backlink]:
        q = select(Backlink).where(Backlink.source_doc_id == source_doc_id)
        return list(self.db.scalars(q))

    def delete_by_source(self, source_doc_id: str) -> None:
        """删除某文档的出链（只 flush；事务由调用方闭合）。"""
        for bl in self.list_sources(source_doc_id):
            self.db.delete(bl)
        self.db.flush()

    def list_by_sources(self, source_ids: list[str]) -> list[Backlink]:
        """关系图谱用：批量取出这些源文档的出链（一次 IN 查询）。"""
        if not source_ids:
            return []
        q = select(Backlink).where(Backlink.source_doc_id.in_(source_ids))
        return list(self.db.scalars(q))

    def replace_source_links(self, source_doc_id: str, links: list[dict]) -> None:
        """重建某文档的全部出链（先删后插，同一事务内一次 flush）。

        参数 links 是 Backlink 字段字典（source_doc_id / target_doc_id /
        target_title）。语义等价于「保存文档」用例里的第二步，提交由
        调用方在用例末尾完成（见 D-04 事务约定）。
        """
        self.db.execute(delete(Backlink).where(Backlink.source_doc_id == source_doc_id))
        if links:
            self.db.add_all([Backlink(**link) for link in links])
        self.db.flush()
