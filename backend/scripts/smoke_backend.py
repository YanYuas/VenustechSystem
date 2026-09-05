# ============================================================
# 后端冒烟测试（零 pytest 依赖，用 FastAPI TestClient 端到端断言）
# 用法：python scripts/smoke_backend.py   （在 backend/ 目录下）
# 通过则退出码 0，失败退出码 1
# ============================================================
from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import date
from pathlib import Path

# Windows 管道/重定向下 stdout 默认 GBK，无法打印 ✅/中文 → 强制 UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BACKEND_DIR = Path(__file__).resolve().parent.parent
SMOKE_DIR = BACKEND_DIR / "data_smoke"

# 必须在 import app 前设置环境（engine/settings 在模块导入时初始化）
os.environ["VENUSTECH_DATA_DIR"] = str(SMOKE_DIR)
os.environ["VENUSTECH_DEV"] = "false"
os.environ["VENUSTECH_DEMO_SEED"] = "true"

if SMOKE_DIR.exists():
    shutil.rmtree(SMOKE_DIR, ignore_errors=True)

sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402

passed = 0
failed = 0


def check(name: str, cond: bool, extra: str = "") -> None:
    global passed, failed
    if cond:
        passed += 1
        print(f"  ✅ {name}")
    else:
        failed += 1
        print(f"  ❌ {name}  {extra}")


