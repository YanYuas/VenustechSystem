# ============================================================
# 演示数据种子 seed_if_empty 测试（Phase7-D · 覆盖率补缺）
#
# 为什么用**独立临时 SQLite 引擎**而不是 conftest 的主测试库：
#   · seed_if_empty 只在「库里没有 default_user」时执行，而 conftest 的
#     clean_db 会保留 default_user（其它用例依赖它），且 session 级
#     default_user_id 夹具缓存了 id —— 删除它会让后续用例 FK 断裂；
#   · 独立引擎完全隔离：不依赖用例执行顺序、也不触碰主测试库与真实 var/data。
#
# 覆盖：种子分支全流程（46 张表相关部分）、幂等（第二次返回 False）、
# 已存在用户时直接短路、跨表引用（文档→文件夹）、时间轴回填、只写临时库。
# ============================================================
from __future__ import annotations

import shutil
import uuid
from datetime import date, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401  导入全部模型以注册 metadata
from app.config import get_settings
from app.models.base import Base
from app.repositories import UserRepository
from app.seed import seed_if_empty
from app.services.document_service import count_words


@pytest.fixture()
def seed_session():
    """独立临时库（在测试数据目录内）：yield (Session, db_path)。"""
    directory = Path(get_settings().data_dir) / f"seed-db-{uuid.uuid4().hex[:8]}"
    directory.mkdir(parents=True, exist_ok=False)
    db_path = directory / "app.db"
    engine = create_engine(
        f"sqlite:///{db_path.as_posix()}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    try:
        yield session_factory, db_path
    finally:
        engine.dispose()
        shutil.rmtree(directory, ignore_errors=True)


def _count(session_factory, model, **filters) -> int:
    db = session_factory()
    try:
        q = select(func.count()).select_from(model)
        for key, value in filters.items():
            q = q.where(getattr(model, key) == value)
        return int(db.scalar(q) or 0)
    finally:
        db.close()


def _one(session_factory, model, **filters):
    db = session_factory()
    try:
        q = select(model)
        for key, value in filters.items():
            q = q.where(getattr(model, key) == value)
        return db.scalars(q).first()
    finally:
        db.close()


# ================================================================
# 一、种子全流程与数据完整性
# ================================================================
class TestSeedAll:
    def test_seed_populates_every_demo_section(self, seed_session):
        session_factory, _ = seed_session
        db = session_factory()
        try:
            assert seed_if_empty(db) is True
        finally:
            db.close()

        from app.models.conversation import Conversation, Message
        from app.models.document import Document
        from app.models.folder import Folder
        from app.models.notification import Notification
        from app.models.panel import QuickTodo, Reminder
        from app.models.review import Review
        from app.models.task import Subtask, Task
        from app.models.user import User

        user = _one(session_factory, User, username="default_user")
        assert user is not None
        assert user.nickname == "启明星用户"
        assert user.pet_position == {"x": 1770, "y": 880}

        assert _count(session_factory, Folder) == 5
        assert _count(session_factory, Task) == 22
        assert _count(session_factory, Subtask) == 10
        assert _count(session_factory, Document) == 15
        assert _count(session_factory, Review) == 10
        assert _count(session_factory, Conversation) == 3
        assert _count(session_factory, Message) == 12
        assert _count(session_factory, QuickTodo) == 5
        assert _count(session_factory, Reminder) == 5
        assert _count(session_factory, Notification) == 6

        # 今日最重要有部分唯一索引（同用户最多 1 个）—— 种子必须自洽
        assert _count(session_factory, Task, is_focus=True) == 1
        # 任务状态分布覆盖四大状态
        assert _statuses(session_factory) == {
            "pending", "in_progress", "waiting", "completed",
        }

    def test_seed_documents_are_filed_into_correct_folders(self, seed_session):
        session_factory, _ = seed_session
        db = session_factory()
        try:
            seed_if_empty(db)
        finally:
            db.close()

        from app.models.document import Document
        from app.models.folder import Folder

        inbox = _one(session_factory, Folder, name="收集箱")
        learn = _one(session_factory, Folder, name="学习")
        assert inbox is not None and inbox.is_inbox is True
        assert learn is not None

        arch_doc = _one(session_factory, Document, title="项目架构设计笔记")
        algo_doc = _one(session_factory, Document, title="算法笔记-动态规划")
        assert arch_doc is not None and arch_doc.folder_id == inbox.id
        assert algo_doc is not None and algo_doc.folder_id == learn.id
        # 字数统计走真实 count_words（不是写死的数字）
        assert arch_doc.word_count == count_words(arch_doc.content)

    def test_seed_backfills_past_timeline(self, seed_session):
        session_factory, _ = seed_session
        db = session_factory()
        try:
            seed_if_empty(db)
        finally:
            db.close()

        from app.models.task import Task

        today = date.today()
        daily_dates = _review_dates(session_factory, "daily")
        weekly_dates = _review_dates(session_factory, "weekly")
        assert len(daily_dates) == 7 and len(weekly_dates) == 3
        # 日报覆盖「今天起往前 7 天」（含今天），用来点亮首页连续打卡
        assert max(daily_dates) == today
        assert min(daily_dates) == today - timedelta(days=6)
        # 周报是过去 3 周的周一
        assert all(today - d <= timedelta(days=21) for d in weekly_dates)
        assert all(d.weekday() == 0 for d in weekly_dates)

        db = session_factory()
        try:
            completed = db.scalars(select(Task).where(Task.status == "completed")).all()
            assert completed, "演示数据应包含已完成任务用于趋势图"
            assert all(t.completed_at is not None for t in completed)
        finally:
            db.close()

    def test_read_only_path_does_not_touch_configured_data_dir(self, seed_session):
        session_factory, db_path = seed_session
        configured = Path(get_settings().data_dir).resolve()
        db = session_factory()
        try:
            seed_if_empty(db)
        finally:
            db.close()

        assert db_path.is_file()
        assert configured != db_path.parent.resolve()
        assert db_path.parent.name.startswith("seed-db-")


# ================================================================
# 二、幂等 / 短路
# ================================================================
class TestSeedIdempotency:
    def test_second_call_returns_false_and_writes_nothing(self, seed_session):
        session_factory, _ = seed_session
        db = session_factory()
        try:
            assert seed_if_empty(db) is True
        finally:
            db.close()

        from app.models.document import Document
        from app.models.task import Task

        before = (_count(session_factory, Task), _count(session_factory, Document))
        db = session_factory()
        try:
            assert seed_if_empty(db) is False      # 已有 default_user → 短路
        finally:
            db.close()
        after = (_count(session_factory, Task), _count(session_factory, Document))
        assert after == before

    def test_existing_user_short_circuits_without_demo_rows(self, seed_session):
        session_factory, _ = seed_session
        db = session_factory()
        try:
            UserRepository(db).create(username="default_user", nickname="已有用户")
            db.commit()
            assert seed_if_empty(db) is False
        finally:
            db.close()

        from app.models.document import Document
        from app.models.folder import Folder
        from app.models.task import Task

        assert _count(session_factory, Task) == 0
        assert _count(session_factory, Document) == 0
        assert _count(session_factory, Folder) == 0


# ---------------------------------------------------------------- helpers
def _statuses(session_factory):
    from app.models.task import Task

    db = session_factory()
    try:
        return set(db.scalars(select(Task.status)).all())
    finally:
        db.close()


def _review_dates(session_factory, type_: str):
    from app.models.review import Review

    db = session_factory()
    try:
        return set(
            db.scalars(select(Review.review_date).where(Review.type == type_)).all()
        )
    finally:
        db.close()
