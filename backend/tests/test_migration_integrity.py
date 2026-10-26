"""迁移完整性守护（审计 D-05 回归护栏）

覆盖四件事：
  1. 全新临时库 `upgrade head` 后，真实 schema 与 ORM metadata **三方对账一致**
     （表 / 列 / 类型 / 可空 / 主键 / 唯一约束 / 外键 / 索引），防止未来「加了模型
     忘了写迁移」；
  2. 0001 是冻结的显式 DDL，**不再出现** `create_all` / `drop_all`；
  3. 迁移链线性、单 head（0021），无分叉、无缺口；
  4. 模拟老库 / 部分升级库，验证 0021 能把缺失的表/列/索引补齐，且不丢数据、
     可重复执行。

为什么要单独守这些：
  0001 旧实现按「当前代码的 metadata」建表，导致同一个 revision 在不同 checkout
  上产出不同 schema，用户升级库与新装库 schema 不一致（实测升级库缺 11 个 ORM
  索引）。本测试文件就是防止这个问题复发的护栏。

约定（与 0021 的实现口径一致）：
  · 「库比 ORM 更宽松」只允许出现在**历史 ALTER 补列**造成的 nullable=True
    （见 0014 的说明：SQLite 给已有数据的表加 NOT NULL 列会失败，迁移只能按可空
    加列 + 回填）；「库比 ORM 更严」一律视为错误。
  · 0005 / 0016 手工创建、ORM 未声明的两条索引允许保留（非重复，删了只损失性能）。
  · 列顺序：全新库必须与 metadata 完全一致；老库由于 ALTER 补列只能追加在末尾，
    按「列集合」比较。
"""
from __future__ import annotations

import ast
import os
import sqlite3
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = BACKEND_DIR / "migrations"
VERSIONS_DIR = MIGRATIONS_DIR / "versions"
HEAD_REVISION = "0021"

# ORM 声明数量（冻结基线快照的规模；变化说明有人改了 0001 历史文件）
BASELINE_TABLE_COUNT = 49
BASELINE_INDEX_COUNT = 79

# 审计 D-05 列出的「ORM 有、升级库缺」的 11 个索引
AUDITED_MISSING_INDEXES = {
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
}

# 0005 / 0016 手工创建、ORM 未声明：允许保留（仅作文档白名单）
KEPT_LEGACY_EXTRA_INDEXES = {"ix_notifications_user_read", "ix_workspace_files_name"}

# 0012–0020 才引入的表（用于构造「部分升级」的老库）
POST_0011_TABLES = (
    "growth_events",
    "growth_states",
    "skill_stats",
    "identities",
    "workspace_files",
    "workspace_roots",
    "vault_items",
    "vault_config",
    "audit_logs",
    "settings_history",
)

_USER_INSERT = """
INSERT INTO users
    (id, username, nickname, theme, automation_level, pet_topmost,
     inspiration_probability, ai_enabled, language, created_at, updated_at, deleted_at)
VALUES
    ('migration-probe-user', 'migration_probe', '迁移探针', 'dark', 'balanced', 0,
     30, 0, 'zh-CN', '2026-01-01 00:00:00', '2026-01-01 00:00:00', NULL)
"""


# ============================================================
# 迁移执行 / schema 快照
# ============================================================
def _alembic_config():
    """构造不加载 alembic.ini 的 Config（避免 fileConfig 重配全局日志）。"""
    from alembic.config import Config

    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    return cfg


@pytest.fixture()
def temp_db(tmp_path):
    """独立临时数据目录 + 迁移执行器（绝不触碰 conftest 的测试库）。"""
    from app import config as app_config

    data_dir = tmp_path / "migration_integrity_data"
    data_dir.mkdir(parents=True, exist_ok=True)
    previous = os.environ.get("VENUSTECH_DATA_DIR")

    def _point_settings_at_temp_db() -> None:
        os.environ["VENUSTECH_DATA_DIR"] = str(data_dir)
        app_config.get_settings.cache_clear()

    def migrate(target: str) -> None:
        from alembic import command

        _point_settings_at_temp_db()
        command.upgrade(_alembic_config(), target)

    def stamp(target: str) -> None:
        from alembic import command

        _point_settings_at_temp_db()
        command.stamp(_alembic_config(), target)

    yield data_dir, migrate, stamp

    if previous is None:
        os.environ.pop("VENUSTECH_DATA_DIR", None)
    else:
        os.environ["VENUSTECH_DATA_DIR"] = previous
    app_config.get_settings.cache_clear()


