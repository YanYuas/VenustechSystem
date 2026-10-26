# ============================================================
# 事务边界回归测试（审计 D-04「事务边界下沉」修复）
#
# 改造后的架构约定：
#   A. Repository 的 create/create_many/update/delete 只 `flush()`，**不 commit**；
#   B. 请求级事务由 `api/deps.get_db` 闭合（异常 → rollback，正常 → commit）；
#   C. service 只在「用例完成点」和「发布领域事件之前」显式 commit；
#   D. 非请求调用方（seed / lifespan / bootstrap 后台任务）自己显式 commit。
#
# 本文件验证三件事（对应验收第 3 条）：
#   1. 用例内第 2 步失败时，第 1 步写入必须**一起回滚**；
#   2. 「写完 → commit → publish」：事件发布时订阅者的**独立 Session**
#      已经能读到已提交数据（订阅者用的是新 Session，未提交就读不到）；
#   3. 没有显式 commit 的 service 写入，由 get_db 请求事务兜底提交。
#
# 为什么走 API（TestClient）而不直接 new service：
#   生产环境的事务边界在 get_db。直接调 service 会绕过它，测的就不是真实
#   回滚路径了。API 返回 4xx/5xx = 请求内抛异常 = get_db 必须 rollback。
#
# 为什么用独立 SessionLocal 查库：
#   同一 Session 的 identity map / 未提交状态会让「没落库」看起来像「没了」。
#   只有另开一条连接查，才能证明是真回滚，而不是同 Session 的假象。
# ============================================================
from __future__ import annotations

import uuid

from sqlalchemy import func, select

from app.core.event_bus import (
    EVENT_DOCUMENT_SAVED,
    EVENT_TASK_CREATED,
    event_bus,
)
from app.core.exceptions import ServerException
from app.database import SessionLocal
from app.models.document import Document, DocumentVersion
from app.models.folder import Folder
from app.models.learning import StudyPlan
from app.models.task import Task


# ============================================================
# 辅助
# ============================================================
def _db():
    """独立 Session：验证数据真的提交进库（而非当前事务/identity map）。"""
    return SessionLocal()


def _name(prefix: str) -> str:
    """唯一名称，避免同一测试会话内的残留/并发冲突。"""
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


