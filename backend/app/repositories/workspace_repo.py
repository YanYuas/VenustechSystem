# ============================================================
# 工作区 Repository（三期 C · D-06 收口）
#
# 两张表：
#   workspace_roots —— 已登记的真实文件夹根
#   workspace_files —— 只存路径元数据的索引条目
#
# 事务语义：只 flush，不 commit（扫描线程自己闭合事务）。
# ============================================================
from __future__ import annotations

from sqlalchemy import delete, func, select

from app.models.workspace import WorkspaceFile, WorkspaceRoot
from app.repositories.base import BaseRepository


class WorkspaceRootRepository(BaseRepository[WorkspaceRoot]):
    """工作区根。"""

    model = WorkspaceRoot

    def list_by_user(self, user_id: str) -> list[WorkspaceRoot]:
        """按登记顺序（created_at 升序）列出全部根。"""
        q = (
            select(WorkspaceRoot)
            .where(WorkspaceRoot.user_id == user_id)
            .order_by(WorkspaceRoot.created_at)
        )
        return list(self.db.scalars(q))

    def get_by_path(self, user_id: str, path: str) -> WorkspaceRoot | None:
        """按已 resolve 的绝对路径查重（同用户同路径唯一）。"""
        return self.db.scalar(
            select(WorkspaceRoot).where(
                WorkspaceRoot.user_id == user_id,
                WorkspaceRoot.path == path,
            )
        )

    def list_enabled(self, user_id: str) -> list[WorkspaceRoot]:
        """安全关卡用：只返回已启用的根。"""
        q = (
            select(WorkspaceRoot)
            .where(
                WorkspaceRoot.user_id == user_id,
                WorkspaceRoot.enabled.is_(True),
            )
        )
        return list(self.db.scalars(q))

    def clear_identity(self, identity_id: str) -> None:
        """把某身份的引用清回「未归类」（身份软删除时用；只 flush）。"""
        self.nullify("identity_id", identity_id=identity_id)


class WorkspaceFileRepository(BaseRepository[WorkspaceFile]):
    """工作区文件索引。"""

    model = WorkspaceFile

    def delete_by_root(self, root_id: str) -> None:
        """清空某根的索引（全量替换 / 删除根时用；只 flush）。"""
        self.db.execute(delete(WorkspaceFile).where(WorkspaceFile.root_id == root_id))
        self.db.flush()

    def replace_root_entries(self, root_id: str, entries: list[dict]) -> None:
        """全量替换某根的索引（删旧 + 批量插新；一次 flush）。

        扫描线程用：个人规模千级，diff 不值得；这里刻意**不逐行 refresh**
        （create_many 会 refresh 每一行，几千条时是几千次多余 SELECT），
        保持与原实现相同的写入量级。
        """
        self.db.execute(delete(WorkspaceFile).where(WorkspaceFile.root_id == root_id))
        if entries:
            self.db.add_all([WorkspaceFile(**entry) for entry in entries])
        self.db.flush()

    def _filtered(self, root_id: str, search: str | None, ext: str | None):
        q = select(WorkspaceFile).where(WorkspaceFile.root_id == root_id)
        if search:
            q = q.where(WorkspaceFile.name.contains(search))
        if ext:
            q = q.where(WorkspaceFile.ext == ext.lower())
        return q

    def list_paginated(
        self,
        root_id: str,
        search: str | None = None,
        ext: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[WorkspaceFile], int]:
        """目录/搜索分页：目录优先、再按名称；计数下推 SQL。"""
        counted = self._filtered(root_id, search, ext)
        total = int(
            self.db.scalar(
                select(func.count()).select_from(counted.subquery())
            )
            or 0
        )
        q = self._filtered(root_id, search, ext)
        q = (
            q.order_by(WorkspaceFile.is_dir.desc(), WorkspaceFile.name)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(self.db.scalars(q)), total