def _db_path(data_dir: Path) -> Path:
    return data_dir / "app.db"


def _db_snapshot(data_dir: Path) -> dict:
    db = _db_path(data_dir)
    con = sqlite3.connect(str(db))
    try:
        tables = sorted(
            r[0]
            for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%' AND name <> 'alembic_version'"
            )
        )
        snap = {
            "tables": set(tables),
            "columns": {},
            "types": {},
            "nullable": {},
            "pk": {},
            "uniques": {},
            "fks": {},
            "indexes": {},
            "row_counts": {},
        }
        for t in tables:
            cols = list(con.execute(f'PRAGMA table_info("{t}")'))
            snap["columns"][t] = [c[1] for c in cols]
            snap["types"][t] = {c[1]: (c[2] or "").upper() for c in cols}
            snap["nullable"][t] = {c[1]: not bool(c[3]) for c in cols}
            snap["pk"][t] = tuple(c[1] for c in sorted(cols, key=lambda c: c[5]) if c[5])
            snap["row_counts"][t] = con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
            uniques, indexes = [], {}
            for name, unique, origin in con.execute(
                'SELECT name, "unique", origin FROM pragma_index_list(?)', (t,)
            ):
                if name.startswith("sqlite_") and origin != "u":
                    continue
                cols_i = tuple(
                    r[2] for r in con.execute(f'PRAGMA index_info("{name}")')
                )
                if origin == "u":
                    uniques.append(cols_i)
                elif origin == "c":
                    indexes[name] = {"columns": cols_i, "unique": bool(unique)}
            snap["uniques"][t] = sorted(uniques)
            snap["indexes"][t] = indexes
            snap["fks"][t] = sorted(
                (r[3], r[2], r[4], r[6] or "")
                for r in con.execute(f'PRAGMA foreign_key_list("{t}")')
            )

        version = None
        if con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'"
        ).fetchone():
            row = con.execute("SELECT version_num FROM alembic_version").fetchone()
            version = row[0] if row else None
        snap["alembic_version"] = version
        return snap
    finally:
        con.close()


def _orm_snapshot() -> dict:
    from app import models  # noqa: F401  注册全部模型
    from app.database import Base

    md = Base.metadata
    snap = {"tables": set(md.tables), "columns": {}, "types": {}, "nullable": {},
            "pk": {}, "uniques": {}, "fks": {}, "indexes": {}}
    for t, table in md.tables.items():
        snap["columns"][t] = [c.name for c in table.columns]
        snap["types"][t] = {c.name: str(c.type).upper() for c in table.columns}
        snap["nullable"][t] = {c.name: bool(c.nullable) for c in table.columns}
        snap["pk"][t] = tuple(c.name for c in table.primary_key.columns)
        snap["uniques"][t] = sorted(
            tuple(c.name for c in con.columns)
            for con in table.constraints
            if con.__class__.__name__ == "UniqueConstraint"
        )
        snap["fks"][t] = sorted(
            (fk.parent.name, fk.column.table.name, fk.column.name, fk.ondelete or "")
            for fk in table.foreign_keys
        )
        snap["indexes"][t] = {
            ix.name: {"columns": tuple(c.name for c in ix.columns), "unique": bool(ix.unique)}
            for ix in table.indexes
        }
    return snap


def _all_index_names(snap: dict) -> set[str]:
    return {name for per_table in snap["indexes"].values() for name in per_table}


