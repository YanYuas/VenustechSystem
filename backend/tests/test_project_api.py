# ============================================================
# Project API 生产级集成测试
#
# 标准：真数据夹具 + API操作后查库验证 + HTTP状态码 + 增量隔离
# ============================================================
from __future__ import annotations


from app.database import SessionLocal
from app.models.project import Project
from tests.factories import count_rows


def _db():
    return SessionLocal()


def _project_payload(name="API项目", **overrides):
    """构造创建项目的 payload，所有字段有默认值，可覆盖。"""
    defaults = dict(
        name=name, description="API描述", color="#ff0000",
        status="active", due_date="2026-12-31",
    )
    defaults.update(overrides)
    return defaults


# ============================================================
# 第 1 组：Project CRUD 的 API→查库交叉验证
# ============================================================

class TestProjectApiGroup1CRUD:
    """第1组：列表 + 创建 + 详情 + 更新 + 删除。"""

    def test_list_projects_via_api(self, client, default_user_id):
        """列表接口返回当前用户的项目，数量和查库一致。

        防什么：list 如果漏了 user_id 过滤，会返回所有用户的项目。
        """
        # 造 2 个项目
        db = _db()
        try:
            db.add(Project(user_id=default_user_id, name="项目A", status="active"))
            db.add(Project(user_id=default_user_id, name="项目B", status="active"))
            db.commit()
        finally:
            db.close()

        r = client.get("/api/v1/projects")
        assert r.status_code == 200
        assert r.json()["code"] == 0
        data = r.json()["data"]
        assert len(data) == 2
        names = {p["name"] for p in data}
        assert "项目A" in names
        assert "项目B" in names

    def test_create_project_via_api_persists_to_db(self, client, default_user_id):
        """通过 API 创建项目后，查库验证 name/color/status/user_id 正确写入。

        防什么：API 层如果没正确传递字段，项目创建后字段为默认值。
        """
        r = client.post("/api/v1/projects", json=_project_payload(name="新建项目", color="#abcdef"))
        assert r.status_code == 200
        project_id = r.json()["data"]["id"]

        # 查库验证
        db = _db()
        try:
            in_db = db.get(Project, project_id)
            assert in_db is not None
            assert in_db.name == "新建项目"
            assert in_db.color == "#abcdef"
            assert in_db.status == "active"
            assert in_db.user_id == default_user_id
        finally:
            db.close()

    def test_get_project_detail_via_api(self, client, default_user_id):
        """详情接口返回项目基础信息 + 关联数据（tasks/milestones 等）。

        防什么：detail 如果漏了关联查询，返回的只有基础信息，前端详情页
        缺少任务/里程碑板块。
        """
        db = _db()
        try:
            p = Project(user_id=default_user_id, name="详情项目", status="active")
            db.add(p)
            db.commit()
            project_id = p.id
        finally:
            db.close()

        r = client.get(f"/api/v1/projects/{project_id}")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["name"] == "详情项目"
        assert "tasks" in data
        assert "milestones" in data
        assert "documents" in data

    def test_update_project_via_api_persists(self, client, default_user_id):
        """通过 API 更新项目后，查库验证指定字段变了，未指定字段不变。

        防什么：update 如果用了全量覆盖而不是增量更新，未传字段会被重置。
        """
        db = _db()
        try:
            p = Project(user_id=default_user_id, name="旧名字", description="旧描述",
                        color="#000000", status="active")
            db.add(p)
            db.commit()
            project_id = p.id
        finally:
            db.close()

        r = client.patch(f"/api/v1/projects/{project_id}", json={"name": "新名字"})
        assert r.status_code == 200
        assert r.json()["data"]["name"] == "新名字"

        # 查库验证
        db = _db()
        try:
            in_db = db.get(Project, project_id)
            assert in_db.name == "新名字"
            assert in_db.description == "旧描述"  # 未指定字段不变
            assert in_db.color == "#000000"  # 未指定字段不变
        finally:
            db.close()

    def test_delete_project_via_api_removes_from_db(self, client, default_user_id):
        """通过 API 删除项目后，查库验证行消失。

        防什么：delete 如果漏了 commit，项目不会真正被删除。
        """
        db = _db()
        try:
            p = Project(user_id=default_user_id, name="待删除", status="active")
            db.add(p)
            db.commit()
            project_id = p.id
        finally:
            db.close()

        r = client.delete(f"/api/v1/projects/{project_id}")
        assert r.status_code == 200
        assert r.json()["code"] == 0

        # 查库验证
        db = _db()
        try:
            assert db.get(Project, project_id) is None
            assert count_rows(db, "projects", user_id=default_user_id) == 0
        finally:
            db.close()


