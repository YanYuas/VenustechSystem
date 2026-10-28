# ============================================================
# 第二分身写操作 IDOR 回归测试（审计 D-20 / Phase 6-B）
#
# 背景：`avatar_service` 的 memory / inspiration 写操作此前只做
# `get_or_404(id)`（只验存在、不验归属）—— 任何已登录用户拿到别人的 id
# 就能改/删/确认其记忆、操作其灵感（IDOR，P1）。
#
# 修复后的契约：
#   1. service 写方法第一个参数是 `user_id`，取对象后校验 `obj.user_id`；
#      不匹配抛 **NotFound**（404 / code 1002），不是 403 —— 403 会告诉
#      攻击者「这个 id 真的存在」。
#   2. api 层所有调用点必须传当前登录用户 `user.id`。
#
# 本文件两层验证：
#   · service 层：用户 B 操作 A 的资源 → NotFound；**独立 Session** 复核
#     数据没被改动（证明真的是权限拦截，而不是对象没保存的假象）；
#     A 自己操作仍然成功。
#   · api 层：单用户系统没有多用户入口，故用「本人调用 7 个写端点成功」
#     证明调用点确实把 user.id 传下去了（漏传会 TypeError → 500，传错
#     会 404，两种回归都能被这条用例抓住）。
# ============================================================
from __future__ import annotations

import pytest

from app.core.exceptions import NotFoundException
from app.database import SessionLocal
from app.models.avatar import AvatarInspiration, AvatarMemory
from app.schemas.avatar import CreateMemoryRequest, GenerateInspirationRequest
from app.services.avatar_service import AvatarService


def _db():
    """独立 Session：与 service 的 Session 不是同一条连接，用于复核真实落库状态。"""
    return SessionLocal()


def _create_memory(svc: AvatarService, user_id: str, title: str = "A 的记忆") -> dict:
    return svc.create_memory(
        user_id,
        CreateMemoryRequest(memory_type="profile", title=title, content="原始内容"),
    )


def _create_inspiration(svc: AvatarService, user_id: str) -> dict:
    batch = svc.generate_inspirations(
        user_id, GenerateInspirationRequest(domain="学习", count=1)
    )
    return batch["inspirations"][0]


def _assert_not_found(exc_info: pytest.ExceptionInfo[NotFoundException]) -> None:
    """越权必须是 404/1002（与「资源不存在」同一语义，不泄漏存在性）。"""
    assert exc_info.value.http_status == 404
    assert exc_info.value.code == 1002


# ============================================================
# 一、记忆写操作（update / delete / verify）
# ============================================================
class TestMemoryIdor:
    def test_update_memory_by_other_user_is_not_found_and_unchanged(
        self, db_session, test_user, other_user
    ):
        """B 改 A 的记忆 → 404，且 A 的标题/正文原封不动。"""
        svc = AvatarService(db_session)
        memory = _create_memory(svc, test_user.id)

        with pytest.raises(NotFoundException) as ei:
            svc.update_memory(
                other_user.id, memory["id"],
                {"title": "越权改名", "content": "越权内容"},
            )
        _assert_not_found(ei)

        db = _db()
        try:
            row = db.get(AvatarMemory, memory["id"])
            assert row is not None, "越权失败不应把数据弄丢"
            assert row.user_id == test_user.id
            assert row.title == "A 的记忆"
            assert row.content == "原始内容"
        finally:
            db.close()

    def test_delete_memory_by_other_user_is_not_found_and_unchanged(
        self, db_session, test_user, other_user
    ):
        """B 删 A 的记忆 → 404，且记录仍然存在。"""
        svc = AvatarService(db_session)
        memory = _create_memory(svc, test_user.id)

        with pytest.raises(NotFoundException) as ei:
            svc.delete_memory(other_user.id, memory["id"])
        _assert_not_found(ei)

        db = _db()
        try:
            assert db.get(AvatarMemory, memory["id"]) is not None
        finally:
            db.close()

    def test_verify_memory_by_other_user_is_not_found_and_unchanged(
        self, db_session, test_user, other_user
    ):
        """B 确认 A 的记忆 → 404，且 is_verified 仍是 False。"""
        svc = AvatarService(db_session)
        memory = _create_memory(svc, test_user.id)
        assert memory["is_verified"] is False

        with pytest.raises(NotFoundException) as ei:
            svc.verify_memory(other_user.id, memory["id"], True)
        _assert_not_found(ei)

        db = _db()
        try:
            row = db.get(AvatarMemory, memory["id"])
            assert row is not None and row.is_verified is False
        finally:
            db.close()

    def test_memory_not_found_does_not_leak_existence(self, db_session, other_user):
        """不存在的 id 与「别人的 id」返回同一种错误 —— 无法据此探测存在性。"""
        svc = AvatarService(db_session)
        with pytest.raises(NotFoundException) as ei:
            svc.update_memory(other_user.id, "ghost-memory-id", {"title": "x"})
        _assert_not_found(ei)

    def test_owner_can_update_verify_delete_memory(self, db_session, test_user):
        """A 自己操作仍然成功（update / verify / delete 全链路）。"""
        svc = AvatarService(db_session)
        memory = _create_memory(svc, test_user.id)

        updated = svc.update_memory(test_user.id, memory["id"], {"title": "本人改名"})
        assert updated["title"] == "本人改名"
        assert updated["user_id"] == test_user.id

        verified = svc.verify_memory(test_user.id, memory["id"], True)
        assert verified["is_verified"] is True

        db_session.commit()  # 落库后由独立 Session 复核
        db = _db()
        try:
            row = db.get(AvatarMemory, memory["id"])
            assert row is not None and row.title == "本人改名" and row.is_verified is True
        finally:
            db.close()

        svc.delete_memory(test_user.id, memory["id"])
        db_session.commit()
        db = _db()
        try:
            assert db.get(AvatarMemory, memory["id"]) is None
        finally:
            db.close()