def _assert_reconciled(snap: dict, *, strict_columns: bool, strict_nullable: bool) -> None:
    """ORM metadata 与真实库的三方对账断言（口径见模块 docstring）。"""
    orm = _orm_snapshot()

    assert snap["tables"] == orm["tables"], (
        f"表集合不一致：缺 {sorted(orm['tables'] - snap['tables'])}，"
        f"多 {sorted(snap['tables'] - orm['tables'])}"
    )

    for table in sorted(orm["tables"]):
        db_cols, orm_cols = snap["columns"][table], orm["columns"][table]
        if strict_columns:
            assert db_cols == orm_cols, f"{table} 列（含顺序）与 ORM 不一致"
        else:
            assert set(db_cols) == set(orm_cols), (
                f"{table} 列集合与 ORM 不一致：缺 {sorted(set(orm_cols) - set(db_cols))}，"
                f"多 {sorted(set(db_cols) - set(orm_cols))}"
            )
        for column in orm_cols:
            assert snap["types"][table][column] == orm["types"][table][column], (
                f"{table}.{column} 类型不一致：ORM={orm['types'][table][column]} "
                f"DB={snap['types'][table][column]}"
            )
            db_nullable = snap["nullable"][table][column]
            if orm["nullable"][table][column]:
                assert db_nullable is True, f"{table}.{column}: ORM 可空但库是 NOT NULL"
            elif strict_nullable:
                assert db_nullable is False, f"{table}.{column}: 全新库不应出现可空放宽"
            # strict_nullable=False 时允许「库更宽松」（0014 的历史补列限制）
        assert snap["pk"][table] == orm["pk"][table], f"{table} 主键不一致"
        assert snap["uniques"][table] == orm["uniques"][table], f"{table} 唯一约束不一致"
        assert snap["fks"][table] == orm["fks"][table], f"{table} 外键不一致"

    orm_names = {name for per_table in orm["indexes"].values() for name in per_table}
    db_names = _all_index_names(snap)
    missing = orm_names - db_names
    assert not missing, f"ORM 索引在库中缺失：{sorted(missing)}"
    assert "idx_tasks_project_id" not in db_names, "DB 与 ORM 重复的 idx_tasks_project_id 未被清理"

    extras = db_names - orm_names
    assert extras <= KEPT_LEGACY_EXTRA_INDEXES, (
        f"出现 ORM 未声明的额外索引：{sorted(extras - KEPT_LEGACY_EXTRA_INDEXES)}"
    )

    # 逐条比对 ORM 索引的列与 unique；并确保没有「同表同列不同名」的重复
    for table in sorted(orm["tables"]):
        for name, expected in orm["indexes"][table].items():
            actual = snap["indexes"][table][name]
            assert actual["columns"] == expected["columns"], f"{table}.{name} 索引列不一致"
            assert actual["unique"] == expected["unique"], f"{table}.{name} unique 标记不一致"
        orm_by_columns = {v["columns"] for v in orm["indexes"][table].values()}
        for name, actual in snap["indexes"][table].items():
            if name in orm["indexes"][table]:
                continue
            assert actual["columns"] not in orm_by_columns, (
                f"{table} 存在与 ORM 索引同列的重复索引 {name}"
            )


# ============================================================
# 1. 全新库 upgrade head 的三方对账（核心护栏）
# ============================================================
def test_fresh_upgrade_head_reconciles_with_orm_metadata(temp_db):
    data_dir, migrate, _stamp = temp_db
    migrate("head")

    snap = _db_snapshot(data_dir)
    assert snap["alembic_version"] == HEAD_REVISION
    assert len(snap["tables"]) == BASELINE_TABLE_COUNT
    assert len(_all_index_names(snap)) == BASELINE_INDEX_COUNT + len(
        KEPT_LEGACY_EXTRA_INDEXES
    )

    _assert_reconciled(snap, strict_columns=True, strict_nullable=True)

    # 审计清单逐项：11 个缺失索引在全新库必须全部存在
    missing = AUDITED_MISSING_INDEXES - _all_index_names(snap)
    assert not missing, f"全新库缺少审计要求的索引：{sorted(missing)}"


# ============================================================
# 2. 0001 必须是冻结的显式 DDL
# ============================================================
def test_0001_baseline_is_frozen_explicit_ddl():
    source = (VERSIONS_DIR / "0001_initial.py").read_text(encoding="utf-8")

    # 明文禁止 metadata 批量建表/删表 API（含注释里出现也不行，避免误引入）
    assert "create_all" not in source, "0001 重新引入了 create_all（会导致基线随模型漂移）"
    assert "drop_all" not in source, "0001 重新引入了 drop_all"

    tree = ast.parse(source)
    forbidden_calls = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert not forbidden_calls & {"create_all", "drop_all"}

    # 必须是显式 DDL 且覆盖完整基线
    assert source.count("op.create_table(") == BASELINE_TABLE_COUNT
    assert source.count("op.create_index(") == BASELINE_INDEX_COUNT
    assert "revision = \"0001\"" in source
    assert "down_revision = None" in source


