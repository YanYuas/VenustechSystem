# ============================================================
# Project Service 生产级测试
#
# 标准：真数据夹具 + 写操作后查库验证（expire_all+独立查询）+ 增量隔离
#       + 负向断言（保护字段不变）+ 注释写清"防什么bug"
# ============================================================
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from app.core.exceptions import NotFoundException, ValidationException
from app.models.project import Project, ProjectMilestone
from app.models.task import Task
from app.schemas.project import (
    MilestoneCreate,
    MilestoneUpdate,
    ProjectCreate,
    ProjectUpdate,
)
from app.services.project_service import ProjectService
from tests.factories import count_rows


def _make_project(name="测试项目", **overrides):
    """构造 ProjectCreate，所有字段有默认值，可覆盖。"""
    defaults = dict(
        name=name, description="项目描述", color="#ff0000",
        status="active", due_date=date(2026, 12, 31),
    )
    defaults.update(overrides)
    return ProjectCreate(**defaults)


# ============================================================
# 第 1 组：基础 CRUD
# ============================================================

class TestGroup1BasicCRUD:
    """第1组：创建 + 列表（归档过滤）+ 获取 + 更新 + 删除。"""

    def test_create_project_persists_to_db(self, db_session, test_user):
        """创建项目后查库验证 name/color/status/due_date/user_id 正确写入。

        防什么：create 如果漏了某个字段（比如 due_date），项目创建后该字段
        为 None，前端展示异常。
        """
        svc = ProjectService(db_session)
        out = svc.create(test_user.id, _make_project(name="我的项目", color="#123456"))

        assert out["name"] == "我的项目"
        assert out["color"] == "#123456"
        assert out["status"] == "active"

        # 查库验证
        db_session.expire_all()
        in_db = db_session.get(Project, out["id"])
        assert in_db is not None
        assert in_db.name == "我的项目"
        assert in_db.color == "#123456"
        assert in_db.status == "active"
        assert in_db.due_date == date(2026, 12, 31)
        assert in_db.user_id == test_user.id
        assert in_db.sort_order == 0

    def test_list_excludes_archived_by_default(self, db_session, test_user):
        """列表默认排除归档项目，只有 active/completed 的出现。

        防什么：list_by_user 如果漏了 status != archived 过滤，归档项目会
        出现在主列表里，用户体验混乱。
        """
        svc = ProjectService(db_session)
        svc.create(test_user.id, _make_project(name="进行中"))
        svc.create(test_user.id, _make_project(name="已完成", status="completed"))
        archived = svc.create(test_user.id, _make_project(name="已归档"))
        svc.archive(test_user.id, archived["id"])

        result = svc.list(test_user.id)
        names = {p["name"] for p in result}
        assert "进行中" in names
        assert "已完成" in names
        assert "已归档" not in names
        assert len(result) == 2

    def test_list_includes_archived_when_flagged(self, db_session, test_user):
        """include_archived=True 时列表包含归档项目。

        防什么：list 的 include_archived 参数如果没正确传递给 repo，归档
        项目永远不显示。
        """
        svc = ProjectService(db_session)
        svc.create(test_user.id, _make_project(name="进行中"))
        archived = svc.create(test_user.id, _make_project(name="已归档"))
        svc.archive(test_user.id, archived["id"])

        result = svc.list(test_user.id, include_archived=True)
        names = {p["name"] for p in result}
        assert "进行中" in names
        assert "已归档" in names
        assert len(result) == 2

    def test_get_returns_task_stats(self, db_session, test_user):
        """获取单个项目时返回任务统计（task_count/completed_count/progress）。

        防什么：get 如果漏了 stats 查询，返回的 task_count 永远是 0，
        前端进度条不显示。
        """
        svc = ProjectService(db_session)
        project = svc.create(test_user.id, _make_project(name="有任务的项目"))

        # 造 3 个任务，1 个完成
        for i in range(3):
            t = Task(user_id=test_user.id, title=f"任务{i}", project_id=project["id"])
            if i == 0:
                t.status = "completed"
                t.completed_at = datetime.utcnow()
            db_session.add(t)
        db_session.commit()

        result = svc.get(test_user.id, project["id"])
        assert result["task_count"] == 3
        assert result["completed_count"] == 1
        assert result["progress"] == 33  # round(1/3*100) = 33

    def test_update_project_persists_changes(self, db_session, test_user):
        """更新项目后查库验证指定字段变了，未指定字段不变。

        防什么：update 如果用了 model_dump() 而不是 exclude_unset=True，
        未传的字段会被覆盖为 None。
        """
        svc = ProjectService(db_session)
        project = svc.create(test_user.id, _make_project(
            name="旧名字", description="旧描述", color="#000000",
        ))

        # 只更新 name 和 color
        svc.update(test_user.id, project["id"], ProjectUpdate(
            name="新名字", color="#ffffff",
        ))

        # 查库验证
        db_session.expire_all()
        in_db = db_session.get(Project, project["id"])
        assert in_db.name == "新名字"
        assert in_db.color == "#ffffff"
        assert in_db.description == "旧描述"  # 未指定字段不变
        assert in_db.status == "active"  # 未指定字段不变


