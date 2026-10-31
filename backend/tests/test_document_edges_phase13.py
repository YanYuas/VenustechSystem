# ============================================================
# Phase13 · A 类覆盖率补缺：Document 仓库/服务边界
#
# 覆盖此前缺失的真实路径：
#   · DocumentRepository.count_by_user / list_all_by_user（关系图用）
#   · DocumentRepository.delete_by_source（删文档时清出链）
#   · DocumentRepository.list_by_sources([]) 空入参短路
#   · DocumentService.get_document（单文档读取）
#   · DocumentService.delete_folder 失败回滚（repo 抛错 → rollback + 原样抛）
#   · DocumentService.delete_document 清入链/出链
#   · _folder_name(None) 的「收集箱」兜底
# ============================================================
from __future__ import annotations

import pytest

from app.models.document import Backlink
from app.models.folder import Folder
from app.repositories.document_repo import BacklinkRepository, DocumentRepository
from app.schemas.document import CreateDocumentRequest
from app.services.document_service import DocumentService
from tests.factories import make_document


class TestDocumentRepositoryEdges:
    def test_count_list_all_and_empty_sources(self, db_session, test_user):
        make_document(db_session, test_user.id, title="一")
        make_document(db_session, test_user.id, title="二")
        db_session.commit()

        repo = DocumentRepository(db_session)
        assert repo.count_by_user(test_user.id) == 2
        assert len(repo.list_all_by_user(test_user.id)) == 2
        assert BacklinkRepository(db_session).list_by_sources([]) == []   # 空入参短路

    def test_delete_by_source_removes_outgoing_links(self, db_session, test_user):
        source = make_document(db_session, test_user.id, title="源")
        target = make_document(db_session, test_user.id, title="目标")
        db_session.flush()
        db_session.add(Backlink(
            source_doc_id=source.id, target_doc_id=target.id, target_title="目标",
        ))
        db_session.commit()

        repo = BacklinkRepository(db_session)
        assert len(repo.list_sources(source.id)) == 1
        repo.delete_by_source(source.id)
        db_session.commit()
        assert repo.list_sources(source.id) == []
        # 反向的入链查询仍可用（说明只删了出链）
        assert [b.target_title for b in repo.list_targets(target.id)] == []


class TestDocumentServiceEdges:
    def test_get_document_returns_inbox_folder_name(self, db_session, test_user):
        svc = DocumentService(db_session)
        created = svc.create_document(test_user.id, CreateDocumentRequest(title="无显式文件夹"))

        out = svc.get_document(test_user.id, created.id)

        assert out.id == created.id
        assert out.folder_name == "收集箱"

    def test_delete_folder_failure_rolls_back_and_reraises(
        self, db_session, test_user, monkeypatch
    ):
        svc = DocumentService(db_session)
        folder = svc.create_folder(test_user.id, "待删文件夹")
        db_session.commit()          # 让文件夹先落库，才能验证回滚后仍存在

        def _boom(*_args, **_kwargs):
            raise RuntimeError("folder repo exploded")

        monkeypatch.setattr(svc.doc_repo, "list_documents", _boom)
        with pytest.raises(RuntimeError, match="folder repo exploded"):
            svc.delete_folder(test_user.id, folder.id)

        # rollback 生效：文件夹仍在（没有被半删）
        assert db_session.get(Folder, folder.id) is not None

    def test_delete_document_removes_back_links(self, db_session, test_user):
        source = make_document(db_session, test_user.id, title="源文档")
        target = make_document(db_session, test_user.id, title="目标文档")
        db_session.flush()
        db_session.add(Backlink(
            source_doc_id=source.id, target_doc_id=target.id, target_title="目标文档",
        ))
        db_session.commit()

        DocumentService(db_session).delete_document(test_user.id, source.id)

        left = db_session.query(Backlink).filter(
            Backlink.source_doc_id == source.id).all()
        assert left == []

    def test_folder_name_falls_back_to_inbox_for_none(self, db_session, test_user):
        svc = DocumentService(db_session)
        assert svc._folder_name(None) == "收集箱"