# ============================================================
# 第 2 组：归档恢复 + 统计 + 越权 + 无效状态
# ============================================================

class TestProjectApiGroup2ArchiveStatsAuth:
    """第2组：归档/恢复 + 统计 + 越权获取/删除 + 无效状态校验。"""

    def test_archive_and_restore_via_api(self, client, default_user_id):
        """通过 API 归档后状态变为 archived，恢复后变回 active，查库验证。

        防什么：archive/restore 接口如果调用了错误的 service 方法，状态
        不会改变。
        """
        db = _db()
        try:
            p = Project(user_id=default_user_id, name="可归档", status="active")
            db.add(p)
            db.commit()
            project_id = p.id
        finally:
            db.close()

        # 归档
        r = client.post(f"/api/v1/projects/{project_id}/archive")
        assert r.status_code == 200
        assert r.json()["data"]["status"] == "archived"

        # 恢复
        r = client.post(f"/api/v1/projects/{project_id}/restore")
        assert r.status_code == 200
        assert r.json()["data"]["status"] == "active"

        # 查库验证
        db = _db()
        try:
            in_db = db.get(Project, project_id)
            assert in_db.status == "active"
        finally:
            db.close()

    def test_project_stats_via_api(self, client, default_user_id):
        """统计接口返回进度、状态分布、健康度等字段。

        防什么：stats 接口如果返回了错误的字段结构，前端统计面板无法渲染。
        """
        from app.models.task import Task
        from datetime import datetime

        db = _db()
        try:
            p = Project(user_id=default_user_id, name="统计项目", status="active")
            db.add(p)
            db.flush()
            # 造 2 个任务，1 个完成
            db.add(Task(user_id=default_user_id, title="完成", status="completed",
                        project_id=p.id, completed_at=datetime.utcnow()))
            db.add(Task(user_id=default_user_id, title="未完成", status="pending",
                        project_id=p.id))
            db.commit()
            project_id = p.id
        finally:
            db.close()

        r = client.get(f"/api/v1/projects/{project_id}/stats")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["task_count"] == 2
        assert data["completed_count"] == 1
        assert data["progress"] == 50
        assert "status_distribution" in data
        assert "health" in data
        assert "weekly_trend" in data

    def test_get_other_users_project_returns_404(self, client, default_user_id):
        """获取其他用户的项目返回 404，不泄露数据。

        防什么：get 如果只检查存在性而不检查 user_id，用户可以通过遍历 id
        看到别人的项目详情。
        """
        from app.models.user import User

        db = _db()
        try:
            other = User(username="other_proj_api", nickname="其他")
            db.add(other)
            db.flush()
            other_project = Project(user_id=other.id, name="他人项目", status="active")
            db.add(other_project)
            db.commit()
            other_project_id = other_project.id
        finally:
            db.close()

        r = client.get(f"/api/v1/projects/{other_project_id}")
        assert r.status_code == 404
        assert r.json()["code"] == 1002

    def test_create_invalid_status_returns_400(self, client, default_user_id):
        """创建时指定无效状态返回 400，不产生项目。

        防什么：API 层如果没正确传递 service 层的 ValidationException，
        非法状态会触发 500 而不是 400。
        """
        payload = _project_payload(name="非法状态", status="invalid")
        r = client.post("/api/v1/projects", json=payload)
        assert r.status_code == 400

        # 查库：没有产生项目
        db = _db()
        try:
            assert count_rows(db, "projects", user_id=default_user_id) == 0
        finally:
            db.close()

    def test_delete_other_users_project_returns_404(self, client, default_user_id):
        """删除其他用户的项目返回 404，库中项目仍在。

        防什么：delete 如果只检查存在性而不检查 user_id，用户可以删除
        别人的项目。
        """
        from app.models.user import User

        db = _db()
        try:
            other = User(username="other_proj_del", nickname="其他")
            db.add(other)
            db.flush()
            other_project = Project(user_id=other.id, name="他人项目", status="active")
            db.add(other_project)
            db.commit()
            other_project_id = other_project.id
        finally:
            db.close()

        r = client.delete(f"/api/v1/projects/{other_project_id}")
        assert r.status_code == 404
        assert r.json()["code"] == 1002

        # 查库：项目仍在
        db = _db()
        try:
            assert db.get(Project, other_project_id) is not None
        finally:
            db.close()


# ============================================================
# 第 3 组：里程碑CRUD + timeline + export + include_archived + 空名称
# ============================================================

