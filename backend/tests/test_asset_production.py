# ============================================================
# AssetService 生产级测试（原缺失模块，本轮补齐）
#
# 长期资产库 = SOP / Prompt模板 / Skill / 项目记忆 四组 CRUD。
# 它是「PATCH 请求体是裸 dict」的典型区，也是本轮越权问题的重灾区。
#
# 2026-10-11 补测时实测到三类真实缺陷，本文件均留了回归断言：
#   ① 归属未校验（IDOR）—— 详情/更新/删除/使用只查存在性，拿到 id 即可操作他人数据；
#   ② 裸 dict 无差别 setattr（越权改字段）—— 可改 user_id / id / use_count / rating；
#   ③ 项目记忆的 project_id 只靠外键兜底 —— 不存在的 id 撞 IntegrityError（→500），
#      他人的 id 被静默接受。
# ============================================================
from __future__ import annotations

import pytest

from app.core.exceptions import NotFoundException, ValidationException
from app.models.asset import SOP, ProjectMemory, PromptTemplate, Skill
from app.models.base import utcnow
from app.models.identity import Identity
from app.models.project import Project
from app.schemas.asset import (
    CreateProjectMemoryRequest,
    CreatePromptTemplateRequest,
    CreateSkillRequest,
    CreateSOPRequest,
)
from app.services.asset_service import AssetService
from tests.factories import count_rows

SOP_STEPS = [{"title": "收集数据"}, {"title": "写结论"}]
SOP_CHECKLIST = ["导出周数据", "写三条收获"]


def _svc(db) -> AssetService:
    return AssetService(db)


def _make_sop(db, user_id, **overrides) -> dict:
    payload = {
        "name": "周复盘 SOP", "category": "review", "description": "每周日固定流程",
        "steps": SOP_STEPS, "checklist": SOP_CHECKLIST, "tags": ["复盘", "习惯"],
    }
    payload.update(overrides)
    return _svc(db).create_sop(user_id, CreateSOPRequest(**payload))


def _make_prompt(db, user_id, **overrides) -> dict:
    payload = {
        "name": "建模拆题模板", "category": "math",
        "role_setting": "你是资深数学建模手",
        "task_description": "把 {{topic}} 拆成子问题",
        "constraints": "必须给出 {{budget}} 元预算内的方案",
        "output_format": "表格",
        "variables": ["topic", "budget"],
    }
    payload.update(overrides)
    return _svc(db).create_prompt(user_id, CreatePromptTemplateRequest(**payload))


def _make_skill(db, user_id, **overrides) -> dict:
    payload = {"name": "最小覆盖圆算法", "category": "算法",
               "methodology": "增量化 Welzl", "tags": ["几何"]}
    payload.update(overrides)
    return _svc(db).create_skill(user_id, CreateSkillRequest(**payload))


def _make_memory(db, user_id, **overrides) -> dict:
    payload = {"name": "最小覆盖圆论文复盘", "summary": "投 CGTA",
               "successes": "算法收敛快", "failures": "灵敏度章节写浅", "tags": ["科研"]}
    payload.update(overrides)
    return _svc(db).create_memory(user_id, CreateProjectMemoryRequest(**payload))


def _make_identity(db, user_id, slug: str = "math", **overrides) -> Identity:
    idn = Identity(user_id=user_id, name="数学建模手", slug=slug,
                   color_token="primary", icon="star", **overrides)
    db.add(idn)
    db.flush()
    return idn


def _make_project(db, user_id, name: str = "启明星") -> Project:
    project = Project(user_id=user_id, name=name)
    db.add(project)
    db.flush()
    return project


