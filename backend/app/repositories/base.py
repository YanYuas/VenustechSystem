# ============================================================
# 通用 CRUD 基类（对齐架构 v2.0 §5.3 Repository 模式）
# ============================================================
from __future__ import annotations

from typing import Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundException
from app.models.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    model: type[ModelT]

    def __init__(self, db: Session):
        self.db = db

    def get(self, id: str) -> ModelT | None:
        return self.db.get(self.model, id)

    def get_or_404(self, id: str) -> ModelT:
        obj = self.get(id)
        if obj is None:
            raise NotFoundException(f"{self.model.__name__} 不存在: {id}")
        return obj

    def list(self, skip: int = 0, limit: int = 100, **filters) -> list[ModelT]:
        q = select(self.model)
        for key, value in filters.items():
            if value is not None:
                q = q.where(getattr(self.model, key) == value)
        q = q.offset(skip).limit(limit)
        return list(self.db.scalars(q))

    def count(self, **filters) -> int:
        q = select(func.count()).select_from(self.model)
        for key, value in filters.items():
            if value is not None:
                q = q.where(getattr(self.model, key) == value)
        return int(self.db.scalar(q))

    def create(self, **kwargs) -> ModelT:
        obj = self.model(**kwargs)
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def update(self, obj: ModelT, **kwargs) -> ModelT:
        for key, value in kwargs.items():
            setattr(obj, key, value)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def delete(self, obj: ModelT) -> None:
        self.db.delete(obj)
        self.db.commit()
