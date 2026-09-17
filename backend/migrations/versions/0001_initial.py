"""初始建表（11 张表）

以 ORM metadata 为准建表，保证模型与 DB 同步不漂移。
后续 schema 变更用 `alembic revision --autogenerate` 生成增量迁移。

Revision ID: 0001
Revises:
Create Date: 2026-08-28
"""
from alembic import op  # noqa: E402
from app.database import Base  # noqa: E402

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind)
