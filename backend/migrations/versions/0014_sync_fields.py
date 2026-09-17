"""sync fields for S6-3a (updated_at / deleted_at on 32 tables)

Revision ID: 0014
Revises: 0013
Create Date: 2026-09-16

背景
  S6-3 的 diff-sync 依赖两个字段在**每一张业务表**上都存在：
    updated_at —— 判断"这条记录是否变过"（增量同步的基础）
    deleted_at —— 软删除墓碑（否则删除无法同步，多端必然复活数据）
  W0 的审计基线是 39 张表仅 7 张就绪；本迁移把缺口补平。

⚠️ 本迁移的边界（**务必读完再改**）
  这里只做**字段补齐**，**不启用软删除语义**：
    · BaseRepository.delete() 仍是硬删除（db.delete + commit）
    · 各 Repository 的自定义查询也**不会**自动过滤 deleted_at
  也就是说，加了列之后"软删除"目前只是一个可用的位置，还没有消费者。

  为什么不一起改语义：
    1. 改动面极大：base.py 的 list/count/paginate 要加过滤，
       而各 Repository 里还有大量**直接写 select() 的自定义查询**
       （如 TaskRepository.list_user_tasks），它们不会继承 base 的过滤。
       只改一半会造成"有的查询过滤、有的不过滤"的不一致 —— 那比现在更糟。
    2. 当前没有任何消费方：本地优先、无云端同步，软删除语义没有读者。
  因此语义落地推迟到 S6-3b（diff-sync 引擎）时与同步逻辑一并做，
  届时才能连同自定义查询一起梳理，并有同步测试来验证。

幂等（B-1 复发防护）
  0001_initial 用 create_all() 建的是「当前全部模型」，全新库上这些列
  **很可能已随建表一起存在**。故一律走 add_column_if_missing 守卫。

关于 nullable
  Mixin 里 created_at/updated_at 声明为 nullable=False，但 SQLite 对
  已有数据的表加 NOT NULL 列会失败。这里按 nullable 加入，随后把 NULL
  回填为当前时间 —— 历史数据拿到的是"迁移时刻"而非真实创建时间，
  这是已知的近似（数据库中此前并未记录该信息，无法还原）。
"""
from alembic import op
import sqlalchemy as sa

from app.migration_helpers import add_column_if_missing  # noqa: E402

revision = '0014'
down_revision = '0013'
branch_labels = None
depends_on = None

# 只缺软删除（已有 updated_at）
SOFT_DELETE_ONLY = (
    "sops", "prompt_templates", "skills", "project_memories",
    "avatar_memories", "avatar_inspirations", "avatar_configs",
    "messages", "document_versions", "backlinks",
    "study_plans", "flashcards",
    "habits", "diaries",
    "notifications",
    "quick_todos", "reminders",
    "pet_configs", "pet_avatars",
    "project_milestones",
    "inbox_items", "templates", "domains",
    "settings",
    "subtasks", "focus_sessions",
    "workflows",
)

# updated_at 与 deleted_at 都缺（created_at 同缺）
TIMESTAMP_AND_SOFT = (
    "sop_versions",
    "study_time_logs",
    "habit_checkins",
    "mood_logs",
    "workflow_applications",
)


def upgrade() -> None:
    conn = op.get_bind()
    dt = sa.DateTime(timezone=True)

    for table in SOFT_DELETE_ONLY:
        add_column_if_missing(conn, table, "deleted_at", dt)

    for table in TIMESTAMP_AND_SOFT:
        add_column_if_missing(conn, table, "created_at", dt)
        add_column_if_missing(conn, table, "updated_at", dt)
        add_column_if_missing(conn, table, "deleted_at", dt)

    # 回填：让历史行的时间列不为 NULL（否则前端序列化和后续增量同步都会踩坑）
    for table in TIMESTAMP_AND_SOFT:
        for column in ("created_at", "updated_at"):
            op.execute(
                sa.text(
                    f"UPDATE {table} SET {column} = CURRENT_TIMESTAMP "
                    f"WHERE {column} IS NULL"
                )
            )


def downgrade() -> None:
    conn = op.get_bind()
    from app.migration_helpers import column_exists

    for table in TIMESTAMP_AND_SOFT:
        for column in ("deleted_at", "updated_at", "created_at"):
            if column_exists(conn, table, column):
                op.drop_column(table, column)
    for table in SOFT_DELETE_ONLY:
        if column_exists(conn, table, "deleted_at"):
            op.drop_column(table, "deleted_at")
