# ============================================================
# 文档 / 标签 / 搜索 路由（PRD §13.4）
# ============================================================
from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.response import success
from app.schemas.document import CreateDocumentRequest, UpdateDocumentRequest
from app.services.document_service import DocumentService


if TYPE_CHECKING:
    from app.models.user import User

router = APIRouter(prefix="/documents", tags=["documents"])
tags_router = APIRouter(prefix="/tags", tags=["knowledge"])
search_router = APIRouter(prefix="/search", tags=["knowledge"])


@router.get("")
def list_documents(
    folder_id: str | None = None,
    tag: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
    sort: str = "-updated_at",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    data = DocumentService(db).list_documents(
        user.id, folder_id=folder_id, tag=tag, search=search,
        page=page, page_size=page_size, sort=sort,
    )
    return success(data)


@router.post("")
def create_document(data: CreateDocumentRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(DocumentService(db).create_document(user.id, data))


@router.get("/{doc_id}")
def document_detail(doc_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(DocumentService(db).get_document(user.id, doc_id))


@router.patch("/{doc_id}")
def update_document(
    doc_id: str,
    data: UpdateDocumentRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(DocumentService(db).update_document(user.id, doc_id, data))


@router.delete("/{doc_id}")
def delete_document(doc_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    DocumentService(db).delete_document(user.id, doc_id)
    return success()


@router.get("/{doc_id}/versions")
def versions(doc_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(DocumentService(db).versions(user.id, doc_id))


@router.get("/{doc_id}/versions/{ver}")
def version_detail(doc_id: str, ver: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(DocumentService(db).version_detail(user.id, doc_id, ver))


@router.post("/{doc_id}/versions/{ver}/restore")
def restore_version(doc_id: str, ver: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(DocumentService(db).restore_version(user.id, doc_id, ver))


@router.get("/{doc_id}/backlinks")
def backlinks(doc_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(DocumentService(db).backlinks(user.id, doc_id))


@tags_router.get("")
def all_tags(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(DocumentService(db).tags(user.id))


@search_router.get("")
def search(q: str = "", type: str | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(DocumentService(db).search(user.id, q, type))
