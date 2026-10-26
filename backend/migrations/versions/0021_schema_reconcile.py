"""0021_schema_reconcile —— 以 ORM metadata 为准，对历史库做一次幂等对账

背景（审计 D-05）
  0001 曾经用「按当前 models 一次性建表」实现，于是**升级过的老库拿不到后来
  加进 models/ 的索引**：实测 0020 版本的 data/app.db 缺 11 个 ORM 声明的索引，
  并且多出 3 个 ORM 未声明的索引（其中 idx_tasks_project_id 与 ORM 的
  ix_tasks_project_id 落在同一列上，是真正的重复索引）。
  0001 已改为冻结的显式 DDL 基线；本迁移负责把**已存在的库**拉回到与 ORM
  metadata 一致的状态。

本迁移做什么（全部幂等，可重复执行 / 可在部分升级的库上执行）
  1. 缺表 —— 按 `Base.metadata.sorted_tables` 依赖序用 `Table.create()` 建出
     （含该表的索引/唯一约束/外键）；
  2. 缺列 —— 按 ORM 列定义 `ADD COLUMN`；NOT NULL 且无 server_default 的列
     用一个**类型兜底默认值**加列（SQLite 不允许给非空表加无默认值的 NOT NULL
     列），兜底值只影响历史行，不回填业务语义；
  3. 缺索引 —— 按 ORM Index 定义补建（含 partial index 的 `sqlite_where`、
     unique 标记）；
  4. 重复索引 —— DB 侧「与某个 ORM 索引同表同列但名字不同」的索引一律删除
     （本次即 `idx_tasks_project_id`；`ix_tasks_project_id` 由第 3 步补建）；
  5. 其余 ORM 未声明的历史索引**保留**：`ix_notifications_user_read`（0005 手工
     建）、`ix_workspace_files_name`（0016 手工建）。它们不与任何 ORM 索引重复，
     删掉只会白白丢掉查询性能；对账测试把它们列为白名单。

为什么用 `Table.create()` 而不是全量手写 DDL
  0021 是「对账」而不是「历史快照」：它要跟随 ORM 演进，保证任何版本的老库
  都能收敛到当前 metadata。0001 则相反，是冻结快照，两者职责不同。

不可逆说明
  downgrade 不做破坏性回退（删表/删列会丢数据）：补出的对象保留，只把被删的
  重复索引 `idx_tasks_project_id` 恢复回去，使 0020 ⇄ 0021 的版本号往返自洽。
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from app import models  # noqa: F401  —— 确保全部模型注册到 Base.metadata
from app.database import Base
from app.migration_helpers import (
    column_exists,
    index_exists,
    table_exists,
)

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None

# 审计 D-05 明确列出的 11 个「ORM 有、升级库缺」索引（本迁移由 metadata 驱动
# 自动补齐；这里保留常量便于审计与测试逐项核对，不参与逻辑）。
AUDITED_MISSING_INDEXES = (
    "idx_domains_user",
    "idx_flashcards_user_category",
    "idx_habits_user_status",
    "idx_project_memories_project",
    "idx_project_memories_user",
    "idx_prompts_user_category",
    "idx_skills_user_category",
    "idx_sop_versions_sop",
    "idx_sops_user_category",
    "ix_study_time_logs_logged_date",
    "ix_tasks_project_id",
)

# 0016 / 0005 手工创建、ORM 未声明的历史索引：非重复，保留（仅作文档）。
KEPT_LEGACY_EXTRA_INDEXES = (
    "ix_notifications_user_read",
    "ix_workspace_files_name",
)


def _underlying_type(type_) -> sa.types.TypeEngine:
    """剥掉 TypeDecorator（JSONType / StringListType）拿到真实 SQL 类型。"""
    from sqlalchemy.types import TypeDecorator

    seen = 0
    while isinstance(type_, TypeDecorator) and seen < 5:
        impl = type_.impl
        type_ = impl() if isinstance(impl, type) else impl
        seen += 1
    return type_


def _fallback_server_default(column: sa.Column) -> sa.TextClause:
    """给「NOT NULL 且无默认值」的补列场景选一个合法常量默认值。

    SQLite 的 ADD COLUMN 对 NOT NULL 列必须带默认值；这里只保证历史行可读，
    不承担业务语义（真实值应由应用在下次写入时覆盖）。
    """
    t = _underlying_type(column.type)
    if isinstance(t, sa.Boolean):
        return sa.text("0")
    if isinstance(t, (sa.Integer, sa.Float, sa.Numeric)):
        return sa.text("0")
    if isinstance(t, sa.DateTime):
        return sa.text("'1970-01-01 00:00:00'")
    if isinstance(t, sa.Date):
        return sa.text("'1970-01-01'")
    if isinstance(t, sa.JSON):
        return sa.text("'{}'")
    return sa.text("''")


def _add_missing_column(conn, table: sa.Table, column: sa.Column) -> None:
    """按 ORM 定义补一列（PK 列无法用 ALTER 追加，跳过并告警）。"""
    if column.primary_key:
        print(f"0021_schema_reconcile: 跳过主键列 {table.name}.{column.name}（SQLite 无法 ADD COLUMN 主键）")
        return

    if column.nullable:
        op.add_column(table.name, sa.Column(column.name, column.type, nullable=True))
        print(f"0021_schema_reconcile: +列 {table.name}.{column.name}（nullable）")
        return

    default = column.server_default.arg if column.server_default is not None else None
    if default is None:
        default = _fallback_server_default(column)
    op.add_column(
        table.name,
        sa.Column(column.name, column.type, nullable=False, server_default=default),
    )
    print(f"0021_schema_reconcile: +列 {table.name}.{column.name}（NOT NULL，兜底默认 {default}）")


def _index_sqlite_where(index: sa.Index):
    """ORM Index 上的 SQLite partial index 条件（无则 None）。"""
    return index.dialect_options["sqlite"].get("where")


def _create_orm_index(table: sa.Table, index: sa.Index) -> None:
    kwargs = {"unique": bool(index.unique)}
    where = _index_sqlite_where(index)
    if where is not None:
        kwargs["sqlite_where"] = where
    op.create_index(index.name, table.name, [c.name for c in index.columns], **kwargs)
    print(f"0021_schema_reconcile: +索引 {index.name} on {table.name}")


def _db_index_names(conn) -> set[str]:
    return {
        row[0]
        for row in conn.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    }


def upgrade() -> None:
    conn = op.get_bind()
    metadata = Base.metadata

    # ---------- 1. 补缺表（依赖序；Table.create 会连带建该表的索引/约束）----------
    for table in metadata.sorted_tables:
        if not table_exists(conn, table.name):
            table.create(bind=conn)
            print(f"0021_schema_reconcile: +表 {table.name}")

    # ---------- 2. 补缺列 ----------
    for table in metadata.sorted_tables:
        if not table_exists(conn, table.name):
            continue
        for column in table.columns:
            if not column_exists(conn, table.name, column.name):
                _add_missing_column(conn, table, column)

    # ---------- 3. 补缺索引（以 ORM Index 定义为准）----------
    existing = _db_index_names(conn)
    for table in metadata.sorted_tables:
        if not table_exists(conn, table.name):
            continue
        for index in sorted(table.indexes, key=lambda ix: ix.name):
            if index.name not in existing:
                _create_orm_index(table, index)
                existing.add(index.name)

    # ---------- 4. 删除 DB 侧「同表同列不同名」的重复索引 ----------
    inspector = sa.inspect(conn)
    orm_index_names = {ix.name for table in metadata.tables.values() for ix in table.indexes}
    for table in metadata.sorted_tables:
        if not table_exists(conn, table.name):
            continue
        orm_by_columns = {
            tuple(c.name for c in ix.columns): ix.name for ix in table.indexes
        }
        for db_index in inspector.get_indexes(table.name):
            name = db_index["name"]
            if not name or name.startswith("sqlite_") or name in orm_index_names:
                continue
            columns = tuple(db_index["column_names"])
            if columns in orm_by_columns:
                op.drop_index(name, table_name=table.name)
                print(
                    f"0021_schema_reconcile: -重复索引 {name} on {table.name}"
                    f"（与 ORM {orm_by_columns[columns]} 同列）"
                )


def downgrade() -> None:
    """不做破坏性回退（详见模块 docstring）。

    仅恢复 0021 删除的历史重复索引，保证 0020 ⇄ 0021 版本号往返时 schema 语义
    可回到「旧库」形态；补出的表/列/索引保留（删列删表会丢用户数据）。
    """
    conn = op.get_bind()
    if table_exists(conn, "tasks") and not index_exists(conn, "idx_tasks_project_id"):
        op.create_index("idx_tasks_project_id", "tasks", ["project_id"])
