# ============================================================
# Report Service 生产级测试（S6-5 · 人生报告 三轴聚合）
#
# 三轴 = 身份 × 成长 × 档案，外加「近期经历」叙事面。
# 本文件重点：
#   1. 每条计数都**写后查库交叉验证**（报告最容易出现「数错但页面正常」）
#   2. 未归类（identity_id IS NULL）与按身份分组的边界
#   3. 档案轴的工作区开关语义（关闭 → 不读磁盘、roots 为空）
#   4. 越权：他人数据一条都不能进我的报告
#   5. 如实钉住「首次生成会写入 growth_states 并 commit」这一副作用
# ============================================================
from __future__ import annotations

from datetime import date, datetime

import pytest
from sqlalchemy import func, select

from app.models.growth import GrowthState
from app.models.life import Diary
from app.models.review import Review
from app.models.task import Task
from app.services.growth_service import GrowthService
from app.services.report_service import ReportService
from app.services.workspace_service import WorkspaceService
from tests.factories import (
    count_rows,
    make_avatar_memory,
    make_diary,
    make_document,
    make_identity,
    make_project_memory,
    make_prompt,
    make_review,
    make_skill,
    make_sop,
    make_task,
    make_workspace_root,
)


def _report(db, user_id, nickname="测试用户"):
    return ReportService(db, user_id, nickname).get()


def _by_id(axis, ident_id):
    return next(r for r in axis.identities if r.id == ident_id)


# ============================================================
# 第 1 组：报告骨架
# ============================================================
class TestGroup1ReportShape:
    """第1组：空用户的报告也必须是完整可序列化的结构。"""

    def test_report_shape_for_empty_user(self, db_session, test_user):
        """空库 → 三轴齐全、计数全 0、近期经历为空（不抛异常）。"""
        rep = _report(db_session, test_user.id)

        assert rep.nickname == "测试用户"
        assert isinstance(rep.generated_at, datetime)
        assert rep.identity_axis.identities == []
        assert rep.growth_axis.level == 1
        assert rep.growth_axis.exp == 0
        assert rep.archive_axis.workspace_enabled is False
        assert rep.archive_axis.roots == []
        assert rep.archive_axis.documents_total == 0
        assert rep.recent_experience == []

    def test_nickname_is_taken_verbatim(self, db_session, test_user):
        """nickname 原样透传（报告抬头用）。"""
        assert _report(db_session, test_user.id, nickname="衍煜").nickname == "衍煜"

    def test_generated_at_is_naive_utc_now(self, db_session, test_user):
        """generated_at 是本次生成时间（与 utcnow 同分钟），不是固定值。"""
        from app.models.base import utcnow

        rep = _report(db_session, test_user.id)
        assert abs((utcnow() - rep.generated_at).total_seconds()) < 60

    def test_report_is_json_serializable(self, db_session, test_user):
        """能 model_dump(mode='json')（前端要把这份 JSON 渲染成单文件 HTML）。"""
        payload = _report(db_session, test_user.id).model_dump(mode="json")
        assert set(payload) == {
            "generated_at", "nickname", "identity_axis",
            "growth_axis", "archive_axis", "recent_experience",
        }
        assert isinstance(payload["generated_at"], str)


