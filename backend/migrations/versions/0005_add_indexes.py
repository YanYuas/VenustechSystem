# ============================================================
# 0005_add_indexes — 高频过滤列补索引（老库 metadata.create_all 不会自动补）
# - documents.user_id / documents.folder_id（列表页过滤）
# - backlinks.target_doc_id（反向链接查询，此前全表扫描）
# - conversations.user_id（会话列表）
# - notifications (user_id, is_read) 复合索引（30s 轮询统计端点）
# ============================================================
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

# (索引名, 表, 列) — 全部幂等创建
_INDEXES: list[tuple[str, str, list[str]]] = [
    ("ix_documents_user_id", "documents", ["user_id"]),
    ("ix_documents_folder_id", "documents", ["folder_id"]),
    ("ix_backlinks_target_doc_id", "backlinks", ["target_doc_id"]),
    ("ix_conversations_user_id", "conversations", ["user_id"]),
    ("ix_notifications_user_read", "notifications", ["user_id", "is_read"]),
]


def upgrade() -> None:
    conn = op.get_bind()
    existing = {
        row[0]
        for row in conn.execute(
            sa.text("SELECT name FROM sqlite_master WHERE type='index'")
        ).fetchall()
    }
    for name, table, columns in _INDEXES:
        # 表可能不存在（全新库由 metadata.create_all 建表时已含索引）
        table_exists = conn.execute(
            sa.text("SELECT name FROM sqlite_master WHERE type='table' AND name=:t"),
            {"t": table},
        ).fetchone()
        if table_exists and name not in existing:
            op.create_index(name, table, columns)


def downgrade() -> None:
    conn = op.get_bind()
    existing = {
        row[0]
        for row in conn.execute(
            sa.text("SELECT name FROM sqlite_master WHERE type='index'")
        ).fetchall()
    }
    for name, _table, _columns in _INDEXES:
        if name in existing:
            op.drop_index(name, table_name=_table)
