# ============================================================
# Experience Service 生产级测试（S6-4 · 经历视图）
#
# 定位：经历 = 四源（日记 / 复盘 / 分身记忆 / 项目记忆）在**读取时**
# 的聚合视图，**不建表**（总路线 R1）。因此本文件的两个重点是：
#   1. 聚合语义正确（归一 occurred_at、跨源降序、内存分页、身份过滤）
#   2. **真的只读**：调用前后四张源表行数不变、不新建任何表
#
# 标准：真数据夹具 + 跨源交叉验证 + 边界 + 越权隔离 + 只读副作用断言
# ============================================================
from __future__ import annotations

from datetime import date, datetime

import pytest

from app.services.experience_service import (
    _PER_SOURCE_CAP,
    SOURCE_LABELS,
    ExperienceService,
    _as_datetime,
)
from tests.factories import (
    FIXTURE_EXPERIENCE_DESC_ORDER,
    count_rows,
    make_avatar_memory,
    make_diary,
    make_identity,
    make_project_memory,
    make_review,
    seed_four_sources,
)


def _svc(db, user_id) -> ExperienceService:
    return ExperienceService(db, user_id)


def _sources(out) -> list[str]:
    return [i.source for i in out.items]


# ============================================================
# 第 1 组：空态与返回结构
# ============================================================
class TestGroup1EmptyAndShape:
    """第1组：空库返回合法空结构（不是 None / 不是 500）。"""

    def test_empty_timeline_returns_empty_payload(self, db_session, test_user):
        """四源皆空 → items 为空、total=0、source_counts 为空 dict。

        防什么：前端 ExperienceView 直接读 res.items / res.source_counts。
        若返回 None，页面会在空态下崩（新用户第一次打开该页即触发）。
        """
        out = _svc(db_session, test_user.id).list()

        assert out.items == []
        assert out.total == 0
        assert out.source_counts == {}
        assert out.page == 1
        assert out.page_size == 30

    def test_default_pagination_values(self, db_session, test_user):
        """默认 page=1 / page_size=30（与路由签名一致）。"""
        out = _svc(db_session, test_user.id).list()
        assert out.page == 1
        assert out.page_size == 30

    def test_each_item_carries_required_fields(self, db_session, test_user):
        """每条 ExperienceItem 的必填字段齐全且类型正确。"""
        seed_four_sources(db_session, test_user.id)
        out = _svc(db_session, test_user.id).list()

        assert len(out.items) == 4
        for it in out.items:
            assert isinstance(it.id, str) and it.id
            assert isinstance(it.source, str)
            assert isinstance(it.source_label, str) and it.source_label
            assert isinstance(it.title, str) and it.title
            assert isinstance(it.occurred_at, datetime)
            assert it.identity_id is None


# ============================================================
# 第 2 组：四源聚合与标签
# ============================================================
class TestGroup2FourSourcesAggregation:
    """第2组：四源都被读到、计数正确、标签是中文语义标签。"""

    def test_four_sources_aggregated_total_and_counts(self, db_session, test_user):
        """四源各一条 → total=4 且每源各计 1。

        防什么：任何一源被漏掉（比如只合了三源），用户会「明明写过却看不到」。
        """
        seed_four_sources(db_session, test_user.id)
        out = _svc(db_session, test_user.id).list()

        assert out.total == 4
        assert out.source_counts == {
            "diary": 1, "review": 1, "avatar_memory": 1, "project_memory": 1,
        }

    def test_source_labels_are_chinese_labels(self, db_session, test_user):
        """source_label 来自 SOURCE_LABELS，不是裸英文 key。"""
        seed_four_sources(db_session, test_user.id)
        out = _svc(db_session, test_user.id).list()

        for it in out.items:
            assert it.source_label == SOURCE_LABELS[it.source]

    def test_source_field_within_literal_set(self, db_session, test_user):
        """source 只能取 Schema 里 Literal 声明的 4 个值（否则前端图标映射会落空）。"""
        seed_four_sources(db_session, test_user.id)
        out = _svc(db_session, test_user.id).list()

        assert set(_sources(out)) == {"diary", "review", "avatar_memory", "project_memory"}

    def test_multi_row_per_source_counts(self, db_session, test_user):
        """同源多条时计数累加（日记 3 + 复盘 2 → {diary:3, review:2}）。"""
        for i in range(3):
            make_diary(db_session, test_user.id, title=f"日记{i}",
                       diary_date=date(2026, 1, 1 + i))
        for i in range(2):
            make_review(db_session, test_user.id, type_="daily",
                        review_date=date(2026, 2, 1 + i))

        out = _svc(db_session, test_user.id).list()
        assert out.total == 5
        assert out.source_counts == {"diary": 3, "review": 2}


