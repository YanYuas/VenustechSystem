"""初始 schema —— **冻结的显式 DDL 基线**（49 张表 / 79 个索引）

冻结日期：2026-10-26
Revision ID: 0001
Revises:
Create Date: 2026-08-28

为什么改掉旧的"导入 Base 后按当前 ORM metadata 一次性建全部表"（D-05）：
  旧实现建的是「执行迁移那一刻代码里注册的全部模型」，因此 0001 会随 models/
  变化**静默改变**：同一个 revision 在不同 checkout 上产出不同 schema，历史
  不可复现；两种安装路径（新装 vs 老库升级）会得到两份不同 schema（实测升级库
  缺 11 个 ORM 索引）。现在 0001 是显式 DDL 快照，revision id 与 down_revision
  保持不变，因此已升级到 0020 的库完全不受影响。

生成方式（可复现，不是手写）：
  1. 空 SQLite + 临时 alembic 配置（script_location 指向临时目录）
       alembic revision --autogenerate -m baseline
     产出 create_table/create_index 全集；
  2. 用 .arch-audit/migration/gen_baseline.py 转成静态 DDL：
     表块按 `Base.metadata.sorted_tables`（依赖序）排列、batch 块展开为
     普通 op.create_index、downgrade 生成显式逆序 drop；
  3. 校验：`.arch-audit/migration/verify_baseline.py` 比对
     「0001 建出的库」与「导入 Base 后按 metadata 建出的库」的表/列/类型/
     nullable/默认值/索引，必须零差异；`tests/test_migration_integrity.py`
     再对 ORM metadata 做一次三方对账。

维护约定（勿回退）：
  - **禁止**在本文件重新引入 SQLAlchemy 的 metadata 批量建表/删表 API；
  - 本文件是历史快照，**不要再往里加表/列**：新增 schema 走新迁移；
  - 建表/建索引带 table_exists 守卫，是为了让 0001 在「已有部分手工表的库」
    （如 data_smoke）上也能安全重入；列/索引级的最终对账由 0021 负责。
"""
from alembic import op  # noqa: E402
import sqlalchemy as sa  # noqa: E402

