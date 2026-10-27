# ============================================================
# Repository 契约测试（D-06 Repository 收口）
#
# 目的：service 层迁移到 repository 后，「数据行为」必须与迁移前一致。
# 这些用例直接对 repository 的**公开语义**做契约断言（排序 / 过滤 /
# 分页 / 计数 / 解除关联 / 批量写），而不是断言 SQL 长什么样 ——
# 将来 repo 内部换实现只要契约不变，测试就仍然有效。
#
# 覆盖原则：
#   1. 每个新补的 Repository（growth/audit/settings_history/vault/
#      workspace）至少一条；
#   2. 每个为 D-06 新增的查询方法（identity_counts / clear_* /
#      list_* / title_id_map / replace_source_links / stats_user ...）
#      至少一条；
#   3. 只依赖 db_session（函数级回滚隔离）+ test_user（真实用户行）。
# ============================================================
from __future__ import annotations

import uuid
from datetime import date, timedelta

from app.core.utils import local_day_bounds_utc
from app.models.base import utcnow
from app.repositories import (
    AuditLogRepository,
    AvatarMemoryRepository,
    BacklinkRepository,
    ConversationRepository,
    DocumentRepository,
    FocusSessionRepository,
    FolderRepository,
    GrowthEventRepository,
    GrowthStateRepository,
    MilestoneRepository,
    NotificationRepository,
    ProjectMemoryRepository,
    ProjectRepository,
    ReviewRepository,
    SettingHistoryRepository,
    SkillStatRepository,
    TaskRepository,
    VaultItemRepository,
    WorkspaceFileRepository,
    WorkspaceRootRepository,
)


def _uid() -> str:
    """唯一后缀：同一次测试会话内避免同名冲突（clean_db 只保证跨用例干净）。"""
    return uuid.uuid4().hex[:8]


# ============================================================
# task 域
# ============================================================
class TestTaskRepositoryContract:
    def test_identity_counts_and_unassigned_by_completion(self, db_session, test_user):
        """报告「身份轴」依赖的分组计数：跳过未归类、可按完成态细分。"""
        repo = TaskRepository(db_session)
        id_a, id_b = _uid(), _uid()
        repo.create(user_id=test_user.id, title="A-完成", status="completed", identity_id=id_a)
        repo.create(user_id=test_user.id, title="A-未完成", status="pending", identity_id=id_a)
        repo.create(user_id=test_user.id, title="B-未完成", status="in_progress", identity_id=id_b)
        repo.create(user_id=test_user.id, title="未归类")

        assert repo.identity_counts(test_user.id) == {id_a: 2, id_b: 1}
        assert repo.identity_counts(test_user.id, completed=True) == {id_a: 1}
        assert repo.identity_counts(test_user.id, completed=False) == {id_a: 1, id_b: 1}
        assert repo.count_identity_unassigned(test_user.id) == 1
        assert repo.count_identity_unassigned(test_user.id, completed=False) == 1
        assert repo.count_identity_unassigned(test_user.id, completed=True) == 0
        assert repo.count_user(test_user.id, status="completed") == 1

    def test_clear_project_and_clear_identity_only_touch_target_rows(
        self, db_session, test_user, other_user
    ):
        """项目删除 / 身份软删除依赖的「解除引用」：只清指定值，不误伤其他行。"""
        project = ProjectRepository(db_session).create(user_id=test_user.id, name="P")
        repo = TaskRepository(db_session)
        identity = _uid()
        mine = repo.create(
            user_id=test_user.id, title="我的", project_id=project.id, identity_id=identity
        )
        repo.create(user_id=other_user.id, title="他人的", identity_id=identity)
        keep = repo.create(user_id=test_user.id, title="保留", identity_id=_uid())

        repo.clear_project(project.id)
        db_session.refresh(mine)
        assert mine.project_id is None
        assert keep.identity_id is not None

        repo.clear_identity(identity)
        db_session.refresh(mine)
        assert mine.identity_id is None
        assert keep.identity_id is not None

    def test_recurring_templates_and_exists_instance(self, db_session, test_user):
        """重复任务生成依赖的两条查询：模板筛选（只取 recurrence 非空）+ 幂等判重。"""
        repo = TaskRepository(db_session)
        template = repo.create(
            user_id=test_user.id, title="每日复盘", status="pending",
            recurrence={"type": "daily", "interval": 1}, due_date=date.today(),
        )
        repo.create(user_id=test_user.id, title="普通任务", status="pending")

        templates = repo.list_recurring_templates(test_user.id)
        assert [t.id for t in templates] == [template.id]
        assert repo.exists_instance(test_user.id, "每日复盘", date.today()) is True
        assert repo.exists_instance(test_user.id, "每日复盘", date.today() + timedelta(days=1)) is False

    def test_autofill_candidates_and_overdue_count(self, db_session, test_user):
        """每日复盘自动填充：今天完成 + 今天到期未完成；逾期数单独统计。"""
        repo = TaskRepository(db_session)
        today = date.today()
        day_start, day_end = local_day_bounds_utc(today)
        done = repo.create(
            user_id=test_user.id, title="今天完成", status="completed", completed_at=utcnow()
        )
        due_today = repo.create(user_id=test_user.id, title="今天到期", status="pending", due_date=today)
        repo.create(
            user_id=test_user.id, title="逾期", status="pending",
            due_date=today - timedelta(days=3),
        )

        rows = repo.list_autofill_candidates(test_user.id, day_start, day_end, today)
        ids = {t.id for t in rows}
        assert ids == {done.id, due_today.id}
        assert repo.count_overdue_for_user(test_user.id, today) == 1

    def test_project_scoped_lists_keep_ordering_and_limit(self, db_session, test_user):
        """项目详情/时间线/导出依赖的三种取数：排序、只取完成、上限。"""
        project = ProjectRepository(db_session).create(user_id=test_user.id, name="P")
        repo = TaskRepository(db_session)
        repo.create(user_id=test_user.id, title="t1", status="pending", project_id=project.id)
        repo.create(user_id=test_user.id, title="t2", status="completed",
                    project_id=project.id, completed_at=utcnow())
        repo.create(user_id=test_user.id, title="t3", status="in_progress", project_id=project.id)

        detail_rows = repo.list_by_project(project.id, limit=2)
        assert len(detail_rows) == 2
        assert [t.status for t in detail_rows] == sorted(t.status for t in detail_rows)

        completed = repo.list_completed_by_project(project.id, limit=20)
        assert [t.title for t in completed] == ["t2"]
        assert len(repo.list_all_by_project(project.id)) == 3

    def test_focus_session_list_and_get(self, db_session, test_user):
        """番茄钟：按任务取会话（新的在前）+ 单条读取。"""
        task = TaskRepository(db_session).create(user_id=test_user.id, title="专注")
        repo = FocusSessionRepository(db_session)
        old = repo.create(task_id=task.id, user_id=test_user.id,
                          start_time=utcnow() - timedelta(hours=2))
        new = repo.create(task_id=task.id, user_id=test_user.id, start_time=utcnow())

        rows = repo.list_by_task(task.id, limit=10)
        assert [s.id for s in rows] == [new.id, old.id]
        assert repo.get(old.id).id == old.id