# ============================================================
# 第 3 组：occurred_at 归一（业务日期优先，回退 created_at）
# ============================================================
class TestGroup3OccurredAtNormalization:
    """第3组：四源各有自己的「业务日期」定义，归一规则错会让时间线乱序。"""

    def test_diary_uses_diary_date_not_created_at(self, db_session, test_user):
        """日记的 occurred_at 取 diary_date（业务日期），不是入库时间。

        防什么：若用 created_at，补写的旧日记会全部挤在「今天」。
        """
        make_diary(db_session, test_user.id, diary_date=date(2020, 5, 6))
        out = _svc(db_session, test_user.id).list()

        assert out.items[0].occurred_at == datetime(2020, 5, 6, 0, 0)

    def test_review_uses_review_date_not_created_at(self, db_session, test_user):
        """复盘的 occurred_at 取 review_date。"""
        make_review(db_session, test_user.id, review_date=date(2021, 7, 8))
        out = _svc(db_session, test_user.id).list()

        assert out.items[0].occurred_at == datetime(2021, 7, 8, 0, 0)

    def test_avatar_memory_uses_created_at(self, db_session, test_user):
        """分身记忆没有业务日期，occurred_at = created_at。"""
        make_avatar_memory(db_session, test_user.id,
                           created_at=datetime(2022, 9, 10, 8, 30))
        out = _svc(db_session, test_user.id).list()

        assert out.items[0].occurred_at == datetime(2022, 9, 10, 8, 30)

    def test_project_memory_uses_created_at(self, db_session, test_user):
        """项目记忆同理取 created_at。"""
        make_project_memory(db_session, test_user.id,
                            created_at=datetime(2023, 11, 12, 18, 0))
        out = _svc(db_session, test_user.id).list()

        assert out.items[0].occurred_at == datetime(2023, 11, 12, 18, 0)

    def test_as_datetime_none_falls_back(self):
        """_as_datetime(None, fallback) → fallback（四源日期列为空时的兜底路径）。"""
        fb = datetime(2026, 1, 1, 9, 0)
        assert _as_datetime(None, fb) == fb

    def test_as_datetime_datetime_passthrough(self):
        """_as_datetime 收到 datetime 时原样返回（不做二次归一）。"""
        dt = datetime(2026, 2, 3, 4, 5)
        assert _as_datetime(dt, datetime(2000, 1, 1)) == dt

    def test_as_datetime_date_becomes_midnight(self):
        """date → 当天 00:00（保证与 datetime 可比较排序）。"""
        assert _as_datetime(date(2026, 3, 4), datetime(2000, 1, 1)) == \
            datetime(2026, 3, 4, 0, 0)

    def test_all_occurred_at_are_comparable(self, db_session, test_user):
        """四源混排后 occurred_at 全为 naive datetime（混 aware/naive 会在 sort 处 TypeError）。

        防什么：date 归一产出 naive、created_at 若为 aware → 排序直接抛异常。
        实测（探针）：SQLite 读写后 created_at 为 naive UTC，故可比较 —— 本用例把
        这个前提钉成契约，避免日后有人改回 aware 就静默 500。
        """
        seed_four_sources(db_session, test_user.id)
        out = _svc(db_session, test_user.id).list()

        for it in out.items:
            assert it.occurred_at.tzinfo is None


# ============================================================
# 第 4 组：跨源归并排序
# ============================================================
class TestGroup4MergedOrdering:
    """第4组：时间线必须是**跨源**降序，而不是各源分块拼接。"""

    def test_merged_descending_order_across_sources(self, db_session, test_user):
        """四源日期 3/1 < 3/2 < 3/3 < 3/4 → 降序应为 项目记忆→分身记忆→复盘→日记。

        防什么：若按「源」分块拼接（先所有日记、再所有复盘…），时间线就失去
        叙事意义 —— 这正是「四源聚合」要解决的问题本身。
        """
        seed_four_sources(db_session, test_user.id)
        out = _svc(db_session, test_user.id).list()

        assert _sources(out) == FIXTURE_EXPERIENCE_DESC_ORDER

    def test_ordering_interleaves_sources(self, db_session, test_user):
        """同源多条时也严格按时间插入（日记1/复盘1/日记2 交错）。"""
        make_diary(db_session, test_user.id, title="老日记", diary_date=date(2026, 1, 1))
        make_review(db_session, test_user.id, review_date=date(2026, 1, 2))
        make_diary(db_session, test_user.id, title="新日记", diary_date=date(2026, 1, 3))

        out = _svc(db_session, test_user.id).list()
        assert [(i.source, i.title) for i in out.items] == [
            ("diary", "新日记"), ("review", "复盘（daily）"), ("diary", "老日记"),
        ]

    def test_occurred_at_is_monotonic_desc(self, db_session, test_user):
        """整个列表的 occurred_at 单调不增（契约级断言，覆盖任意夹具形态）。"""
        seed_four_sources(db_session, test_user.id)
        out = _svc(db_session, test_user.id).list()

        stamps = [i.occurred_at for i in out.items]
        assert stamps == sorted(stamps, reverse=True)


