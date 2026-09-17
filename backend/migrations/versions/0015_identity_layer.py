"""identity layer for Phase-3 B (identities + identity_id on 8 tables)

Revision ID: 0015
Revises: 0014
Create Date: 2026-09-16

内容（总路线波次一「立轴」，见 docs/management/总路线-二三期融合-2026-09-16.md）
  1. identities 身份表 —— 横切维度的锚点
       一重身份 = 一套目标 + 一批资料 + 一类产出。身份不是第五个模块，
       而是任务/项目/文档/日记等所有记录共用的分类轴。
  2. 8 张业务表加可空 identity_id：
       tasks / projects / documents / diaries / reviews /
       avatar_memories / project_memories / inbox_items
     前四张承接日常记录，后四张是 S6-4「经历视图」的四源
     （二期卡在概念归并上 —— 身份轴落地后「经历」= 按身份聚合的
     视图，不再需要新表，见总路线 R1）。

为什么 identity_id 不加外键约束（**有意为之，勿"修复"**）
  SQLite 给已有数据的表加约束需要重建整表，8 张表逐个重建的风险
  远大于收益；关联完整性由应用层保证（写入前校验身份存在且属于
  同一用户，见 identity_service / 各 create 路径）。

幂等（B-1 铁律）
  0001_initial 用 create_all() 建的是「当前全部模型」—— 全新库上
  identities 表和 8 个 identity_id 列**都已存在**。建表/加列一律守卫。
  索引名与 create_all 的命名规则一致（ix_<table>_<column>），
  避免同一索引以两个名字重复出现。
"""
from alembic import op
import sqlalchemy as sa

from app.migration_helpers import (  # noqa: E402
    add_column_if_missing,
    column_exists,
    index_exists,
    table_exists,
)

revision = '0015'
down_revision = '0014'
branch_labels = None
depends_on = None

# 挂身份轴的 8 张业务表
IDENTITY_TABLES = (
    "tasks",
    "projects",
    "documents",
    "diaries",
    "reviews",
    "avatar_memories",
    "project_memories",
    "inbox_items",
)


def upgrade() -> None:
    conn = op.get_bind()

    # ---------- 1. identities 表 ----------
    if not table_exists(conn, 'identities'):
        op.create_table(
            'identities',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('user_id', sa.String(36),
                      sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('name', sa.String(60), nullable=False),
            sa.Column('slug', sa.String(60), nullable=False),
            sa.Column('color_token', sa.String(40), nullable=False, server_default='primary'),
            sa.Column('icon', sa.String(40), nullable=False, server_default='star'),
            sa.Column('description', sa.Text, nullable=True),
            sa.Column('sort_order', sa.Integer, nullable=False, server_default='0'),
            sa.Column('is_active', sa.Boolean, nullable=False, server_default=sa.true()),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint('user_id', 'slug', name='uq_identities_user_slug'),
        )
        op.create_index('ix_identities_user_id', 'identities', ['user_id'])
    elif not index_exists(conn, 'ix_identities_user_id'):
        op.create_index('ix_identities_user_id', 'identities', ['user_id'])

    # ---------- 2. 8 张业务表加 identity_id ----------
    for table in IDENTITY_TABLES:
        add_column_if_missing(
            conn, table, 'identity_id', sa.String(36),
            index_name=f'ix_{table}_identity_id',
        )


def downgrade() -> None:
    conn = op.get_bind()

    for table in IDENTITY_TABLES:
        if column_exists(conn, table, 'identity_id'):
            op.drop_column(table, 'identity_id')

    if table_exists(conn, 'identities'):
        op.drop_table('identities')