# ============================================================
# document / folder 域
# ============================================================
class TestDocumentRepositoryContract:
    def test_title_id_map_and_backlink_replace(self, db_session, test_user):
        """[[双向链接]] 重建：标题解析（一次 IN）+ 先删后插 + 批量查询。"""
        doc_repo = DocumentRepository(db_session)
        link_repo = BacklinkRepository(db_session)
        source = doc_repo.create(user_id=test_user.id, title=f"源-{_uid()}")
        target_a = doc_repo.create(user_id=test_user.id, title=f"目标A-{_uid()}")
        title_map = doc_repo.title_id_map(
            test_user.id, [target_a.title, "不存在的标题"]
        )
        assert title_map == {target_a.title: target_a.id}

        link_repo.replace_source_links(source.id, [
            {"source_doc_id": source.id, "target_doc_id": target_a.id,
             "target_title": target_a.title},
            {"source_doc_id": source.id, "target_doc_id": None,
             "target_title": "不存在的标题"},
        ])
        links = link_repo.list_by_sources([source.id])
        assert len(links) == 2
        assert {bl.target_title for bl in links} == {target_a.title, "不存在的标题"}

        # 再次替换 → 旧链必须清空（不是追加）
        link_repo.replace_source_links(source.id, [])
        assert link_repo.list_by_sources([source.id]) == []

    def test_project_cards_created_between_and_counts(self, db_session, test_user):
        """项目详情卡片字段 / 复盘自动填充的文档 / 报告计数三件套。"""
        project = ProjectRepository(db_session).create(user_id=test_user.id, name="P")
        repo = DocumentRepository(db_session)
        created = repo.create(
            user_id=test_user.id, title="卡片", project_id=project.id,
            content="正文", tags=["a"], word_count=2,
        )
        start, end = local_day_bounds_utc(date.today())
        cards = repo.list_project_cards(project.id, limit=10)
        assert [(c.id, c.title, c.word_count) for c in cards] == [
            (created.id, "卡片", 2)
        ]
        assert [d.id for d in repo.list_created_between(test_user.id, start, end)] == [created.id]
        assert repo.count_by_user(test_user.id) == 1
        assert repo.count_identity_unassigned(test_user.id) == 1

    def test_folder_name_map(self, db_session, test_user):
        """文档列表消 N+1 的批量取名：一次查询返回 id→name。"""
        repo = FolderRepository(db_session)
        a = repo.create(user_id=test_user.id, name=f"甲-{_uid()}")
        b = repo.create(user_id=test_user.id, name=f"乙-{_uid()}")
        name_map = repo.name_map([a.id, b.id, "ghost"])
        assert name_map == {a.id: a.name, b.id: b.name}
        assert repo.name_map([]) == {}


