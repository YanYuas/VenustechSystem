# ============================================================
# 文件夹 schema（对齐前端 types/document.ts Folder）
# ============================================================
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class FolderOut(BaseModel):
    id: str
    name: str
    parent_id: str | None = None
    sort_order: int = 0
    is_inbox: bool = False
    created_at: datetime
    updated_at: datetime
    children: list["FolderOut"] = []


class CreateFolderRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    parent_id: str | None = None


class RenameFolderRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
