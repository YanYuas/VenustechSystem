"""audit logs (mod-platform P1 · F5.4)

Revision ID: 0019
Revises: 0018
Create Date: 2026-09-18

内容：新增 audit_logs 表 —— 记录敏感动作（加密/解密/密钥轮换/保险箱
解锁/查看凭据/插件加载与错误/同步导出导入），配合加密端点的解锁门禁
形成可追溯链。

幂等：table_exists / index_exists 守卫（迁移铁律：0001 的 create_all
已预建当前全部模型，全新库上本迁移必须可跳过）。
"""
from alembic import op
import sqlalchemy as sa

from app.migration_helpers import index_exists, table_exists  # noqa: E402

revision = '0019'
down_revision = '0018'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    if not table_exists(conn, "audit_logs"):
        op.create_table(
            "audit_logs",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), nullable=False, index=True),
            sa.Column("action", sa.String(64), nullable=False),
            sa.Column("target", sa.String(200), nullable=True),
            sa.Column("ok", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("detail", sa.Text(), nullable=True),
            sa.Column("ip", sa.String(64), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        )
    if not index_exists(conn, "ix_audit_logs_user_created"):
        op.create_index("ix_audit_logs_user_created", "audit_logs", ["user_id", "created_at"])
    if not index_exists(conn, "ix_audit_logs_action"):
        op.create_index("ix_audit_logs_action", "audit_logs", ["action"])


def downgrade():
    conn = op.get_bind()
    if table_exists(conn, "audit_logs"):
        op.drop_table("audit_logs")