# ============================================================
# SOP
# ============================================================
class TestSopCrud:
    """SOP 基础 CRUD 与版本管理。"""

    def test_create_defaults_and_persistence(self, db_session, test_user):
        """创建：version=1 / use_count=0，JSON 列（steps/checklist/tags）原样往返。"""
        out = _make_sop(db_session, test_user.id)

        assert set(out) == {
            "id", "name", "category", "description", "steps", "checklist", "tags",
            "use_count", "version", "created_at", "updated_at",
        }
        assert out["version"] == 1
        assert out["use_count"] == 0
        assert out["steps"] == SOP_STEPS
        assert out["checklist"] == SOP_CHECKLIST
        assert out["tags"] == ["复盘", "习惯"]

        row = db_session.get(SOP, out["id"])
        assert row.user_id == test_user.id
        assert row.name == "周复盘 SOP"
        assert row.steps[1]["title"] == "写结论"
        assert count_rows(db_session, "sops", user_id=test_user.id) == 1

    def test_create_minimal_payload_defaults_to_empty_lists(self, db_session, test_user):
        """只给 name 时：category/description 为 None，三个 JSON 列表为空数组（不是 null）。"""
        out = _svc(db_session).create_sop(test_user.id, CreateSOPRequest(name="空壳 SOP"))

        assert out["category"] is None and out["description"] is None
        assert out["steps"] == [] and out["checklist"] == [] and out["tags"] == []

    def test_list_category_filter_and_pagination(self, db_session, test_user):
        for i in range(3):
            _make_sop(db_session, test_user.id, name=f"复盘{i}", category="review")
        _make_sop(db_session, test_user.id, name="读书流程", category="reading")

        got = _svc(db_session).list_sops(test_user.id, page=1, page_size=2)
        assert got["total"] == 4 and len(got["list"]) == 2

        only_review = _svc(db_session).list_sops(test_user.id, category="review")
        assert only_review["total"] == 3
        assert all(s["category"] == "review" for s in only_review["list"])

    def test_list_isolated_per_user(self, db_session, test_user, other_user):
        _make_sop(db_session, test_user.id, name="我的 SOP")
        _make_sop(db_session, other_user.id, name="别人的 SOP")

        got = _svc(db_session).list_sops(test_user.id)
        assert [s["name"] for s in got["list"]] == ["我的 SOP"]

    def test_update_bumps_version_and_archives_snapshot(self, db_session, test_user):
        """更新必须：版本 +1，且把**改动前**的内容快照写进 sop_versions。"""
        sop = _make_sop(db_session, test_user.id)
        out = _svc(db_session).update_sop(
            test_user.id, sop["id"], {"name": "周复盘 SOP v2", "description": "加一条：复盘上周决策"},
            change_note="补充决策回顾",
        )

        assert out["version"] == 2
        assert out["name"] == "周复盘 SOP v2"
        assert out["description"] == "加一条：复盘上周决策"
        # 未传的字段保持原值（steps 未动）
        assert out["steps"] == SOP_STEPS

        versions = _svc(db_session).list_sop_versions(test_user.id, sop["id"])["versions"]
        assert len(versions) == 1
        v1 = versions[0]
        assert v1["version"] == 1
        assert v1["change_note"] == "补充决策回顾"
        # 快照是改动**前**的内容（这是版本管理存在的意义，写错就等于丢了旧版）
        assert v1["content"] == {
            "steps": SOP_STEPS, "checklist": SOP_CHECKLIST,
            "description": "每周日固定流程", "name": "周复盘 SOP",
        }

    def test_update_default_change_note_and_version_sequence(self, db_session, test_user):
        """连更两次：默认变更说明 + 版本历史降序 + 快照逐版递增。"""
        sop = _make_sop(db_session, test_user.id)
        _svc(db_session).update_sop(test_user.id, sop["id"], {"description": "第二版"})
        out = _svc(db_session).update_sop(test_user.id, sop["id"], {"description": "第三版"})

        assert out["version"] == 3
        versions = _svc(db_session).list_sop_versions(test_user.id, sop["id"])["versions"]
        assert [v["version"] for v in versions] == [2, 1]           # 降序
        assert versions[0]["change_note"] == "更新至v3"
        assert versions[1]["change_note"] == "更新至v2"
        assert versions[0]["content"]["description"] == "第二版"
        assert versions[1]["content"]["description"] == "每周日固定流程"
        assert count_rows(db_session, "sop_versions", sop_id=sop["id"]) == 2

    def test_update_cannot_escalate_fields(self, db_session, test_user, other_user):
        """回归（2026-10-11）：裸 dict 无差别 setattr 的越权改字段。

        原实现 `{k: v for k, v in data.items() if v is not None}` 会照单全收：
        user_id → 资产改归他人；id → 改主键让记录"消失"；version/use_count → 伪造计数。
        """
        sop = _make_sop(db_session, test_user.id)
        out = _svc(db_session).update_sop(test_user.id, sop["id"], {
            "name": "被改的名",
            "user_id": other_user.id,
            "id": "hacked-id",
            "use_count": 999,
            "version": 500,
            "deleted_at": utcnow().isoformat(),
        })

        assert out["name"] == "被改的名"        # 白名单内字段正常生效
        assert out["id"] == sop["id"]           # 主键不可改
        assert out["use_count"] == 0            # 计数不可伪造
        assert out["version"] == 2              # 只由服务端自增，不取客户端值

        row = db_session.get(SOP, sop["id"])
        assert row is not None, "主键被改会导致记录查不到"
        assert row.user_id == test_user.id
        assert row.deleted_at is None

    def test_update_does_not_clear_field_with_none(self, db_session, test_user):
        """契约：None 被丢弃（PATCH 不支持置空），想清空请传空串。"""
        sop = _make_sop(db_session, test_user.id)
        out = _svc(db_session).update_sop(test_user.id, sop["id"], {"description": None})
        assert out["description"] == "每周日固定流程"

    def test_use_sop_increments_and_returns_steps(self, db_session, test_user):
        sop = _make_sop(db_session, test_user.id)
        first = _svc(db_session).use_sop(test_user.id, sop["id"])
        second = _svc(db_session).use_sop(test_user.id, sop["id"])

        assert first["use_count"] == 1 and second["use_count"] == 2
        assert second["steps"] == SOP_STEPS         # 使用即返回步骤清单（前端弹窗用）
        assert db_session.get(SOP, sop["id"]).use_count == 2

    def test_delete_cascades_version_history(self, db_session, test_user):
        """删 SOP 必须连带清掉版本历史（靠 FK ON DELETE CASCADE，需 foreign_keys=ON）。"""
        sop = _make_sop(db_session, test_user.id)
        _svc(db_session).update_sop(test_user.id, sop["id"], {"description": "v2"})
        _svc(db_session).update_sop(test_user.id, sop["id"], {"description": "v3"})
        assert count_rows(db_session, "sop_versions", sop_id=sop["id"]) == 2

        _svc(db_session).delete_sop(test_user.id, sop["id"])
        assert count_rows(db_session, "sops", id=sop["id"]) == 0
        assert count_rows(db_session, "sop_versions", sop_id=sop["id"]) == 0, "版本历史成了孤儿"

    def test_get_unknown_raises_404(self, db_session, test_user):
        with pytest.raises(NotFoundException):
            _svc(db_session).get_sop(test_user.id, "no-such-sop")


