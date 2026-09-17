# ============================================================
# 通用 schema：分页（对齐前端 types/api.ts PaginatedData）
# ============================================================
from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginatedData(BaseModel, Generic[T]):
    list: list[T]
    total: int
    page: int
    page_size: int
