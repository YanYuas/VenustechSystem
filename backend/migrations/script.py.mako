"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# ============================================================
# 【必读】迁移必须幂等
#
# 0001_initial.py 用的是 Base.metadata.create_all()，它建的是**当前代码里注册的
# 全部模型**（不是 0001 当时的 schema）。所以本迁移要建的表，在全新库上很可能
# 已经被 0001 建好了。
#
# 凡是没加守卫的建表/建索引，都会在全新库上抛
#   sqlite3.OperationalError: table xxx already exists
# 直接中断迁移链 —— 表现为「新装用户完全起不来」（0009/0010/0011 曾因此长期不可用）。
#
# 因此：建表 -> if not table_exists(conn, ...)；建索引 -> if not index_exists(conn, ...)。
# autogenerate 产出的 create_table / create_index 请手动包上守卫。
# ============================================================
from app.migration_helpers import index_exists, table_exists  # noqa: F401

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    conn = op.get_bind()
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
