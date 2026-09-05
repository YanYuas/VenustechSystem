# ============================================================
# 核心接口冒烟（pytest 版，逻辑与 scripts/smoke_backend.py 一致）
# ============================================================
from __future__ import annotations

import json
from datetime import date


def test_health(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["code"] == 0


def test_task_crud_and_focus(client):
    r = client.post("/api/v1/tasks", json={"title": "测试任务", "priority": "high"})
    assert r.json()["code"] == 0
    tid = r.json()["data"]["id"]

    r = client.post(f"/api/v1/tasks/{tid}/focus")
    assert r.json()["code"] == 0
    r = client.get("/api/v1/tasks/focus")
    assert r.json()["data"]["id"] == tid

    # 非法流转 completed -> waiting 返回 3001
    client.patch(f"/api/v1/tasks/{tid}", json={"status": "completed"})
    r = client.patch(f"/api/v1/tasks/{tid}", json={"status": "waiting"})
    assert r.json()["code"] == 3001


def test_subtask_progress(client):
    r = client.post("/api/v1/tasks", json={"title": "进度任务"})
    tid = r.json()["data"]["id"]
    client.post(f"/api/v1/tasks/{tid}/subtasks", json={"title": "A"})
    sa = client.post(f"/api/v1/tasks/{tid}/subtasks", json={"title": "B"}).json()["data"]["id"]
    client.patch(f"/api/v1/tasks/{tid}/subtasks/{sa}", json={"completed": True})
    d = client.get(f"/api/v1/tasks/{tid}").json()["data"]
    assert d["progress"] == 50 and d["subtasks_count"] == 2


def test_document_version_and_tags(client):
    r = client.post("/api/v1/documents", json={"title": "文档", "content": "第一版内容"})
    assert r.json()["code"] == 0
    did = r.json()["data"]["id"]
    r = client.patch(f"/api/v1/documents/{did}", json={"content": "第二版内容更多", "tags": ["测试"]})
    assert r.json()["data"]["version"] == 2
    r = client.get(f"/api/v1/documents/{did}/versions")
    assert len(r.json()["data"]) >= 1


def test_review_upsert_and_autofill(client):
    today = date.today().isoformat()
    r = client.put("/api/v1/reviews", json={
        "type": "daily", "date": today,
        "data": {"completed_tasks": "A", "mood": 4, "energy": 3, "reflections": []},
    })
    assert r.json()["code"] == 0
    r = client.get(f"/api/v1/reviews/{today}/auto-fill")
    assert "stats" in r.json()["data"]


def test_dashboard_and_stats(client):
    d = client.get("/api/v1/dashboard").json()["data"]
    assert "today_stats" in d and "user" in d
    s = client.get("/api/v1/data/stats").json()["data"]
    assert "documents" in s


def test_conversation_sse_stream(client):
    cid = client.post("/api/v1/conversations", json={"title": "冒烟"}).json()["data"]["id"]
    types = []
    with client.stream("POST", f"/api/v1/conversations/{cid}/messages", json={"content": "你好"}) as res:
        assert res.status_code == 200
        for line in res.iter_lines():
            if line.startswith("data: "):
                types.append(json.loads(line[6:])["type"])
    assert "content" in types and "done" in types
