"""vault module for Phase-3 D (safe box / credentials)

Revision ID: 0017
Revises: 0016
Create Date: 2026-09-16

内容（三期规划 §6）
  1. vault_config  每用户一条：随机 salt + 主密码校验器（无密码哈希）
  2. vault_items   凭据条目：secret 只存 Fernet token（密文）

幂等（B-1 铁律）：全新库 0001 create_all 已建当前全部模型，建表一律守卫。
"""
from alembic import op
import sqlalchemy as sa

from app.migration_helpers import index_exists, table_exists  # noqa: E402

revision = '0017'
down_revision = '0016'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    if not table_exists(conn, 'vault_config'):
        op.create_table(
            'vault_config',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('user_id', sa.String(36),
                      sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('salt', sa.String(64), nullable=False),
            sa.Column('verifier', sa.Text, nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index('uq_vault_config_user', 'vault_config', ['user_id'], unique=True)
    elif not index_exists(conn, 'uq_vault_config_user'):
        op.create_index('uq_vault_config_user', 'vault_config', ['user_id'], unique=True)

    if not table_exists(conn, 'vault_items'):
        op.create_table(
            'vault_items',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('user_id', sa.String(36),
                      sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('name', sa.String(200), nullable=False),
            sa.Column('category', sa.String(20), nullable=False, server_default='login'),
            sa.Column('username', sa.String(200), nullable=True),
            sa.Column('url', sa.String(500), nullable=True),
            sa.Column('secret_encrypted', sa.Text, nullable=True),
            sa.Column('notes', sa.Text, nullable=True),
            sa.Column('identity_id', sa.String(36), nullable=True),
            sa.Column('last_accessed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index('ix_vault_items_user_id', 'vault_items', ['user_id'])
        op.create_index('ix_vault_items_identity_id', 'vault_items', ['identity_id'])
    else:
        for name, cols in (
            ('ix_vault_items_user_id', ['user_id']),
            ('ix_vault_items_identity_id', ['identity_id']),
        ):
            if not index_exists(conn, name):
                op.create_index(name, 'vault_items', cols)


def downgrade() -> None:
    conn = op.get_bind()
    if table_exists(conn, 'vault_items'):
        op.drop_table('vault_items')
    if table_exists(conn, 'vault_config'):
        op.drop_table('vault_config')