# ============================================================
# 二、灵感写操作（select / execute / feedback / discard）
# ============================================================
class TestInspirationIdor:
    def test_select_inspiration_by_other_user_is_not_found_and_unchanged(
        self, db_session, test_user, other_user
    ):
        """B 选择 A 的灵感 → 404，状态仍是 generated、prompt 仍为空。"""
        svc = AvatarService(db_session)
        insp = _create_inspiration(svc, test_user.id)

        with pytest.raises(NotFoundException) as ei:
            svc.select_inspiration(other_user.id, insp["id"])
        _assert_not_found(ei)

        db = _db()
        try:
            row = db.get(AvatarInspiration, insp["id"])
            assert row is not None
            assert row.status == "generated"
            assert row.prompt is None
        finally:
            db.close()

    def test_execute_inspiration_by_other_user_is_not_found_and_unchanged(
        self, db_session, test_user, other_user
    ):
        """B 执行 A 的灵感 → 404，状态/结果都没被改。"""
        svc = AvatarService(db_session)
        insp = _create_inspiration(svc, test_user.id)

        with pytest.raises(NotFoundException) as ei:
            svc.execute_inspiration(other_user.id, insp["id"], "越权执行结果")
        _assert_not_found(ei)

        db = _db()
        try:
            row = db.get(AvatarInspiration, insp["id"])
            assert row is not None
            assert row.status == "generated"
            assert row.result is None
        finally:
            db.close()

    def test_feedback_inspiration_by_other_user_is_not_found_and_unchanged(
        self, db_session, test_user, other_user
    ):
        """B 给 A 的灵感反馈 → 404，feedback 仍为空。"""
        svc = AvatarService(db_session)
        insp = _create_inspiration(svc, test_user.id)

        with pytest.raises(NotFoundException) as ei:
            svc.feedback_inspiration(other_user.id, insp["id"], "useless")
        _assert_not_found(ei)

        db = _db()
        try:
            row = db.get(AvatarInspiration, insp["id"])
            assert row is not None and row.feedback is None
        finally:
            db.close()

    def test_discard_inspiration_by_other_user_is_not_found_and_unchanged(
        self, db_session, test_user, other_user
    ):
        """B 丢弃 A 的灵感 → 404，状态仍是 generated（没被 discarded）。"""
        svc = AvatarService(db_session)
        insp = _create_inspiration(svc, test_user.id)

        with pytest.raises(NotFoundException) as ei:
            svc.discard_inspiration(other_user.id, insp["id"])
        _assert_not_found(ei)

        db = _db()
        try:
            row = db.get(AvatarInspiration, insp["id"])
            assert row is not None and row.status == "generated"
        finally:
            db.close()

    def test_inspiration_not_found_does_not_leak_existence(self, db_session, other_user):
        svc = AvatarService(db_session)
        with pytest.raises(NotFoundException) as ei:
            svc.discard_inspiration(other_user.id, "ghost-inspiration-id")
        _assert_not_found(ei)

    def test_owner_can_select_execute_feedback_discard_inspiration(
        self, db_session, test_user
    ):
        """A 自己操作仍然成功（四步全链路，独立 Session 复核最终状态）。"""
        svc = AvatarService(db_session)
        insp = _create_inspiration(svc, test_user.id)

        selected = svc.select_inspiration(test_user.id, insp["id"])
        assert selected["status"] == "selected"
        assert selected["prompt"]

        executed = svc.execute_inspiration(test_user.id, insp["id"], "本人执行结果")
        assert executed["status"] == "completed"
        assert executed["result"] == "本人执行结果"

        feedbacked = svc.feedback_inspiration(test_user.id, insp["id"], "useful")
        assert feedbacked["feedback"] == "useful"

        discarded = svc.discard_inspiration(test_user.id, insp["id"])
        assert discarded["status"] == "discarded"

        db_session.commit()
        db = _db()
        try:
            row = db.get(AvatarInspiration, insp["id"])
            assert row is not None
            assert row.user_id == test_user.id
            assert row.status == "discarded"
            assert row.result == "本人执行结果"
            assert row.feedback == "useful"
        finally:
            db.close()