def main() -> int:
    with TestClient(app) as client:
        # 1. 健康检查
        r = client.get("/api/v1/health")
        check("health", r.status_code == 200 and r.json().get("code") == 0, r.text[:120])

        # 2. auth/me
        r = client.get("/api/v1/auth/me")
        d = r.json()
        check("auth/me", d.get("code") == 0 and bool(d["data"]["nickname"]), r.text[:120])

        # 3. 创建任务
        r = client.post("/api/v1/tasks", json={"title": "冒烟任务", "priority": "high", "project_tag": "测试"})
        d = r.json()
        check("task create", d.get("code") == 0 and d["data"]["status"] == "pending", r.text[:120])
        tid = d["data"]["id"]

        # 4. 任务列表
        r = client.get("/api/v1/tasks")
        d = r.json()
        check("task list", d.get("code") == 0 and d["data"]["total"] >= 1 and isinstance(d["data"]["list"], list), r.text[:120])

        # 5. 状态流转 pending -> in_progress
        r = client.patch(f"/api/v1/tasks/{tid}", json={"status": "in_progress"})
        check("task update status", r.json()["data"]["status"] == "in_progress", r.text[:120])

        # 6. 非法流转 in_progress -> completed 后 -> waiting 应 3001
        r = client.patch(f"/api/v1/tasks/{tid}", json={"status": "completed"})
        r = client.patch(f"/api/v1/tasks/{tid}", json={"status": "waiting"})
        check("illegal transition 3001", r.json().get("code") == 3001, r.text[:120])

        # 7. 设为今日最重要 + 互斥
        r = client.post(f"/api/v1/tasks/{tid}/focus")
        check("set focus", r.json().get("code") == 0, r.text[:120])
        r = client.get("/api/v1/tasks/focus")
        check("focus get", r.json()["data"]["id"] == tid, r.text[:120])
        r = client.post("/api/v1/tasks", json={"title": "第二个任务"})
        tid2 = r.json()["data"]["id"]
        client.post(f"/api/v1/tasks/{tid2}/focus")
        r = client.get("/api/v1/tasks/focus")
        check("focus exclusive", r.json()["data"]["id"] == tid2, r.text[:120])

        # 8. 子任务 + 进度
        r = client.post(f"/api/v1/tasks/{tid2}/subtasks", json={"title": "子任务A"})
        sa = r.json()["data"]["id"]
        r = client.post(f"/api/v1/tasks/{tid2}/subtasks", json={"title": "子任务B"})
        sb = r.json()["data"]["id"]
        client.patch(f"/api/v1/tasks/{tid2}/subtasks/{sa}", json={"completed": True})
        r = client.get(f"/api/v1/tasks/{tid2}")
        d = r.json()["data"]
        check("subtask progress 50", d["progress"] == 50 and d["subtasks_count"] == 2, str(d))

        # 9. 今日统计
        r = client.get("/api/v1/tasks/today/stats")
        d = r.json()["data"]
        check("today stats", all(k in d for k in ("must_do", "in_progress", "waiting", "completed_today")), str(d))

        # 10. 文件夹
        r = client.get("/api/v1/folders")
        d = r.json()
        check("folders tree", d.get("code") == 0 and any(f["is_inbox"] for f in d["data"]), r.text[:120])
        r = client.post("/api/v1/folders", json={"name": "冒烟文件夹"})
        d = r.json()
        check("create folder", d.get("code") == 0, r.text[:120])
        fid = d["data"]["id"]

        # 11. 文档创建
        r = client.post("/api/v1/documents", json={
            "title": "测试文档", "content": "这是一篇用于冒烟测试的文档，包含架构设计要点。", "folder_id": fid,
        })
        d = r.json()
        check("doc create", d.get("code") == 0, r.text[:120])
        did = d["data"]["id"]

        # 12. 更新文档 -> 版本 +1 + tags
        r = client.patch(f"/api/v1/documents/{did}", json={"content": "更新后的内容，包含更多文字。", "tags": ["架构", "测试"]})
        d = r.json()
        check("doc update version2", d.get("code") == 0 and d["data"]["version"] == 2 and d["data"]["tags"] == ["架构", "测试"], r.text[:120])

        # 13. 版本历史
        r = client.get(f"/api/v1/documents/{did}/versions")
        d = r.json()
        check("doc versions", d.get("code") == 0 and len(d["data"]) >= 1, str(d))

        # 14. 标签
        r = client.get("/api/v1/tags")
        d = r.json()
        check("tags", d.get("code") == 0 and len(d["data"]) >= 1, str(d))

        # 15. 搜索
        r = client.get("/api/v1/search", params={"q": "测试"})
        d = r.json()
        check("search", d.get("code") == 0 and len(d["data"]["documents"]) >= 1, str(d))

        # 16. 复盘 upsert / get / auto-fill
        today = date.today().isoformat()
        r = client.put("/api/v1/reviews", json={
            "type": "daily", "date": today,
            "data": {"completed_tasks": "完成A", "gains": "收获X", "mood": 4, "energy": 3,
                     "reflections": [{"question": "今天怎么样？", "answer": "不错"}]},
        })
        d = r.json()
        check("review upsert", d.get("code") == 0, r.text[:120])
        rid = d["data"]["id"]
        r = client.get(f"/api/v1/reviews/{today}", params={"type": "daily"})
        check("review get", r.json()["data"]["id"] == rid, r.text[:120])
        r = client.get(f"/api/v1/reviews/{today}/auto-fill")
        check("review auto-fill", r.json().get("code") == 0 and "stats" in r.json()["data"], r.text[:120])

        # 17. 仪表盘
        r = client.get("/api/v1/dashboard")
        d = r.json()
        check("dashboard", d.get("code") == 0 and d["data"]["focus_task"] is not None and "user" in d["data"], str(d)[:120])

        # 18. 数据统计
        r = client.get("/api/v1/data/stats")
        d = r.json()
        check("data stats", d.get("code") == 0 and d["data"]["documents"] >= 1, str(d))

        # 19. 会话 + SSE 流式
        r = client.post("/api/v1/conversations", json={"title": "冒烟会话"})
        cid = r.json()["data"]["id"]
        sse_types: list[str] = []
        with client.stream("POST", f"/api/v1/conversations/{cid}/messages", json={"content": "你好"}) as res:
            check("SSE status", res.status_code == 200, str(res.status_code))
            for line in res.iter_lines():
                if line.startswith("data: "):
                    ev = json.loads(line[6:])
                    sse_types.append(ev["type"])
        check("SSE has content+done", "content" in sse_types and "done" in sse_types, str(sse_types))
        r = client.get(f"/api/v1/conversations/{cid}/messages")
        d = r.json()
        check("messages saved", d.get("code") == 0 and len(d["data"]) >= 2, str(d))

        # 20. AI 摘要（未配 Key → mock 秒回）
        r = client.post("/api/v1/ai/summarize", json={"document_id": did})
        check("ai summarize", r.status_code == 200 and r.json().get("code") == 0, r.text[:120])

        # 21. 备份导出
        r = client.post("/api/v1/backup/export")
        d = r.json()
        check("backup export", d.get("code") == 0 and os.path.exists(d["data"]["path"]), str(d))

    print(f"\n冒烟结果: {passed} 通过, {failed} 失败")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