class TestSopOwnership:
    """越权：他人 SOP 一律 404，且不得产生任何副作用。"""

    def test_other_user_cannot_read_or_modify(self, db_session, test_user, other_user):
        sop = _make_sop(db_session, test_user.id)
        mine = _svc(db_session)

        with pytest.raises(NotFoundException):
            mine.get_sop(other_user.id, sop["id"])
        with pytest.raises(NotFoundException):
            mine.update_sop(other_user.id, sop["id"], {"name": "篡改"})
        with pytest.raises(NotFoundException):
            mine.use_sop(other_user.id, sop["id"])
        with pytest.raises(NotFoundException):
            mine.list_sop_versions(other_user.id, sop["id"])
        with pytest.raises(NotFoundException):
            mine.delete_sop(other_user.id, sop["id"])

        # 副作用为零：没被改名、没被计数、没写版本、没被删
        row = db_session.get(SOP, sop["id"])
        assert row.name == "周复盘 SOP"
        assert row.version == 1 and row.use_count == 0
        assert count_rows(db_session, "sop_versions", sop_id=sop["id"]) == 0

    def test_owner_still_works(self, db_session, test_user):
        """补齐越权校验后，属主路径必须照常可用（防止"一刀切成 404"）。"""
        sop = _make_sop(db_session, test_user.id)
        assert _svc(db_session).get_sop(test_user.id, sop["id"])["id"] == sop["id"]
        assert _svc(db_session).use_sop(test_user.id, sop["id"])["use_count"] == 1
        _svc(db_session).delete_sop(test_user.id, sop["id"])
        assert count_rows(db_session, "sops", id=sop["id"]) == 0