# ============================================================
# 第 2 组：身份轴
# ============================================================
class TestGroup2IdentityAxis:
    """第2组：身份轴 —— 每个身份的六项计数与未归类桶。"""

    @pytest.fixture()
    def ident(self, db_session, test_user):
        return make_identity(db_session, test_user.id, name="研究生", slug="grad",
                             color_token="lilac", icon="book")

    def test_identity_row_carries_display_fields(self, db_session, test_user, ident):
        """身份行带 name/slug/color_token/icon 供前端着色与图标。"""
        rep = _report(db_session, test_user.id)
        row = _by_id(rep.identity_axis, ident.id)

        assert row.name == "研究生"
        assert row.slug == "grad"
        assert row.color_token == "lilac"
        assert row.icon == "book"
        assert row.is_archived is False

    def test_archived_identity_is_flagged_not_dropped(self, db_session, test_user):
        """归档身份（is_active=False）仍出现在报告里，但标记 is_archived=True。

        防什么：报告若直接过滤掉归档身份，历史数据会「凭空消失」——
        归档不是删除，历史仍挂在它上面。
        """
        archived = make_identity(db_session, test_user.id, name="旧身份",
                                 slug="old", is_active=False)
        rep = _report(db_session, test_user.id)

        row = _by_id(rep.identity_axis, archived.id)
        assert row.is_archived is True
        assert len(rep.identity_axis.identities) == 1

    def test_soft_deleted_identity_excluded(self, db_session, test_user):
        """软删除的身份不出现在报告里（deleted_at 过滤）。"""
        from app.models.base import utcnow

        gone = make_identity(db_session, test_user.id, name="已删身份", slug="gone")
        gone.deleted_at = utcnow()
        db_session.flush()

        rep = _report(db_session, test_user.id)
        assert [r.id for r in rep.identity_axis.identities] == []

    def test_tasks_split_open_vs_completed(self, db_session, test_user, ident):
        """任务按 status 分两桶：open = 非 completed，completed 单算。"""
        make_task(db_session, test_user.id, status="pending", title="待办")
        make_task(db_session, test_user.id, status="in_progress", title="进行中")
        make_task(db_session, test_user.id, status="waiting", title="等待")
        make_task(db_session, test_user.id, status="completed", title="已完成")
        # 上面 4 条都没有 identity_id，先赋给身份
        for t in db_session.scalars(select(Task)).all():
            t.identity_id = ident.id
        db_session.flush()

        row = _by_id(_report(db_session, test_user.id).identity_axis, ident.id)
        assert row.tasks_open == 3
        assert row.tasks_completed == 1

    def test_documents_diaries_reviews_counted_per_identity(self, db_session, test_user, ident):
        """文档 / 日记 / 复盘各按 identity_id 分组计数。"""
        make_document(db_session, test_user.id, title="文档", identity_id=ident.id)
        make_diary(db_session, test_user.id, title="日记", identity_id=ident.id,
                   diary_date=date(2026, 1, 1))
        make_review(db_session, test_user.id, type_="daily",
                    review_date=date(2026, 1, 2), identity_id=ident.id)

        row = _by_id(_report(db_session, test_user.id).identity_axis, ident.id)
        assert row.documents == 1
        assert row.diaries == 1
        assert row.reviews == 1

    def test_memories_sum_avatar_and_project(self, db_session, test_user, ident):
        """memories = 分身记忆 + 项目记忆（Schema 注释里写明是合计数）。"""
        make_avatar_memory(db_session, test_user.id, title="记忆1", identity_id=ident.id)
        make_avatar_memory(db_session, test_user.id, title="记忆2", identity_id=ident.id)
        make_project_memory(db_session, test_user.id, name="PM1", identity_id=ident.id)

        row = _by_id(_report(db_session, test_user.id).identity_axis, ident.id)
        assert row.memories == 3

    def test_identity_without_data_is_all_zero(self, db_session, test_user, ident):
        """新建身份没有任何数据 → 六项计数全 0（不是 None，前端直接相加）。"""
        row = _by_id(_report(db_session, test_user.id).identity_axis, ident.id)
        assert (row.tasks_open, row.tasks_completed, row.documents,
                row.diaries, row.reviews, row.memories) == (0, 0, 0, 0, 0, 0)

    def test_counts_are_verified_against_db(self, db_session, test_user, ident):
        """写后查库交叉验证：报告里的计数与 SQL 直接 count 一致。

        防什么：GROUP BY 写错（比如漏了 user_id 过滤或多算了 NULL 行）时
        页面照样渲染，只是数字不对 —— 必须用 SQL 反向核对。
        """
        for i in range(3):
            make_diary(db_session, test_user.id, title=f"日记{i}", identity_id=ident.id,
                       diary_date=date(2026, 1, 1 + i))
        # 未归类的日记不应计入该身份
        make_diary(db_session, test_user.id, title="未归类", diary_date=date(2026, 2, 1))

        db_session.flush()
        sql_count = db_session.scalar(
            select(func.count()).select_from(Diary).where(
                Diary.user_id == test_user.id, Diary.identity_id == ident.id
            )
        )
        row = _by_id(_report(db_session, test_user.id).identity_axis, ident.id)

        assert row.diaries == sql_count == 3

    def test_unassigned_bucket_counts_null_identity(self, db_session, test_user, ident):
        """未归类桶只统计 identity_id IS NULL 的行（含任务分两桶 + 记忆合计）。"""
        make_task(db_session, test_user.id, status="pending", title="未归类待办")
        make_task(db_session, test_user.id, status="completed", title="未归类完成")
        make_document(db_session, test_user.id, title="未归类文档")
        make_diary(db_session, test_user.id, title="未归类日记", diary_date=date(2026, 1, 1))
        make_review(db_session, test_user.id, type_="daily", review_date=date(2026, 1, 2))
        make_avatar_memory(db_session, test_user.id, title="未归类记忆")
        make_project_memory(db_session, test_user.id, name="未归类项目记忆")
        # 这些有身份的**不能**被算进未归类桶
        make_diary(db_session, test_user.id, title="已归类", identity_id=ident.id,
                   diary_date=date(2026, 3, 1))
        make_task(db_session, test_user.id, status="pending", title="已归类任务",
                  project_tag=None)

        for t in db_session.scalars(
            select(Task).where(Task.title == "已归类任务")
        ).all():
            t.identity_id = ident.id
        db_session.flush()

        un = _report(db_session, test_user.id).identity_axis.unassigned
        assert un.tasks_open == 1
        assert un.documents == 1
        assert un.diaries == 1
        assert un.reviews == 1
        assert un.memories == 2


