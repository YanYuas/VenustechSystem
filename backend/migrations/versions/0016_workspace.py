"""workspace module for Phase-3 C (optional feature, opt-in)

Revision ID: 0016
Revises: 0015
Create Date: 2026-09-16

内容（三期规划 §5 + 2026-09-16 用户决策修正）
  1. workspace_roots    用户登记的工作区根（默认零条 —— 可选功能）
  2. workspace_files    索引条目（只存路径元数据，不复制内容）

设计决策（勿"修复"回旧方案）：
  工作区**默认关闭、零预设**。别人的电脑文件夹结构与作者不同，
  不存在内置路径；目录结构由引导流程建立（登记现有文件夹，或
  按用户自己的身份一键生成骨架）。作者的本机路径只是作者实例。

幂等（B-1 铁律）：0001 create_all() 建当前全部模型，全新库上
  这两张表已存在，建表一律守卫。两表均带 updated_at/deleted_at，
  不拉低同步就绪审计。
"""
from alembic import op
import sqlalchemy as sa

from app.migration_helpers import (  # noqa: E402
    index_exists,
    table_exists,
)

revision = '0016'
down_revision = '0015'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    if not table_exists(conn, 'workspace_roots'):
        op.create_table(
            'workspace_roots',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('user_id', sa.String(36),
                      sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('path', sa.String(500), nullable=False),
            sa.Column('label', sa.String(100), nullable=True),
            sa.Column('identity_id', sa.String(36), nullable=True),
            sa.Column('enabled', sa.Boolean, nullable=False, server_default=sa.true()),
            sa.Column('scan_status', sa.String(10), nullable=False, server_default='never'),
            sa.Column('scan_error', sa.Text, nullable=True),
            sa.Column('last_scanned_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('file_count', sa.Integer, nullable=False, server_default='0'),
            sa.Column('total_size', sa.Integer, nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint('user_id', 'path', name='uq_workspace_roots_user_path'),
        )
        op.create_index('ix_workspace_roots_user_id', 'workspace_roots', ['user_id'])
        op.create_index('ix_workspace_roots_identity_id', 'workspace_roots', ['identity_id'])
    else:
        if not index_exists(conn, 'ix_workspace_roots_user_id'):
            op.create_index('ix_workspace_roots_user_id', 'workspace_roots', ['user_id'])
        if not index_exists(conn, 'ix_workspace_roots_identity_id'):
            op.create_index('ix_workspace_roots_identity_id', 'workspace_roots', ['identity_id'])

    if not table_exists(conn, 'workspace_files'):
        op.create_table(
            'workspace_files',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('root_id', sa.String(36),
                      sa.ForeignKey('workspace_roots.id', ondelete='CASCADE'), nullable=False),
            sa.Column('rel_path', sa.String(500), nullable=False),
            sa.Column('name', sa.String(255), nullable=False),
            sa.Column('ext', sa.String(30), nullable=True),
            sa.Column('is_dir', sa.Boolean, nullable=False, server_default=sa.false()),
            sa.Column('size', sa.Integer, nullable=False, server_default='0'),
            sa.Column('mtime', sa.Float, nullable=False, server_default='0'),
            sa.Column('identity_id', sa.String(36), nullable=True),
            sa.Column('indexed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index('ix_workspace_files_root_id', 'workspace_files', ['root_id'])
        op.create_index('ix_workspace_files_identity_id', 'workspace_files', ['identity_id'])
        op.create_index('ix_workspace_files_name', 'workspace_files', ['name'])
    else:
        for name, cols in (
            ('ix_workspace_files_root_id', ['root_id']),
            ('ix_workspace_files_identity_id', ['identity_id']),
            ('ix_workspace_files_name', ['name']),
        ):
            if not index_exists(conn, name):
                op.create_index(name, 'workspace_files', cols)


def downgrade() -> None:
    conn = op.get_bind()
    if table_exists(conn, 'workspace_files'):
        op.drop_table('workspace_files')
    if table_exists(conn, 'workspace_roots'):
        op.drop_table('workspace_roots')
