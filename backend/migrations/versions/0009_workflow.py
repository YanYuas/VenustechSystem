"""workflow tables

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-07
"""
from alembic import op
import sqlalchemy as sa
from app.models.types import JSONType

revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None


# 幂等守卫统一走 migration_helpers（0001 的 create_all 会预建全部表，必须守卫）
from app.migration_helpers import index_exists as _index_exists  # noqa: E402
from app.migration_helpers import table_exists as _table_exists  # noqa: E402


def upgrade() -> None:
    conn = op.get_bind()

    if not _table_exists(conn, 'workflows'):
        op.create_table(
            'workflows',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('name', sa.String(200), nullable=False),
            sa.Column('description', sa.Text, nullable=True),
            sa.Column('icon', sa.String(50), nullable=True),
            sa.Column('category', sa.String(50), nullable=True),
            sa.Column('scenario', sa.String(200), nullable=True),
            sa.Column('config', JSONType, nullable=False, server_default='{}'),
            sa.Column('is_preset', sa.Boolean, nullable=False, server_default=sa.text('0')),
            sa.Column('is_active', sa.Boolean, nullable=False, server_default=sa.text('1')),
            sa.Column('use_count', sa.Integer, nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index('idx_workflows_category', 'workflows', ['category'])
        op.create_index('idx_workflows_is_preset', 'workflows', ['is_preset'])
    else:
        if not _index_exists(conn, 'idx_workflows_category'):
            op.create_index('idx_workflows_category', 'workflows', ['category'])
        if not _index_exists(conn, 'idx_workflows_is_preset'):
            op.create_index('idx_workflows_is_preset', 'workflows', ['is_preset'])

    if not _table_exists(conn, 'workflow_applications'):
        op.create_table(
            'workflow_applications',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('workflow_id', sa.String(36), sa.ForeignKey('workflows.id', ondelete='CASCADE'), nullable=False),
            sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('params', JSONType, nullable=False, server_default='{}'),
            sa.Column('status', sa.String(20), nullable=False, server_default='completed'),
            sa.Column('result_summary', sa.Text, nullable=True),
            sa.Column('applied_at', sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index('idx_workflow_apps_user', 'workflow_applications', ['user_id'])
        op.create_index('idx_workflow_apps_workflow', 'workflow_applications', ['workflow_id'])
    else:
        if not _index_exists(conn, 'idx_workflow_apps_user'):
            op.create_index('idx_workflow_apps_user', 'workflow_applications', ['user_id'])
        if not _index_exists(conn, 'idx_workflow_apps_workflow'):
            op.create_index('idx_workflow_apps_workflow', 'workflow_applications', ['workflow_id'])


def downgrade() -> None:
    conn = op.get_bind()
    if _table_exists(conn, 'workflow_applications'):
        op.drop_index('idx_workflow_apps_workflow', table_name='workflow_applications')
        op.drop_index('idx_workflow_apps_user', table_name='workflow_applications')
        op.drop_table('workflow_applications')
    if _table_exists(conn, 'workflows'):
        op.drop_index('idx_workflows_is_preset', table_name='workflows')
        op.drop_index('idx_workflows_category', table_name='workflows')
        op.drop_table('workflows')
