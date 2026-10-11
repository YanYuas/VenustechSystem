# ============================================================
# ConversationService 生产级测试（原缺失模块，本轮补齐）
#
# 覆盖：会话 CRUD / 越权隔离 / 消息落库 / 流式对话（含降级 mock）/
# 文档引用上下文注入。
#
# 说明：Service 的流式接口是 async generator，本环境未装 pytest-asyncio，
# 因此用 asyncio.run() 驱动（同步测试 + 事件循环），保持零额外依赖。
# ============================================================
from __future__ import annotations

import asyncio

import pytest

from app.core.exceptions import NotFoundException
from app.schemas.conversation import SendMessageRequest
from app.services.conversation_service import ConversationService
from tests.factories import count_rows, make_document


def _svc(db, user) -> ConversationService:
    return ConversationService(db, user)


def _collect(agen) -> list[dict]:
    """把异步生成器跑完并收集事件。"""

    async def run() -> list[dict]:
        out = []
        async for ev in agen:
            out.append(ev)
        return out

    return asyncio.run(run())


class TestConversationCrud:
    """会话 CRUD 与越权隔离。"""

    def test_create_default_title(self, db_session, test_user):
        """不传标题时使用「未命名对话」。"""
        out = _svc(db_session, test_user).create()
        assert out.title == "未命名对话"
        assert out.scene == "general"
        assert count_rows(db_session, "conversations", user_id=test_user.id) == 1

    def test_create_with_title_and_project(self, db_session, test_user):
        """标题/项目关联写入并落库。"""
        from app.models.project import Project

        proj = Project(user_id=test_user.id, name="论文项目")
        db_session.add(proj)
        db_session.flush()

        out = _svc(db_session, test_user).create(title="论文讨论", project_id=proj.id)
        assert out.title == "论文讨论"
        assert out.project_id == proj.id

        from app.models.conversation import Conversation
        row = db_session.get(Conversation, out.id)
        assert row.title == "论文讨论"
        assert row.project_id == proj.id
        assert row.user_id == test_user.id

    def test_list_isolated_per_user(self, db_session, test_user, other_user):
        """列表只返回本人会话。"""
        _svc(db_session, test_user).create(title="我的会话")
        _svc(db_session, other_user).create(title="别人的会话")
        titles = [c.title for c in _svc(db_session, test_user).list()]
        assert titles == ["我的会话"]

    def test_delete_removes_conversation(self, db_session, test_user):
        """删除会话后查库确认消失。"""
        out = _svc(db_session, test_user).create()
        _svc(db_session, test_user).delete(out.id)

        from app.models.conversation import Conversation
        assert db_session.get(Conversation, out.id) is None
        assert count_rows(db_session, "conversations", user_id=test_user.id) == 0

    def test_delete_cascades_messages(self, db_session, test_user):
        """删除会话级联删除其消息（不留孤儿消息）。"""
        out = _svc(db_session, test_user).create()
        _svc(db_session, test_user).messages(out.id)  # 触发一次 owned 校验
        # 造一条消息
        from app.repositories import MessageRepository
        MessageRepository(db_session).create(
            conversation_id=out.id, role="user", content="hi"
        )
        assert count_rows(db_session, "messages", conversation_id=out.id) == 1

        _svc(db_session, test_user).delete(out.id)
        assert count_rows(db_session, "messages", conversation_id=out.id) == 0

    def test_unknown_conversation_raises(self, db_session, test_user):
        """不存在的会话在 messages/delete 上抛 NotFound。"""
        with pytest.raises(NotFoundException):
            _svc(db_session, test_user).messages("no-such-conv")
        with pytest.raises(NotFoundException):
            _svc(db_session, test_user).delete("no-such-conv")

    def test_cross_user_access_denied(self, db_session, test_user, other_user):
        """越权访问他人会话一律 NotFound（不泄露存在性）。"""
        other = _svc(db_session, other_user).create(title="别人的")
        with pytest.raises(NotFoundException):
            _svc(db_session, test_user).messages(other.id)
        with pytest.raises(NotFoundException):
            _svc(db_session, test_user).delete(other.id)


