# ============================================================
# Alembic 迁移共享守卫（2026-09-15 新增）
#
# 与 app/migrate.py 并列：迁移入口 + 迁移辅助。
#
# 为什么放在 app/ 而不是 migrations/：
#   迁移文件需要 import 它，而 `alembic revision` / `alembic history` 等命令
#   在加载 revision 映射时**不会执行 env.py**，因此 env.py 里的 sys.path 注入
#   对它们无效（实测 `ModuleNotFoundError: No module named 'migration_helpers'`）。
#   而 `app` 包在所有迁移运行场景下都可用（alembic.ini 的 prepend_sys_path=.
#   加上 env.py 的显式注入），且现有迁移本就已 `from app.models.types import ...`。
#
# ---------------- 背景（B-1，P0）----------------
#   0001_initial.py 用的是 `Base.metadata.create_all()`，它建的是**当前代码里注册的
#   全部模型**（实测 39 张表），不是 0001 当时的 schema。因此每个后续迁移要建的表，
#   在全新库上**可能已经被 0001 建好了**。
#   凡是没写幂等守卫的迁移，都会在全新库上抛
#     sqlite3.OperationalError: table xxx already exists
#   而中断迁移链 —— 表现为「新装用户完全起不来」。
#   0009/0010/0011 就曾因此长期不可用（仓库里那个已建表的历史 app.db 把问题掩盖了）。
#
# 铁律：**任何新建的迁移，建表/建索引/加列前一律先守卫。**
#       migrations/script.py.mako 模板已默认引入本模块，新迁移天然带守卫。
#
# 用法：
#   from app.migration_helpers import table_exists, index_exists, column_exists
#
#   def upgrade() -> None:
#       conn = op.get_bind()
#       if not table_exists(conn, "my_table"):
#           op.create_table("my_table", ...)
#           op.create_index("idx_a", "my_table", ["a"])
#       elif not index_exists(conn, "idx_a"):
#           op.create_index("idx_a", "my_table", ["a"])   # 表在但索引缺，补上
# ============================================================
from __future__ import annotations

import sqlalchemy as sa


def table_exists(conn, name: str) -> bool:
    """表是否已存在。"""
    return conn.execute(
        sa.text("SELECT name FROM sqlite_master WHERE type='table' AND name=:n"),
        {"n": name},
    ).fetchone() is not None


def index_exists(conn, name: str) -> bool:
    """显式索引是否已存在（不含 sqlite_autoindex_*）。"""
    return conn.execute(
        sa.text("SELECT name FROM sqlite_master WHERE type='index' AND name=:n"),
        {"n": name},
    ).fetchone() is not None


def column_exists(conn, table: str, column: str) -> bool:
    """列是否已存在（SQLite 无 information_schema，走 PRAGMA table_info）。"""
    rows = conn.execute(sa.text(f"PRAGMA table_info({table})")).fetchall()
    return any(r[1] == column for r in rows)


def create_index_if_missing(conn, name: str, table: str, columns: list[str]) -> None:
    """建索引（缺才建）。"""
    from alembic import op

    if not index_exists(conn, name):
        op.create_index(name, table, columns)


def add_column_if_missing(conn, table: str, column: str, col_type, *,
                          index_name: str | None = None) -> None:
    """加列（缺才加）；给了 index_name 就顺带补索引。"""
    from alembic import op

    if column_exists(conn, table, column):
        return
    op.add_column(table, sa.Column(column, col_type, nullable=True))
    if index_name:
        op.create_index(index_name, table, [column])