# ============================================================
# 第 5 组：内存分页
# ============================================================
class TestGroup5Pagination:
    """第5组：内存分页 —— 切片只影响 items，total 始终是全量。"""

    @pytest.fixture()
    def twelve(self, db_session, test_user):
        """造 12 条日记（2026-01-01..12），日期递增便于断言切片端点。"""
        for i in range(1, 13):
            make_diary(db_session, test_user.id, title=f"日记{i:02d}",
                       diary_date=date(2026, 1, i))
        return test_user

    def test_pagination_slices_items_but_total_is_full(self, db_session, twelve):
        """page=2 / page_size=5 → 取回第 6..10 条，但 total 仍为 12。

        防什么：在 SQL 层 LIMIT 后把 total 写成「本页条数」，前端分页器会消失。
        """
        out = _svc(db_session, twelve.id).list(page=2, page_size=5)

        assert out.total == 12
        assert len(out.items) == 5
        assert [i.title for i in out.items] == [
            "日记07", "日记06", "日记05", "日记04", "日记03",
        ]

    def test_last_page_partial_slice(self, db_session, twelve):
        """末页只剩余数（12 条 / 每页 5 → 第 3 页 2 条）。"""
        out = _svc(db_session, twelve.id).list(page=3, page_size=5)
        assert out.total == 12
        assert len(out.items) == 2

    def test_page_beyond_range_returns_empty_items(self, db_session, twelve):
        """页码越界 → items 为空但 total 不变（前端据此显示空态而非报错）。"""
        out = _svc(db_session, twelve.id).list(page=99, page_size=5)
        assert out.items == []
        assert out.total == 12

    def test_page_size_larger_than_total_returns_all(self, db_session, twelve):
        """page_size > total → 一次取回全部。"""
        out = _svc(db_session, twelve.id).list(page=1, page_size=100)
        assert len(out.items) == 12
        assert out.total == 12


# ============================================================
# 第 6 组：身份过滤
# ============================================================
class TestGroup6IdentityFilter:
    """第6组：identity_id / identity_unassigned 的过滤语义（与任务列表一致）。"""

    @pytest.fixture()
    def two_identities(self, db_session, test_user):
        ident_a = make_identity(db_session, test_user.id, name="身份A", slug="a")
        ident_b = make_identity(db_session, test_user.id, name="身份B", slug="b")
        seed_four_sources(db_session, test_user.id, identity_id=ident_a.id, day_offset=0)
        seed_four_sources(db_session, test_user.id, identity_id=ident_b.id, day_offset=7)
        seed_four_sources(db_session, test_user.id, identity_id=None, day_offset=14)
        return {"a": ident_a, "b": ident_b}

    def test_no_filter_returns_all(self, db_session, test_user, two_identities):
        """不传任何过滤 → 三个来源全都在（4×3=12）。"""
        out = _svc(db_session, test_user.id).list()
        assert out.total == 12

    def test_filter_by_identity_id_only_that_identity(self, db_session, test_user,
                                                      two_identities):
        """identity_id 有值 → 只看该身份（4 条），且每条 identity_id 都对得上。"""
        out = _svc(db_session, test_user.id).list(identity_id=two_identities["a"].id)

        assert out.total == 4
        assert all(i.identity_id == two_identities["a"].id for i in out.items)

    def test_filter_unassigned_only_null_identity(self, db_session, test_user,
                                                  two_identities):
        """identity_unassigned=True → 只看未归类（4 条，identity_id 全为 None）。"""
        out = _svc(db_session, test_user.id).list(identity_unassigned=True)

        assert out.total == 4
        assert all(i.identity_id is None for i in out.items)

    def test_identity_id_takes_precedence_over_unassigned(self, db_session, test_user,
                                                          two_identities):
        """两者同时传 → identity_id 优先（elif 分支；不叠加、不取并集）。

        防什么：若实现成两个独立 if 取并集，前端「选了具体身份又残留哨兵」
        时会串出未归类数据。
        """
        out = _svc(db_session, test_user.id).list(
            identity_id=two_identities["b"].id, identity_unassigned=True,
        )
        assert out.total == 4
        assert all(i.identity_id == two_identities["b"].id for i in out.items)

    def test_source_counts_reflect_filtered_set(self, db_session, test_user,
                                                two_identities):
        """source_counts 是**过滤后**的计数，不是全库计数。

        防什么：前端用 source_counts 做各源空态提示；若给全库计数，
        「该身份一条日记都没有」时仍会显示有数据。
        """
        out = _svc(db_session, test_user.id).list(identity_id=two_identities["a"].id)
        assert out.source_counts == {
            "diary": 1, "review": 1, "avatar_memory": 1, "project_memory": 1,
        }

    def test_unknown_identity_returns_empty(self, db_session, test_user, two_identities):
        """不存在的 identity_id → 空结果（不报错、不回落成全量）。"""
        out = _svc(db_session, test_user.id).list(identity_id="no-such-identity")
        assert out.total == 0
        assert out.source_counts == {}


