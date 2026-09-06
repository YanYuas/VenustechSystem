# ============================================================
# 0008_new_modules — 二期4大新模块数据表
# - 资源中心：inbox_items / templates / domains
# - 学习成长：study_plans / flashcards / study_time_logs
# - 生活记录：habits / habit_checkins / mood_logs / diaries
# - 长期资产库：sops / sop_versions / prompt_templates / skills / project_memories
# 幂等：全部检查_table_exists后再创建
# ============================================================
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def _table_exists(conn, name: str) -> bool:
    return conn.execute(
        sa.text("SELECT name FROM sqlite_master WHERE type='table' AND name=:n"),
        {"n": name},
    ).fetchone() is not None


def upgrade() -> None:
    conn = op.get_bind()

    # ===== 资源中心 =====
    if not _table_exists(conn, "inbox_items"):
        op.create_table(
            "inbox_items",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("content_type", sa.String(20), nullable=False),
            sa.Column("content", sa.Text(), nullable=True),
            sa.Column("title", sa.String(500), nullable=True),
            sa.Column("preview_url", sa.String(1000), nullable=True),
            sa.Column("file_path", sa.String(1000), nullable=True),
            sa.Column("source", sa.String(500), nullable=True),
            sa.Column("tags", sa.Text(), nullable=True),
            sa.Column("status", sa.String(20), server_default="pending"),
            sa.Column("processed_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
        op.create_index("idx_inbox_user_status", "inbox_items", ["user_id", "status"])

    if not _table_exists(conn, "templates"):
        op.create_table(
            "templates",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("category", sa.String(50), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("variables", sa.Text(), nullable=True),
            sa.Column("tags", sa.Text(), nullable=True),
            sa.Column("is_builtin", sa.Boolean(), server_default="0"),
            sa.Column("use_count", sa.Integer(), server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
        op.create_index("idx_templates_user_category", "templates", ["user_id", "category"])

    if not _table_exists(conn, "domains"):
        op.create_table(
            "domains",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("icon", sa.String(50), nullable=True),
            sa.Column("color", sa.String(20), nullable=True),
            sa.Column("sort_order", sa.Integer(), server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )

    # ===== 学习成长 =====
    if not _table_exists(conn, "study_plans"):
        op.create_table(
            "study_plans",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("target_date", sa.Date(), nullable=True),
            sa.Column("estimated_hours", sa.Integer(), nullable=True),
            sa.Column("progress", sa.Integer(), server_default="0"),
            sa.Column("status", sa.String(20), server_default="active"),
            sa.Column("config", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
        op.create_index("idx_study_plans_user_status", "study_plans", ["user_id", "status"])

    if not _table_exists(conn, "flashcards"):
        op.create_table(
            "flashcards",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("plan_id", sa.String(36), sa.ForeignKey("study_plans.id", ondelete="SET NULL"), nullable=True),
            sa.Column("front", sa.Text(), nullable=False),
            sa.Column("back", sa.Text(), nullable=False),
            sa.Column("card_type", sa.String(20), server_default="qa"),
            sa.Column("category", sa.String(100), nullable=True),
            sa.Column("tags", sa.Text(), nullable=True),
            sa.Column("difficulty", sa.Integer(), server_default="3"),
            sa.Column("ef", sa.Float(), server_default="2.5"),
            sa.Column("interval", sa.Integer(), server_default="0"),
            sa.Column("repetition", sa.Integer(), server_default="0"),
            sa.Column("next_review", sa.Date(), nullable=True),
            sa.Column("last_reviewed_at", sa.DateTime(), nullable=True),
            sa.Column("review_count", sa.Integer(), server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
        op.create_index("idx_flashcards_user_next_review", "flashcards", ["user_id", "next_review"])

    if not _table_exists(conn, "study_time_logs"):
        op.create_table(
            "study_time_logs",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("plan_id", sa.String(36), sa.ForeignKey("study_plans.id", ondelete="SET NULL"), nullable=True),
            sa.Column("subject", sa.String(200), nullable=True),
            sa.Column("duration", sa.Integer(), nullable=False),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("source", sa.String(50), nullable=True),
            sa.Column("logged_date", sa.Date(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
        op.create_index("idx_study_time_user_date", "study_time_logs", ["user_id", "logged_date"])

    # ===== 生活记录 =====
    if not _table_exists(conn, "habits"):
        op.create_table(
            "habits",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("icon", sa.String(50), nullable=True),
            sa.Column("color", sa.String(20), nullable=True),
            sa.Column("frequency", sa.String(20), server_default="daily"),
            sa.Column("target_per_week", sa.Integer(), server_default="7"),
            sa.Column("reminder_time", sa.Time(), nullable=True),
            sa.Column("goal_days", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(20), server_default="active"),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )

    if not _table_exists(conn, "habit_checkins"):
        op.create_table(
            "habit_checkins",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("habit_id", sa.String(36), sa.ForeignKey("habits.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("checkin_date", sa.Date(), nullable=False),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("habit_id", "checkin_date", name="uq_habit_checkin"),
        )
        op.create_index("idx_habit_checkins_user_date", "habit_checkins", ["user_id", "checkin_date"])

    if not _table_exists(conn, "mood_logs"):
        op.create_table(
            "mood_logs",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("score", sa.Integer(), nullable=False),
            sa.Column("tags", sa.Text(), nullable=True),
            sa.Column("content", sa.Text(), nullable=True),
            sa.Column("logged_date", sa.Date(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
        op.create_index("idx_mood_logs_user_date", "mood_logs", ["user_id", "logged_date"])

    if not _table_exists(conn, "diaries"):
        op.create_table(
            "diaries",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("dimension", sa.String(20), nullable=True),
            sa.Column("title", sa.String(200), nullable=True),
            sa.Column("content", sa.Text(), nullable=True),
            sa.Column("diary_date", sa.Date(), nullable=False),
            sa.Column("tags", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
        op.create_index("idx_diaries_user_date", "diaries", ["user_id", "diary_date"])

    # ===== 长期资产库 =====
    if not _table_exists(conn, "sops"):
        op.create_table(
            "sops",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("category", sa.String(100), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("steps", sa.Text(), nullable=True),
            sa.Column("checklist", sa.Text(), nullable=True),
            sa.Column("tags", sa.Text(), nullable=True),
            sa.Column("use_count", sa.Integer(), server_default="0"),
            sa.Column("version", sa.Integer(), server_default="1"),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )

    if not _table_exists(conn, "sop_versions"):
        op.create_table(
            "sop_versions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("sop_id", sa.String(36), sa.ForeignKey("sops.id", ondelete="CASCADE"), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("content", sa.Text(), nullable=True),
            sa.Column("change_note", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )

    if not _table_exists(conn, "prompt_templates"):
        op.create_table(
            "prompt_templates",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("category", sa.String(50), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("role_setting", sa.Text(), nullable=True),
            sa.Column("task_description", sa.Text(), nullable=True),
            sa.Column("constraints", sa.Text(), nullable=True),
            sa.Column("output_format", sa.Text(), nullable=True),
            sa.Column("variables", sa.Text(), nullable=True),
            sa.Column("use_count", sa.Integer(), server_default="0"),
            sa.Column("rating", sa.Float(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )

    if not _table_exists(conn, "skills"):
        op.create_table(
            "skills",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("category", sa.String(100), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("methodology", sa.Text(), nullable=True),
            sa.Column("proficiency", sa.String(20), server_default="beginner"),
            sa.Column("tags", sa.Text(), nullable=True),
            sa.Column("use_count", sa.Integer(), server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )

    if not _table_exists(conn, "project_memories"):
        op.create_table(
            "project_memories",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("summary", sa.Text(), nullable=True),
            sa.Column("successes", sa.Text(), nullable=True),
            sa.Column("failures", sa.Text(), nullable=True),
            sa.Column("extracted_assets", sa.Text(), nullable=True),
            sa.Column("key_metrics", sa.Text(), nullable=True),
            sa.Column("tags", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )

    print("0008_new_modules: 15 tables created")


def downgrade() -> None:
    conn = op.get_bind()
    for table in [
        "project_memories", "skills", "prompt_templates", "sop_versions", "sops",
        "diaries", "mood_logs", "habit_checkins", "habits",
        "study_time_logs", "flashcards", "study_plans",
        "domains", "templates", "inbox_items",
    ]:
        if _table_exists(conn, table):
            op.drop_table(table)
