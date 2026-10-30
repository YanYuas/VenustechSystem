# ============================================================
# 领域规则引擎（domain_engine）边界测试（Phase7-D · 覆盖率补缺）
#
# 本模块是通过 learning_service 间接被调用的（生成学习计划），因此主流程
# 已有覆盖；这里补 Phase6 term-missing 指出的**边界与用户扩展层**：
#   · 用户领域扩展（F4.1）：合法加载 / 坏 JSON / 缺 key 或 patterns /
#     与内置 key 冲突 / 用户内重复 key / 内置优先于用户；
#   · extract_skill_name 的三条兜底路径（冒号、学会句型、前缀清洗）；
#   · parse_duration_minutes 的文本归一与「识别失败返回 None」；
#   · expand_tasks 的空池/0 条、循环池与「（第N次）」后缀；
#   · generate_plan 的空单元守卫、日模式配额不足补齐、周模式全分支；
#   · generate_study_plan 的入参钳制与 weekly_mode 判定。
#
# 用户领域文件写在 VENUSTECH_TEST_DATA_DIR/rules/domains 下（生产路径），
# 用例前后清理并把模块级缓存/全局态恢复原值。
# ============================================================
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from app.config import get_settings
from app.services.rules import domain_engine as de
from app.services.rules.domain_lib import DOMAIN_LIB, DomainDef, TaskDef, UnitDef


def _domains_dir() -> Path:
    return Path(get_settings().data_dir) / "rules" / "domains"


@pytest.fixture()
def user_domains_env():
    """隔离用户扩展层：清空目录 + 保存/恢复模块级全局态。"""
    directory = _domains_dir()
    shutil.rmtree(directory, ignore_errors=True)
    directory.mkdir(parents=True, exist_ok=True)
    saved = (de._user_domains, de._user_domains_loaded)
    de._user_domains = ()
    de._user_domains_loaded = False
    try:
        yield directory
    finally:
        de._user_domains, de._user_domains_loaded = saved
        shutil.rmtree(directory, ignore_errors=True)


def _write_domain(directory: Path, filename: str, payload: dict | str) -> None:
    text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
    (directory / filename).write_text(text, encoding="utf-8")


# ================================================================
# 一、用户扩展层（F4.1）
# ================================================================
class TestUserDomainLayer:
    def test_reload_loads_valid_user_domain_and_match_falls_back_to_it(
        self, user_domains_env
    ):
        _write_domain(user_domains_env, "coffee.json", {
            "key": "pour-over-coffee",
            "name": "手冲咖啡",
            "patterns": ["手冲咖啡"],
            "verify_task": "独立冲出一杯手冲并记录风味",
            "units": [
                {
                    "name": "器具与参数",
                    "tasks": [
                        {"task": "列出必备器具", "duration": "30分钟",
                         "acceptance": "一份器具清单"},
                        {"task": "练习注水", "duration": "45分钟",
                         "acceptance": "连续 3 杯稳定", "repeatable": True},
                    ],
                },
            ],
        })

        stats = de.reload_user_domains()
        assert stats["user"] == 1
        assert stats["builtin"] == len(DOMAIN_LIB)
        assert stats["total"] == len(DOMAIN_LIB) + 1
        assert stats["skipped"] == []

        matched = de.match_domain("我想学手冲咖啡")
        assert matched is not None
        assert matched.key == "pour-over-coffee"
        assert matched.source == "user"
        assert matched.units[0].tasks[1].repeatable is True  # _parse_user_domain 生效

    def test_builtin_domain_wins_over_user_extension(self, user_domains_env):
        _write_domain(user_domains_env, "ielts-clone.json", {
            "key": "my-ielts", "name": "我的雅思", "patterns": ["雅思"],
            "verify_task": "v", "units": [],
        })
        de.reload_user_domains()

        matched = de.match_domain("我想考雅思")
        assert matched is not None
        assert matched.key == DOMAIN_LIB[0].key     # 内置优先
        assert matched.source == "builtin"

    def test_list_domains_appends_user_extensions(self, user_domains_env):
        assert len(de.list_domains()) == len(DOMAIN_LIB)
        _write_domain(user_domains_env, "x.json", {
            "key": "knitting", "name": "织毛衣", "patterns": ["织毛衣"],
            "verify_task": "v", "units": [],
        })
        de.reload_user_domains()
        domains = de.list_domains()
        assert len(domains) == len(DOMAIN_LIB) + 1
        assert domains[-1].key == "knitting"
        assert domains[-1].source == "user"

    def test_reload_skips_broken_json(self, user_domains_env):
        _write_domain(user_domains_env, "broken.json", "{not valid json")
        stats = de.reload_user_domains()
        assert stats["user"] == 0
        assert [s["file"] for s in stats["skipped"]] == ["broken.json"]
        assert stats["skipped"][0]["reason"]

    def test_reload_skips_missing_key_or_patterns(self, user_domains_env):
        _write_domain(user_domains_env, "no-key.json",
                      {"name": "x", "patterns": ["x"]})
        _write_domain(user_domains_env, "no-patterns.json",
                      {"key": "no-pat", "name": "x"})
        stats = de.reload_user_domains()
        assert stats["user"] == 0
        assert {s["file"] for s in stats["skipped"]} == {"no-key.json", "no-patterns.json"}
        assert all("缺少 key 或 patterns" in s["reason"] for s in stats["skipped"])

    def test_reload_skips_builtin_key_conflict(self, user_domains_env):
        builtin_key = DOMAIN_LIB[0].key
        _write_domain(user_domains_env, "conflict.json", {
            "key": builtin_key, "name": "覆盖内置", "patterns": ["zzz-unused"],
            "verify_task": "v", "units": [],
        })
        stats = de.reload_user_domains()
        assert stats["user"] == 0
        assert stats["skipped"][0]["file"] == "conflict.json"
        assert "内置优先" in stats["skipped"][0]["reason"]

    def test_reload_skips_duplicate_user_key(self, user_domains_env):
        payload = {"key": "dup", "name": "重复", "patterns": ["重复"], "units": []}
        _write_domain(user_domains_env, "a-first.json", payload)
        _write_domain(user_domains_env, "b-second.json", payload)
        stats = de.reload_user_domains()
        assert stats["user"] == 1
        assert [s["file"] for s in stats["skipped"]] == ["b-second.json"]
        assert stats["skipped"][0]["reason"] == "key 重复"

    def test_reload_is_idempotent_and_creates_missing_directory(self, user_domains_env):
        shutil.rmtree(user_domains_env)  # 目录不存在也要能自愈
        stats = de.reload_user_domains()
        assert stats["user"] == 0
        assert user_domains_env.is_dir()
        assert de.reload_user_domains()["user"] == 0