# ============================================================
# 第 7 组：标题与摘要
# ============================================================
class TestGroup7TitleAndSnippet:
    """第7组：标题兜底与摘要截断（时间线卡片直接渲染这两个字段）。"""

    def test_snippet_truncated_to_120_chars(self, db_session, test_user):
        """正文超 120 字 → 摘要恰好 120 字（不截断会把卡片撑爆）。"""
        make_diary(db_session, test_user.id, content="字" * 300)
        out = _svc(db_session, test_user.id).list()

        assert out.items[0].snippet is not None
        assert len(out.items[0].snippet) == 120

    def test_snippet_exactly_120_not_truncated(self, db_session, test_user):
        """恰好 120 字 → 原样返回（边界不含糊）。"""
        make_diary(db_session, test_user.id, content="字" * 120)
        out = _svc(db_session, test_user.id).list()
        assert out.items[0].snippet == "字" * 120

    def test_snippet_none_when_content_empty(self, db_session, test_user):
        """正文为空串 / None → snippet 为 None，而不是空串（前端 v-if 依赖它）。"""
        make_diary(db_session, test_user.id, title="空正文", content="")
        make_avatar_memory(db_session, test_user.id, title="无内容", content=None)
        out = _svc(db_session, test_user.id).list()

        assert all(i.snippet is None for i in out.items)

    def test_diary_title_falls_back_to_default(self, db_session, test_user):
        """日记没有标题 → 兜底为「日记」。"""
        make_diary(db_session, test_user.id, title=None, content="有正文无标题")
        out = _svc(db_session, test_user.id).list()

        assert out.items[0].title == "日记"
        assert out.items[0].snippet == "有正文无标题"

    def test_review_title_includes_type(self, db_session, test_user):
        """复盘标题带类型：`复盘（weekly）`。"""
        make_review(db_session, test_user.id, type_="weekly")
        out = _svc(db_session, test_user.id).list()
        assert out.items[0].title == "复盘（weekly）"

    def test_review_title_falls_back_when_type_blank(self, db_session, test_user):
        """复盘 type 为空串（列非空但可为空串）→ 标题兜底 `复盘（daily）`。"""
        make_review(db_session, test_user.id, type_="")
        out = _svc(db_session, test_user.id).list()
        assert out.items[0].title == "复盘（daily）"

    def test_review_snippet_none_without_summary(self, db_session, test_user):
        """复盘 data 里没有 summary 键 → snippet 为 None（不抛 KeyError）。"""
        make_review(db_session, test_user.id, data={"mood": 4})
        out = _svc(db_session, test_user.id).list()
        assert out.items[0].snippet is None

    def test_memory_titles_are_used_verbatim(self, db_session, test_user):
        """分身记忆用 title、项目记忆用 name 作为标题（不加工、不加前缀）。"""
        make_avatar_memory(db_session, test_user.id, title="我不爱吃香菜")
        make_project_memory(db_session, test_user.id, name="启明星三期")
        out = _svc(db_session, test_user.id).list()

        titles = {i.source: i.title for i in out.items}
        assert titles["avatar_memory"] == "我不爱吃香菜"
        assert titles["project_memory"] == "启明星三期"


