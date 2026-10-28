# ============================================================
# Phase5 · schemas 校验边界测试
#
# 目标：把 Pydantic 层"哪些输入会被拒绝/接受"钉死，防止契约静默松动。
# 重点：
#   - 必填缺失 / 空串 / 超长 / 非法枚举 / 非法正则；
#   - ADR-0008：Update 模型"省略 ≠ 显式 null"（exclude_unset 语义）；
#   - 输出侧 Literal 收紧（非法状态在响应校验时立即暴露）。
# 纯单元测试：不建库、不联网。
# ============================================================
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.auth import InitRequest, PetPosition, UpdateConfigRequest
from app.schemas.document import CreateDocumentRequest, UpdateDocumentRequest
from app.schemas.identity import CreateIdentityRequest, UpdateIdentityRequest
from app.schemas.panel import UpdateQuickTodoRequest
from app.schemas.project import MilestoneUpdate, ProjectUpdate
from app.schemas.task import (
    BatchTaskRequest,
    CreateSubtaskRequest,
    CreateTaskRequest,
    TaskOut,
    UpdateSubtaskRequest,
    UpdateTaskRequest,
)


# ================================================================
# 一、Create 必填/长度边界
# ================================================================
class TestCreateRequestBoundaries:
    def test_create_task_requires_title(self):
        with pytest.raises(ValidationError):
            CreateTaskRequest()

    def test_create_task_rejects_empty_title(self):
        with pytest.raises(ValidationError):
            CreateTaskRequest(title="")

    def test_create_task_accepts_title_at_max_length(self):
        assert CreateTaskRequest(title="x" * 500).title == "x" * 500

    def test_create_task_rejects_title_over_max_length(self):
        with pytest.raises(ValidationError):
            CreateTaskRequest(title="x" * 501)

    def test_create_task_rejects_invalid_due_date(self):
        with pytest.raises(ValidationError):
            CreateTaskRequest(title="t", due_date="not-a-date")

    def test_create_task_ignores_unknown_fields(self):
        """默认 extra=ignore：未知字段不报错，但也不会进入模型。"""
        obj = CreateTaskRequest(title="t", definitely_unknown_field=1)
        assert "definitely_unknown_field" not in obj.model_dump()

    def test_create_subtask_title_boundaries(self):
        assert CreateSubtaskRequest(title="x" * 500).title == "x" * 500
        with pytest.raises(ValidationError):
            CreateSubtaskRequest(title="")
        with pytest.raises(ValidationError):
            CreateSubtaskRequest(title="x" * 501)

    def test_create_document_requires_non_empty_title(self):
        with pytest.raises(ValidationError):
            CreateDocumentRequest(title="")
        with pytest.raises(ValidationError):
            CreateDocumentRequest(title="x" * 501)

    def test_init_request_nickname_boundaries(self):
        assert InitRequest(nickname="x" * 50).nickname == "x" * 50
        with pytest.raises(ValidationError):
            InitRequest(nickname="")
        with pytest.raises(ValidationError):
            InitRequest(nickname="x" * 51)


# ================================================================
# 二、Update 模型：省略 = 不改；显式 null = 清空（ADR-0008）
# ================================================================
class TestNullVersusOmittedSemantics:
    def test_update_task_all_omitted_dumps_nothing(self):
        assert UpdateTaskRequest().model_dump(exclude_unset=True) == {}

    def test_update_task_explicit_null_is_kept(self):
        payload = UpdateTaskRequest(project_id=None).model_dump(exclude_unset=True)
        assert payload == {"project_id": None}

    def test_update_task_omitted_field_absent_from_payload(self):
        payload = UpdateTaskRequest(title="新标题").model_dump(exclude_unset=True)
        assert payload == {"title": "新标题"}
        assert "project_id" not in payload

    def test_update_document_null_vs_omitted(self):
        assert UpdateDocumentRequest().model_dump(exclude_unset=True) == {}
        assert UpdateDocumentRequest(folder_id=None).model_dump(exclude_unset=True) == {
            "folder_id": None
        }

    def test_update_document_title_null_is_allowed_but_empty_rejected(self):
        assert UpdateDocumentRequest(title=None).title is None
        with pytest.raises(ValidationError):
            UpdateDocumentRequest(title="")

    def test_project_update_null_vs_omitted(self):
        assert ProjectUpdate().model_dump(exclude_unset=True) == {}
        assert ProjectUpdate(identity_id=None).model_dump(exclude_unset=True) == {
            "identity_id": None
        }


