# ============================================================
# 文件夹路由（PRD §13.4 知识资源）
# ============================================================
from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.response import success
from app.schemas.folder import CreateFolderRequest, RenameFolderRequest
from app.services.document_service import DocumentService


if TYPE_CHECKING:
    from app.models.user import User

router = APIRouter(prefix="/folders", tags=["folders"])


@router.get("")
def folders_tree(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(DocumentService(db).folders_tree(user.id))


@router.post("")
def create_folder(data: CreateFolderRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(DocumentService(db).create_folder(user.id, data.name, data.parent_id))


@router.patch("/{folder_id}")
def rename_folder(
    folder_id: str,
    data: RenameFolderRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(DocumentService(db).rename_folder(user.id, folder_id, data.name))


@router.delete("/{folder_id}")
def delete_folder(folder_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    DocumentService(db).delete_folder(user.id, folder_id)
    return success()