# ============================================================
# 第 2 组：删除 + 归档恢复 + 越权 + 无效状态
# ============================================================

class TestGroup2DeleteArchiveAuth:
    """第2组：删除（解除关联）+ 归档恢复 + 越权 + 无效状态校验。"""

    def test_delete_project_removes_from_db(self, db_session, test_user):
        """删除项目后查库验证行消失（硬删除）。

        防什么：delete 如果漏了 db.commit()，项目不会真正被删除。
        """
        svc = ProjectService(db_session)
        project = svc.create(test_user.id, _make_project(name="待删除"))

        svc.delete(test_user.id, project["id"])

        db_session.expire_all()
        assert db_session.get(Project, project["id"]) is None
        assert count_rows(db_session, "projects", user_id=test_user.id) == 0

    def test_delete_project_unlinks_tasks(self, db_session, test_user):
        """删除项目后，关联任务的 project_id 变为 None（任务不被删除）。

        防什么：delete 如果漏了关联解除逻辑，任务的 project_id 会指向
        已删除的项目（外键 CASCADE 会删除任务，这是错误的）。
        """
        svc = ProjectService(db_session)
        project = svc.create(test_user.id, _make_project(name="有任务的项目"))

        # 造 2 个关联任务
        task_ids = []
        for i in range(2):
            t = Task(user_id=test_user.id, title=f"任务{i}", project_id=project["id"])
            db_session.add(t)
            db_session.flush()
            task_ids.append(t.id)
        db_session.commit()

        svc.delete(test_user.id, project["id"])

        # 查库：任务还在，project_id 为 None
        db_session.expire_all()
        for tid in task_ids:
            task = db_session.get(Task, tid)
            assert task is not None
            assert task.project_id is None

    def test_archive_then_restore(self, db_session, test_user):
        """归档后状态变为 archived，恢复后变回 active，查库验证。

        防什么：archive/restore 如果直接修改了其他字段（比如 sort_order），
        项目的排序会被意外改变。
        """
        svc = ProjectService(db_session)
        project = svc.create(test_user.id, _make_project(name="可归档项目"))
        original_sort = project["sort_order"]

        # 归档
        archived = svc.archive(test_user.id, project["id"])
        assert archived["status"] == "archived"

        # 恢复
        restored = svc.restore(test_user.id, project["id"])
        assert restored["status"] == "active"

        # 查库：sort_order 没变
        db_session.expire_all()
        in_db = db_session.get(Project, project["id"])
        assert in_db.status == "active"
        assert in_db.sort_order == original_sort

    def test_get_other_users_project_raises(self, db_session, test_user, other_user):
        """获取其他用户的项目抛 NotFoundException，不泄露数据。

        防什么：_owned 如果只检查存在性而不检查 user_id，用户可以通过
        遍历 id 看到别人的项目。
        """
        # 造其他用户的项目
        other_project = Project(user_id=other_user.id, name="他人项目", status="active")
        db_session.add(other_project)
        db_session.commit()

        svc = ProjectService(db_session)
        with pytest.raises(NotFoundException, match="项目不存在"):
            svc.get(test_user.id, other_project.id)

    def test_create_invalid_status_raises(self, db_session, test_user):
        """创建时指定无效状态抛 ValidationException，不产生项目。

        防什么：如果 status 校验漏了，非法 status 会被写入数据库，
        列表过滤逻辑异常。
        """
        svc = ProjectService(db_session)
        with pytest.raises(ValidationException, match="无效的项目状态"):
            svc.create(test_user.id, _make_project(name="非法状态", status="invalid"))

        assert count_rows(db_session, "projects", user_id=test_user.id) == 0


