"""pet tables

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-07
"""
from alembic import op
import sqlalchemy as sa
from app.models.types import JSONType

revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None


# 幂等守卫统一走 migration_helpers（同 0009）
from app.migration_helpers import index_exists as _index_exists  # noqa: E402
from app.migration_helpers import table_exists as _table_exists  # noqa: E402


def upgrade() -> None:
    conn = op.get_bind()

    if not _table_exists(conn, 'pet_configs'):
        op.create_table(
            'pet_configs',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True),
            sa.Column('enabled', sa.Boolean, nullable=False, server_default=sa.text('1')),
            sa.Column('size', sa.String(10), nullable=False, server_default='medium'),
            sa.Column('opacity', sa.Float, nullable=False, server_default='1.0'),
            sa.Column('always_on_top', sa.Boolean, nullable=False, server_default=sa.text('1')),
            sa.Column('auto_start', sa.Boolean, nullable=False, server_default=sa.text('0')),
            sa.Column('position_x', sa.Integer, nullable=False, server_default='0'),
            sa.Column('position_y', sa.Integer, nullable=False, server_default='0'),
            sa.Column('current_avatar_id', sa.String(36), nullable=True),
            sa.Column('state_awareness_enabled', sa.Boolean, nullable=False, server_default=sa.text('1')),
            sa.Column('action_switch_interval', sa.Integer, nullable=False, server_default='30'),
            sa.Column('show_bubble', sa.Boolean, nullable=False, server_default=sa.text('1')),
            sa.Column('bubble_duration', sa.Integer, nullable=False, server_default='5'),
            sa.Column('click_interaction', sa.Boolean, nullable=False, server_default=sa.text('1')),
            sa.Column('draggable', sa.Boolean, nullable=False, server_default=sa.text('1')),
            sa.Column('right_click_menu', sa.Boolean, nullable=False, server_default=sa.text('1')),
            sa.Column('tts_enabled', sa.Boolean, nullable=False, server_default=sa.text('0')),
            sa.Column('tts_voice', sa.String(50), nullable=True),
            sa.Column('tts_rate', sa.Float, nullable=False, server_default='1.0'),
            sa.Column('tts_pitch', sa.Float, nullable=False, server_default='1.0'),
            sa.Column('tts_volume', sa.Float, nullable=False, server_default='0.8'),
            sa.Column('speak_scene', sa.String(20), nullable=False, server_default='remind'),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        )

    if not _table_exists(conn, 'pet_avatars'):
        op.create_table(
            'pet_avatars',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('name', sa.String(50), nullable=False),
            sa.Column('description', sa.String(200), nullable=True),
            sa.Column('avatar_type', sa.String(20), nullable=False, server_default='builtin'),
            sa.Column('image_url', sa.String(500), nullable=True),
            sa.Column('mode', sa.String(20), nullable=False, server_default='simple'),
            sa.Column('eye_position', JSONType, nullable=False, server_default='{}'),
            sa.Column('mouth_position', JSONType, nullable=False, server_default='{}'),
            sa.Column('action_frames', JSONType, nullable=False, server_default='{}'),
            sa.Column('tags', JSONType, nullable=False, server_default='[]'),
            sa.Column('is_active', sa.Boolean, nullable=False, server_default=sa.text('0')),
            sa.Column('sort_order', sa.Integer, nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index('idx_pet_avatars_user', 'pet_avatars', ['user_id'])
    else:
        if not _index_exists(conn, 'idx_pet_avatars_user'):
            op.create_index('idx_pet_avatars_user', 'pet_avatars', ['user_id'])


def downgrade() -> None:
    conn = op.get_bind()
    if _table_exists(conn, 'pet_avatars'):
        op.drop_index('idx_pet_avatars_user', table_name='pet_avatars')
        op.drop_table('pet_avatars')
    if _table_exists(conn, 'pet_configs'):
        op.drop_table('pet_configs')
