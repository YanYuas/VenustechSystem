# ============================================================
# 通用 CRUD 基类（对齐架构 v2.0 §5.3 Repository 模式）
# ============================================================
from __future__ import annotations

from typing import Generic, TypeVar

from sqlalchemy import func, select, update
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

    # ---------- 事务边界（架构 v2.0 §5.3 / 审计 D-04） ----------
    # 本类**只 flush，不 commit**。写入的原子性由调用方（service 用例边界 /
    # get_db 请求事务）负责：
    #   · flush 把 SQL 发到数据库、拿到自增主键与默认值，但事务仍开放；
    #   · 同一用例内后续步骤失败时，调用方一次 rollback 即可回滚全部写入；
    #   · 需要提交时调用方显式 `repo.commit()`（或 `db.commit()`）。
    # 历史教训：此前每个方法内部 commit，导致 service 的多步用例（删除文件夹、
    # 保存文档 + 重建双链、批量生成任务）每一步都各自落库，中途失败留下中间态。

    def create(self, **kwargs) -> ModelT:
        obj = self.model(**kwargs)
        self.db.add(obj)
        self.db.flush()
        self.db.refresh(obj)
        return obj

    def create_many(self, items: list[dict]) -> list[ModelT]:
        """批量插入，**同一事务内 flush 一次**。

        为什么需要它（而不是循环调用 create）：
          即使 create() 已不再 commit，批量场景仍需要它：
            1. 一次 flush 只发一批 INSERT，40 条任务的开销远小于逐条 flush；
            2. 语义清晰 —— 这一批要么全在事务里、要么全回滚，不依赖调用方
               再逐条补提交；
            3. 历史上它就是为了修「中途失败留下半套数据」而引入的，
               现在把 commit 上移后，原子性由调用方的事务统一保证。
        """
        if not items:
            return []
        objs = [self.model(**kwargs) for kwargs in items]
        self.db.add_all(objs)
        self.db.flush()
        for obj in objs:
            self.db.refresh(obj)
        return objs

    def update(self, obj: ModelT, **kwargs) -> ModelT:
        for key, value in kwargs.items():
            setattr(obj, key, value)
        self.db.flush()
        self.db.refresh(obj)
        return obj

    def commit(self) -> None:
        """显式提交事务（供调用方在用例边界使用，本类内部不调用）。"""
        self.db.commit()

    def nullify(self, column: str, **filters) -> None:
        """把满足 filters 的行的 `column` 置 NULL（跨表解除引用用；只 flush）。

        典型场景：删除项目时把 task/document/conversation/review 的
        project_id 清空；软删除身份时把各表 identity_id 清回「未归类」。
        放在基类是因为它是纯 DAO 动作（不碰业务语义），各域 repo 只需
        声明自己哪张表要清哪个列，避免在 service 里写 UPDATE 语句。
        """
        model = self.model
        conditions = [getattr(model, name) == value for name, value in filters.items()]
        self.db.execute(update(model).where(*conditions).values({column: None}))
        self.db.flush()

    def paginate(self, page: int = 1, page_size: int = 20, **filters) -> tuple[list[ModelT], int]:
        """分页查询，返回 (数据列表, 总数)"""
        skip = (page - 1) * page_size
        items = self.list(skip=skip, limit=page_size, **filters)
        total = self.count(**filters)
        return items, total

    def delete(self, obj: ModelT) -> None:
        self.db.delete(obj)
        self.db.flush()