# ============================================================
# 第 3 组：里程碑 CRUD
# ============================================================

class TestGroup3Milestones:
    """第3组：里程碑创建 + 列表排序 + 完成/取消完成 + 删除。"""

    def test_create_milestone_persists_to_db(self, db_session, test_user):
        """创建里程碑后查库验证 name/target_date/sort_order/project_id 正确写入。

        防什么：create_milestone 如果漏了 project_id，里程碑会变成孤立数据。
        """
        svc = ProjectService(db_session)
        project = svc.create(test_user.id, _make_project(name="有里程碑的项目"))

        out = svc.create_milestone(test_user.id, project["id"], MilestoneCreate(
            name="需求评审", target_date=date(2026, 11, 1), sort_order=1,
        ))

        assert out["name"] == "需求评审"
        assert out["completed"] is False

        # 查库验证
        db_session.expire_all()
        in_db = db_session.get(ProjectMilestone, out["id"])
        assert in_db is not None
        assert in_db.name == "需求评审"
        assert in_db.target_date == date(2026, 11, 1)
        assert in_db.sort_order == 1
        assert in_db.project_id == project["id"]
        assert in_db.completed is False
        assert in_db.completed_at is None

    def test_list_milestones_returns_sorted(self, db_session, test_user):
        """里程碑列表按 sort_order 升序返回。

        防什么：list_by_project 如果漏了 order_by，里程碑顺序随机，
        前端展示混乱。
        """
        svc = ProjectService(db_session)
        project = svc.create(test_user.id, _make_project(name="排序项目"))

        # 按倒序创建
        svc.create_milestone(test_user.id, project["id"], MilestoneCreate(name="第三", sort_order=3))
        svc.create_milestone(test_user.id, project["id"], MilestoneCreate(name="第一", sort_order=1))
        svc.create_milestone(test_user.id, project["id"], MilestoneCreate(name="第二", sort_order=2))

        result = svc.list_milestones(test_user.id, project["id"])
        names = [m["name"] for m in result]
        assert names == ["第一", "第二", "第三"]

    def test_update_milestone_completed_sets_completed_at(self, db_session, test_user):
        """勾选里程碑完成时，completed_at 被自动设置为当前时间。

        防什么：update_milestone 如果漏了 completed_at 补全逻辑，里程碑
        显示"已完成"但没有完成时间，时间线无法展示。
        """
        svc = ProjectService(db_session)
        project = svc.create(test_user.id, _make_project(name="完成项目"))
        milestone = svc.create_milestone(test_user.id, project["id"], MilestoneCreate(name="节点"))

        assert milestone["completed_at"] is None

        # 勾选完成
        updated = svc.update_milestone(test_user.id, milestone["id"], MilestoneUpdate(completed=True))
        assert updated["completed"] is True
        assert updated["completed_at"] is not None

        # 查库验证
        db_session.expire_all()
        in_db = db_session.get(ProjectMilestone, milestone["id"])
        assert in_db.completed is True
        assert in_db.completed_at is not None

    def test_update_milestone_uncompleted_clears_completed_at(self, db_session, test_user):
        """取消里程碑完成时，completed_at 被清除为 None。

        防什么：update_milestone 如果漏了 completed_at 清除逻辑，取消完成后
        completed_at 还在，数据不一致。
        """
        svc = ProjectService(db_session)
        project = svc.create(test_user.id, _make_project(name="取消完成项目"))
        milestone = svc.create_milestone(test_user.id, project["id"], MilestoneCreate(name="节点"))
        svc.update_milestone(test_user.id, milestone["id"], MilestoneUpdate(completed=True))

        # 取消完成
        updated = svc.update_milestone(test_user.id, milestone["id"], MilestoneUpdate(completed=False))
        assert updated["completed"] is False
        assert updated["completed_at"] is None

        # 查库验证
        db_session.expire_all()
        in_db = db_session.get(ProjectMilestone, milestone["id"])
        assert in_db.completed is False
        assert in_db.completed_at is None

    def test_delete_milestone_removes_from_db(self, db_session, test_user):
        """删除里程碑后查库验证行消失，项目不受影响。

        防什么：delete_milestone 如果误删了项目（级联删除方向错误），
        项目会丢失。
        """
        svc = ProjectService(db_session)
        project = svc.create(test_user.id, _make_project(name="有里程碑项目"))
        milestone = svc.create_milestone(test_user.id, project["id"], MilestoneCreate(name="待删除"))

        svc.delete_milestone(test_user.id, milestone["id"])

        # 查库：里程碑消失，项目还在
        db_session.expire_all()
        assert db_session.get(ProjectMilestone, milestone["id"]) is None
        assert db_session.get(Project, project["id"]) is not None
        assert count_rows(db_session, "project_milestones", project_id=project["id"]) == 0