# ============================================================
# 3. 迁移链：线性、单 head、无缺口
# ============================================================
def test_migration_chain_is_linear_single_head():
    from alembic.script import ScriptDirectory

    script = ScriptDirectory.from_config(_alembic_config())
    revisions = list(script.walk_revisions())
    by_id = {rev.revision: rev for rev in revisions}

    assert script.get_heads() == [HEAD_REVISION]
    assert len(by_id) == 21, f"迁移数量异常：{len(by_id)}"

    bases = [rev.revision for rev in revisions if rev.down_revision is None]
    assert bases == ["0001"]

    children: dict[str, list[str]] = {}
    for rev in revisions:
        down = rev.down_revision
        assert not isinstance(down, tuple), f"{rev.revision} 出现分支/合并，迁移链必须线性"
        if down is not None:
            assert down in by_id, f"{rev.revision} 的 down_revision={down} 不存在"
            children.setdefault(down, []).append(rev.revision)
    for parent, kids in children.items():
        assert len(kids) == 1, f"{parent} 有多个子 revision：{kids}（分叉）"
    assert len(children) == len(by_id) - 1


# ============================================================
# 4. 模拟老库：upgrade 到 0011 后缺索引/有重复索引 → head 后 0021 补齐
# ============================================================
def test_old_db_0011_to_head_reconciled_by_0021(temp_db):
    data_dir, migrate, _stamp = temp_db
    migrate("0011")

    # 还原真实老库的两种缺陷：
    #   a) 11 个 ORM 索引缺失（模型后来加的，历史迁移没建）
    #   b) DB 侧多余的同列重复索引 idx_tasks_project_id
    con = sqlite3.connect(str(_db_path(data_dir)))
    try:
        for name in AUDITED_MISSING_INDEXES:
            con.execute(f'DROP INDEX IF EXISTS "{name}"')
        con.execute("CREATE INDEX IF NOT EXISTS idx_tasks_project_id ON tasks (project_id)")
        con.execute(_USER_INSERT)
        con.commit()
        rows_before = con.execute("SELECT username FROM users").fetchall()
    finally:
        con.close()

    migrate("head")

    snap = _db_snapshot(data_dir)
    assert snap["alembic_version"] == HEAD_REVISION
    assert snap["row_counts"]["users"] == len(rows_before) == 1
    assert not (AUDITED_MISSING_INDEXES - _all_index_names(snap))
    _assert_reconciled(snap, strict_columns=False, strict_nullable=False)


# ============================================================
# 5. 部分升级库：版本已到 0020 但 schema 落后 → 0021 单独补齐
# ============================================================
def test_0021_reconciles_partially_upgraded_db(temp_db):
    data_dir, migrate, stamp = temp_db
    migrate("0011")
    db = _db_path(data_dir)

    # 构造「版本号跑到 0020、schema 仍是 0011」的部分升级库：
    # 删掉 0012–0020 才有的表、列、索引，并留一段用户数据验证不丢。
    con = sqlite3.connect(str(db))
    try:
        for table in POST_0011_TABLES:
            con.execute(f'DROP TABLE IF EXISTS "{table}"')
        con.execute("DROP INDEX IF EXISTS ix_tasks_identity_id")
        con.execute('DROP INDEX IF EXISTS idx_domains_user')
        con.execute("ALTER TABLE tasks DROP COLUMN identity_id")
        con.execute("ALTER TABLE tasks DROP COLUMN estimated_minutes")
        con.execute("ALTER TABLE tasks DROP COLUMN acceptance_criteria")
        con.execute("ALTER TABLE habits DROP COLUMN deleted_at")
        con.execute("ALTER TABLE workflow_applications DROP COLUMN updated_at")
        con.execute("ALTER TABLE workflow_applications DROP COLUMN created_at")
        con.execute("ALTER TABLE workflow_applications DROP COLUMN deleted_at")
        for column in ("intimacy", "satiety", "mood", "energy"):
            con.execute(f"ALTER TABLE pet_configs DROP COLUMN {column}")
        con.execute(_USER_INSERT)
        con.commit()
        rows_before = con.execute("SELECT username FROM users").fetchall()
    finally:
        con.close()

    stamp("0020")
    migrate("head")  # head=0021：只会执行 0021（对账）

    snap = _db_snapshot(data_dir)
    assert snap["alembic_version"] == HEAD_REVISION
    assert len(snap["tables"]) == BASELINE_TABLE_COUNT
    assert snap["row_counts"]["users"] == len(rows_before) == 1
    # 0021 补出来的表/列完全按 metadata 建，nullable 应当严格一致
    _assert_reconciled(snap, strict_columns=False, strict_nullable=True)


# ============================================================
# 6. 0021 幂等：重复执行不报错、schema 不变
# ============================================================
def test_0021_is_idempotent(temp_db):
    _data_dir, migrate, stamp = temp_db
    migrate("head")
    first = _db_snapshot(_data_dir)

    stamp("0020")
    migrate("head")  # 0021 再跑一遍

    second = _db_snapshot(_data_dir)
    assert first == second