# ============================================================
# 三、API 调用点接线（真值来源：api/avatar.py 必须传 user.id）
# ============================================================
class TestApiCallSitesPassUser:
    """单用户系统无法从 HTTP 模拟第二个用户，因此这里验证「本人调用成功」：

    若 api 层漏传 user.id → service 缺参 TypeError → 500；
    若传错对象 → 404。两种接线回归都能让本类变红。
    """

    def test_memory_write_endpoints_work_for_owner(self, client, default_user_id):
        r = client.post(
            "/api/v1/avatar/memories",
            json={"memory_type": "profile", "title": "API 记忆", "content": "初始"},
        )
        assert r.status_code == 200, r.text
        memory_id = r.json()["data"]["id"]

        r = client.patch(
            f"/api/v1/avatar/memories/{memory_id}", json={"title": "API 改名"}
        )
        assert r.status_code == 200, r.text
        assert r.json()["data"]["title"] == "API 改名"

        r = client.post(f"/api/v1/avatar/memories/{memory_id}/verify?verified=true")
        assert r.status_code == 200, r.text
        assert r.json()["data"]["is_verified"] is True

        r = client.delete(f"/api/v1/avatar/memories/{memory_id}")
        assert r.status_code == 200, r.text
        assert r.json()["data"] is None

        db = _db()
        try:
            assert db.get(AvatarMemory, memory_id) is None
        finally:
            db.close()

    def test_inspiration_write_endpoints_work_for_owner(self, client, default_user_id):
        r = client.post(
            "/api/v1/avatar/inspirations/generate",
            json={"domain": "学习", "count": 1},
        )
        assert r.status_code == 200, r.text
        inspiration_id = r.json()["data"]["inspirations"][0]["id"]

        r = client.post(f"/api/v1/avatar/inspirations/{inspiration_id}/select")
        assert r.status_code == 200, r.text
        assert r.json()["data"]["status"] == "selected"
        assert r.json()["data"]["prompt"]

        r = client.post(
            f"/api/v1/avatar/inspirations/{inspiration_id}/execute?result=API执行"
        )
        assert r.status_code == 200, r.text
        assert r.json()["data"]["status"] == "completed"
        assert r.json()["data"]["result"] == "API执行"

        r = client.post(
            f"/api/v1/avatar/inspirations/{inspiration_id}/feedback?feedback=useful"
        )
        assert r.status_code == 200, r.text
        assert r.json()["data"]["feedback"] == "useful"

        r = client.post(f"/api/v1/avatar/inspirations/{inspiration_id}/discard")
        assert r.status_code == 200, r.text
        assert r.json()["data"]["status"] == "discarded"

        db = _db()
        try:
            row = db.get(AvatarInspiration, inspiration_id)
            assert row is not None
            assert row.status == "discarded"
            assert row.result == "API执行"
            assert row.feedback == "useful"
        finally:
            db.close()