# ============================================================
# 第 4 组：统计 + 详情聚合
# ============================================================

class TestGroup4StatsDetail:
    """第4组：统计（进度/分布/逾期/健康度/周趋势）+ 详情聚合 + 越权。"""

    def test_stats_returns_progress_and_distribution(self, db_session, test_user):
        """统计返回正确的进度百分比和状态分布。

        防什么：stats 如果用了错误的 COUNT 逻辑（比如把归档任务也算进去），
        进度百分比会不准。
        """
        svc = ProjectService(db_session)
        project = svc.create(test_user.id, _make_project(name="统计项目"))

        # 4 个任务：2 completed, 1 in_progress, 1 pending
        statuses = ["completed", "completed", "in_progress", "pending"]
        for i, s in enumerate(statuses):
            t = Task(user_id=test_user.id, title=f"任务{i}", status=s, project_id=project["id"])
            if s == "completed":
                t.completed_at = datetime.utcnow()
            db_session.add(t)
        db_session.commit()

        stats = svc.stats(test_user.id, project["id"])
        assert stats.task_count == 4
        assert stats.completed_count == 2
        assert stats.progress == 50
        assert stats.status_distribution["completed"] == 2
        assert stats.status_distribution["in_progress"] == 1
        assert stats.status_distribution["pending"] == 1

    def test_stats_overdue_makes_health_risk(self, db_session, test_user):
        """有逾期未完成任务时，健康度为 risk。

        防什么：health 计算如果漏了 overdue 判断，逾期项目会显示 good，
        误导用户。
        """
        svc = ProjectService(db_session)
        project = svc.create(test_user.id, _make_project(name="逾期项目"))

        # 造一个逾期任务（due_date 在昨天，状态未完成）
        overdue = Task(
            user_id=test_user.id, title="逾期任务", status="pending",
            project_id=project["id"], due_date=date.today() - timedelta(days=1),
        )
        db_session.add(overdue)
        db_session.commit()

        stats = svc.stats(test_user.id, project["id"])
        assert stats.overdue_count == 1
        assert stats.health == "risk"

    def test_stats_weekly_trend_counts_completions(self, db_session, test_user):
        """近7天趋势正确统计每天的完成数（completed_at 按本地日边界换算）。

        防什么：completions_by_day 如果用了 UTC 日期而不是本地日边界，
        UTC+8 时区下午夜前后的完成会算到错误的日期。
        """
        svc = ProjectService(db_session)
        project = svc.create(test_user.id, _make_project(name="趋势项目"))

        # 造一个今天完成的任务
        today_task = Task(
            user_id=test_user.id, title="今天完成", status="completed",
            project_id=project["id"], completed_at=datetime.utcnow(),
        )
        db_session.add(today_task)
        db_session.commit()

        stats = svc.stats(test_user.id, project["id"])
        assert len(stats.weekly_trend) == 7
        # 最后一天是今天，完成数 >= 1
        assert stats.weekly_trend[-1]["completed"] >= 1
        assert stats.weekly_trend[-1]["date"] == date.today().isoformat()

    def test_detail_includes_tasks_and_milestones(self, db_session, test_user):
        """详情聚合返回任务列表和里程碑列表，字段完整。

        防什么：detail 如果漏了某个关联表的查询，前端详情页会缺少对应
        板块（比如没有里程碑列表）。
        """
        svc = ProjectService(db_session)
        project = svc.create(test_user.id, _make_project(name="详情项目"))

        # 造任务和里程碑
        db_session.add(Task(user_id=test_user.id, title="详情任务", project_id=project["id"]))
        svc.create_milestone(test_user.id, project["id"], MilestoneCreate(name="详情里程碑"))
        db_session.commit()

        detail = svc.detail(test_user.id, project["id"])
        assert "tasks" in detail
        assert len(detail["tasks"]) == 1
        assert detail["tasks"][0]["title"] == "详情任务"
        assert "milestones" in detail
        assert len(detail["milestones"]) == 1
        assert detail["milestones"][0]["name"] == "详情里程碑"
        # 基础信息也在
        assert detail["name"] == "详情项目"
        assert detail["task_count"] == 1

    def test_detail_other_users_project_raises(self, db_session, test_user, other_user):
        """详情聚合对其他用户的项目抛 NotFoundException，不泄露关联数据。

        防什么：detail 如果先查关联表再校验归属，会在报错前泄露任务/文档
        数量等信息。
        """
        other_project = Project(user_id=other_user.id, name="他人项目", status="active")
        db_session.add(other_project)
        db_session.commit()

        svc = ProjectService(db_session)
        with pytest.raises(NotFoundException, match="项目不存在"):
            svc.detail(test_user.id, other_project.id)