# ============================================================
# 第 8 组：越权隔离（单用户模式下仍必须按 user_id 过滤）
# ============================================================
class TestGroup8OwnershipIsolation:
    """第8组：四源查询都必须带 user_id 过滤，否则他人数据会汇进我的时间线。"""

    def test_other_user_sources_excluded(self, db_session, test_user, other_user):
        """他人四源各一条 → 我的时间线仍为空、total=0、source_counts={}。

        防什么：聚合视图最容易漏掉 WHERE user_id —— 单用户开发时看不出来，
        多用户/同步后就是隐私事故。
        """
        seed_four_sources(db_session, other_user.id)
        out = _svc(db_session, test_user.id).list()

        assert out.total == 0
        assert out.items == []
        assert out.source_counts == {}

    def test_own_data_unaffected_by_other_user(self, db_session, test_user, other_user):
        """他人有数据不干扰我的条数与顺序。"""
        seed_four_sources(db_session, test_user.id)
        seed_four_sources(db_session, other_user.id)
        out = _svc(db_session, test_user.id).list()

        assert out.total == 4
        assert _sources(out) == FIXTURE_EXPERIENCE_DESC_ORDER

    def test_other_user_identity_not_filterable(self, db_session, test_user, other_user):
        """拿他人的 identity_id 过滤 → 得到 0 条（身份过滤不越过用户边界）。"""
        other_ident = make_identity(db_session, other_user.id, name="他人身份")
        seed_four_sources(db_session, other_user.id, identity_id=other_ident.id)

        out = _svc(db_session, test_user.id).list(identity_id=other_ident.id)
        assert out.total == 0


# ============================================================
# 第 9 组：真的只读 + 单源上限
# ============================================================
class TestGroup9ReadOnlyAndCap:
    """第9组：铁律「经历视图不建表、不写数据」必须被测试守住。"""

    def test_read_only_does_not_write_source_rows(self, db_session, test_user):
        """调用 list() 前后四张源表行数完全不变。"""
        seed_four_sources(db_session, test_user.id)
        before = {
            t: count_rows(db_session, t)
            for t in ("diaries", "reviews", "avatar_memories", "project_memories")
        }

        _svc(db_session, test_user.id).list()

        db_session.expire_all()
        after = {
            t: count_rows(db_session, t)
            for t in ("diaries", "reviews", "avatar_memories", "project_memories")
        }
        assert after == before
        assert before["diaries"] == 1

    def test_read_only_does_not_create_tables(self, db_session, test_user):
        """调用前后 sqlite_master 的表集合不变（不出现 experiences 之类的表）。"""
        from sqlalchemy import text

        def tables():
            return {
                r[0] for r in db_session.execute(
                    text("SELECT name FROM sqlite_master WHERE type='table'")
                ).all()
            }

        before = tables()
        seed_four_sources(db_session, test_user.id)
        _svc(db_session, test_user.id).list()
        after = tables()

        assert after == before
        assert not any("experience" in t for t in after)

    def test_repeated_calls_are_idempotent(self, db_session, test_user):
        """连续两次调用结果一致（只读视图不应有自增/副作用导致的漂移）。"""
        seed_four_sources(db_session, test_user.id)
        first = _svc(db_session, test_user.id).list()
        second = _svc(db_session, test_user.id).list()

        assert first.total == second.total == 4
        assert _sources(first) == _sources(second)
        assert [i.id for i in first.items] == [i.id for i in second.items]

    def test_per_source_cap_limits_single_source(self, db_session, test_user):
        """单源超过 _PER_SOURCE_CAP(500) → 该源只取 500 条（防御性上限）。

        防什么：个人规模虽远达不到，但一旦某一源被脚本灌爆（例如导入历史日记），
        全量拉取 + 内存归并会让请求卡死。上限是明确的降级策略，写成契约。
        """
        from app.models.life import Diary

        db_session.add_all([
            Diary(user_id=test_user.id, title=f"批量{i}", content="x",
                  diary_date=date(2026, 1, 1), tags=[])
            for i in range(_PER_SOURCE_CAP + 1)
        ])
        db_session.flush()
        assert count_rows(db_session, "diaries") == _PER_SOURCE_CAP + 1

        out = _svc(db_session, test_user.id).list(page=1, page_size=1000)

        assert out.total == _PER_SOURCE_CAP
        assert out.source_counts == {"diary": _PER_SOURCE_CAP}

    def test_cap_is_per_source_not_global(self, db_session, test_user):
        """上限是「每源」而不是全局：一源打满不影响另一源照常返回。"""
        from app.models.life import Diary

        db_session.add_all([
            Diary(user_id=test_user.id, title=f"批量{i}", content="x",
                  diary_date=date(2026, 1, 1), tags=[])
            for i in range(_PER_SOURCE_CAP + 1)
        ])
        make_review(db_session, test_user.id, review_date=date(2026, 2, 2))
        db_session.flush()

        out = _svc(db_session, test_user.id).list(page=1, page_size=1000)

        assert out.total == _PER_SOURCE_CAP + 1
        assert out.source_counts == {"diary": _PER_SOURCE_CAP, "review": 1}