from app.migration_helpers import table_exists  # noqa: E402
from app.models.types import JSONType, StringListType  # noqa: E402,F401

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """按依赖序建全部表与索引（幂等：已存在的表整块跳过）。"""
    conn = op.get_bind()

    if not table_exists(conn, 'audit_logs'):
        op.create_table('audit_logs',
            sa.Column('user_id', sa.String(length=36), nullable=False),
            sa.Column('action', sa.String(length=64), nullable=False),
            sa.Column('target', sa.String(length=200), nullable=True),
            sa.Column('ok', sa.Boolean(), nullable=False),
            sa.Column('detail', sa.Text(), nullable=True),
            sa.Column('ip', sa.String(length=64), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint('id')
            )
        op.create_index('ix_audit_logs_action', 'audit_logs', ['action'], unique=False)
        op.create_index('ix_audit_logs_user_created', 'audit_logs', ['user_id', 'created_at'], unique=False)
        op.create_index('ix_audit_logs_user_id', 'audit_logs', ['user_id'], unique=False)

    if not table_exists(conn, 'settings_history'):
        op.create_table('settings_history',
            sa.Column('user_id', sa.String(length=36), nullable=False),
            sa.Column('key', sa.String(length=200), nullable=False),
            sa.Column('old_value', sa.Text(), nullable=True),
            sa.Column('new_value', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint('id')
            )
        op.create_index('ix_settings_history_key', 'settings_history', ['key'], unique=False)
        op.create_index('ix_settings_history_user_created', 'settings_history', ['user_id', 'created_at'], unique=False)

    if not table_exists(conn, 'users'):
        op.create_table('users',
            sa.Column('username', sa.String(length=50), nullable=False),
            sa.Column('nickname', sa.String(length=50), nullable=False),
            sa.Column('avatar_path', sa.String(length=500), nullable=True),
            sa.Column('api_key_encrypted', sa.Text(), nullable=True),
            sa.Column('theme', sa.String(length=20), nullable=False),
            sa.Column('automation_level', sa.String(length=10), nullable=False),
            sa.Column('pet_position', JSONType(), nullable=True),
            sa.Column('pet_topmost', sa.Boolean(), nullable=False),
            sa.Column('inspiration_probability', sa.Integer(), nullable=False),
            sa.Column('ai_enabled', sa.Boolean(), nullable=False),
            sa.Column('language', sa.String(length=20), nullable=False),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('username')
            )

    if not table_exists(conn, 'workflows'):
        op.create_table('workflows',
            sa.Column('name', sa.String(length=200), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('icon', sa.String(length=50), nullable=True),
            sa.Column('category', sa.String(length=50), nullable=True),
            sa.Column('scenario', sa.String(length=200), nullable=True),
            sa.Column('config', JSONType(), nullable=False),
            sa.Column('is_preset', sa.Boolean(), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False),
            sa.Column('use_count', sa.Integer(), nullable=False),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint('id')
            )
        op.create_index('idx_workflows_category', 'workflows', ['category'], unique=False)
        op.create_index('idx_workflows_is_preset', 'workflows', ['is_preset'], unique=False)

    if not table_exists(conn, 'avatar_configs'):
        op.create_table('avatar_configs',
            sa.Column('user_id', sa.String(length=36), nullable=False),
            sa.Column('automation_level', sa.String(length=10), nullable=False),
            sa.Column('local_model_enabled', sa.Boolean(), nullable=False),
            sa.Column('local_model_provider', sa.String(length=20), nullable=True),
            sa.Column('local_model_name', sa.String(length=100), nullable=True),
            sa.Column('local_model_url', sa.String(length=200), nullable=True),
            sa.Column('cloud_model_enabled', sa.Boolean(), nullable=False),
            sa.Column('cloud_model_provider', sa.String(length=20), nullable=True),
            sa.Column('cloud_model_name', sa.String(length=100), nullable=True),
            sa.Column('cloud_api_key', sa.String(length=200), nullable=True),
            sa.Column('persona_name', sa.String(length=50), nullable=False),
            sa.Column('persona_setting', sa.Text(), nullable=True),
            sa.Column('inspiration_enabled', sa.Boolean(), nullable=False),
            sa.Column('inspiration_frequency', sa.String(length=20), nullable=False),
            sa.Column('inspiration_domains', JSONType(), nullable=False),
            sa.Column('reply_length', sa.String(length=20), nullable=False),
            sa.Column('language_style', sa.String(length=20), nullable=False),
            sa.Column('creativity', sa.Float(), nullable=False),
            sa.Column('operation_overrides', JSONType(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('user_id')
            )

    if not table_exists(conn, 'avatar_inspirations'):
        op.create_table('avatar_inspirations',
            sa.Column('user_id', sa.String(length=36), nullable=False),
            sa.Column('title', sa.String(length=200), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('domain', sa.String(length=50), nullable=True),
            sa.Column('estimated_value', sa.String(length=100), nullable=True),
            sa.Column('prompt', sa.Text(), nullable=True),
            sa.Column('result', sa.Text(), nullable=True),
            sa.Column('status', sa.String(length=20), nullable=False),
            sa.Column('feedback', sa.String(length=20), nullable=True),
            sa.Column('batch_id', sa.String(length=36), nullable=True),
            sa.Column('source_type', sa.String(length=20), nullable=False),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
            )
        op.create_index('idx_avatar_inspirations_status', 'avatar_inspirations', ['status'], unique=False)
        op.create_index('idx_avatar_inspirations_user', 'avatar_inspirations', ['user_id'], unique=False)

    if not table_exists(conn, 'avatar_memories'):
        op.create_table('avatar_memories',
            sa.Column('user_id', sa.String(length=36), nullable=False),
            sa.Column('memory_type', sa.String(length=20), nullable=False),
            sa.Column('identity_id', sa.String(length=36), nullable=True),
            sa.Column('category', sa.String(length=50), nullable=True),
            sa.Column('title', sa.String(length=200), nullable=False),
            sa.Column('content', sa.Text(), nullable=True),
            sa.Column('tags', JSONType(), nullable=False),
            sa.Column('source', sa.String(length=100), nullable=True),
            sa.Column('source_id', sa.String(length=36), nullable=True),
            sa.Column('confidence', sa.Float(), nullable=False),
            sa.Column('is_verified', sa.Boolean(), nullable=False),
            sa.Column('importance', sa.Integer(), nullable=False),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
            )
        op.create_index('idx_avatar_memories_category', 'avatar_memories', ['category'], unique=False)
        op.create_index('idx_avatar_memories_user_type', 'avatar_memories', ['user_id', 'memory_type'], unique=False)
        op.create_index('ix_avatar_memories_identity_id', 'avatar_memories', ['identity_id'], unique=False)

    if not table_exists(conn, 'diaries'):
        op.create_table('diaries',
            sa.Column('user_id', sa.String(length=36), nullable=False),
            sa.Column('dimension', sa.String(length=20), nullable=True),
            sa.Column('identity_id', sa.String(length=36), nullable=True),
            sa.Column('title', sa.String(length=200), nullable=True),
            sa.Column('content', sa.Text(), nullable=True),
            sa.Column('diary_date', sa.Date(), nullable=False),
            sa.Column('tags', JSONType(), nullable=False),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
            )
        op.create_index('idx_diaries_user_date', 'diaries', ['user_id', 'diary_date'], unique=False)
        op.create_index('ix_diaries_identity_id', 'diaries', ['identity_id'], unique=False)

    if not table_exists(conn, 'domains'):
        op.create_table('domains',
            sa.Column('user_id', sa.String(length=36), nullable=False),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('icon', sa.String(length=50), nullable=True),
            sa.Column('color', sa.String(length=20), nullable=True),
            sa.Column('sort_order', sa.Integer(), nullable=False),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
            )
        op.create_index('idx_domains_user', 'domains', ['user_id'], unique=False)

    if not table_exists(conn, 'folders'):
        op.create_table('folders',
            sa.Column('user_id', sa.String(length=36), nullable=False),
            sa.Column('name', sa.String(length=200), nullable=False),
            sa.Column('parent_id', sa.String(length=36), nullable=True),
            sa.Column('sort_order', sa.Integer(), nullable=False),
            sa.Column('is_inbox', sa.Boolean(), nullable=False),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['parent_id'], ['folders.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
            )
        op.create_index('idx_folders_user_name_parent', 'folders', ['user_id', 'parent_id', 'name'], unique=True, sqlite_where=sa.text('deleted_at IS NULL'))

    if not table_exists(conn, 'growth_events'):
        op.create_table('growth_events',
            sa.Column('user_id', sa.String(length=36), nullable=False),
            sa.Column('source_key', sa.String(length=200), nullable=False),
            sa.Column('event_type', sa.String(length=50), nullable=False),
            sa.Column('exp', sa.Integer(), nullable=False),
            sa.Column('label', sa.String(length=200), nullable=True),
            sa.Column('skill_cat_ids', JSONType(), nullable=True),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
            )
        op.create_index('idx_growth_events_source', 'growth_events', ['user_id', 'source_key'], unique=True)
        op.create_index('idx_growth_events_user', 'growth_events', ['user_id'], unique=False)

    if not table_exists(conn, 'growth_states'):
        op.create_table('growth_states',
            sa.Column('user_id', sa.String(length=36), nullable=False),
            sa.Column('exp', sa.Integer(), nullable=False),
            sa.Column('level', sa.Integer(), nullable=False),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
            )
        op.create_index('idx_growth_states_user', 'growth_states', ['user_id'], unique=True)

    if not table_exists(conn, 'habits'):
        op.create_table('habits',
            sa.Column('user_id', sa.String(length=36), nullable=False),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('icon', sa.String(length=50), nullable=True),
            sa.Column('color', sa.String(length=20), nullable=True),
            sa.Column('frequency', sa.String(length=20), nullable=False),
            sa.Column('target_per_week', sa.Integer(), nullable=False),
            sa.Column('reminder_time', sa.Time(), nullable=True),
            sa.Column('goal_days', sa.Integer(), nullable=True),
            sa.Column('status', sa.String(length=20), nullable=False),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
            )
        op.create_index('idx_habits_user_status', 'habits', ['user_id', 'status'], unique=False)

    if not table_exists(conn, 'identities'):
        op.create_table('identities',
            sa.Column('user_id', sa.String(length=36), nullable=False),
            sa.Column('name', sa.String(length=60), nullable=False),
            sa.Column('slug', sa.String(length=60), nullable=False),
            sa.Column('color_token', sa.String(length=40), nullable=False),
            sa.Column('icon', sa.String(length=40), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('sort_order', sa.Integer(), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('user_id', 'slug', name='uq_identities_user_slug')
            )
        op.create_index('ix_identities_user_id', 'identities', ['user_id'], unique=False)

    if not table_exists(conn, 'inbox_items'):
        op.create_table('inbox_items',
            sa.Column('user_id', sa.String(length=36), nullable=False),
            sa.Column('content_type', sa.String(length=20), nullable=False),
            sa.Column('identity_id', sa.String(length=36), nullable=True),
            sa.Column('content', sa.Text(), nullable=True),
            sa.Column('title', sa.String(length=500), nullable=True),
            sa.Column('preview_url', sa.String(length=1000), nullable=True),
            sa.Column('file_path', sa.String(length=1000), nullable=True),
            sa.Column('source', sa.String(length=500), nullable=True),
            sa.Column('tags', JSONType(), nullable=False),
            sa.Column('status', sa.String(length=20), nullable=False),
            sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
            )
        op.create_index('idx_inbox_user_status', 'inbox_items', ['user_id', 'status'], unique=False)
        op.create_index('ix_inbox_items_identity_id', 'inbox_items', ['identity_id'], unique=False)

    if not table_exists(conn, 'mood_logs'):
        op.create_table('mood_logs',
            sa.Column('user_id', sa.String(length=36), nullable=False),
            sa.Column('score', sa.Integer(), nullable=False),
            sa.Column('tags', JSONType(), nullable=False),
            sa.Column('content', sa.Text(), nullable=True),
            sa.Column('logged_date', sa.Date(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
            )
        op.create_index('idx_mood_logs_user_date', 'mood_logs', ['user_id', 'logged_date'], unique=False)

    if not table_exists(conn, 'notifications'):
        op.create_table('notifications',
            sa.Column('user_id', sa.String(length=36), nullable=False),
            sa.Column('type', sa.String(length=20), nullable=False),
            sa.Column('title', sa.String(length=200), nullable=False),
            sa.Column('content', sa.Text(), nullable=True),
            sa.Column('is_read', sa.Boolean(), nullable=False),
            sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('source_type', sa.String(length=30), nullable=True),
            sa.Column('source_id', sa.String(length=36), nullable=True),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
            )
        op.create_index('ix_notifications_is_read', 'notifications', ['is_read'], unique=False)
        op.create_index('ix_notifications_user_id', 'notifications', ['user_id'], unique=False)

    if not table_exists(conn, 'pet_avatars'):
        op.create_table('pet_avatars',
            sa.Column('user_id', sa.String(length=36), nullable=False),
            sa.Column('name', sa.String(length=50), nullable=False),
            sa.Column('description', sa.String(length=200), nullable=True),
            sa.Column('avatar_type', sa.String(length=20), nullable=False),
            sa.Column('image_url', sa.String(length=500), nullable=True),
            sa.Column('mode', sa.String(length=20), nullable=False),
            sa.Column('eye_position', JSONType(), nullable=False),
            sa.Column('mouth_position', JSONType(), nullable=False),
            sa.Column('action_frames', JSONType(), nullable=False),
            sa.Column('tags', JSONType(), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False),
            sa.Column('sort_order', sa.Integer(), nullable=False),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
            )
        op.create_index('idx_pet_avatars_user', 'pet_avatars', ['user_id'], unique=False)

    if not table_exists(conn, 'pet_configs'):
        op.create_table('pet_configs',
            sa.Column('user_id', sa.String(length=36), nullable=False),
            sa.Column('enabled', sa.Boolean(), nullable=False),
            sa.Column('size', sa.String(length=10), nullable=False),
            sa.Column('opacity', sa.Float(), nullable=False),
            sa.Column('always_on_top', sa.Boolean(), nullable=False),
            sa.Column('auto_start', sa.Boolean(), nullable=False),
            sa.Column('position_x', sa.Integer(), nullable=False),
            sa.Column('position_y', sa.Integer(), nullable=False),
            sa.Column('current_avatar_id', sa.String(length=36), nullable=True),
            sa.Column('state_awareness_enabled', sa.Boolean(), nullable=False),
            sa.Column('action_switch_interval', sa.Integer(), nullable=False),
            sa.Column('show_bubble', sa.Boolean(), nullable=False),
            sa.Column('bubble_duration', sa.Integer(), nullable=False),
            sa.Column('click_interaction', sa.Boolean(), nullable=False),
            sa.Column('draggable', sa.Boolean(), nullable=False),
            sa.Column('right_click_menu', sa.Boolean(), nullable=False),
            sa.Column('tts_enabled', sa.Boolean(), nullable=False),
            sa.Column('tts_voice', sa.String(length=50), nullable=True),
            sa.Column('tts_rate', sa.Float(), nullable=False),
            sa.Column('tts_pitch', sa.Float(), nullable=False),
            sa.Column('tts_volume', sa.Float(), nullable=False),
            sa.Column('speak_scene', sa.String(length=20), nullable=False),
            sa.Column('intimacy', sa.Integer(), nullable=False),
            sa.Column('satiety', sa.Integer(), nullable=False),
            sa.Column('mood', sa.Integer(), nullable=False),
            sa.Column('energy', sa.Integer(), nullable=False),
            sa.Column('stats_updated_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('user_id')
            )

    if not table_exists(conn, 'projects'):
        op.create_table('projects',
            sa.Column('user_id', sa.String(length=36), nullable=False),
            sa.Column('name', sa.String(length=200), nullable=False),
            sa.Column('identity_id', sa.String(length=36), nullable=True),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('color', sa.String(length=20), nullable=False),
            sa.Column('status', sa.String(length=20), nullable=False),
            sa.Column('due_date', sa.Date(), nullable=True),
            sa.Column('sort_order', sa.Integer(), nullable=False),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
            )
        op.create_index('ix_projects_identity_id', 'projects', ['identity_id'], unique=False)
        op.create_index('ix_projects_user_id', 'projects', ['user_id'], unique=False)

    if not table_exists(conn, 'prompt_templates'):
        op.create_table('prompt_templates',
            sa.Column('user_id', sa.String(length=36), nullable=False),
            sa.Column('name', sa.String(length=200), nullable=False),
            sa.Column('category', sa.String(length=50), nullable=True),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('role_setting', sa.Text(), nullable=True),
            sa.Column('task_description', sa.Text(), nullable=True),
            sa.Column('constraints', sa.Text(), nullable=True),
            sa.Column('output_format', sa.Text(), nullable=True),
            sa.Column('variables', JSONType(), nullable=False),
            sa.Column('use_count', sa.Integer(), nullable=False),
            sa.Column('rating', sa.Float(), nullable=True),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
            )
        op.create_index('idx_prompts_user_category', 'prompt_templates', ['user_id', 'category'], unique=False)

    if not table_exists(conn, 'quick_todos'):
        op.create_table('quick_todos',
            sa.Column('user_id', sa.String(length=36), nullable=False),
            sa.Column('title', sa.String(length=200), nullable=False),
            sa.Column('completed', sa.Boolean(), nullable=False),
            sa.Column('sort_order', sa.Integer(), nullable=False),
            sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
            )
        op.create_index('idx_quick_todos_user', 'quick_todos', ['user_id'], unique=False)

    if not table_exists(conn, 'reminders'):
        op.create_table('reminders',
            sa.Column('user_id', sa.String(length=36), nullable=False),
            sa.Column('title', sa.String(length=200), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('remind_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('type', sa.String(length=20), nullable=False),
            sa.Column('dismissed', sa.Boolean(), nullable=False),
            sa.Column('repeat', sa.String(length=20), nullable=False),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
            )
        op.create_index('idx_reminders_user_time', 'reminders', ['user_id', 'remind_at'], unique=False)

    if not table_exists(conn, 'settings'):
        op.create_table('settings',
            sa.Column('user_id', sa.String(length=36), nullable=False),
            sa.Column('key', sa.String(length=100), nullable=False),
            sa.Column('value', sa.Text(), nullable=True),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('user_id', 'key')
            )

    if not table_exists(conn, 'skill_stats'):
        op.create_table('skill_stats',
            sa.Column('user_id', sa.String(length=36), nullable=False),
            sa.Column('category_id', sa.String(length=50), nullable=False),
            sa.Column('count', sa.Integer(), nullable=False),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
            )
        op.create_index('idx_skill_stats_user_cat', 'skill_stats', ['user_id', 'category_id'], unique=True)

    if not table_exists(conn, 'skills'):
        op.create_table('skills',
            sa.Column('user_id', sa.String(length=36), nullable=False),
            sa.Column('name', sa.String(length=200), nullable=False),
            sa.Column('category', sa.String(length=100), nullable=True),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('methodology', sa.Text(), nullable=True),
            sa.Column('proficiency', sa.String(length=20), nullable=False),
            sa.Column('tags', JSONType(), nullable=False),
            sa.Column('use_count', sa.Integer(), nullable=False),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
            )
        op.create_index('idx_skills_user_category', 'skills', ['user_id', 'category'], unique=False)

    if not table_exists(conn, 'sops'):
        op.create_table('sops',
            sa.Column('user_id', sa.String(length=36), nullable=False),
            sa.Column('name', sa.String(length=200), nullable=False),
            sa.Column('category', sa.String(length=100), nullable=True),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('steps', JSONType(), nullable=False),
            sa.Column('checklist', JSONType(), nullable=False),
            sa.Column('tags', JSONType(), nullable=False),
            sa.Column('use_count', sa.Integer(), nullable=False),
            sa.Column('version', sa.Integer(), nullable=False),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
            )
        op.create_index('idx_sops_user_category', 'sops', ['user_id', 'category'], unique=False)

    if not table_exists(conn, 'study_plans'):
        op.create_table('study_plans',
            sa.Column('user_id', sa.String(length=36), nullable=False),
            sa.Column('name', sa.String(length=200), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('target_date', sa.Date(), nullable=True),
            sa.Column('estimated_hours', sa.Integer(), nullable=True),
            sa.Column('progress', sa.Integer(), nullable=False),
            sa.Column('status', sa.String(length=20), nullable=False),
            sa.Column('config', JSONType(), nullable=False),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
            )
        op.create_index('idx_study_plans_user_status', 'study_plans', ['user_id', 'status'], unique=False)

    if not table_exists(conn, 'templates'):
        op.create_table('templates',
            sa.Column('user_id', sa.String(length=36), nullable=False),
            sa.Column('name', sa.String(length=200), nullable=False),
            sa.Column('category', sa.String(length=50), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('content', sa.Text(), nullable=False),
            sa.Column('variables', JSONType(), nullable=False),
            sa.Column('tags', JSONType(), nullable=False),
            sa.Column('is_builtin', sa.Boolean(), nullable=False),
            sa.Column('use_count', sa.Integer(), nullable=False),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
            )
        op.create_index('idx_templates_user_category', 'templates', ['user_id', 'category'], unique=False)

    if not table_exists(conn, 'vault_config'):
        op.create_table('vault_config',
            sa.Column('user_id', sa.String(length=36), nullable=False),
            sa.Column('salt', sa.String(length=64), nullable=False),
            sa.Column('verifier', sa.Text(), nullable=False),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
            )
        op.create_index('uq_vault_config_user', 'vault_config', ['user_id'], unique=True)

    if not table_exists(conn, 'vault_items'):
        op.create_table('vault_items',
            sa.Column('user_id', sa.String(length=36), nullable=False),
            sa.Column('name', sa.String(length=200), nullable=False),
            sa.Column('category', sa.String(length=20), nullable=False),
            sa.Column('username', sa.String(length=200), nullable=True),
            sa.Column('url', sa.String(length=500), nullable=True),
            sa.Column('secret_encrypted', sa.Text(), nullable=True),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('identity_id', sa.String(length=36), nullable=True),
            sa.Column('last_accessed_at', sa.DateTime(), nullable=True),
            sa.Column('action_type', sa.String(length=20), nullable=False),
            sa.Column('action_host', sa.String(length=255), nullable=True),
            sa.Column('action_user', sa.String(length=255), nullable=True),
            sa.Column('action_port', sa.String(length=10), nullable=True),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
            )
        op.create_index('ix_vault_items_identity_id', 'vault_items', ['identity_id'], unique=False)
        op.create_index('ix_vault_items_user_id', 'vault_items', ['user_id'], unique=False)

    if not table_exists(conn, 'workflow_applications'):
        op.create_table('workflow_applications',
            sa.Column('workflow_id', sa.String(length=36), nullable=False),
            sa.Column('user_id', sa.String(length=36), nullable=False),
            sa.Column('params', JSONType(), nullable=False),
            sa.Column('status', sa.String(length=20), nullable=False),
            sa.Column('result_summary', sa.Text(), nullable=True),
            sa.Column('applied_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['workflow_id'], ['workflows.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
            )
        op.create_index('idx_workflow_apps_user', 'workflow_applications', ['user_id'], unique=False)
        op.create_index('idx_workflow_apps_workflow', 'workflow_applications', ['workflow_id'], unique=False)

    if not table_exists(conn, 'workspace_roots'):
        op.create_table('workspace_roots',
            sa.Column('user_id', sa.String(length=36), nullable=False),
            sa.Column('path', sa.String(length=500), nullable=False),
            sa.Column('label', sa.String(length=100), nullable=True),
            sa.Column('identity_id', sa.String(length=36), nullable=True),
            sa.Column('enabled', sa.Boolean(), nullable=False),
            sa.Column('scan_status', sa.String(length=10), nullable=False),
            sa.Column('scan_error', sa.Text(), nullable=True),
            sa.Column('last_scanned_at', sa.DateTime(), nullable=True),
            sa.Column('file_count', sa.Integer(), nullable=False),
            sa.Column('total_size', sa.Integer(), nullable=False),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('user_id', 'path', name='uq_workspace_roots_user_path')
            )
        op.create_index('ix_workspace_roots_identity_id', 'workspace_roots', ['identity_id'], unique=False)
        op.create_index('ix_workspace_roots_user_id', 'workspace_roots', ['user_id'], unique=False)

    if not table_exists(conn, 'conversations'):
        op.create_table('conversations',
            sa.Column('user_id', sa.String(length=36), nullable=False),
            sa.Column('project_id', sa.String(length=36), nullable=True),
            sa.Column('title', sa.String(length=200), nullable=True),
            sa.Column('scene', sa.String(length=30), nullable=False),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
            )
        op.create_index('ix_conversations_project_id', 'conversations', ['project_id'], unique=False)
        op.create_index('ix_conversations_user_id', 'conversations', ['user_id'], unique=False)

    if not table_exists(conn, 'documents'):
        op.create_table('documents',
            sa.Column('user_id', sa.String(length=36), nullable=False),
            sa.Column('title', sa.String(length=500), nullable=False),
            sa.Column('identity_id', sa.String(length=36), nullable=True),
            sa.Column('content', sa.Text(), nullable=True),
            sa.Column('folder_id', sa.String(length=36), nullable=True),
            sa.Column('project_id', sa.String(length=36), nullable=True),
            sa.Column('tags', StringListType(), nullable=False),
            sa.Column('summary', sa.Text(), nullable=True),
            sa.Column('ai_suggested_tags', StringListType(), nullable=False),
            sa.Column('version', sa.Integer(), nullable=False),
            sa.Column('word_count', sa.Integer(), nullable=False),
            sa.Column('file_path', sa.String(length=500), nullable=True),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['folder_id'], ['folders.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
            )
        op.create_index('ix_documents_folder_id', 'documents', ['folder_id'], unique=False)
        op.create_index('ix_documents_identity_id', 'documents', ['identity_id'], unique=False)
        op.create_index('ix_documents_project_id', 'documents', ['project_id'], unique=False)
        op.create_index('ix_documents_user_id', 'documents', ['user_id'], unique=False)

    if not table_exists(conn, 'flashcards'):
        op.create_table('flashcards',
            sa.Column('user_id', sa.String(length=36), nullable=False),
            sa.Column('plan_id', sa.String(length=36), nullable=True),
            sa.Column('front', sa.Text(), nullable=False),
            sa.Column('back', sa.Text(), nullable=False),
            sa.Column('card_type', sa.String(length=20), nullable=False),
            sa.Column('category', sa.String(length=100), nullable=True),
            sa.Column('tags', JSONType(), nullable=False),
            sa.Column('difficulty', sa.Integer(), nullable=False),
            sa.Column('ef', sa.Float(), nullable=False),
            sa.Column('interval', sa.Integer(), nullable=False),
            sa.Column('repetition', sa.Integer(), nullable=False),
            sa.Column('next_review', sa.Date(), nullable=True),
            sa.Column('last_reviewed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('review_count', sa.Integer(), nullable=False),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['plan_id'], ['study_plans.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
            )
        op.create_index('idx_flashcards_user_category', 'flashcards', ['user_id', 'category'], unique=False)
        op.create_index('idx_flashcards_user_next_review', 'flashcards', ['user_id', 'next_review'], unique=False)

    if not table_exists(conn, 'habit_checkins'):
        op.create_table('habit_checkins',
            sa.Column('habit_id', sa.String(length=36), nullable=False),
            sa.Column('user_id', sa.String(length=36), nullable=False),
            sa.Column('checkin_date', sa.Date(), nullable=False),
            sa.Column('note', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['habit_id'], ['habits.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('habit_id', 'checkin_date', name='uq_habit_checkin')
            )
        op.create_index('idx_habit_checkins_user_date', 'habit_checkins', ['user_id', 'checkin_date'], unique=False)

    if not table_exists(conn, 'project_memories'):
        op.create_table('project_memories',
            sa.Column('user_id', sa.String(length=36), nullable=False),
            sa.Column('project_id', sa.String(length=36), nullable=True),
            sa.Column('identity_id', sa.String(length=36), nullable=True),
            sa.Column('name', sa.String(length=200), nullable=False),
            sa.Column('summary', sa.Text(), nullable=True),
            sa.Column('successes', sa.Text(), nullable=True),
            sa.Column('failures', sa.Text(), nullable=True),
            sa.Column('extracted_assets', JSONType(), nullable=False),
            sa.Column('key_metrics', JSONType(), nullable=False),
            sa.Column('tags', JSONType(), nullable=False),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
            )
        op.create_index('idx_project_memories_project', 'project_memories', ['project_id'], unique=False)
        op.create_index('idx_project_memories_user', 'project_memories', ['user_id'], unique=False)
        op.create_index('ix_project_memories_identity_id', 'project_memories', ['identity_id'], unique=False)

    if not table_exists(conn, 'project_milestones'):
        op.create_table('project_milestones',
            sa.Column('project_id', sa.String(length=36), nullable=False),
            sa.Column('name', sa.String(length=200), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('target_date', sa.Date(), nullable=True),
            sa.Column('completed', sa.Boolean(), nullable=False),
            sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('task_ids', StringListType(), nullable=False),
            sa.Column('sort_order', sa.Integer(), nullable=False),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
            )
        op.create_index('ix_project_milestones_project_id', 'project_milestones', ['project_id'], unique=False)

    if not table_exists(conn, 'reviews'):
        op.create_table('reviews',
            sa.Column('user_id', sa.String(length=36), nullable=False),
            sa.Column('project_id', sa.String(length=36), nullable=True),
            sa.Column('identity_id', sa.String(length=36), nullable=True),
            sa.Column('type', sa.String(length=10), nullable=False),
            sa.Column('review_date', sa.Date(), nullable=False),
            sa.Column('data', JSONType(), nullable=False),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('user_id', 'type', 'review_date')
            )
        op.create_index('ix_reviews_identity_id', 'reviews', ['identity_id'], unique=False)
        op.create_index('ix_reviews_project_id', 'reviews', ['project_id'], unique=False)

    if not table_exists(conn, 'sop_versions'):
        op.create_table('sop_versions',
            sa.Column('sop_id', sa.String(length=36), nullable=False),
            sa.Column('version', sa.Integer(), nullable=False),
            sa.Column('content', JSONType(), nullable=False),
            sa.Column('change_note', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['sop_id'], ['sops.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
            )
        op.create_index('idx_sop_versions_sop', 'sop_versions', ['sop_id'], unique=False)

    if not table_exists(conn, 'study_time_logs'):
        op.create_table('study_time_logs',
            sa.Column('user_id', sa.String(length=36), nullable=False),
            sa.Column('plan_id', sa.String(length=36), nullable=True),
            sa.Column('subject', sa.String(length=200), nullable=True),
            sa.Column('duration', sa.Integer(), nullable=False),
            sa.Column('note', sa.Text(), nullable=True),
            sa.Column('source', sa.String(length=50), nullable=True),
            sa.Column('logged_date', sa.Date(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['plan_id'], ['study_plans.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
            )
        op.create_index('idx_study_time_user_date', 'study_time_logs', ['user_id', 'logged_date'], unique=False)
        op.create_index('ix_study_time_logs_logged_date', 'study_time_logs', ['logged_date'], unique=False)

    if not table_exists(conn, 'tasks'):
        op.create_table('tasks',
            sa.Column('user_id', sa.String(length=36), nullable=False),
            sa.Column('title', sa.String(length=500), nullable=False),
            sa.Column('identity_id', sa.String(length=36), nullable=True),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('status', sa.String(length=20), nullable=False),
            sa.Column('priority', sa.String(length=20), nullable=False),
            sa.Column('project_tag', sa.String(length=100), nullable=True),
            sa.Column('project_id', sa.String(length=36), nullable=True),
            sa.Column('due_date', sa.Date(), nullable=True),
            sa.Column('is_focus', sa.Boolean(), nullable=False),
            sa.Column('sort_order', sa.Integer(), nullable=False),
            sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('reminder_time', sa.DateTime(), nullable=True),
            sa.Column('recurrence', JSONType(), nullable=True),
            sa.Column('focus_duration', sa.Integer(), nullable=False),
            sa.Column('estimated_minutes', sa.Integer(), nullable=True),
            sa.Column('acceptance_criteria', sa.Text(), nullable=True),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
            )
        op.create_index('idx_tasks_unique_focus', 'tasks', ['user_id'], unique=True, sqlite_where=sa.text('is_focus = 1'))
        op.create_index('idx_tasks_user_due', 'tasks', ['user_id', 'due_date'], unique=False)
        op.create_index('idx_tasks_user_project', 'tasks', ['user_id', 'project_id'], unique=False)
        op.create_index('idx_tasks_user_status', 'tasks', ['user_id', 'status'], unique=False)
        op.create_index('ix_tasks_identity_id', 'tasks', ['identity_id'], unique=False)
        op.create_index('ix_tasks_project_id', 'tasks', ['project_id'], unique=False)
        op.create_index('ix_tasks_reminder_time', 'tasks', ['reminder_time'], unique=False)
        op.create_index('ix_tasks_status', 'tasks', ['status'], unique=False)

    if not table_exists(conn, 'workspace_files'):
        op.create_table('workspace_files',
            sa.Column('root_id', sa.String(length=36), nullable=False),
            sa.Column('rel_path', sa.String(length=500), nullable=False),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('ext', sa.String(length=30), nullable=True),
            sa.Column('is_dir', sa.Boolean(), nullable=False),
            sa.Column('size', sa.Integer(), nullable=False),
            sa.Column('mtime', sa.Float(), nullable=False),
            sa.Column('identity_id', sa.String(length=36), nullable=True),
            sa.Column('indexed_at', sa.DateTime(), nullable=True),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['root_id'], ['workspace_roots.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
            )
        op.create_index('ix_workspace_files_identity_id', 'workspace_files', ['identity_id'], unique=False)
        op.create_index('ix_workspace_files_root_id', 'workspace_files', ['root_id'], unique=False)

    if not table_exists(conn, 'backlinks'):
        op.create_table('backlinks',
            sa.Column('source_doc_id', sa.String(length=36), nullable=False),
            sa.Column('target_doc_id', sa.String(length=36), nullable=True),
            sa.Column('target_title', sa.String(length=500), nullable=True),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['source_doc_id'], ['documents.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['target_doc_id'], ['documents.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('source_doc_id', 'target_doc_id')
            )
        op.create_index('ix_backlinks_source_doc_id', 'backlinks', ['source_doc_id'], unique=False)
        op.create_index('ix_backlinks_target_doc_id', 'backlinks', ['target_doc_id'], unique=False)

    if not table_exists(conn, 'document_versions'):
        op.create_table('document_versions',
            sa.Column('document_id', sa.String(length=36), nullable=False),
            sa.Column('content', sa.Text(), nullable=False),
            sa.Column('version', sa.Integer(), nullable=False),
            sa.Column('word_count', sa.Integer(), nullable=False),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
            )
        op.create_index('ix_document_versions_document_id', 'document_versions', ['document_id'], unique=False)

    if not table_exists(conn, 'focus_sessions'):
        op.create_table('focus_sessions',
            sa.Column('task_id', sa.String(length=36), nullable=True),
            sa.Column('user_id', sa.String(length=36), nullable=False),
            sa.Column('start_time', sa.DateTime(timezone=True), nullable=False),
            sa.Column('end_time', sa.DateTime(timezone=True), nullable=True),
            sa.Column('duration', sa.Integer(), nullable=False),
            sa.Column('note', sa.String(length=500), nullable=True),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
            )
        op.create_index('ix_focus_sessions_task_id', 'focus_sessions', ['task_id'], unique=False)
        op.create_index('ix_focus_sessions_user_id', 'focus_sessions', ['user_id'], unique=False)

    if not table_exists(conn, 'messages'):
        op.create_table('messages',
            sa.Column('conversation_id', sa.String(length=36), nullable=False),
            sa.Column('role', sa.String(length=20), nullable=False),
            sa.Column('content', sa.Text(), nullable=False),
            sa.Column('tokens', sa.Integer(), nullable=True),
            sa.Column('referenced_doc_ids', StringListType(), nullable=False),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
            )
        op.create_index('ix_messages_conversation_id', 'messages', ['conversation_id'], unique=False)

    if not table_exists(conn, 'subtasks'):
        op.create_table('subtasks',
            sa.Column('task_id', sa.String(length=36), nullable=False),
            sa.Column('title', sa.String(length=500), nullable=False),
            sa.Column('completed', sa.Boolean(), nullable=False),
            sa.Column('sort_order', sa.Integer(), nullable=False),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
            )
        op.create_index('ix_subtasks_task_id', 'subtasks', ['task_id'], unique=False)
            # ### end Alembic commands ###

def downgrade() -> None:
    """显式 drop（逆依赖序）。downgrade base 的语义即「清空 0001 基线表」。"""
    op.drop_index('ix_subtasks_task_id', table_name='subtasks')
    op.drop_table('subtasks')

    op.drop_index('ix_messages_conversation_id', table_name='messages')
    op.drop_table('messages')

    op.drop_index('ix_focus_sessions_task_id', table_name='focus_sessions')
    op.drop_index('ix_focus_sessions_user_id', table_name='focus_sessions')
    op.drop_table('focus_sessions')

    op.drop_index('ix_document_versions_document_id', table_name='document_versions')
    op.drop_table('document_versions')

    op.drop_index('ix_backlinks_source_doc_id', table_name='backlinks')
    op.drop_index('ix_backlinks_target_doc_id', table_name='backlinks')
    op.drop_table('backlinks')

    op.drop_index('ix_workspace_files_identity_id', table_name='workspace_files')
    op.drop_index('ix_workspace_files_root_id', table_name='workspace_files')
    op.drop_table('workspace_files')

    op.drop_index('idx_tasks_unique_focus', table_name='tasks')
    op.drop_index('idx_tasks_user_due', table_name='tasks')
    op.drop_index('idx_tasks_user_project', table_name='tasks')
    op.drop_index('idx_tasks_user_status', table_name='tasks')
    op.drop_index('ix_tasks_identity_id', table_name='tasks')
    op.drop_index('ix_tasks_project_id', table_name='tasks')
    op.drop_index('ix_tasks_reminder_time', table_name='tasks')
    op.drop_index('ix_tasks_status', table_name='tasks')
    op.drop_table('tasks')

    op.drop_index('idx_study_time_user_date', table_name='study_time_logs')
    op.drop_index('ix_study_time_logs_logged_date', table_name='study_time_logs')
    op.drop_table('study_time_logs')

    op.drop_index('idx_sop_versions_sop', table_name='sop_versions')
    op.drop_table('sop_versions')

    op.drop_index('ix_reviews_identity_id', table_name='reviews')
    op.drop_index('ix_reviews_project_id', table_name='reviews')
    op.drop_table('reviews')

    op.drop_index('ix_project_milestones_project_id', table_name='project_milestones')
    op.drop_table('project_milestones')

    op.drop_index('idx_project_memories_project', table_name='project_memories')
    op.drop_index('idx_project_memories_user', table_name='project_memories')
    op.drop_index('ix_project_memories_identity_id', table_name='project_memories')
    op.drop_table('project_memories')

    op.drop_index('idx_habit_checkins_user_date', table_name='habit_checkins')
    op.drop_table('habit_checkins')

    op.drop_index('idx_flashcards_user_category', table_name='flashcards')
    op.drop_index('idx_flashcards_user_next_review', table_name='flashcards')
    op.drop_table('flashcards')

    op.drop_index('ix_documents_folder_id', table_name='documents')
    op.drop_index('ix_documents_identity_id', table_name='documents')
    op.drop_index('ix_documents_project_id', table_name='documents')
    op.drop_index('ix_documents_user_id', table_name='documents')
    op.drop_table('documents')

    op.drop_index('ix_conversations_project_id', table_name='conversations')
    op.drop_index('ix_conversations_user_id', table_name='conversations')
    op.drop_table('conversations')

    op.drop_index('ix_workspace_roots_identity_id', table_name='workspace_roots')
    op.drop_index('ix_workspace_roots_user_id', table_name='workspace_roots')
    op.drop_table('workspace_roots')

    op.drop_index('idx_workflow_apps_user', table_name='workflow_applications')
    op.drop_index('idx_workflow_apps_workflow', table_name='workflow_applications')
    op.drop_table('workflow_applications')

    op.drop_index('ix_vault_items_identity_id', table_name='vault_items')
    op.drop_index('ix_vault_items_user_id', table_name='vault_items')
    op.drop_table('vault_items')

    op.drop_index('uq_vault_config_user', table_name='vault_config')
    op.drop_table('vault_config')

    op.drop_index('idx_templates_user_category', table_name='templates')
    op.drop_table('templates')

    op.drop_index('idx_study_plans_user_status', table_name='study_plans')
    op.drop_table('study_plans')

    op.drop_index('idx_sops_user_category', table_name='sops')
    op.drop_table('sops')

    op.drop_index('idx_skills_user_category', table_name='skills')
    op.drop_table('skills')

    op.drop_index('idx_skill_stats_user_cat', table_name='skill_stats')
    op.drop_table('skill_stats')

    op.drop_table('settings')

    op.drop_index('idx_reminders_user_time', table_name='reminders')
    op.drop_table('reminders')

    op.drop_index('idx_quick_todos_user', table_name='quick_todos')
    op.drop_table('quick_todos')

    op.drop_index('idx_prompts_user_category', table_name='prompt_templates')
    op.drop_table('prompt_templates')

    op.drop_index('ix_projects_identity_id', table_name='projects')
    op.drop_index('ix_projects_user_id', table_name='projects')
    op.drop_table('projects')

    op.drop_table('pet_configs')

    op.drop_index('idx_pet_avatars_user', table_name='pet_avatars')
    op.drop_table('pet_avatars')

    op.drop_index('ix_notifications_is_read', table_name='notifications')
    op.drop_index('ix_notifications_user_id', table_name='notifications')
    op.drop_table('notifications')

    op.drop_index('idx_mood_logs_user_date', table_name='mood_logs')
    op.drop_table('mood_logs')

    op.drop_index('idx_inbox_user_status', table_name='inbox_items')
    op.drop_index('ix_inbox_items_identity_id', table_name='inbox_items')
    op.drop_table('inbox_items')

    op.drop_index('ix_identities_user_id', table_name='identities')
    op.drop_table('identities')

    op.drop_index('idx_habits_user_status', table_name='habits')
    op.drop_table('habits')

    op.drop_index('idx_growth_states_user', table_name='growth_states')
    op.drop_table('growth_states')

    op.drop_index('idx_growth_events_source', table_name='growth_events')
    op.drop_index('idx_growth_events_user', table_name='growth_events')
    op.drop_table('growth_events')

    op.drop_index('idx_folders_user_name_parent', table_name='folders')
    op.drop_table('folders')

    op.drop_index('idx_domains_user', table_name='domains')
    op.drop_table('domains')

    op.drop_index('idx_diaries_user_date', table_name='diaries')
    op.drop_index('ix_diaries_identity_id', table_name='diaries')
    op.drop_table('diaries')

    op.drop_index('idx_avatar_memories_category', table_name='avatar_memories')
    op.drop_index('idx_avatar_memories_user_type', table_name='avatar_memories')
    op.drop_index('ix_avatar_memories_identity_id', table_name='avatar_memories')
    op.drop_table('avatar_memories')

    op.drop_index('idx_avatar_inspirations_status', table_name='avatar_inspirations')
    op.drop_index('idx_avatar_inspirations_user', table_name='avatar_inspirations')
    op.drop_table('avatar_inspirations')

    op.drop_table('avatar_configs')

    op.drop_index('idx_workflows_category', table_name='workflows')
    op.drop_index('idx_workflows_is_preset', table_name='workflows')
    op.drop_table('workflows')

    op.drop_table('users')

    op.drop_index('ix_settings_history_key', table_name='settings_history')
    op.drop_index('ix_settings_history_user_created', table_name='settings_history')
    op.drop_table('settings_history')

    op.drop_index('ix_audit_logs_action', table_name='audit_logs')
    op.drop_index('ix_audit_logs_user_created', table_name='audit_logs')
    op.drop_index('ix_audit_logs_user_id', table_name='audit_logs')
    op.drop_table('audit_logs')
