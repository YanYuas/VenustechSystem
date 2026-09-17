"""growth tables + pet stats fields for S6-2

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-16

内容
  1. 成长体系三张新表（S6-2）
       growth_states  经验值 / 等级（每用户一条）
       growth_events  EXP 流水账本，带 (user_id, source_key) 唯一幂等键
       skill_stats    技能分类累计计数
  2. pet_configs 补四维数值列 + 更新时间
       交付物 A 的桌宠数值原本只写在浏览器 localStorage：
       不进备份、换设备即归零、清缓存全丢。
       落库后才真正受「本地优先 + 备份」保护。

为什么数值列必须落库而不能继续用 localStorage
   启明星的卖点是本地数据主权与备份导入导出，而成长/陪伴数据是用户投入
   时间最多、最不可再生的那部分。放浏览器里等于随时可能归零。

幂等（B-1 教训，务必保留）
   0001_initial.py 用 Base.metadata.create_all() 建的是「当前全部模型」，
   所以全新库上 0001 很可能已经把这几张表、这几列都建好了
   （新表已在 models/__init__ 注册）。因此建表/加列一律先守卫，
   否则全新库迁移会中断，表现为新装用户完全起不来。

  注意：新表本身也都带 updated_at / deleted_at（同步就绪），
  不会拉低 W3 的同步就绪性审计通过率。
"""
from alembic import op
import sqlalchemy as sa

from app.migration_helpers import (  # noqa: E402
    add_column_if_missing,
    column_exists,
    index_exists,
    table_exists,
)
from app.models.types import JSONType  # noqa: E402

revision = '0013'
down_revision = '0012'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # ---------- 1. 成长体系三张表 ----------
    if not table_exists(conn, 'growth_states'):
        op.create_table(
            'growth_states',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('user_id', sa.String(36),
                      sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('exp', sa.Integer, nullable=False, server_default='0'),
            sa.Column('level', sa.Integer, nullable=False, server_default='1'),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index('idx_growth_states_user', 'growth_states', ['user_id'], unique=True)
    elif not index_exists(conn, 'idx_growth_states_user'):
        op.create_index('idx_growth_states_user', 'growth_states', ['user_id'], unique=True)

    if not table_exists(conn, 'growth_events'):
        op.create_table(
            'growth_events',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('user_id', sa.String(36),
                      sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('source_key', sa.String(200), nullable=False),
            sa.Column('event_type', sa.String(50), nullable=False),
            sa.Column('exp', sa.Integer, nullable=False, server_default='0'),
            sa.Column('label', sa.String(200), nullable=True),
            sa.Column('skill_cat_ids', JSONType, nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index('idx_growth_events_source', 'growth_events',
                        ['user_id', 'source_key'], unique=True)
        op.create_index('idx_growth_events_user', 'growth_events', ['user_id'])
    else:
        if not index_exists(conn, 'idx_growth_events_source'):
            op.create_index('idx_growth_events_source', 'growth_events',
                            ['user_id', 'source_key'], unique=True)
        if not index_exists(conn, 'idx_growth_events_user'):
            op.create_index('idx_growth_events_user', 'growth_events', ['user_id'])

    if not table_exists(conn, 'skill_stats'):
        op.create_table(
            'skill_stats',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('user_id', sa.String(36),
                      sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('category_id', sa.String(50), nullable=False),
            sa.Column('count', sa.Integer, nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index('idx_skill_stats_user_cat', 'skill_stats',
                        ['user_id', 'category_id'], unique=True)
    elif not index_exists(conn, 'idx_skill_stats_user_cat'):
        op.create_index('idx_skill_stats_user_cat', 'skill_stats',
                        ['user_id', 'category_id'], unique=True)

    # ---------- 2. pet_configs 四维数值 ----------
    # 四维数值由前端 localStorage 迁入，语义见 pet.py
    add_column_if_missing(conn, 'pet_configs', 'intimacy', sa.Integer)
    add_column_if_missing(conn, 'pet_configs', 'satiety', sa.Integer)
    add_column_if_missing(conn, 'pet_configs', 'mood', sa.Integer)
    add_column_if_missing(conn, 'pet_configs', 'energy', sa.Integer)
    add_column_if_missing(conn, 'pet_configs', 'stats_updated_at', sa.DateTime(timezone=True))


def downgrade() -> None:
    conn = op.get_bind()
    for column in ('stats_updated_at', 'energy', 'mood', 'satiety', 'intimacy'):
        if column_exists(conn, 'pet_configs', column):
            op.drop_column('pet_configs', column)

    if table_exists(conn, 'skill_stats'):
        op.drop_table('skill_stats')
    if table_exists(conn, 'growth_events'):
        op.drop_table('growth_events')
    if table_exists(conn, 'growth_states'):
        op.drop_table('growth_states')