# ============================================================
# Prompt 模板
# ============================================================
class TestPromptTemplate:
    """Prompt 模板：变量替换、评分、越权。"""

    def test_create_defaults(self, db_session, test_user):
        out = _make_prompt(db_session, test_user.id)
        assert out["use_count"] == 0
        assert out["rating"] is None            # 未评分 = None（不是 0，前端才能显示"未评分"）
        assert out["variables"] == ["topic", "budget"]

        bare = _svc(db_session).create_prompt(test_user.id, CreatePromptTemplateRequest(name="纯文本模板"))
        assert bare["role_setting"] is None and bare["variables"] == []

    def test_apply_renders_sections_in_fixed_order(self, db_session, test_user):
        """渲染顺序固定为 角色设定 → 任务描述 → 约束条件 → 输出格式，# 小节 + 空行分隔。"""
        prompt = _make_prompt(db_session, test_user.id)
        res = _svc(db_session).apply_prompt(
            test_user.id, prompt["id"], {"topic": "最小覆盖圆", "budget": "0"}
        )

        expected = (
            "# 角色设定\n你是资深数学建模手\n\n"
            "# 任务描述\n把 最小覆盖圆 拆成子问题\n\n"
            "# 约束条件\n必须给出 0 元预算内的方案\n\n"
            "# 输出格式\n表格"
        )
        assert res["rendered"] == expected
        assert set(res["variables_used"]) == {"topic", "budget"}
        assert res["prompt_id"] == prompt["id"]
        assert res["use_count"] == 1

    def test_apply_ignores_unmatched_variables_and_keeps_unknown_placeholders(
        self, db_session, test_user
    ):
        """只替换出现的占位符：多余的键不报错、未提供的占位符原样保留（可见即可修）。"""
        prompt = _make_prompt(db_session, test_user.id)
        res = _svc(db_session).apply_prompt(
            test_user.id, prompt["id"], {"topic": "T", "unused_key": "X"}
        )

        assert res["variables_used"] == ["topic"]
        assert "把 T 拆成子问题" in res["rendered"]
        assert "{{budget}}" in res["rendered"]      # 未提供 → 保留占位，便于用户发现漏填

    def test_apply_partial_template_omits_empty_sections(self, db_session, test_user):
        """未填写的小节整段不出现（不留空标题）。"""
        bare = _svc(db_session).create_prompt(
            test_user.id, CreatePromptTemplateRequest(name="最小模板", task_description="只做 {{x}}")
        )
        res = _svc(db_session).apply_prompt(test_user.id, bare["id"], {"x": "这件事"})
        assert res["rendered"] == "# 任务描述\n只做 这件事"

    def test_apply_empty_template_returns_empty_string(self, db_session, test_user):
        """四个字段都没填 → 渲染结果是空串（而非 None / 报错），计数照样 +1。"""
        bare = _svc(db_session).create_prompt(test_user.id, CreatePromptTemplateRequest(name="空模板"))
        res = _svc(db_session).apply_prompt(test_user.id, bare["id"], {})
        assert res["rendered"] == ""
        assert res["variables_used"] == []
        assert res["use_count"] == 1

    def test_use_count_accumulates(self, db_session, test_user):
        prompt = _make_prompt(db_session, test_user.id)
        for expected in (1, 2, 3):
            assert _svc(db_session).apply_prompt(test_user.id, prompt["id"], {})["use_count"] == expected
        assert db_session.get(PromptTemplate, prompt["id"]).use_count == 3

    def test_rate_first_then_moving_average(self, db_session, test_user):
        """评分语义：首次直接落值，之后取「上次与本次的均值」，保留 1 位小数。"""
        prompt = _make_prompt(db_session, test_user.id)
        assert _svc(db_session).rate_prompt(test_user.id, prompt["id"], 4)["rating"] == 4.0
        assert _svc(db_session).rate_prompt(test_user.id, prompt["id"], 2)["rating"] == 3.0   # (4+2)/2
        assert _svc(db_session).rate_prompt(test_user.id, prompt["id"], 5)["rating"] == 4.0   # (3+5)/2

    def test_rate_rounds_to_one_decimal(self, db_session, test_user):
        prompt = _make_prompt(db_session, test_user.id)
        _svc(db_session).rate_prompt(test_user.id, prompt["id"], 4)
        # (4 + 3.33) / 2 = 3.665 → 3.7（round 到 1 位）
        assert _svc(db_session).rate_prompt(test_user.id, prompt["id"], 3.33)["rating"] == 3.7

    def test_update_whitelist_blocks_use_count_and_rating(self, db_session, test_user, other_user):
        """回归（2026-10-11）：更新白名单 —— rating 只能由 rate 接口产生，计数只能由 apply 累加。"""
        prompt = _make_prompt(db_session, test_user.id)
        out = _svc(db_session).update_prompt(test_user.id, prompt["id"], {
            "description": "改了说明",
            "user_id": other_user.id,
            "use_count": 999,
            "rating": 5.0,
            "id": "hacked",
        })

        assert out["description"] == "改了说明"
        assert out["use_count"] == 0
        assert out["rating"] is None
        assert out["id"] == prompt["id"]
        assert db_session.get(PromptTemplate, prompt["id"]).user_id == test_user.id

    def test_delete_prompt(self, db_session, test_user):
        prompt = _make_prompt(db_session, test_user.id)
        _svc(db_session).delete_prompt(test_user.id, prompt["id"])
        assert count_rows(db_session, "prompt_templates", id=prompt["id"]) == 0
        with pytest.raises(NotFoundException):
            _svc(db_session).get_prompt(test_user.id, prompt["id"])

    def test_other_user_cannot_read_modify_or_use(self, db_session, test_user, other_user):
        prompt = _make_prompt(db_session, test_user.id)
        svc = _svc(db_session)
        for call in (
            lambda: svc.get_prompt(other_user.id, prompt["id"]),
            lambda: svc.update_prompt(other_user.id, prompt["id"], {"name": "篡改"}),
            lambda: svc.delete_prompt(other_user.id, prompt["id"]),
            lambda: svc.apply_prompt(other_user.id, prompt["id"], {}),
            lambda: svc.rate_prompt(other_user.id, prompt["id"], 1),
        ):
            with pytest.raises(NotFoundException):
                call()

        row = db_session.get(PromptTemplate, prompt["id"])
        assert row.name == "建模拆题模板"
        assert row.use_count == 0 and row.rating is None


