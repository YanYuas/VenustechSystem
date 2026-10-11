# ============================================================
# Conversation API 集成测试（原缺失模块，本轮补齐）
#
# 覆盖：会话列表/创建/删除、消息历史、SSE 流式对话、参数校验、404。
# ============================================================
from __future__ import annotations

import json

from app.database import SessionLocal


def _create_conv(client, **payload):
    r = client.post("/api/v1/conversations", json=payload or None)
    assert r.status_code == 200, r.text
    return r.json()["data"]


def _db_count(table: str, **where) -> int:
    from sqlalchemy import func, select, text

    db = SessionLocal()
    try:
        q = select(func.count()).select_from(text(table))
        for col, val in where.items():
            q = q.where(text(f"{table}.{col} = :{col}")).params(**{col: val})
        return int(db.scalar(q) or 0)
    finally:
        db.close()


def _stream_message(client, conv_id: str, content: str = "你好", mode: str = "normal") -> list[dict]:
    """调用 SSE 端点并解析事件列表。"""
    events: list[dict] = []
    with client.stream("POST", f"/api/v1/conversations/{conv_id}/messages",
                       json={"content": content, "mode": mode}) as res:
        assert res.status_code == 200
        for line in res.iter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
    return events


class TestConversationApiGroup1Crud:
    """第1组：列表 / 创建 / 删除 / 404。"""

    def test_list_empty(self, client):
        """空库返回空数组。"""
        r = client.get("/api/v1/conversations")
        assert r.status_code == 200
        assert r.json()["code"] == 0
        assert r.json()["data"] == []

    def test_create_without_body_uses_default_title(self, client, default_user_id):
        """POST 不带 body 也能创建（默认标题）。"""
        data = _create_conv(client)
        assert data["title"] == "未命名对话"
        assert _db_count("conversations", user_id=default_user_id) == 1

    def test_create_with_title_and_project(self, client):
        """带标题/项目创建并回显（项目必须是已存在的，外键生效）。"""
        proj = client.post("/api/v1/projects", json={"name": "论文项目"}).json()["data"]
        data = _create_conv(client, title="论文讨论", project_id=proj["id"])
        assert data["title"] == "论文讨论"
        assert data["project_id"] == proj["id"]

    def test_delete_then_absent(self, client, default_user_id):
        """删除后列表为空、库中无记录。"""
        conv = _create_conv(client, title="待删")
        assert client.delete(f"/api/v1/conversations/{conv['id']}").status_code == 200
        assert client.get("/api/v1/conversations").json()["data"] == []
        assert _db_count("conversations", user_id=default_user_id) == 0

    def test_messages_of_unknown_conversation_returns_404(self, client):
        """未知会话取消息返回 404 + 1002。"""
        r = client.get("/api/v1/conversations/ghost/messages")
        assert r.status_code == 404
        assert r.json()["code"] == 1002

    def test_delete_unknown_conversation_returns_404(self, client):
        """删除未知会话返回 404 + 1002。"""
        r = client.delete("/api/v1/conversations/ghost")
        assert r.status_code == 404
        assert r.json()["code"] == 1002


class TestConversationApiGroup2Stream:
    """第2组：SSE 流式对话。"""

    def test_stream_returns_content_and_done_and_persists(self, client):
        """SSE 返回 content/done 事件，且消息落库（user + assistant）。"""
        conv = _create_conv(client)
        events = _stream_message(client, conv["id"], content="你好")
        types = [e["type"] for e in events]
        assert "content" in types
        assert "done" in types

        assert _db_count("messages", conversation_id=conv["id"]) == 2

        msgs = client.get(f"/api/v1/conversations/{conv['id']}/messages").json()["data"]
        roles = [m["role"] for m in msgs]
        assert roles == ["user", "assistant"]
        assert msgs[0]["content"] == "你好"

    def test_stream_empty_content_rejected(self, client):
        """空 content 被 Pydantic 拦截（min_length=1）→ 400。"""
        conv = _create_conv(client)
        r = client.post(f"/api/v1/conversations/{conv['id']}/messages", json={"content": ""})
        assert r.status_code == 400
        assert r.json()["code"] == 1001

    def test_stream_unknown_conversation_emits_error_event(self, client):
        """对不存在会话发起对话：SSE 已 200 开头，故以 error 事件告知。

        防什么：若异常未被捕获，连接会被无声掐断，前端只看到「卡住」。
        """
        events = _stream_message(client, "ghost-conv", content="hi")
        assert any(e["type"] == "error" for e in events)
        assert events[0].get("code") == 1002

    def test_stream_thinking_mode_accepted(self, client):
        """带 mode=deep 的请求正常完成。"""
        conv = _create_conv(client)
        events = _stream_message(client, conv["id"], content="深度思考", mode="deep")
        assert any(e["type"] == "done" for e in events)

    def test_stream_with_referenced_docs(self, client, default_user_id):
        """带 referenced_doc_ids 的请求正常完成并记录引用。"""
        doc = client.post("/api/v1/documents", json={
            "title": "被引文档", "content": "引用内容"
        }).json()["data"]
        conv = _create_conv(client)

        events: list[dict] = []
        with client.stream(
            "POST", f"/api/v1/conversations/{conv['id']}/messages",
            json={"content": "看看这份文档", "referenced_doc_ids": [doc["id"]]},
        ) as res:
            for line in res.iter_lines():
                if line.startswith("data: "):
                    events.append(json.loads(line[6:]))
        assert any(e["type"] == "done" for e in events)

        msgs = client.get(f"/api/v1/conversations/{conv['id']}/messages").json()["data"]
        assert msgs[0]["referenced_doc_ids"] == [doc["id"]]