# ============================================================
# 一、用例原子性：第 2 步失败 → 第 1 步必须回滚
# ============================================================
class TestCaseAtomicityRollback:
    """一个用例内的多步写入，要么全成、要么全不成。"""

    def test_create_document_rolls_back_document_when_backlink_step_fails(
        self, client, default_user_id, monkeypatch
    ):
        """创建文档 = ① 写 documents 行 + ② 重建双链（_sync_backlinks）。

        防什么：改造前 `repo.create()` 内部 commit，第 ① 步已经落库；
        第 ② 步失败后库里留下一篇「双链缺失」的文档 —— 用户看到的是
        「文档建成功了，但关系图谱里没有它」，属于不可修复的中间态。
        """
        from app.services.document_service import DocumentService

        title = _name("原子性-建文档")

        def _boom(self, user_id, doc):
            raise ServerException("模拟第 2 步失败：双链重建")

        monkeypatch.setattr(DocumentService, "_sync_backlinks", _boom)

        r = client.post(
            "/api/v1/documents",
            json={"title": title, "content": "正文里有一个 [[目标文档]] 链接"},
        )
        assert r.status_code == 500, "第 2 步抛 ServerException，响应应是 500"

        db = _db()
        try:
            found = db.scalars(select(Document).where(Document.title == title)).first()
            assert found is None, (
                "第 2 步失败后 documents 行仍然存在 → 用例没有原子回滚"
                "（repository 又 commit 了，或 get_db 没有 rollback）"
            )
        finally:
            db.close()

    def test_update_document_rolls_back_content_and_version_when_step2_fails(
        self, client, default_user_id, monkeypatch
    ):
        """保存文档 = ① 版本快照 + 正文/字数/版本号更新 + ② 重建双链。

        防什么：第 ① 步已经改了正文、写了 DocumentVersion 行。若第 ② 步
        失败而第 ① 步已提交，正文与双链就不一致（旧链接还指向旧标题），
        且版本历史里多出一条「正文没变」的快照。
        """
        created = client.post(
            "/api/v1/documents",
            json={"title": _name("原子性-改文档"), "content": "旧正文"},
        ).json()["data"]
        doc_id = created["id"]
        assert created["version"] == 1

        from app.services.document_service import DocumentService

        def _boom(self, user_id, doc):
            raise ServerException("模拟第 2 步失败：双链重建")

        monkeypatch.setattr(DocumentService, "_sync_backlinks", _boom)

        r = client.patch(
            f"/api/v1/documents/{doc_id}",
            json={"content": "新正文 [[新目标]]"},
        )
        assert r.status_code == 500

        db = _db()
        try:
            doc = db.get(Document, doc_id)
            assert doc is not None
            assert doc.content == "旧正文", "正文更新没回滚"
            assert doc.version == 1, "版本号已 +1 → 版本快照那一步被提前提交了"
            version_rows = db.scalar(
                select(func.count())
                .select_from(DocumentVersion)
                .where(DocumentVersion.document_id == doc_id)
            )
            assert version_rows == 0, "DocumentVersion 快照没回滚（用例内中间态）"
        finally:
            db.close()

    def test_update_document_real_failure_rolls_back_content_and_version(
        self, client, default_user_id
    ):
        """**真实的**第 2 步失败（不靠 monkeypatch）：folder_id 校验不过。

        顺序是「先改正文/写版本，后校验 folder_id」——
        请求返回 404，则正文与版本快照都必须回到原状。
        改造前 `DocumentVersionRepository.create()` 自己 commit，
        这条路径会留下一条孤立版本快照。
        """
        created = client.post(
            "/api/v1/documents",
            json={"title": _name("原子性-真失败"), "content": "旧正文"},
        ).json()["data"]
        doc_id = created["id"]

        r = client.patch(
            f"/api/v1/documents/{doc_id}",
            json={"content": "新正文", "folder_id": "folder-does-not-exist"},
        )
        assert r.status_code == 404
        assert r.json()["code"] == 1002

        db = _db()
        try:
            doc = db.get(Document, doc_id)
            assert doc is not None
            assert doc.content == "旧正文", "请求失败后正文仍是新值 → get_db 没回滚"
            assert doc.version == 1
            version_rows = db.scalar(
                select(func.count())
                .select_from(DocumentVersion)
                .where(DocumentVersion.document_id == doc_id)
            )
            assert version_rows == 0, "请求失败后仍留下版本快照（旧 repo.commit 的残留）"
        finally:
            db.close()

    def test_generate_plan_rolls_back_plan_when_task_batch_fails(
        self, client, default_user_id, monkeypatch
    ):
        """S6-1 领域引擎：① 写 StudyPlan + ② 批量写 Task（30~40 条）。

        防什么：这是 base.py 注释里点名的原始场景 —— 计划建好了、任务只建了
        一半。现在两步同属一个请求事务，第 ② 步失败则计划也必须消失。
        """
        from app.repositories.task_repo import TaskRepository

        plan_name = _name("原子性-学习计划")

        def _boom(self, items):
            raise ServerException("模拟第 2 步失败：批量写任务")

        monkeypatch.setattr(TaskRepository, "create_many", _boom)

        r = client.post(
            "/api/v1/learning/plans/generate/apply",
            json={
                "goal": "我想学英语",
                "total_days": 7,
                "minutes_per_day": 30,
                "plan_name": plan_name,
            },
        )
        assert r.status_code == 500

        db = _db()
        try:
            found = db.scalars(select(StudyPlan).where(StudyPlan.name == plan_name)).first()
            assert found is None, "任务批量写入失败后计划仍然存在 → 计划/任务不是原子用例"
        finally:
            db.close()