# ============================================================
# 第 5 组：时间线 + 导出 + 里程碑越权 + update 无效状态 + identity_id 越权
# ============================================================

class TestGroup5TimelineExportAuth:
    """第5组：时间线事件 + 导出内容 + 里程碑越权 + update 状态校验 + identity 归属。"""

    def test_timeline_includes_task_completed_events(self, db_session, test_user):
        """时间线包含已完成任务的事件，按时间倒序排列。

        防什么：timeline 如果漏了 task_completed 事件类型，已完成任务不会
        出现在时间线上。
        """
        svc = ProjectService(db_session)
        project = svc.create(test_user.id, _make_project(name="时间线项目"))

        # 造一个已完成任务
        completed = Task(
            user_id=test_user.id, title="已完成任务", status="completed",
            project_id=project["id"], completed_at=datetime.utcnow(),
        )
        db_session.add(completed)
        db_session.commit()

        timeline = svc.timeline(test_user.id, project["id"])
        assert len(timeline) >= 1
        task_events = [e for e in timeline if e["type"] == "task_completed"]
        assert len(task_events) == 1
        assert "已完成任务" in task_events[0]["title"]

    def test_export_includes_tasks_and_project_info(self, db_session, test_user):
        """导出包含项目基础信息和关联任务，字段完整。

        防什么：export 如果漏了某个关联表，导出的 JSON 会缺少对应数据，
        用户备份不完整。
        """
        svc = ProjectService(db_session)
        project = svc.create(test_user.id, _make_project(name="导出项目", description="导出描述"))

        # 造任务
        db_session.add(Task(user_id=test_user.id, title="导出任务", project_id=project["id"]))
        db_session.commit()

        result = svc.export(test_user.id, project["id"])
        assert result["project"]["name"] == "导出项目"
        assert result["project"]["description"] == "导出描述"
        assert len(result["tasks"]) == 1
        assert result["tasks"][0]["title"] == "导出任务"
        assert "exported_at" in result

    def test_update_milestone_other_users_project_raises(self, db_session, test_user, other_user):
        """更新其他用户项目的里程碑抛 NotFoundException，不修改数据。

        防什么：_owned_milestone 如果只检查里程碑存在性而不通过 project 校验
        归属，用户可以篡改别人项目的里程碑。
        """
        from app.models.identity import Identity  # noqa: F401  确保模型注册

        # 造其他用户的项目和里程碑
        other_project = Project(user_id=other_user.id, name="他人项目", status="active")
        db_session.add(other_project)
        db_session.flush()
        other_milestone = ProjectMilestone(project_id=other_project.id, name="他人里程碑")
        db_session.add(other_milestone)
        db_session.commit()

        svc = ProjectService(db_session)
        with pytest.raises(NotFoundException, match="里程碑不存在"):
            svc.update_milestone(test_user.id, other_milestone.id, MilestoneUpdate(name="篡改"))

        # 查库：名字没变
        db_session.expire_all()
        in_db = db_session.get(ProjectMilestone, other_milestone.id)
        assert in_db.name == "他人里程碑"

    def test_update_invalid_status_raises(self, db_session, test_user):
        """更新时指定无效状态抛 ValidationException，原状态不变。

        防什么：update 的 status 校验如果漏了，非法 status 会被写入数据库。
        """
        svc = ProjectService(db_session)
        project = svc.create(test_user.id, _make_project(name="状态项目"))

        with pytest.raises(ValidationException, match="无效的项目状态"):
            svc.update(test_user.id, project["id"], ProjectUpdate(status="invalid"))

        # 查库：状态没变
        db_session.expire_all()
        in_db = db_session.get(Project, project["id"])
        assert in_db.status == "active"

    def test_create_with_other_users_identity_raises(self, db_session, test_user, other_user):
        """创建时指定其他用户的 identity_id 抛 ValidationException，不产生项目。

        防什么：identity_id 没有外键约束，如果 _ensure_identity_owned 漏了
        归属校验，用户可以把项目关联到别人的身份下。
        """
        from app.models.identity import Identity

        other_identity = Identity(
            user_id=other_user.id, name="他人身份", slug="other-identity",
        )
        db_session.add(other_identity)
        db_session.commit()

        svc = ProjectService(db_session)
        with pytest.raises(ValidationException, match="身份不存在"):
            svc.create(test_user.id, _make_project(name="越权身份项目", identity_id=other_identity.id))

        assert count_rows(db_session, "projects", user_id=test_user.id) == 0


