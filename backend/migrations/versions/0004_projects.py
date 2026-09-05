# ============================================================
# 0004_projects — 项目表 + tasks.project_id 外键
# ============================================================
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0004"
down_revision = "c8758a7bd81f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. 创建 projects 表（幂等检查）
    conn = op.get_bind()
    existing = conn.execute(sa.text("SELECT name FROM sqlite_master WHERE type='table' AND name='projects'")).fetchone()
    if not existing:
        op.create_table(
            "projects",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("description", sa.Text, nullable=True),
            sa.Column("color", sa.String(20), nullable=False, server_default="#7c5cff"),
            sa.Column("status", sa.String(20), nullable=False, server_default="active"),
            sa.Column("due_date", sa.Date, nullable=True),
            sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        )

    # 2. tasks 表添加 project_id 列（幂等检查）
    cols = conn.execute(sa.text("PRAGMA table_info(tasks)")).fetchall()
    col_names = [c[1] for c in cols]
    if "project_id" not in col_names:
        op.add_column("tasks", sa.Column("project_id", sa.String(36), nullable=True))
        op.create_index("idx_tasks_project_id", "tasks", ["project_id"])


def downgrade() -> None:
    op.drop_index("idx_tasks_project_id", table_name="tasks")
    op.drop_column("tasks", "project_id")
    op.drop_table("projects")
