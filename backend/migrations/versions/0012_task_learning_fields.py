"""task learning fields for S6-1

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-16

背景（S6-1 领域规则引擎）
    交付物 A 的领域库任务带四要素：do（做什么）/ time（预估时长）/
    standard（达标标准）/ repeat（是否可重复）。

    而启明星的 tasks 表没有「预估时长」与「达标标准」两列 —— 若把这两个
    信息塞进 description 文本，它们就变得**不可结构化**：无法按时长统计、
    无法作为验收依据、无法在 UI 上单独呈现。

    因此做正式 schema 变更，而不是有损地挤进现有列。

幂等性（B-1 教训，务必保留）
    0001_initial.py 用 Base.metadata.create_all() 建的是「当前全部模型」，
    所以在**全新库**上，tasks 表（含本迁移要加的两列）可能已被 0001 建好。
    直接 op.add_column 会撞「duplicate column name」而中断迁移链，
    表现为新装用户完全起不来。故一律走 add_column_if_missing 守卫。

    另注：本迁移**不改动已有列**，只做可加性变更，因此对已有数据无损。
"""
from alembic import op
import sqlalchemy as sa

from app.migration_helpers import add_column_if_missing, column_exists  # noqa: E402

revision = '0012'
down_revision = '0011'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    # 预估时长（分钟，整数）——领域库的 time 是文本（"40分钟"/"约 3 小时"），
    # 落库前由 domain_engine.parse_duration_minutes 归一化
    add_column_if_missing(conn, 'tasks', 'estimated_minutes', sa.Integer)
    # 达标标准：做到什么程度算完成（领域库 90/90 条任务都有）
    add_column_if_missing(conn, 'tasks', 'acceptance_criteria', sa.Text)


def downgrade() -> None:
    conn = op.get_bind()
    for column in ('acceptance_criteria', 'estimated_minutes'):
        if column_exists(conn, 'tasks', column):
            op.drop_column('tasks', column)