# ============================================================
# 聚合 / 平台域
# ============================================================
class TestAggregateRepositoryContract:
    def test_review_identity_counts_and_recent_dates(self, db_session, test_user):
        """报告身份轴 + 首页连续打卡依赖的两种复盘查询。"""
        repo = ReviewRepository(db_session)
        identity = _uid()
        # reviews 有 (user_id, type, review_date) 唯一约束 → 每条用不同日期
        repo.create(user_id=test_user.id, type="daily", review_date=date.today(),
                    identity_id=identity, data={})
        repo.create(user_id=test_user.id, type="daily",
                    review_date=date.today() - timedelta(days=5), data={})
        repo.create(user_id=test_user.id, type="daily",
                    review_date=date.today() - timedelta(days=10), data={})

        assert repo.identity_counts(test_user.id) == {identity: 1}
        assert repo.count_identity_unassigned(test_user.id) == 2
        dates = repo.list_recent_dates(test_user.id, date.today() - timedelta(days=30))
        assert date.today() in dates and len(dates) == 3
        # 时间窗口外的记录不返回
        assert all(d >= date.today() - timedelta(days=30) for d in dates)

    def test_project_memory_and_avatar_memory_identity_counts(self, db_session, test_user):
        """报告把两类「记忆」相加：两域 repo 的分组计数口径必须一致。"""
        identity = _uid()
        pm = ProjectMemoryRepository(db_session)
        am = AvatarMemoryRepository(db_session)
        pm.create(user_id=test_user.id, name="pm1", identity_id=identity)
        pm.create(user_id=test_user.id, name="pm2")
        am.create(user_id=test_user.id, memory_type="profile", title="am1",
                  identity_id=identity)

        assert pm.identity_counts(test_user.id) == {identity: 1}
        assert am.identity_counts(test_user.id) == {identity: 1}
        assert pm.count_identity_unassigned(test_user.id) == 1
        assert am.count_identity_unassigned(test_user.id) == 0
        assert pm.count_by_user(test_user.id) == 2
        assert am.count_by_user(test_user.id) == 1

    def test_notification_stats_single_query(self, db_session, test_user):
        """通知角标：总数 + 未读数一次聚合（轮询端点）。"""
        repo = NotificationRepository(db_session)
        for i in range(3):
            repo.create(user_id=test_user.id, type="info", title=f"n{i}",
                        is_read=(i == 0))
        assert repo.stats_user(test_user.id) == (3, 2)
        assert repo.stats_user(test_user.id + "-none") == (0, 0)

    def test_audit_repo_trim_and_recent_list(self, db_session, test_user):
        """审计日志：只增 + 按上限修剪最旧 + 新→旧列表。"""
        repo = AuditLogRepository(db_session)
        for i in range(5):
            repo.create_entry(user_id=test_user.id, action="security.encrypt",
                              target=f"t{i}")
        assert repo.count_user(test_user.id) == 5
        stale = repo.stale_ids(test_user.id, keep=2)
        assert len(stale) == 3
        repo.delete_by_ids(stale)
        assert repo.count_user(test_user.id) == 2
        assert len(repo.list_user(test_user.id, limit=50)) == 2
        assert repo.stale_ids(test_user.id, keep=2) == []

    def test_setting_history_add_trim_and_list(self, db_session, test_user):
        """设置变更历史：追加 + 保留最近 N 条 + 新→旧列表。"""
        repo = SettingHistoryRepository(db_session)
        for i in range(4):
            repo.add_entry(user_id=test_user.id, key="notify.task",
                           old_value="true", new_value=f"v{i}")
        assert repo.count_user(test_user.id) == 4
        repo.trim(test_user.id, keep=2)
        rows = repo.list_user(test_user.id, limit=10)
        assert len(rows) == 2
        assert {r.new_value for r in rows} == {"v2", "v3"}

    def test_conversation_search_and_project_filters(self, db_session, test_user):
        """全局搜索 + 项目详情/时间线/导出的三种对话取数。"""
        project = ProjectRepository(db_session).create(user_id=test_user.id, name="P")
        repo = ConversationRepository(db_session)
        hit = repo.create(user_id=test_user.id, title="论文讨论", project_id=project.id)
        repo.create(user_id=test_user.id, title="随便聊聊", project_id=project.id)

        assert [c.id for c in repo.search_by_title(test_user.id, "论文")] == [hit.id]
        assert len(repo.list_project_by_updated(project.id)) == 2
        assert len(repo.list_project_by_created(project.id, limit=1)) == 1
        assert len(repo.list_all_by_project(project.id)) == 2
        assert repo.count_by_user(test_user.id) == 2

    def test_milestone_timeline_order(self, db_session, test_user):
        """项目时间线：里程碑按创建时间倒序取最近 N 条。"""
        project = ProjectRepository(db_session).create(user_id=test_user.id, name="P")
        repo = MilestoneRepository(db_session)
        first = repo.create(
            project_id=project.id, name="一",
            created_at=utcnow() - timedelta(minutes=5),
        )
        second = repo.create(project_id=project.id, name="二", created_at=utcnow())
        rows = repo.list_for_timeline(project.id, limit=10)
        assert [m.name for m in rows] == ["二", "一"]
        assert {m.id for m in rows} == {first.id, second.id}
        assert len(repo.list_for_timeline(project.id, limit=1)) == 1


