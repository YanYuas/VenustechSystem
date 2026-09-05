"""新增 quick_todos 和 reminders 表（左侧信息面板）

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-28
"""
from alembic import op
import sqlalchemy as sa


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 0001 用 create_all 已建表，此处用 IF NOT EXISTS 防冲突
    op.execute("""
        CREATE TABLE IF NOT EXISTS quick_todos (
            id VARCHAR(36) NOT NULL PRIMARY KEY,
            user_id VARCHAR(36) NOT NULL,
            title VARCHAR(200) NOT NULL,
            completed BOOLEAN DEFAULT 0 NOT NULL,
            sort_order INTEGER DEFAULT 0 NOT NULL,
            completed_at DATETIME,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_quick_todos_user ON quick_todos (user_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id VARCHAR(36) NOT NULL PRIMARY KEY,
            user_id VARCHAR(36) NOT NULL,
            title VARCHAR(200) NOT NULL,
            description TEXT,
            remind_at DATETIME NOT NULL,
            type VARCHAR(20) DEFAULT 'custom' NOT NULL,
            dismissed BOOLEAN DEFAULT 0 NOT NULL,
            repeat VARCHAR(20) DEFAULT 'none' NOT NULL,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_reminders_user_time ON reminders (user_id, remind_at)")


def downgrade() -> None:
    op.drop_index("idx_reminders_user_time", table_name="reminders")
    op.drop_table("reminders")
    op.drop_index("idx_quick_todos_user", table_name="quick_todos")
    op.drop_table("quick_todos")
