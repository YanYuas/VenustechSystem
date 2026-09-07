"""avatar tables

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-07
"""
from alembic import op
import sqlalchemy as sa
from app.models.types import JSONType

revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'avatar_memories',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('memory_type', sa.String(20), nullable=False),
        sa.Column('category', sa.String(50), nullable=True),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('content', sa.Text, nullable=True),
        sa.Column('tags', JSONType, nullable=False, server_default='[]'),
        sa.Column('source', sa.String(100), nullable=True),
        sa.Column('source_id', sa.String(36), nullable=True),
        sa.Column('confidence', sa.Float, nullable=False, server_default='1.0'),
        sa.Column('is_verified', sa.Boolean, nullable=False, server_default=sa.text('0')),
        sa.Column('importance', sa.Integer, nullable=False, server_default='3'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('idx_avatar_memories_user_type', 'avatar_memories', ['user_id', 'memory_type'])
    op.create_index('idx_avatar_memories_category', 'avatar_memories', ['category'])

    op.create_table(
        'avatar_inspirations',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('domain', sa.String(50), nullable=True),
        sa.Column('estimated_value', sa.String(100), nullable=True),
        sa.Column('prompt', sa.Text, nullable=True),
        sa.Column('result', sa.Text, nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='generated'),
        sa.Column('feedback', sa.String(20), nullable=True),
        sa.Column('batch_id', sa.String(36), nullable=True),
        sa.Column('source_type', sa.String(20), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('idx_avatar_inspirations_user', 'avatar_inspirations', ['user_id'])
    op.create_index('idx_avatar_inspirations_status', 'avatar_inspirations', ['status'])

    op.create_table(
        'avatar_configs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('automation_level', sa.String(10), nullable=False, server_default='L2'),
        sa.Column('local_model_enabled', sa.Boolean, nullable=False, server_default=sa.text('0')),
        sa.Column('local_model_provider', sa.String(20), nullable=True),
        sa.Column('local_model_name', sa.String(100), nullable=True),
        sa.Column('local_model_url', sa.String(200), nullable=True),
        sa.Column('cloud_model_enabled', sa.Boolean, nullable=False, server_default=sa.text('1')),
        sa.Column('cloud_model_provider', sa.String(20), nullable=True),
        sa.Column('cloud_model_name', sa.String(100), nullable=True),
        sa.Column('cloud_api_key', sa.String(200), nullable=True),
        sa.Column('persona_name', sa.String(50), nullable=False, server_default='启明星'),
        sa.Column('persona_setting', sa.Text, nullable=True),
        sa.Column('inspiration_enabled', sa.Boolean, nullable=False, server_default=sa.text('1')),
        sa.Column('inspiration_frequency', sa.String(20), nullable=False, server_default='manual'),
        sa.Column('inspiration_domains', JSONType, nullable=False, server_default='[]'),
        sa.Column('reply_length', sa.String(20), nullable=False, server_default='medium'),
        sa.Column('language_style', sa.String(20), nullable=False, server_default='professional'),
        sa.Column('creativity', sa.Float, nullable=False, server_default='0.7'),
        sa.Column('operation_overrides', JSONType, nullable=False, server_default='{}'),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('avatar_configs')
    op.drop_index('idx_avatar_inspirations_status', table_name='avatar_inspirations')
    op.drop_index('idx_avatar_inspirations_user', table_name='avatar_inspirations')
    op.drop_table('avatar_inspirations')
    op.drop_index('idx_avatar_memories_category', table_name='avatar_memories')
    op.drop_index('idx_avatar_memories_user_type', table_name='avatar_memories')
    op.drop_table('avatar_memories')