# ============================================================
# 第 3 组：成长轴
# ============================================================
class TestGroup3GrowthAxis:
    """第3组：成长轴来自 GrowthService + 三个总量计数。"""

    def test_growth_defaults_for_new_user(self, db_session, test_user):
        """新用户：level=1 / exp=0 / percent=0 / 无技能。"""
        g = _report(db_session, test_user.id).growth_axis
        assert (g.level, g.exp, g.percent) == (1, 0, 0)
        assert g.skills == []

    def test_growth_reflects_awarded_exp(self, db_session, test_user):
        """award 之后报告中的等级/经验同步变化（不读缓存旧值）。"""
        GrowthService(db_session).award(
            user_id=test_user.id, source_key="task:t1:completed",
            event_type="task.completed", exp=25,
        )

        g = _report(db_session, test_user.id).growth_axis
        assert g.exp == 25
        assert g.level >= 1

    def test_skills_list_from_skill_tree(self, db_session, test_user):
        """技能树里有计数的分类出现在报告里，名称由分类表派生（不是裸 id）。"""
        from app.models.growth import SkillStat
        from app.services.rules.skill_cats import SKILL_CATS as CATS

        db_session.add(SkillStat(user_id=test_user.id, category_id=CATS[0].id, count=3))
        db_session.flush()

        g = _report(db_session, test_user.id).growth_axis
        assert [(s.name, s.count) for s in g.skills] == [(CATS[0].name, 3)]

    def test_zero_count_skill_stat_is_filtered_out(self, db_session, test_user):
        """计数为 0 的分类不出现在技能树里（避免报告列出一堆空技能）。"""
        from app.models.growth import SkillStat
        from app.services.rules.skill_cats import SKILL_CATS as CATS

        db_session.add(SkillStat(user_id=test_user.id, category_id=CATS[0].id, count=0))
        db_session.flush()

        assert _report(db_session, test_user.id).growth_axis.skills == []

    def test_unknown_skill_category_falls_back_to_id(self, db_session, test_user):
        """分类被移除后历史计数不丢弃 —— 名称退化为 id（GrowthService 的注释承诺）。

        防什么：分类表改名/删除后，若报告直接丢弃该行，用户会看到技能
        「凭空少了一项」。
        """
        from app.models.growth import SkillStat

        db_session.add(SkillStat(user_id=test_user.id, category_id="__removed__", count=2))
        db_session.flush()

        g = _report(db_session, test_user.id).growth_axis
        assert [(s.name, s.count) for s in g.skills] == [("__removed__", 2)]

    def test_totals_for_tasks_diaries_reviews(self, db_session, test_user):
        """三个总量：完成任务数 / 日记数 / 复盘数（跨全部身份）。"""
        make_task(db_session, test_user.id, status="completed", title="已完成")
        make_task(db_session, test_user.id, status="pending", title="未完成")
        make_diary(db_session, test_user.id, title="日记1", diary_date=date(2026, 1, 1))
        make_diary(db_session, test_user.id, title="日记2", diary_date=date(2026, 1, 2))
        make_review(db_session, test_user.id, type_="daily", review_date=date(2026, 1, 3))

        g = _report(db_session, test_user.id).growth_axis
        assert g.tasks_completed_total == 1
        assert g.diaries_total == 2
        assert g.reviews_total == 1

    def test_totals_count_only_my_rows(self, db_session, test_user, other_user):
        """他人数据不进我的成长总量。"""
        make_task(db_session, other_user.id, status="completed", title="他人的")
        make_diary(db_session, other_user.id, title="他人日记",
                   diary_date=date(2026, 1, 1))

        g = _report(db_session, test_user.id).growth_axis
        assert g.tasks_completed_total == 0
        assert g.diaries_total == 0


