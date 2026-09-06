# ============================================================
# 0007_task_deep — M02 任务深度开发
# - tasks 增加 reminder_time / recurrence / focus_duration
# - 新建 focus_sessions 番茄钟表
# 幂等：全部检查后再执行
# ============================================================
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0007"
down_revision = "0006"
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

    # 1. tasks 扩展列
    if _table_exists(conn, "tasks"):
        if not _column_exists(conn, "tasks", "reminder_time"):
            op.add_column("tasks", sa.Column("reminder_time", sa.DateTime(), nullable=True))
            op.create_index("ix_tasks_reminder_time", "tasks", ["reminder_time"])
        if not _column_exists(conn, "tasks", "recurrence"):
            op.add_column("tasks", sa.Column("recurrence", sa.Text(), nullable=True))
        if not _column_exists(conn, "tasks", "focus_duration"):
            op.add_column(
                "tasks",
                sa.Column("focus_duration", sa.Integer(), nullable=False, server_default="0"),
            )

    # 2. 番茄钟会话表
    if not _table_exists(conn, "focus_sessions"):
        op.create_table(
            "focus_sessions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "task_id", sa.String(36),
                sa.ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True,
            ),
            sa.Column(
                "user_id", sa.String(36),
                sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
            ),
            sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
            sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
            sa.Column("duration", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("note", sa.String(500), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_focus_sessions_task_id", "focus_sessions", ["task_id"])
        op.create_index("ix_focus_sessions_user_id", "focus_sessions", ["user_id"])


def downgrade() -> None:
    conn = op.get_bind()
    if _table_exists(conn, "focus_sessions"):
        op.drop_table("focus_sessions")
    if _table_exists(conn, "tasks"):
        for col in ("focus_duration", "recurrence", "reminder_time"):
            if _column_exists(conn, "tasks", col):
                op.drop_column("tasks", col)
        op.drop_index("ix_tasks_reminder_time", table_name="tasks")
