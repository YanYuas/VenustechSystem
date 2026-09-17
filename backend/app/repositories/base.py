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

    def create_many(self, items: list[dict]) -> list[ModelT]:
        """批量插入，**单次 commit**。

        为什么需要它（而不是循环调用 create）：
          create() 每次都会 commit。批量场景下（例如 S6-1 领域引擎一次生成
          30~40 条学习任务）就会 commit 同样多次，带来两个后果：
            1. **原子性被破坏** —— 中途任一条失败，前面的都已落库，
               留下「计划已建、任务只建了一半」的中间态，且难以回滚；
            2. 性能浪费 —— SQLite 默认每个事务一次 fsync，40 次 commit
               的开销远大于一条 INSERT 语句本身。
        """
        if not items:
            return []
        objs = [self.model(**kwargs) for kwargs in items]
        self.db.add_all(objs)
        self.db.commit()
        for obj in objs:
            self.db.refresh(obj)
        return objs

    def update(self, obj: ModelT, **kwargs) -> ModelT:
        for key, value in kwargs.items():
            setattr(obj, key, value)
        self.db.commit()
        self.db.refresh(obj)
        return obj


    def paginate(self, page: int = 1, page_size: int = 20, **filters) -> tuple[list[ModelT], int]:
        """分页查询，返回 (数据列表, 总数)"""
        skip = (page - 1) * page_size
        items = self.list(skip=skip, limit=page_size, **filters)
        total = self.count(**filters)
        return items, total

    def delete(self, obj: ModelT) -> None:
        self.db.delete(obj)
        self.db.commit()