# ============================================================
# 第 4 组：档案轴
# ============================================================
class TestGroup4ArchiveAxis:
    """第4组：档案轴 —— 工作区开关语义 + 资产计数。"""

    def test_workspace_disabled_means_no_roots(self, db_session, test_user):
        """默认关闭时 roots 为空（**默认值即 workspace.enabled=false**）。

        防什么：关闭态还去读磁盘会拖慢报告生成；更糟的是把别人的目录结构
        泄漏进报告。
        """
        make_workspace_root(db_session, test_user.id, path="D:/secret")
        a = _report(db_session, test_user.id).archive_axis

        assert a.workspace_enabled is False
        assert a.roots == []

    def test_workspace_enabled_lists_roots(self, db_session, test_user):
        """开启后列出已登记根（含 file_count / total_size 元数据）。"""
        WorkspaceService(db_session, test_user.id).set_enabled(True)
        make_workspace_root(db_session, test_user.id, path="D:/YanYuas",
                            label="主工作区", file_count=7, total_size=4096)
        db_session.commit()

        a = _report(db_session, test_user.id).archive_axis
        assert a.workspace_enabled is True
        assert len(a.roots) == 1
        assert a.roots[0].path == "D:/YanYuas"
        assert a.roots[0].label == "主工作区"
        assert a.roots[0].file_count == 7
        assert a.roots[0].total_size == 4096

    def test_workspace_roots_are_user_scoped(self, db_session, test_user, other_user):
        """开着工作区也只列自己的根（不泄漏他人的登记路径）。"""
        WorkspaceService(db_session, test_user.id).set_enabled(True)
        make_workspace_root(db_session, other_user.id, path="D:/other-user-secret")
        db_session.commit()

        a = _report(db_session, test_user.id).archive_axis
        assert a.roots == []

    def test_asset_totals(self, db_session, test_user):
        """文档 / SOP / Prompt / Skill / 项目记忆 / 分身记忆 六个总量。"""
        make_document(db_session, test_user.id, title="D")
        make_sop(db_session, test_user.id, name="S")
        make_sop(db_session, test_user.id, name="S2")
        make_prompt(db_session, test_user.id, name="P")
        make_skill(db_session, test_user.id, name="K")
        make_project_memory(db_session, test_user.id, name="PM")
        make_avatar_memory(db_session, test_user.id, title="AM")

        a = _report(db_session, test_user.id).archive_axis
        assert a.documents_total == 1
        assert a.sops_total == 2
        assert a.prompts_total == 1
        assert a.skills_total == 1
        assert a.project_memories_total == 1
        assert a.avatar_memories_total == 1

    def test_asset_totals_only_my_rows(self, db_session, test_user, other_user):
        """他人资产不计入我的档案轴。"""
        make_sop(db_session, other_user.id, name="他人SOP")
        make_document(db_session, other_user.id, title="他人文档")

        a = _report(db_session, test_user.id).archive_axis
        assert a.sops_total == 0
        assert a.documents_total == 0


