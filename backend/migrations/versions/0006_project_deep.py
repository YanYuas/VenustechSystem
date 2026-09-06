# ============================================================
# 0006_project_deep — M06 项目深度开发
# - documents/conversations/reviews 增加 project_id 关联列（SET NULL + 索引）
# - 新建 project_milestones 里程碑表
# 幂等：全部检查后再执行
# ============================================================
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def _table_exists(conn, name: str) -> bool:
    return conn.execute(
        sa.text("SELECT name FROM sqlite_master WHERE type='table' AND name=:n"),
        {"n": name},
    ).fetchone() is not None


def _column_exists(conn, table: str, column: str) -> bool:
    cols = conn.execute(sa.text(f"PRAGMA table_info({table})")).fetchall()
    return column in [c[1] for c in cols]


def upgrade() -> None:
    conn = op.get_bind()

    # 1. 跨模块项目关联列
    for table in ("documents", "conversations", "reviews"):
        if _table_exists(conn, table) and not _column_exists(conn, table, "project_id"):
            op.add_column(table, sa.Column("project_id", sa.String(36), nullable=True))
            op.create_index(f"ix_{table}_project_id", table, ["project_id"])

    # 2. 里程碑表
    if not _table_exists(conn, "project_milestones"):
        op.create_table(
            "project_milestones",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "project_id", sa.String(36),
                sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False,
            ),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("description", sa.Text, nullable=True),
            sa.Column("target_date", sa.Date, nullable=True),
            sa.Column("completed", sa.Boolean, nullable=False, server_default=sa.text("0")),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("task_ids", sa.Text, nullable=True),
            sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_project_milestones_project_id", "project_milestones", ["project_id"])


def downgrade() -> None:
    conn = op.get_bind()
    if _table_exists(conn, "project_milestones"):
        op.drop_table("project_milestones")
    for table in ("documents", "conversations", "reviews"):
        if _table_exists(conn, table) and _column_exists(conn, table, "project_id"):
            op.drop_index(f"ix_{table}_project_id", table_name=table)
            op.drop_column(table, "project_id")
