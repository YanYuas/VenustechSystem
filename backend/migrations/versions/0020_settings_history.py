"""settings change history (mod-platform P2 · F6.2)

Revision ID: 0020
Revises: 0019
Create Date: 2026-09-19

内容：新增 settings_history 表 —— 记录设置变更（key/旧值/新值），保留最近
200 条，支持单 key 回滚。敏感值写库前脱敏。

幂等：table_exists / index_exists 守卫（迁移铁律）。
"""
from alembic import op
import sqlalchemy as sa

from app.migration_helpers import index_exists, table_exists  # noqa: E402

revision = '0020'
down_revision = '0019'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    if not table_exists(conn, "settings_history"):
        op.create_table(
            "settings_history",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), nullable=False),
            sa.Column("key", sa.String(200), nullable=False),
            sa.Column("old_value", sa.Text(), nullable=True),
            sa.Column("new_value", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        )
    if not index_exists(conn, "ix_settings_history_user_created"):
        op.create_index("ix_settings_history_user_created", "settings_history",
                        ["user_id", "created_at"])
    if not index_exists(conn, "ix_settings_history_key"):
        op.create_index("ix_settings_history_key", "settings_history", ["key"])


def downgrade():
    conn = op.get_bind()
    if table_exists(conn, "settings_history"):
        op.drop_table("settings_history")
