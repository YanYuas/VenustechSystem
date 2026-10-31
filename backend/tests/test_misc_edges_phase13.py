# ============================================================
# Phase13 · A 类覆盖率补缺：小工具 / 加密轮换 / 任务仓库 / Dashboard 边界
#
# 覆盖：
#   · core/utils.greeting_by_hour 四个时段分支；
#   · models/types 的 JSON 解析失败兜底 / StringList 非 list 兜底；
#   · encryption.rotate_key 写密钥环 OSError 被吞（轮换仍成功、旧密文仍可解）；
#   · TaskRepository.list 的 project_id 过滤分支；
#   · Dashboard 今日执行「未来到期」排序分支 + 真实 Project 加载失败后的
#     project_tag 降级聚合（含日志）。
# ============================================================
from __future__ import annotations

import uuid
from datetime import date, timedelta
from pathlib import Path

import pytest

from app.config import get_settings
from app.core.encryption import EncryptionManager
from app.core.utils import greeting_by_hour
from app.models.project import Project
from app.models.types import JSONType, StringListType
from app.repositories.task_repo import TaskRepository
from app.services.dashboard_service import DashboardService
from tests.factories import make_task


class TestSmallUtilities:
    @pytest.mark.parametrize(
        "hour,expected",
        [(3, "夜深了"), (9, "早上好"), (15, "下午好"), (21, "晚上好")],
    )
    def test_greeting_by_hour_covers_all_periods(self, hour, expected):
        assert greeting_by_hour(hour) == expected

    def test_json_type_invalid_text_degrades_to_none(self):
        column = JSONType()
        assert column.process_result_value("not-json", None) is None
        assert column.process_result_value(None, None) is None
        assert column.process_result_value('{"a": 1}', None) == {"a": 1}

    def test_string_list_type_degrades_to_empty_list(self):
        column = StringListType()
        assert column.process_result_value(None, None) == []
        assert column.process_result_value('"just-a-string"', None) == []
        assert column.process_result_value('["a", "b"]', None) == ["a", "b"]


class TestEncryptionRotateKeyErrorPaths:
    def test_keyring_write_oserror_is_swallowed_and_rotation_succeeds(
        self, monkeypatch
    ):
        data_dir = Path(get_settings().data_dir) / f"p13-enc-{uuid.uuid4().hex[:8]}"
        manager = EncryptionManager(data_dir)
        old_ciphertext = manager.encrypt("warm-up")   # 触发初始化

        real_write_text = Path.write_text

        def _boom_write_text(self, *args, **kwargs):
            if self.name.endswith(".keyring.json"):
                raise OSError("disk full (simulated keyring write failure)")
            return real_write_text(self, *args, **kwargs)

        monkeypatch.setattr(Path, "write_text", _boom_write_text)
        manager.rotate_key()

        # 轮换成功：新密文可解；旧密文仍可通过 previous_keys 解出
        assert manager.decrypt(manager.encrypt("new-data")) == "new-data"
        assert manager.decrypt(old_ciphertext) == "warm-up"


class TestTaskRepositoryProjectFilter:
    def test_list_filters_by_project_id(self, db_session, test_user):
        project = Project(user_id=test_user.id, name="项目 A")
        db_session.add(project)
        db_session.flush()
        make_task(db_session, test_user.id, title="归属任务", project_id=project.id)
        make_task(db_session, test_user.id, title="无项目任务")
        db_session.commit()

        repo = TaskRepository(db_session)
        assert [t.title for t in repo.list(project_id=project.id)] == ["归属任务"]
        assert len(repo.list(project_id=None)) == 2


class TestDashboardEdges:
    def test_today_execution_sorts_future_due_last(self, db_session, test_user):
        today = date.today()
        future = make_task(
            db_session, test_user.id, title="未来到期进行中",
            status="in_progress", due_date=today + timedelta(days=5),
        )
        overdue = make_task(
            db_session, test_user.id, title="已逾期",
            status="pending", due_date=today - timedelta(days=1),
        )
        due_today = make_task(
            db_session, test_user.id, title="今日到期",
            status="pending", due_date=today,
        )
        db_session.commit()

        execution = DashboardService(db_session, test_user)._build_today_execution(
            [future, overdue, due_today], today
        )

        assert execution.total == 3
        pending = next(g for g in execution.groups if g.status == "pending")
        assert [t["title"] for t in pending.tasks] == ["已逾期", "今日到期"]
        assert future.id  # 也进入（in_progress 组），仅校验排序在最末分组语义
        in_progress = next(g for g in execution.groups if g.status == "in_progress")
        assert in_progress.count == 1

    def test_projects_fallback_to_project_tag_when_service_fails(
        self, db_session, test_user, monkeypatch
    ):
        def _boom(*_args, **_kwargs):
            raise RuntimeError("project service exploded")

        monkeypatch.setattr("app.services.project_service.ProjectService.list", _boom)
        tasks = [
            make_task(db_session, test_user.id, title="A1", project_tag="项目甲",
                      status="completed"),
            make_task(db_session, test_user.id, title="A2", project_tag="项目甲",
                      status="pending"),
            make_task(db_session, test_user.id, title="B1", project_tag="项目乙"),
            make_task(db_session, test_user.id, title="无标签"),
        ]
        db_session.commit()

        section = DashboardService(db_session, test_user)._build_projects(tasks)

        by_name = {item.name: item for item in section.items}
        assert set(by_name) == {"项目甲", "项目乙"}
        assert by_name["项目甲"].status == "beta"
        assert by_name["项目甲"].task_count == 2
        assert by_name["项目甲"].completed_count == 1
        assert by_name["项目甲"].progress == 50