# ============================================================
# 保险箱 / 工作区 / 成长（新补 Repository）
# ============================================================
class TestNewRepositoryContract:
    def test_vault_item_count_and_secret_filter(self, db_session, test_user):
        """保险箱：状态计数 + 密钥轮换只遍历真正有密文的条目。"""
        repo = VaultItemRepository(db_session)
        with_secret = repo.create(user_id=test_user.id, name="ssh", category="login",
                                  secret_encrypted="fernet:xxx")
        repo.create(user_id=test_user.id, name="note", category="note", secret_encrypted=None)
        assert repo.count_by_user(test_user.id) == 2
        assert [i.id for i in repo.list_with_secret(test_user.id)] == [with_secret.id]
        assert len(repo.list_by_user(test_user.id)) == 2

    def test_workspace_entries_replace_and_paginate(self, db_session, test_user):
        """工作区扫描：全量替换索引 + 过滤/计数/排序分页。"""
        root = WorkspaceRootRepository(db_session).create(
            user_id=test_user.id, path=f"D:/tmp/{_uid()}", label="工作区"
        )
        file_repo = WorkspaceFileRepository(db_session)
        file_repo.replace_root_entries(root.id, [
            {"root_id": root.id, "rel_path": "docs/a.md", "name": "a.md",
             "ext": ".md", "is_dir": False, "size": 1, "mtime": 1.0},
            {"root_id": root.id, "rel_path": "docs/b.md", "name": "b.md",
             "ext": ".md", "is_dir": False, "size": 2, "mtime": 2.0},
            {"root_id": root.id, "rel_path": "img/c.png", "name": "c.png",
             "ext": ".png", "is_dir": False, "size": 3, "mtime": 3.0},
        ])
        rows, total = file_repo.list_paginated(root.id)
        assert total == 3
        assert [f.name for f in rows] == ["a.md", "b.md", "c.png"]

        rows, total = file_repo.list_paginated(root.id, ext=".md", page_size=1)
        assert (total, [f.name for f in rows]) == (2, ["a.md"])

        rows, total = file_repo.list_paginated(root.id, search="c.")
        assert (total, [f.name for f in rows]) == (1, ["c.png"])

        # 再次全量替换 → 旧索引清空（不是追加）
        file_repo.replace_root_entries(root.id, [])
        assert file_repo.list_paginated(root.id)[1] == 0
        file_repo.delete_by_root(root.id)
        assert file_repo.list_paginated(root.id)[1] == 0

    def test_growth_state_event_skill(self, db_session, test_user):
        """成长三表：状态单例读取、流水按幂等键取、技能计数行读取。"""
        state_repo = GrowthStateRepository(db_session)
        assert state_repo.get_by_user(test_user.id) is None
        created_state = state_repo.create(user_id=test_user.id, exp=10, level=2)
        assert state_repo.get_by_user(test_user.id).id == created_state.id

        event_repo = GrowthEventRepository(db_session)
        source_key = f"task:{_uid()}:completed"
        assert event_repo.get_by_source_key(test_user.id, source_key) is None
        event_repo.create(user_id=test_user.id, source_key=source_key,
                          event_type="task.completed", exp=8)
        found = event_repo.get_by_source_key(test_user.id, source_key)
        assert found is not None and found.exp == 8
        assert [e.id for e in event_repo.list_user(test_user.id, limit=5)] == [found.id]

        skill_repo = SkillStatRepository(db_session)
        assert skill_repo.get_by_category(test_user.id, "code") is None
        row = skill_repo.create(user_id=test_user.id, category_id="code", count=1)
        row.count += 1
        db_session.flush()
        assert skill_repo.get_by_category(test_user.id, "code").count == 2
        assert [s.id for s in skill_repo.list_counted(test_user.id)] == [row.id]