class TestProjectApiGroup3MilestoneTimelineExport:
    """第3组：里程碑CRUD API + 时间线 + 导出 + include_archived + 空名称400。"""

    def test_milestone_crud_via_api(self, client, default_user_id):
        """里程碑的创建/列表/更新/删除通过 API 完整走通，查库验证。

        防什么：里程碑 API 如果调用了错误的 service 方法，里程碑操作不会
        持久化。
        """
        # 先创建项目
        r = client.post("/api/v1/projects", json=_project_payload(name="里程碑项目"))
        project_id = r.json()["data"]["id"]

        # 创建里程碑
        r = client.post(f"/api/v1/projects/{project_id}/milestones", json={
            "name": "需求评审", "target_date": "2026-11-01", "sort_order": 1,
        })
        assert r.status_code == 200
        milestone_id = r.json()["data"]["id"]

        # 列表
        r = client.get(f"/api/v1/projects/{project_id}/milestones")
        assert r.status_code == 200
        assert len(r.json()["data"]) == 1
        assert r.json()["data"][0]["name"] == "需求评审"

        # 更新（勾选完成）
        r = client.patch(f"/api/v1/projects/milestones/{milestone_id}", json={"completed": True})
        assert r.status_code == 200
        assert r.json()["data"]["completed"] is True
        assert r.json()["data"]["completed_at"] is not None

        # 查库验证
        db = _db()
        try:
            from app.models.project import ProjectMilestone
            in_db = db.get(ProjectMilestone, milestone_id)
            assert in_db.completed is True
            assert in_db.completed_at is not None
        finally:
            db.close()

        # 删除
        r = client.delete(f"/api/v1/projects/milestones/{milestone_id}")
        assert r.status_code == 200

        # 查库：里程碑消失
        db = _db()
        try:
            from app.models.project import ProjectMilestone
            assert db.get(ProjectMilestone, milestone_id) is None
        finally:
            db.close()

    def test_timeline_via_api(self, client, default_user_id):
        """时间线接口返回事件列表，包含任务完成事件。

        防什么：timeline 接口如果返回了错误的字段结构，前端时间线无法渲染。
        """
        from app.models.task import Task
        from datetime import datetime

        db = _db()
        try:
            p = Project(user_id=default_user_id, name="时间线项目", status="active")
            db.add(p)
            db.flush()
            db.add(Task(user_id=default_user_id, title="完成任务", status="completed",
                        project_id=p.id, completed_at=datetime.utcnow()))
            db.commit()
            project_id = p.id
        finally:
            db.close()

        r = client.get(f"/api/v1/projects/{project_id}/timeline")
        assert r.status_code == 200
        data = r.json()["data"]
        assert isinstance(data, list)
        assert len(data) >= 1
        assert "type" in data[0]
        assert "title" in data[0]
        assert "time" in data[0]

    def test_export_via_api(self, client, default_user_id):
        """导出接口返回项目完整数据（含任务/文档），字段完整。

        防什么：export 接口如果漏了某个关联表，导出的备份不完整。
        """
        from app.models.task import Task

        db = _db()
        try:
            p = Project(user_id=default_user_id, name="导出项目", status="active",
                        description="导出描述")
            db.add(p)
            db.flush()
            db.add(Task(user_id=default_user_id, title="导出任务", project_id=p.id))
            db.commit()
            project_id = p.id
        finally:
            db.close()

        r = client.get(f"/api/v1/projects/{project_id}/export")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["project"]["name"] == "导出项目"
        assert data["project"]["description"] == "导出描述"
        assert len(data["tasks"]) == 1
        assert data["tasks"][0]["title"] == "导出任务"
        assert "exported_at" in data

    def test_list_include_archived_param(self, client, default_user_id):
        """列表接口默认排除归档项目（include_archived=False），显式传 true 时包含。

        防什么：list 的 include_archived 默认值如果被改错，归档项目会
        默认显示或永远不显示。
        """
        # 创建项目并归档
        r = client.post("/api/v1/projects", json=_project_payload(name="归档项目"))
        project_id = r.json()["data"]["id"]
        client.post(f"/api/v1/projects/{project_id}/archive")

        # 默认排除归档
        r = client.get("/api/v1/projects")
        assert len(r.json()["data"]) == 0

        # include_archived=true 包含归档
        r = client.get("/api/v1/projects?include_archived=true")
        assert len(r.json()["data"]) == 1
        assert r.json()["data"][0]["name"] == "归档项目"

    def test_create_empty_name_returns_400(self, client, default_user_id):
        """创建时空名称返回 400，不产生项目。

        防什么：ProjectBase.name 的 min_length=1 校验确保空名称被拒绝。
        """
        r = client.post("/api/v1/projects", json=_project_payload(name=""))
        assert r.status_code == 400

        # 查库：没有产生项目
        db = _db()
        try:
            assert count_rows(db, "projects", user_id=default_user_id) == 0
        finally:
            db.close()