# ================================================================
# 二、技能名提取 / 领域匹配
# ================================================================
class TestSkillNameExtraction:
    def test_rule_table_has_priority_over_fallbacks(self):
        assert de.extract_skill_name("我想学 python") == "Python编程"
        assert de.extract_skill_name("想练英语口语") == "英语口语"

    def test_colon_is_used_as_skill_name(self):
        # 规则表未命中 → 冒号后的短语即技能名
        assert de.extract_skill_name("我想学点什么：手冲咖啡") == "手冲咖啡"

    def test_learn_phrase_is_used_as_skill_name(self):
        assert de.extract_skill_name("学会打绳结") == "打绳结"

    def test_prefix_strip_fallback(self):
        # 无规则/无冒号/无「学会」句型 → 清洗「我想/用30天/里」等前缀
        assert de.extract_skill_name("用30天织毛衣") == "织毛衣"
        assert de.extract_skill_name("我想学织毛衣") == "织毛衣"

    def test_unknown_goal_does_not_match_builtin_domain(self, user_domains_env):
        de.reload_user_domains()
        assert de.match_domain("zzz-不存在的领域-qqq") is None


# ================================================================
# 三、时长归一化 / 任务展开
# ================================================================
class TestDurationAndExpansion:
    def test_parse_duration_minutes_variants(self):
        assert de.parse_duration_minutes(None) is None
        assert de.parse_duration_minutes("") is None
        assert de.parse_duration_minutes("十分钟") is None      # 识别失败不猜
        assert de.parse_duration_minutes("90分钟") == 90
        assert de.parse_duration_minutes("约 3 小时（可拆两个半天）") == 180
        assert de.parse_duration_minutes("45分") == 45
        assert de.parse_duration_minutes("2h") == 120
        assert de.parse_duration_minutes("30min") == 30

    def test_expand_tasks_empty_pool_or_zero_count(self):
        assert de.expand_tasks((), 5, "30分钟") == []
        pool = (TaskDef(task="t", duration="10分钟", acceptance="a"),)
        assert de.expand_tasks(pool, 0, "30分钟") == []

    def test_expand_tasks_cycles_and_marks_repeat_suffix(self):
        pool = (
            TaskDef(task="重复练习", duration="20分钟", acceptance="a", repeatable=True),
            TaskDef(task="一次性任务", duration="10分钟", acceptance="b"),
        )
        counts: dict[int, int] = {}
        expanded = de.expand_tasks(pool, 5, "45分钟", 0, counts)
        titles = [e.task for e in expanded]
        assert titles[0] == "重复练习"
        assert titles[1] == "一次性任务"
        assert titles[2] == "重复练习（第2次）"   # 循环池里 repeatable 占两个槽
        assert titles[3] == "重复练习（第3次）"
        assert titles[4] == "一次性任务（第2次）"
        assert counts == {0: 3, 1: 2}

    def test_expand_tasks_offset_skips_pool_prefix(self):
        pool = tuple(
            TaskDef(task=f"t{i}", duration="10分钟", acceptance="a") for i in range(3)
        )
        expanded = de.expand_tasks(pool, 2, "30分钟", offset=1)
        assert [e.task for e in expanded] == ["t1", "t2"]