# ============================================================
# Skill
# ============================================================
class TestSkill:
    """技能库。"""

    def test_create_defaults_and_proficiency(self, db_session, test_user):
        out = _make_skill(db_session, test_user.id)
        assert out["use_count"] == 0
        assert out["tags"] == ["几何"]
        assert out["methodology"] == "增量化 Welzl"

        bare = _svc(db_session).create_skill(test_user.id, CreateSkillRequest(name="新技能"))
        assert bare["proficiency"] == "beginner"      # 默认熟练度由 schema 提供
        assert bare["tags"] == [] and bare["category"] is None

    def test_update_and_use_count(self, db_session, test_user):
        skill = _make_skill(db_session, test_user.id)
        out = _svc(db_session).update_skill(test_user.id, skill["id"], {
            "proficiency": "expert", "description": "已用于两篇论文",
        })
        assert out["proficiency"] == "expert"
        assert out["name"] == "最小覆盖圆算法"          # 未传字段不动

        assert _svc(db_session).use_skill(test_user.id, skill["id"])["use_count"] == 1
        assert db_session.get(Skill, skill["id"]).use_count == 1

    def test_update_whitelist_blocks_ownership_change(self, db_session, test_user, other_user):
        """回归（2026-10-11）：越权改字段。"""
        skill = _make_skill(db_session, test_user.id)
        out = _svc(db_session).update_skill(test_user.id, skill["id"], {
            "name": "改名", "user_id": other_user.id, "use_count": 42, "id": "hacked",
        })
        assert out["name"] == "改名"
        assert out["use_count"] == 0
        assert out["id"] == skill["id"]
        assert db_session.get(Skill, skill["id"]).user_id == test_user.id

    def test_other_user_cannot_read_modify_use_or_delete(self, db_session, test_user, other_user):
        skill = _make_skill(db_session, test_user.id)
        svc = _svc(db_session)
        for call in (
            lambda: svc.update_skill(other_user.id, skill["id"], {"name": "篡改"}),
            lambda: svc.use_skill(other_user.id, skill["id"]),
            lambda: svc.delete_skill(other_user.id, skill["id"]),
        ):
            with pytest.raises(NotFoundException):
                call()

        row = db_session.get(Skill, skill["id"])
        assert row.name == "最小覆盖圆算法" and row.use_count == 0

    def test_delete_skill(self, db_session, test_user):
        skill = _make_skill(db_session, test_user.id)
        _svc(db_session).delete_skill(test_user.id, skill["id"])
        assert count_rows(db_session, "skills", id=skill["id"]) == 0