# ================================================================
# 三、数值/枚举/正则边界
# ================================================================
class TestNumericAndEnumBoundaries:
    @pytest.mark.parametrize("value", [-1, 100001])
    def test_update_task_estimated_minutes_out_of_range(self, value):
        with pytest.raises(ValidationError):
            UpdateTaskRequest(estimated_minutes=value)

    @pytest.mark.parametrize("value", [0, 100000])
    def test_update_task_estimated_minutes_boundary_ok(self, value):
        assert UpdateTaskRequest(estimated_minutes=value).estimated_minutes == value

    @pytest.mark.parametrize("value", [-1, 101])
    def test_update_config_inspiration_probability_out_of_range(self, value):
        with pytest.raises(ValidationError):
            UpdateConfigRequest(inspiration_probability=value)

    @pytest.mark.parametrize("value", [0, 100])
    def test_update_config_inspiration_probability_boundary_ok(self, value):
        assert UpdateConfigRequest(inspiration_probability=value).inspiration_probability == value

    def test_update_config_nickname_max_length(self):
        assert UpdateConfigRequest(nickname="x" * 50).nickname == "x" * 50
        with pytest.raises(ValidationError):
            UpdateConfigRequest(nickname="x" * 51)

    def test_batch_task_requires_non_empty_task_ids(self):
        with pytest.raises(ValidationError):
            BatchTaskRequest(task_ids=[], action="complete")

    def test_batch_task_rejects_unknown_action(self):
        with pytest.raises(ValidationError):
            BatchTaskRequest(task_ids=["t1"], action="explode")

    @pytest.mark.parametrize(
        "action", ["complete", "delete", "move_project", "set_priority"]
    )
    def test_batch_task_accepts_documented_actions(self, action):
        assert BatchTaskRequest(task_ids=["t1"], action=action).action == action

    def test_pet_position_rejects_non_numeric(self):
        with pytest.raises(ValidationError):
            PetPosition(x="left", y=1)

    def test_pet_position_coerces_integral_float(self):
        assert PetPosition(x=1.0, y=2.0) == PetPosition(x=1, y=2)

    def test_task_out_rejects_invalid_status_literal(self):
        base = dict(
            id="t1", title="t", status="todo", priority="medium",
            created_at="2026-01-01T00:00:00", updated_at="2026-01-01T00:00:00",
        )
        with pytest.raises(ValidationError):
            TaskOut(**base)

    def test_task_out_rejects_invalid_priority_literal(self):
        base = dict(
            id="t1", title="t", status="pending", priority="critical",
            created_at="2026-01-01T00:00:00", updated_at="2026-01-01T00:00:00",
        )
        with pytest.raises(ValidationError):
            TaskOut(**base)

    def test_task_out_parses_datetime_strings(self):
        out = TaskOut(
            id="t1", title="t", status="in_progress", priority="high",
            created_at="2026-01-01T00:00:00", updated_at="2026-01-02T03:04:05",
        )
        assert out.created_at.year == 2026
        assert out.updated_at.hour == 3


# ================================================================
# 四、Identity / Panel 的正则与空值边界
# ================================================================
class TestIdentityAndPanelBoundaries:
    @pytest.mark.parametrize("slug", ["Bad Slug", "-leading", "UPPER", "中文"])
    def test_identity_slug_pattern_rejects_invalid(self, slug):
        with pytest.raises(ValidationError):
            CreateIdentityRequest(name="身份", slug=slug)

    @pytest.mark.parametrize("slug", ["a", "my-identity", "id-2026"])
    def test_identity_slug_pattern_accepts_valid(self, slug):
        assert CreateIdentityRequest(name="身份", slug=slug).slug == slug

    def test_identity_slug_max_length(self):
        with pytest.raises(ValidationError):
            CreateIdentityRequest(name="身份", slug="a" * 61)

    @pytest.mark.parametrize("color", ["#fff", "Primary", ""])
    def test_identity_color_token_pattern_rejects_invalid(self, color):
        with pytest.raises(ValidationError):
            CreateIdentityRequest(name="身份", slug="ok", color_token=color)

    def test_identity_description_max_length(self):
        with pytest.raises(ValidationError):
            CreateIdentityRequest(name="身份", slug="ok", description="x" * 501)

    def test_update_identity_name_empty_rejected_but_null_allowed(self):
        assert UpdateIdentityRequest(name=None).name is None
        with pytest.raises(ValidationError):
            UpdateIdentityRequest(name="")

    def test_panel_quick_todo_title_boundaries(self):
        assert UpdateQuickTodoRequest(title=None).title is None
        with pytest.raises(ValidationError):
            UpdateQuickTodoRequest(title="")

    def test_milestone_update_name_empty_rejected(self):
        with pytest.raises(ValidationError):
            MilestoneUpdate(name="")
        with pytest.raises(ValidationError):
            MilestoneUpdate(name="x" * 201)

    def test_update_subtask_null_vs_empty_title(self):
        assert UpdateSubtaskRequest(title=None).title is None
        with pytest.raises(ValidationError):
            UpdateSubtaskRequest(title="")