# ================================================================
# 四、计划排期（日 / 周 / 守卫 / 配额补齐）
# ================================================================
def _unit(name: str, task_count: int = 1) -> de.PlannedUnit:
    tasks = tuple(
        TaskDef(task=f"{name}-任务{i}", duration="30分钟", acceptance="a")
        for i in range(task_count)
    )
    return de.PlannedUnit(name=name, tasks=tasks, phase=1)


class TestPlanScheduling:
    def test_generate_plan_without_units_returns_verify_only(self):
        plan = de.generate_plan((), 30, 45, "完成验证")
        assert len(plan) == 1
        assert plan[0].is_verify is True
        assert plan[0].unit_id == "verify"
        assert plan[0].task == "完成验证"
        assert plan[0].acceptance == de.VERIFY_ACCEPTANCE

    def test_daily_plan_fills_quota_shortfall_to_exact_days(self):
        # 4 个单元各只有 1 条不重复任务 → 配额上限 3 天/单元，远小于 29 天，
        # 必须走「轮流补齐」分支才能正好排满 学习日。
        units = tuple(_unit(f"u{i}") for i in range(4))
        plan = de.generate_plan(units, 30, 30, "验证任务")

        assert len(plan) == 30                     # 29 学习日 + 1 验证
        learning = [p for p in plan if not p.is_verify]
        assert [p.day for p in learning] == list(range(1, 30))
        assert [p.day for p in plan][-1] == 30
        assert plan[-1].is_verify is True

    def test_daily_plan_has_one_verify_item_at_end(self):
        domain = de.match_domain("我想学雅思")
        units = de.build_unit_defs(domain, "雅思")
        plan = de.generate_plan(units, 10, 45, "验证任务")
        assert sum(1 for p in plan if p.is_verify) == 1
        assert plan[-1].is_verify is True
        assert all(p.day <= 10 for p in plan)

    def test_weekly_plan_mode_for_long_goals(self):
        result = de.generate_study_plan("我想学雅思", total_days=90, minutes_per_day=60)
        assert result.weekly_mode is True
        assert result.matched is True
        assert result.domain_key == "ielts"
        assert result.skill_name == "雅思"

        learning = [item for item in result.items if not item.is_verify]
        verify = [item for item in result.items if item.is_verify]
        assert learning and len(verify) == 1
        assert all(item.title.startswith("Week ") for item in learning)
        assert verify[0].title.startswith("Week ") and verify[0].is_verify
        # 周号单调不减，且验证周不早于所有学习周
        weeks = [item.day for item in result.items]
        assert weeks == sorted(weeks)
        assert verify[0].day >= max(i.day for i in learning)

    def test_generate_study_plan_clamps_inputs(self):
        result = de.generate_study_plan("学织毛衣", total_days=-5, minutes_per_day=3)
        assert result.total_days == 1                 # max(1, -5)
        assert result.minutes_per_day == 10           # max(10, 3)
        assert result.weekly_mode is False
        assert result.matched is False                # 未命中领域库 → 通用兜底
        assert result.domain_key is None
        assert result.verify_task
        assert result.items[-1].is_verify is True

    def test_build_unit_defs_marks_three_phases(self):
        # 阶段公式：i < 40% → 1；40%~85% → 2；≥85% → 3。
        # 通用拆解只有 4 个单元 → 0.85*4=3.4，最后一个仍落在阶段 2。
        generic = de.build_unit_defs(None, "织毛衣")
        assert [u.phase for u in generic] == [1, 1, 2, 2]

        # 单元数足够多（8 个）时才会出现阶段 3：3/8=37.5% → 1，7/8=87.5% → 3
        many_units = tuple(
            UnitDef(
                name=f"单元{i}",
                tasks=(TaskDef(task=f"任务{i}", duration="30分钟", acceptance="a"),),
            )
            for i in range(8)
        )
        many_domain = DomainDef(
            key="many", name="多单元", patterns=("多单元",),
            verify_task="验证", units=many_units,
        )
        phases = [u.phase for u in de.build_unit_defs(many_domain, "多单元")]
        assert phases == [1, 1, 1, 1, 2, 2, 2, 3]

        # 真实领域库：单元数不同，但阶段必须单调不减
        domain = de.match_domain("我想学雅思")
        ielts_phases = [u.phase for u in de.build_unit_defs(domain, "雅思")]
        assert ielts_phases == sorted(ielts_phases)
        assert ielts_phases[0] == 1

    def test_generic_units_have_executable_acceptance(self):
        units = de.generic_units("织毛衣")
        assert len(units) == 4
        assert [u.name.split(" · ")[-1] for u in units] == [
            "入门准备", "基础操作", "核心练习", "实战产出",
        ]
        assert all(task.acceptance for u in units for task in u.tasks)
        assert "织毛衣" in de.generic_verify_task("织毛衣")

    def test_js_round_half_up_matches_javascript(self):
        assert de.js_round(2.5) == 3
        assert de.js_round(2.4) == 2
        assert de.js_round(3.5) == 4
        assert de.js_round(0.0) == 0