# ============================================================
# 项目记忆（身份轴 + 项目轴）
# ============================================================
class TestProjectMemory:
    """项目记忆：身份轴与项目轴的归属校验是这一组的核心。"""

    def test_create_minimal_defaults(self, db_session, test_user):
        out = _make_memory(db_session, test_user.id)
        assert out["project_id"] is None
        assert out["identity_id"] is None
        assert out["extracted_assets"] == []
        assert out["key_metrics"] == {}
        assert out["tags"] == ["科研"]
        assert count_rows(db_session, "project_memories", user_id=test_user.id) == 1

    def test_create_with_own_project_and_filter(self, db_session, test_user):
        project = _make_project(db_session, test_user.id, name="启明星")
        other = _make_project(db_session, test_user.id, name="神之怒")

        _make_memory(db_session, test_user.id, name="A", project_id=project.id)
        _make_memory(db_session, test_user.id, name="B", project_id=other.id)
        _make_memory(db_session, test_user.id, name="C")

        got = _svc(db_session).list_memories(test_user.id, project_id=project.id)
        assert got["total"] == 1
        assert got["list"][0]["name"] == "A"
        assert _svc(db_session).list_memories(test_user.id)["total"] == 3

    def test_create_with_unknown_project_rejected(self, db_session, test_user):
        """回归（2026-10-11）：不存在的 project_id 原先直接撞外键 →
        IntegrityError 未捕获 → 500。现在应在写入前给出 1001 业务错误。"""
        with pytest.raises(ValidationException):
            _make_memory(db_session, test_user.id, project_id="no-such-project")
        assert count_rows(db_session, "project_memories", user_id=test_user.id) == 0

    def test_create_with_foreign_project_rejected(self, db_session, test_user, other_user):
        """回归（2026-10-11）：他人项目 id 原先被静默接受（跨用户挂靠）。"""
        their_project = _make_project(db_session, other_user.id, name="别人的项目")
        with pytest.raises(ValidationException):
            _make_memory(db_session, test_user.id, project_id=their_project.id)
        assert count_rows(db_session, "project_memories", user_id=test_user.id) == 0

    def test_create_with_own_identity(self, db_session, test_user):
        idn = _make_identity(db_session, test_user.id, slug="math")
        out = _make_memory(db_session, test_user.id, identity_id=idn.id)
        assert out["identity_id"] == idn.id

    def test_create_with_foreign_identity_rejected(self, db_session, test_user, other_user):
        their_idn = _make_identity(db_session, other_user.id, slug="math")
        with pytest.raises(ValidationException):
            _make_memory(db_session, test_user.id, identity_id=their_idn.id)

    def test_create_with_soft_deleted_identity_rejected(self, db_session, test_user):
        """软删身份不得再被挂靠（三期 B：identity_id 是应用层关联，无外键兜底）。"""
        idn = _make_identity(db_session, test_user.id, slug="math", deleted_at=utcnow())
        with pytest.raises(ValidationException):
            _make_memory(db_session, test_user.id, identity_id=idn.id)

    def test_create_with_unknown_identity_rejected(self, db_session, test_user):
        with pytest.raises(ValidationException):
            _make_memory(db_session, test_user.id, identity_id="no-such-identity")

    def test_update_validates_identity_and_project_axes(self, db_session, test_user, other_user):
        """更新同样要过轴校验（否则可以绕过创建时的守卫把记忆挂到他人数据上）。"""
        memory = _make_memory(db_session, test_user.id)
        their_idn = _make_identity(db_session, other_user.id, slug="math")
        their_project = _make_project(db_session, other_user.id, name="别人的项目")

        with pytest.raises(ValidationException):
            _svc(db_session).update_memory(test_user.id, memory["id"], {"identity_id": their_idn.id})
        with pytest.raises(ValidationException):
            _svc(db_session).update_memory(test_user.id, memory["id"], {"project_id": their_project.id})

        # 合法更新仍可用
        mine = _make_identity(db_session, test_user.id, slug="dev")
        out = _svc(db_session).update_memory(test_user.id, memory["id"], {
            "identity_id": mine.id, "key_metrics": {"投稿次数": 2},
        })
        assert out["identity_id"] == mine.id
        assert out["key_metrics"] == {"投稿次数": 2}

    def test_update_whitelist_blocks_ownership_change(self, db_session, test_user, other_user):
        """回归（2026-10-11）：越权改字段（user_id 可被直接改写）。"""
        memory = _make_memory(db_session, test_user.id)
        out = _svc(db_session).update_memory(test_user.id, memory["id"], {
            "summary": "改了摘要",
            "user_id": other_user.id,
            "id": "hacked",
            "extracted_assets": ["可复用：搜索脚本"],
        })

        assert out["summary"] == "改了摘要"
        assert out["extracted_assets"] == ["可复用：搜索脚本"]
        assert out["id"] == memory["id"]
        assert db_session.get(ProjectMemory, memory["id"]).user_id == test_user.id

    def test_other_user_cannot_read_modify_or_delete(self, db_session, test_user, other_user):
        memory = _make_memory(db_session, test_user.id)
        svc = _svc(db_session)
        for call in (
            lambda: svc.get_memory(other_user.id, memory["id"]),
            lambda: svc.update_memory(other_user.id, memory["id"], {"name": "篡改"}),
            lambda: svc.delete_memory(other_user.id, memory["id"]),
        ):
            with pytest.raises(NotFoundException):
                call()

        assert db_session.get(ProjectMemory, memory["id"]).name == "最小覆盖圆论文复盘"

    def test_list_isolated_per_user(self, db_session, test_user, other_user):
        _make_memory(db_session, test_user.id, name="我的记忆")
        _make_memory(db_session, other_user.id, name="别人的记忆")
        got = _svc(db_session).list_memories(test_user.id)
        assert [m["name"] for m in got["list"]] == ["我的记忆"]

    def test_delete_memory(self, db_session, test_user):
        memory = _make_memory(db_session, test_user.id)
        _svc(db_session).delete_memory(test_user.id, memory["id"])
        assert count_rows(db_session, "project_memories", id=memory["id"]) == 0