# ============================================================
# 二、「写完 → commit → publish」硬约束
# ============================================================
class TestPublishAfterCommit:
    """事件订阅者用**独立 Session** 读取数据，publish 前必须先 commit。"""

    def test_task_created_publish_sees_committed_row(
        self, client, default_user_id, monkeypatch
    ):
        """EVENT_TASK_CREATED 的订阅者（成长体系 EXP 结算）用新 Session 反查任务。

        防什么：若 publish 早于 commit，订阅者查不到任务 → EXP 静默不结算，
        且幂等键已经写进事件历史，属于「事件发了但没生效」的隐蔽缺陷。
        """
        seen: dict[str, object] = {}
        real_publish = event_bus.publish

        def spy(event, **kwargs):
            if event == EVENT_TASK_CREATED:
                db = _db()
                try:
                    row = db.get(Task, kwargs.get("task_id"))
                    seen["visible"] = row is not None
                    seen["title"] = getattr(row, "title", None)
                finally:
                    db.close()
            return real_publish(event, **kwargs)

        monkeypatch.setattr(event_bus, "publish", spy)

        title = _name("发布前提交-任务")
        r = client.post("/api/v1/tasks", json={"title": title})
        assert r.status_code == 200
        assert seen.get("visible") is True, (
            "publish 时独立 Session 读不到任务 → commit 发生在 publish 之后"
        )
        assert seen.get("title") == title

    def test_document_saved_publish_sees_committed_content(
        self, client, default_user_id, monkeypatch
    ):
        """EVENT_DOCUMENT_SAVED 的订阅者（AI 摘要/标签、EXP 结算）用新 Session 反查文档。

        要求发布时**正文与版本号都已提交**，否则订阅者会基于旧内容生成摘要。
        """
        created = client.post(
            "/api/v1/documents",
            json={"title": _name("发布前提交-文档"), "content": "初稿"},
        ).json()["data"]
        doc_id = created["id"]

        seen: dict[str, object] = {}
        real_publish = event_bus.publish

        def spy(event, **kwargs):
            if event == EVENT_DOCUMENT_SAVED:
                db = _db()
                try:
                    row = db.get(Document, kwargs.get("document_id"))
                    seen["content"] = getattr(row, "content", None)
                    seen["version"] = getattr(row, "version", None)
                finally:
                    db.close()
            return real_publish(event, **kwargs)

        monkeypatch.setattr(event_bus, "publish", spy)

        r = client.patch(f"/api/v1/documents/{doc_id}", json={"content": "提交后的正文"})
        assert r.status_code == 200
        assert seen.get("content") == "提交后的正文", (
            "publish 时订阅者读到的是旧正文 → 保存后没有先 commit 再 publish"
        )
        assert seen.get("version") == 2


# ============================================================
# 三、Repository 只 flush；get_db 兜底提交
# ============================================================
class TestRepositoryFlushAndRequestTransaction:
    """A 项（repo 不 commit）与 B 项（get_db 兜底）的直接断言。"""

    def test_repository_create_only_flushes_not_commits(self, db_session, default_user_id):
        """`repo.create()` 必须只 flush：主键已分配，但独立 Session 看不到。

        防什么：repository 一旦重新 commit，service 的多步用例原子性立刻失效，
        且 get_db 的 rollback 会变成摆设（无法回滚已提交的数据）。
        """
        from app.repositories.folder_repo import FolderRepository

        repo = FolderRepository(db_session)
        folder = repo.create(user_id=default_user_id, name=_name("只flush"))
        assert folder.id, "flush 后应已分配主键（应用层 uuid 默认值需要 flush 才生效）"

        other = _db()
        try:
            assert other.get(Folder, folder.id) is None, (
                "repo.create() 已经提交了事务 → 独立 Session 能读到未提交的数据"
            )
        finally:
            other.close()

    def test_folder_create_without_service_commit_is_persisted(self, client, default_user_id):
        """`DocumentService.create_folder` 只调 repo.create（无 commit 语句），
        由 get_db 在响应前提交 —— 这是 D-04 改造 B 项的兜底能力。
        """
        name = _name("兜底文件夹")
        r = client.post("/api/v1/folders", json={"name": name})
        assert r.status_code == 200

        db = _db()
        try:
            assert db.scalars(select(Folder).where(Folder.name == name)).first() is not None
        finally:
            db.close()
