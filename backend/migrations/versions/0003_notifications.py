"""add_notifications_table

由于 0001 迁移使用 Base.metadata.create_all() 全量建表，
新增模型会被自动创建。本迁移做幂等处理：
- 表不存在则创建
- 索引不存在则创建

Revision ID: c8758a7bd81f
Revises: 0002
Create Date: 2026-08-29 09:37:15.684787
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'c8758a7bd81f'
down_revision = '0002'
branch_labels = None
depends_on = None


def _table_exists(name: str) -> bool:
    bind = op.get_bind()
    return inspect(bind).has_table(name)


def _index_exists(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    indexes = inspect(bind).get_indexes(table_name)
    return any(idx["name"] == index_name for idx in indexes)


def upgrade() -> None:
    if not _table_exists("notifications"):
        op.create_table(
            "notifications",
            sa.Column("user_id", sa.String(length=36), nullable=False),
            sa.Column("type", sa.String(length=20), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("content", sa.Text(), nullable=True),
            sa.Column("is_read", sa.Boolean(), nullable=False),
            sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("source_type", sa.String(length=30), nullable=True),
            sa.Column("source_id", sa.String(length=36), nullable=True),
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    if not _index_exists("notifications", "ix_notifications_is_read"):
        op.create_index("ix_notifications_is_read", "notifications", ["is_read"], unique=False)
    if not _index_exists("notifications", "ix_notifications_user_id"):
        op.create_index("ix_notifications_user_id", "notifications", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_index("ix_notifications_is_read", table_name="notifications")
    op.drop_table("notifications")