class TestStreamMessages:
    """流式对话：消息落库 + 事件序列 + 降级 mock。"""

    def test_stream_persists_user_and_assistant_messages(self, db_session, test_user):
        """一轮对话后，messages 表应有 user + assistant 各一条。

        防什么：助手消息若在流结束后未落库，刷新页面就丢失全部 AI 回复。
        """
        svc = _svc(db_session, test_user)
        conv = svc.create()
        events = _collect(svc.stream_messages(conv.id, SendMessageRequest(content="你好")))

        assert count_rows(db_session, "messages", conversation_id=conv.id) == 2

        from sqlalchemy import select
        from app.models.conversation import Message
        rows = db_session.scalars(
            select(Message).where(Message.conversation_id == conv.id)
            .order_by(Message.created_at)
        ).all()
        assert [m.role for m in rows] == ["user", "assistant"]
        assert rows[0].content == "你好"
        assert rows[1].content  # 助手回复非空（mock 客户端也应产出文本）

    def test_stream_emits_content_and_done(self, db_session, test_user):
        """事件序列包含 content 与 done（前端据此收尾）。"""
        svc = _svc(db_session, test_user)
        conv = svc.create()
        events = _collect(svc.stream_messages(conv.id, SendMessageRequest(content="测试")))
        types = [e["type"] for e in events]
        assert "content" in types
        assert "done" in types
        assert types[-1] == "done"

    def test_stream_unknown_conversation_raises(self, db_session, test_user):
        """对不存在会话发起对话：消费生成器时抛 NotFound。"""
        svc = _svc(db_session, test_user)
        with pytest.raises(NotFoundException):
            _collect(svc.stream_messages("ghost", SendMessageRequest(content="hi")))

    def test_stream_with_referenced_doc_does_not_leak_other_docs(
        self, db_session, test_user, other_user
    ):
        """引用他人文档时不得注入其内容（越权上下文泄露）。

        防什么：_build_context 若漏了 doc.user_id 校验，别人文档的正文会被
        拼进 system prompt 发给模型 —— 既是数据泄露也是提示注入面。
        """
        other_doc = make_document(db_session, other_user.id, title="别人的私密文档",
                                  content="SECRET-OTHER-USER-CONTENT")
        db_session.commit()

        svc = _svc(db_session, test_user)
        conv = svc.create()
        ctx = svc._build_context(conv.id, "问题", [other_doc.id], "normal")
        joined = "\n".join(m["content"] for m in ctx)
        assert "SECRET-OTHER-USER-CONTENT" not in joined

    def test_stream_injects_own_doc_content(self, db_session, test_user):
        """引用本人文档时，正文进入上下文。"""
        own = make_document(db_session, test_user.id, title="我的笔记",
                            content="OWN-DOC-CONTENT-42")
        db_session.commit()

        svc = _svc(db_session, test_user)
        conv = svc.create()
        ctx = svc._build_context(conv.id, "问题", [own.id], "normal")
        joined = "\n".join(m["content"] for m in ctx)
        assert "OWN-DOC-CONTENT-42" in joined
        assert "我的笔记" in joined

    @pytest.mark.parametrize("mode", ["normal", "deep", "creative", "critical", "brainstorm"])
    def test_stream_accepts_all_think_modes(self, db_session, test_user, mode):
        """5 种思维模式都能跑通（未知模式回落 normal）。"""
        svc = _svc(db_session, test_user)
        conv = svc.create()
        events = _collect(svc.stream_messages(conv.id, SendMessageRequest(content="x", mode=mode)))
        assert any(e["type"] == "done" for e in events)

    def test_stream_unknown_mode_falls_back(self, db_session, test_user):
        """未知 mode 不影响流程（回落 normal）。"""
        svc = _svc(db_session, test_user)
        conv = svc.create()
        events = _collect(svc.stream_messages(
            conv.id, SendMessageRequest(content="x", mode="not-a-mode")
        ))
        assert any(e["type"] == "done" for e in events)