# ============================================================
# 第 6 组：排序 + delete级联 + 健康度warning + detail文档/复盘 + update sort_order
# ============================================================

class TestGroup6SortCascadeHealthDetail:
    """第6组：列表排序 + 删除解除文档/复盘关联 + 健康度warning + 详情文档/复盘 + sort_order。"""

    def test_list_sorted_by_sort_order(self, db_session, test_user):
        """列表按 sort_order 升序返回。

        防什么：list_by_user 如果漏了 order_by，项目顺序随机，前端拖拽
        排序后刷新会乱。
        注意：ProjectCreate 没有 sort_order 字段，创建后需用 update 设置。
        """
        svc = ProjectService(db_session)
        p3 = svc.create(test_user.id, _make_project(name="第三"))
        p1 = svc.create(test_user.id, _make_project(name="第一"))
        p2 = svc.create(test_user.id, _make_project(name="第二"))

        svc.update(test_user.id, p1["id"], ProjectUpdate(sort_order=1))
        svc.update(test_user.id, p2["id"], ProjectUpdate(sort_order=2))
        svc.update(test_user.id, p3["id"], ProjectUpdate(sort_order=3))

        result = svc.list(test_user.id)
        names = [p["name"] for p in result]
        assert names == ["第一", "第二", "第三"]

    def test_delete_unlinks_documents_and_reviews(self, db_session, test_user):
        """删除项目后，关联文档和复盘的 project_id 变为 None（不删除内容）。

        防什么：delete 如果只解除了任务关联而漏了文档/复盘，这些记录的
        project_id 会指向已删除的项目，列表里显示"查无此项目"。
        """
        from app.models.document import Document
        from app.models.review import Review

        svc = ProjectService(db_session)
        project = svc.create(test_user.id, _make_project(name="有文档复盘项目"))

        doc = Document(user_id=test_user.id, title="关联文档", project_id=project["id"])
        review = Review(
            user_id=test_user.id, type="daily", review_date=date(2026, 10, 10),
            project_id=project["id"], data={"mood": 3},
        )
        db_session.add_all([doc, review])
        db_session.commit()
        doc_id, review_id = doc.id, review.id

        svc.delete(test_user.id, project["id"])

        db_session.expire_all()
        assert db_session.get(Document, doc_id).project_id is None
        assert db_session.get(Review, review_id).project_id is None

    def test_stats_health_warning_when_behind_schedule(self, db_session, test_user):
        """项目有截止日期且进度落后于时间时，健康度为 warning。

        防什么：health 计算如果漏了"进度落后于时间"的判断，只有逾期才
        显示 risk，进度缓慢的项目会被误判为 good。
        """
        from sqlalchemy import update as sa_update

        svc = ProjectService(db_session)
        project = svc.create(test_user.id, _make_project(
            name="进度落后项目", due_date=date.today() + timedelta(days=1),
        ))
        # 把 created_at 改到 30 天前（总时长 31 天，已过 30 天，预期进度 ~97%）
        db_session.execute(
            sa_update(Project).where(Project.id == project["id"])
            .values(created_at=datetime.utcnow() - timedelta(days=30))
        )
        db_session.commit()

        # 10 个任务只完成 1 个（进度 10%，远低于预期）
        for i in range(10):
            t = Task(user_id=test_user.id, title=f"任务{i}", status="pending",
                     project_id=project["id"])
            if i == 0:
                t.status = "completed"
                t.completed_at = datetime.utcnow()
            db_session.add(t)
        db_session.commit()

        stats = svc.stats(test_user.id, project["id"])
        assert stats.health == "warning"
        assert stats.overdue_count == 0  # 没有逾期，所以不是 risk

    def test_detail_includes_documents_and_reviews(self, db_session, test_user):
        """详情聚合返回文档列表和复盘列表，文档不拉 content 大字段。

        防什么：detail 如果漏了文档/复盘的关联查询，前端详情页会缺少
        对应板块。
        """
        from app.models.document import Document
        from app.models.review import Review

        svc = ProjectService(db_session)
        project = svc.create(test_user.id, _make_project(name="详情全项目"))

        db_session.add(Document(user_id=test_user.id, title="项目文档",
                                project_id=project["id"], content="大字段内容", word_count=100))
        db_session.add(Review(user_id=test_user.id, type="daily",
                               review_date=date(2026, 10, 10), project_id=project["id"],
                               data={"mood": 4, "gains": "今天收获很大"}))
        db_session.commit()

        detail = svc.detail(test_user.id, project["id"])
        assert len(detail["documents"]) == 1
        assert detail["documents"][0]["title"] == "项目文档"
        assert "content" not in detail["documents"][0]  # 不拉 content 大字段
        assert detail["documents"][0]["word_count"] == 100

        assert len(detail["reviews"]) == 1
        assert detail["reviews"][0]["type"] == "daily"
        assert detail["reviews"][0]["mood"] == 4

    def test_update_sort_order_persists(self, db_session, test_user):
        """更新 sort_order 后列表顺序变化。

        防什么：update 如果漏了 sort_order 字段处理，前端拖拽排序后
        刷新会恢复原状。
        """
        svc = ProjectService(db_session)
        p1 = svc.create(test_user.id, _make_project(name="A", sort_order=1))
        svc.create(test_user.id, _make_project(name="B", sort_order=2))

        svc.update(test_user.id, p1["id"], ProjectUpdate(sort_order=3))

        result = svc.list(test_user.id)
        names = [p["name"] for p in result]
        assert names == ["B", "A"]