# ============================================================
# 第 5 组：近期经历
# ============================================================
class TestGroup5RecentExperience:
    """第5组：报告的叙事面 —— 最近 10 条经历及其身份名。"""

    def test_recent_experience_uses_10_items(self, db_session, test_user):
        """默认取最近 10 条（哪怕源里更多）。"""
        for i in range(1, 16):
            make_diary(db_session, test_user.id, title=f"日记{i:02d}",
                       diary_date=date(2026, 1, 1 + i))

        rep = _report(db_session, test_user.id)
        assert len(rep.recent_experience) == 10
        # 最近的是第 15 篇（日期最晚）
        assert rep.recent_experience[0].title == "日记15"

    def test_recent_experience_sorted_desc(self, db_session, test_user):
        """按 occurred_at 降序（报告的「最近发生」必须真的是最近的）。"""
        for i in range(5):
            make_diary(db_session, test_user.id, title=f"日记{i}",
                       diary_date=date(2026, 1, 1 + i))

        stamps = [e.occurred_at for e in _report(db_session, test_user.id).recent_experience]
        assert stamps == sorted(stamps, reverse=True)

    def test_recent_experience_resolves_identity_name(self, db_session, test_user):
        """有身份 → identity_name 是身份名称（不是 id）。"""
        ident = make_identity(db_session, test_user.id, name="研究生", slug="g2")
        make_diary(db_session, test_user.id, title="带身份日记", identity_id=ident.id,
                   diary_date=date(2026, 1, 1))

        e = _report(db_session, test_user.id).recent_experience[0]
        assert e.identity_name == "研究生"

    def test_recent_experience_identity_name_none_when_unassigned(self, db_session, test_user):
        """未归类 → identity_name 为 None（前端渲染为「未归类」）。"""
        make_diary(db_session, test_user.id, title="无身份", diary_date=date(2026, 1, 1))

        e = _report(db_session, test_user.id).recent_experience[0]
        assert e.identity_name is None

    def test_recent_experience_source_label_populated(self, db_session, test_user):
        """source_label 由 SOURCE_LABELS 派生（与经历视图同一份真源）。"""
        from app.services.experience_service import SOURCE_LABELS

        make_avatar_memory(db_session, test_user.id, title="记忆")
        e = _report(db_session, test_user.id).recent_experience[0]
        assert e.source_label == SOURCE_LABELS[e.source]

    def test_recent_experience_excludes_other_users(self, db_session, test_user, other_user):
        """他人的经历不出现在我的报告里（隐私面）。"""
        make_diary(db_session, other_user.id, title="他人日记",
                   diary_date=date(2026, 9, 9))
        assert _report(db_session, test_user.id).recent_experience == []


# ============================================================
# 第 6 组：副作用与事务语义（如实钉住）
# ============================================================
class TestGroup6SideEffects:
    """第6组：报告自称「只读聚合」，实测并非零写入 —— 把真相钉成契约。"""

    def test_first_call_creates_growth_state_row(self, db_session, test_user):
        """首次生成报告会写入一行 growth_states（GrowthService 的惰性初始化 + commit）。

        **这不是「只读」**：`ReportService` 的类注释写「不新增任何写入」，
        但 `_growth_axis → GrowthService.get_state → get_or_create_state`
        在新用户上会 `db.add(...)` 并 **commit**。这里如实记录，避免后人
        误以为报告是纯读取（也避免有人把它接进别的事务里却没意识到 commit）。
        """
        db_session.flush()
        assert count_rows(db_session, "growth_states", user_id=test_user.id) == 0

        _report(db_session, test_user.id)

        assert count_rows(db_session, "growth_states", user_id=test_user.id) == 1

    def test_second_call_does_not_add_another_growth_state(self, db_session, test_user):
        """第二次生成不会重复插入（幂等初始化）。"""
        _report(db_session, test_user.id)
        _report(db_session, test_user.id)

        assert count_rows(db_session, "growth_states", user_id=test_user.id) == 1

    def test_growth_state_row_is_visible_in_db(self, db_session, test_user):
        """写入的 GrowthState 内容正确（exp=0 / level=1），查库核对。"""
        _report(db_session, test_user.id)
        db_session.expire_all()

        state = db_session.scalar(
            select(GrowthState).where(GrowthState.user_id == test_user.id)
        )
        assert state is not None
        assert state.exp == 0
        assert state.level == 1

    def test_report_does_not_write_business_sources(self, db_session, test_user):
        """除 growth_states 外，报告不写任何业务源表（四源 + 任务 + 文档行数不变）。"""
        make_diary(db_session, test_user.id, title="D", diary_date=date(2026, 1, 1))
        make_task(db_session, test_user.id, title="T", status="pending")
        db_session.commit()

        tables = ("diaries", "reviews", "avatar_memories", "project_memories",
                  "tasks", "documents", "identities")
        before = {t: count_rows(db_session, t) for t in tables}

        _report(db_session, test_user.id)

        after = {t: count_rows(db_session, t) for t in tables}
        assert after == before
