"""vault terminal actions (Phase-3 D wrap-up)

Revision ID: 0018
Revises: 0017
Create Date: 2026-09-16

内容：vault_items 增加"终端动作"字段（凭据驱动的白名单动作）。
  - action_type: none / ssh（白名单，禁止任意命令）
  - action_host / action_user / action_port: 连接参数（明文，非敏感）

安全边界（勿削弱）：动作只接受固定模板（ssh -i 密钥路径 user@host -p port），
动态字段全部过白名单正则；secret 是加密存的**密钥文件路径**，
运行时解密且必须真实存在 —— 不支持把密码塞进命令行。

幂等：add_column_if_missing 守卫（B-1 铁律）。
"""
from alembic import op
import sqlalchemy as sa

from app.migration_helpers import add_column_if_missing  # noqa: E402

revision = '0018'
down_revision = '0017'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    add_column_if_missing(conn, 'vault_items', 'action_type', sa.String(20))
    add_column_if_missing(conn, 'vault_items', 'action_host', sa.String(255))
    add_column_if_missing(conn, 'vault_items', 'action_user', sa.String(255))
    add_column_if_missing(conn, 'vault_items', 'action_port', sa.String(10))


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    cols = {c['name'] for c in insp.get_columns('vault_items')}
    for col in ('action_type', 'action_host', 'action_user', 'action_port'):
        if col in cols:
            op.drop_column('vault_items', col)