# ============================================================
# 第 7 组：timeline多事件 + export文档 + update identity越权 + 里程碑delete越权 + 空名称
# ============================================================

class TestGroup7TimelineExportAuthValidation:
    """第7组：时间线文档/里程碑事件 + 导出文档 + update identity越权 + 里程碑删除越权 + 空名称。"""

    def test_timeline_includes_document_and_milestone_events(self, db_session, test_user):
        """时间线包含文档创建和里程碑事件，按时间倒序排列。

        防什么：timeline 如果漏了 document_created 或 milestone 事件类型，
        时间线不完整，用户看不到项目的完整活动历史。
        """
        from app.models.document import Document

        svc = ProjectService(db_session)
        project = svc.create(test_user.id, _make_project(name="时间线全项目"))

        # 造文档和里程碑
        db_session.add(Document(user_id=test_user.id, title="项目文档", project_id=project["id"]))
        svc.create_milestone(test_user.id, project["id"], MilestoneCreate(name="关键节点"))
        db_session.commit()

        timeline = svc.timeline(test_user.id, project["id"])
        types = {e["type"] for e in timeline}
        assert "document_created" in types
        assert "milestone" in types
        # 按时间倒序
        times = [e["time"] for e in timeline]
        assert times == sorted(times, reverse=True)

    def test_export_includes_documents_with_content(self, db_session, test_user):
        """导出包含文档的完整 content（与 detail 不同，导出需要完整内容）。

        防什么：export 如果漏了文档 content，导出的备份不完整，用户无法
        恢复文档内容。
        """
        from app.models.document import Document

        svc = ProjectService(db_session)
        project = svc.create(test_user.id, _make_project(name="导出项目"))

        db_session.add(Document(user_id=test_user.id, title="导出文档",
                                project_id=project["id"], content="完整文档内容", tags=["tag1"]))
        db_session.commit()

        result = svc.export(test_user.id, project["id"])
        assert len(result["documents"]) == 1
        assert result["documents"][0]["title"] == "导出文档"
        assert result["documents"][0]["content"] == "完整文档内容"  # 导出拉 content
        assert result["documents"][0]["tags"] == ["tag1"]
        assert "exported_at" in result

    def test_update_identity_id_other_user_raises(self, db_session, test_user, other_user):
        """更新时指定其他用户的 identity_id 抛 ValidationException，原 identity_id 不变。

        防什么：update 的 identity_id 校验如果漏了，用户可以把项目改关联
        到别人的身份下。
        """
        from app.models.identity import Identity

        other_identity = Identity(
            user_id=other_user.id, name="他人身份", slug="other-update-id",
        )
        db_session.add(other_identity)
        db_session.commit()

        svc = ProjectService(db_session)
        project = svc.create(test_user.id, _make_project(name="身份项目"))

        with pytest.raises(ValidationException, match="身份不存在"):
            svc.update(test_user.id, project["id"], ProjectUpdate(identity_id=other_identity.id))

        # 查库：identity_id 没变（仍是 None）
        db_session.expire_all()
        in_db = db_session.get(Project, project["id"])
        assert in_db.identity_id is None

    def test_delete_milestone_other_users_project_raises(self, db_session, test_user, other_user):
        """删除其他用户项目的里程碑抛 NotFoundException，里程碑仍在。

        防什么：_owned_milestone 如果只检查里程碑存在性而不通过 project 校验
        归属，用户可以删除别人项目的里程碑。
        """
        other_project = Project(user_id=other_user.id, name="他人项目", status="active")
        db_session.add(other_project)
        db_session.flush()
        other_milestone = ProjectMilestone(project_id=other_project.id, name="他人里程碑")
        db_session.add(other_milestone)
        db_session.commit()

        svc = ProjectService(db_session)
        with pytest.raises(NotFoundException, match="里程碑不存在"):
            svc.delete_milestone(test_user.id, other_milestone.id)

        # 查库：里程碑仍在
        db_session.expire_all()
        assert db_session.get(ProjectMilestone, other_milestone.id) is not None

    def test_create_empty_name_rejected_by_schema(self, db_session, test_user):
        """创建时空名称被 Pydantic 校验拒绝（min_length=1），不产生项目。

        防什么：如果 schema 的 min_length 校验漏了，空名称会进入 service 层
        并被写入数据库。
        """
        from pydantic import ValidationError

        svc = ProjectService(db_session)
        with pytest.raises(ValidationError):
            svc.create(test_user.id, _make_project(name=""))

        assert count_rows(db_session, "projects", user_id=test_user.id) == 0
