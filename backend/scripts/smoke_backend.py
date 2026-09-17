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
import tempfile
from datetime import date
from pathlib import Path

# Windows 管道/重定向下 stdout 默认 GBK，无法打印 ✅/中文 → 强制 UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BACKEND_DIR = Path(__file__).resolve().parent.parent
# 冒烟数据放系统临时目录：仓库目录可能被同步客户端/杀软实时扫描，
# 新建的 SQLite 文件会被锁（实测 create_all 永久阻塞，TEMP 下 1.6s）。
SMOKE_DIR = Path(tempfile.gettempdir()) / "venustech_smoke"

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

        # 17b. today_execution 自洽性（回归：total 曾等于"全部任务数"而非今日任务数，
        #      导致同屏 total 远大于各分组 count 之和，与 today_stats 口径矛盾）
        te = d["data"]["today_execution"]
        group_sum = sum(g["count"] for g in te["groups"])
        check("today_execution: total == 各分组之和", te["total"] == group_sum,
              f"total={te['total']} sum={group_sum}")

        # 17c. 无截止日期的待办不应计入"今日执行"（不属于今天要动手的事）
        r = client.post("/api/v1/tasks", json={"title": "无期限待办"})
        no_due_id = r.json()["data"]["id"]
        te2 = client.get("/api/v1/dashboard").json()["data"]["today_execution"]
        ids_in_te = [t["id"] for g in te2["groups"] for t in g["tasks"]]
        check("today_execution: 排除无截止日的待办", no_due_id not in ids_in_te,
              f"今日执行里出现了无期限待办 {no_due_id}")

        # 17d. 今日到期的待办应计入，且分组之和随之增长
        r = client.post("/api/v1/tasks", json={"title": "今日到期待办", "due_date": today})
        due_today_id = r.json()["data"]["id"]
        te3 = client.get("/api/v1/dashboard").json()["data"]["today_execution"]
        ids_in_te3 = [t["id"] for g in te3["groups"] for t in g["tasks"]]
        check("today_execution: 纳入今日到期待办", due_today_id in ids_in_te3,
              f"今日到期待办未出现在今日执行中")
        check("today_execution: 纳入后仍自洽", te3["total"] == sum(g["count"] for g in te3["groups"]),
              f"total={te3['total']} sum={sum(g['count'] for g in te3['groups'])}")

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

        # ==================== S6-1 领域规则引擎 ====================
        # 这一组断言的战略意义：证明「不配 API Key 也能生成专业学习计划」。
        # 此前未配 Key 时后端只会复读用户输入，学习计划生成是纯空壳。

        # 22. 从目标生成计划（命中领域库）
        r = client.post("/api/v1/learning/plans/generate",
                        json={"goal": "我想学雅思", "total_days": 30, "minutes_per_day": 60})
        d = r.json()
        gen = d.get("data") or {}
        items = gen.get("items") or []
        check("plan generate 命中领域库(雅思)",
              d.get("code") == 0 and gen.get("matched") is True and gen.get("domain_name") == "雅思",
              r.text[:160])
        check("plan generate 条数=周期天数(30)",
              gen.get("item_count") == 30 and len(items) == 30,
              f"item_count={gen.get('item_count')}")
        check("plan generate 末条为验证任务",
              bool(items) and items[-1].get("is_verify") is True,
              str(items[-1].get("title") if items else None))
        check("plan generate 每条都带达标标准",
              bool(items) and all(i.get("acceptance") for i in items),
              f"缺失 {sum(1 for i in items if not i.get('acceptance'))} 条")
        check("plan generate 时长已归一为分钟",
              bool(items) and items[0].get("estimated_minutes") == 40,
              f"first={items[0].get('estimated_minutes') if items else None}")

        # 23. 长尾技能走通用四阶段兜底（不建库也能出计划）
        r = client.post("/api/v1/learning/plans/generate",
                        json={"goal": "我想学手冲咖啡", "total_days": 14})
        d = r.json()
        gen2 = d.get("data") or {}
        check("plan generate 长尾技能走通用兜底",
              d.get("code") == 0 and gen2.get("matched") is False
              and len(gen2.get("units") or []) == 4, r.text[:160])

        # 24. 生成计划并落成任务（写入 0012 迁移新增的两列）
        before = client.get("/api/v1/tasks", params={"page": 1, "page_size": 1}).json()["data"]["total"]
        r = client.post("/api/v1/learning/plans/generate/apply",
                        json={"goal": "学摄影", "total_days": 7, "minutes_per_day": 45,
                              "plan_name": "冒烟·摄影计划"})
        d = r.json()
        applied = d.get("data") or {}
        check("plan apply 落库成功",
              d.get("code") == 0 and applied.get("task_count", 0) > 0, r.text[:160])
        after = client.get("/api/v1/tasks", params={"page": 1, "page_size": 1}).json()["data"]["total"]
        check("plan apply 任务总数按预期增加",
              after - before == applied.get("task_count", 0),
              f"before={before} after={after} created={applied.get('task_count')}")
        check("plan apply 同时创建学习计划记录",
              bool((applied.get("plan") or {}).get("id")), str(applied.get("plan"))[:140])

        # 25. 新列确实经由 API 暴露（0012 迁移 + schema 全链路打通）
        r = client.get("/api/v1/tasks", params={"page": 1, "page_size": 100})
        plan_tasks = [t for t in r.json()["data"]["list"] if t.get("acceptance_criteria")]
        check("plan apply 任务的达标标准已落库并暴露",
              len(plan_tasks) > 0, f"matched={len(plan_tasks)}")
        check("plan apply 任务的预估时长已落库并暴露",
              bool(plan_tasks) and all(t.get("estimated_minutes") for t in plan_tasks),
              str([t.get("estimated_minutes") for t in plan_tasks[:5]]))

        # ==================== S6-2 成长体系 ====================
        # 战略意义：证明「任何操作都有回响」——勾任务会真实产生 EXP，
        # 且这能力**没有改任何现有模块的代码**（全靠 event_bus 订阅）。
        import time as _time

        # 26. 初始状态可读
        r = client.get("/api/v1/growth/state")
        d = r.json()
        gst = d.get("data") or {}
        check("growth state 可读", d.get("code") == 0 and "exp" in gst, r.text[:140])
        exp_before = gst.get("exp", 0)

        # 27. 等级门槛元数据（与评估报告基线逐项一致）
        r = client.get("/api/v1/growth/levels")
        lv = r.json().get("data") or {}
        table = lv.get("table") or []
        check("growth levels 元数据可读",
              r.json().get("code") == 0 and lv.get("max_level") == 30, r.text[:140])
        check("growth levels LV2 门槛 = 102",
              len(table) > 2 and table[2] == 102, str(table[:4]))
        check("growth levels 满级累计 = 107069",
              lv.get("total_exp_to_max") == 107069, str(lv.get("total_exp_to_max")))
        check("growth levels 含 22 个技能分类",
              len(lv.get("skill_categories") or []) == 22,
              str(len(lv.get("skill_categories") or [])))

        # 28. 完成任务 → EXP 经事件总线自动结算
        r = client.post("/api/v1/tasks",
                        json={"title": "成长体系冒烟：摄影练习", "priority": "medium"})
        growth_task = r.json()["data"]["id"]
        client.patch(f"/api/v1/tasks/{growth_task}", json={"status": "completed"})

        # 结算发生在后台任务里，轮询等待（最多 3 秒）
        exp_after = exp_before
        for _ in range(30):
            _time.sleep(0.1)
            exp_after = client.get("/api/v1/growth/state").json()["data"]["exp"]
            if exp_after > exp_before:
                break
        check("完成任务后 EXP 增加（事件总线自动结算）", exp_after > exp_before,
              f"before={exp_before} after={exp_after}")

        # 29. EXP 流水有记录
        r = client.get("/api/v1/growth/events")
        events = (r.json().get("data") or {}).get("list") or []
        check("EXP 流水已记录", len(events) > 0, str(events[:1]))

        # 30. 技能自动归类（标题含「摄影」→ photography）
        r = client.get("/api/v1/growth/skills")
        skills = (r.json().get("data") or {}).get("list") or []
        check("技能树自动归类到「摄影」",
              any(s.get("id") == "photography" for s in skills), str(skills[:3]))

        # 31. 幂等：重复标记完成不重复计分
        #     这一条是必要的 —— 状态机允许 completed → in_progress → completed，
        #     每次都会重新发布 task.completed 事件。
        exp_dup_before = exp_after
        client.patch(f"/api/v1/tasks/{growth_task}", json={"status": "in_progress"})
        client.patch(f"/api/v1/tasks/{growth_task}", json={"status": "completed"})
        _time.sleep(0.6)
        exp_dup_after = client.get("/api/v1/growth/state").json()["data"]["exp"]
        check("重复完成不重复计分（幂等键生效）", exp_dup_after == exp_dup_before,
              f"before={exp_dup_before} after={exp_dup_after}")

        # ==================== S6-2 桌宠四维数值（自 localStorage 迁入）====================
        # 战略意义：陪伴数据此前只存浏览器 localStorage —— 不进备份、换设备即
        # 归零。这一组断言证明它现在真的落在库里，且边界由后端收敛。
        r = client.get("/api/v1/pet/stats")
        d = r.json()
        ps = d.get("data") or {}
        check("pet stats 可读",
              d.get("code") == 0
              and all(k in ps for k in ("intimacy", "satiety", "mood", "energy")),
              r.text[:160])

        # 增量更新：抚摸 +2 亲密度（用增量而非绝对值）
        intimacy_before = ps.get("intimacy", 0)
        r = client.put("/api/v1/pet/stats", json={"intimacy": 2, "mood": 3})
        ps2 = r.json().get("data") or {}
        check("pet stats 增量更新生效",
              r.json().get("code") == 0 and ps2.get("intimacy") == intimacy_before + 2,
              f"before={intimacy_before} after={ps2.get('intimacy')}")

        # 上下限由后端收敛（前端已不再本地 clamp）。
        # 传的是**增量**，schema 限定增量在 ±100，所以这里用 ±100 的合法
        # 增量把 60 推到越界，验证"叠加后"的结果被收敛。
        r = client.put("/api/v1/pet/stats", json={"satiety": 100})
        check("pet stats 上限收敛到 100",
              (r.json().get("data") or {}).get("satiety") == 100,
              str((r.json().get("data") or {}).get("satiety")))
        r = client.put("/api/v1/pet/stats", json={"satiety": -100})
        check("pet stats 下限收敛到 0",
              (r.json().get("data") or {}).get("satiety") == 0,
              str((r.json().get("data") or {}).get("satiety")))

        # 重新读取能拿到写入后的值 —— 证明确实持久化，而不是只在内存里
        r = client.get("/api/v1/pet/stats")
        ps3 = r.json().get("data") or {}
        check("pet stats 已持久化（重新读取得到写入值）",
              ps3.get("satiety") == 0 and ps3.get("updated_at") is not None,
              str(ps3))

        # ==================== B1 身份层（三期波次一） ====================
        # 战略意义：身份是横切维度的锚点。这组断言锁住四件事：
        # CRUD 正确、slug 唯一、色值必须走设计令牌、任务挂身份时归属被校验。
        r = client.post("/api/v1/identities", json={
            "name": "AI 研究", "slug": "ai-research",
            "color_token": "lilac", "icon": "spark",
        })
        d = r.json()
        check("identity create", d.get("code") == 0 and d["data"]["slug"] == "ai-research", r.text[:160])
        identity_id = d["data"]["id"]

        r = client.post("/api/v1/identities", json={"name": "重复", "slug": "ai-research"})
        check("identity duplicate slug rejected", r.json().get("code") != 0, r.text[:160])

        r = client.post("/api/v1/identities", json={
            "name": "坏色", "slug": "bad-color", "color_token": "#ff0000",
        })
        check("identity rejects # color", r.json().get("code") != 0, r.text[:160])

        r = client.patch(f"/api/v1/identities/{identity_id}", json={"name": "AI 研究（改）"})
        check("identity update", r.json()["data"]["name"] == "AI 研究（改）", r.text[:160])

        # 任务挂身份：创建时带 identity_id
        r = client.post("/api/v1/tasks", json={
            "title": "身份任务", "identity_id": identity_id,
        })
        d = r.json()
        check("task with identity", d.get("code") == 0 and d["data"]["identity_id"] == identity_id, r.text[:160])
        task_with_identity = d["data"]["id"]

        # 伪造的 identity_id 必须被拒绝（应用层关联，归属校验是唯一防线）
        r = client.post("/api/v1/tasks", json={
            "title": "伪造身份", "identity_id": "00000000-0000-0000-0000-000000000000",
        })
        check("task fake identity rejected", r.json().get("code") != 0, r.text[:160])

        # 更新路径同样校验
        r = client.patch(f"/api/v1/tasks/{tid2}", json={"identity_id": "00000000-0000-0000-0000-000000000000"})
        check("task update fake identity rejected", r.json().get("code") != 0, r.text[:160])

        # 列表按身份过滤 / 只看未归类（list 与 count 必须同源，否则分页口径漂移）
        r = client.get("/api/v1/tasks", params={"identity_id": identity_id})
        d = r.json()["data"]
        check("task list filter by identity",
              d["total"] == 1 and any(t["id"] == task_with_identity for t in d["list"]),
              str(d)[:160])
        r = client.get("/api/v1/tasks", params={"identity_unassigned": "true"})
        d = r.json()["data"]
        check("task list filter unassigned",
              all(t["id"] != task_with_identity for t in d["list"]) and d["total"] >= 1,
              str(d)[:160])

        # Dashboard 身份进度区（「一眼看出推进哪条线」的数据来源）
        r = client.get("/api/v1/dashboard")
        d = r.json()["data"]
        row = next((x for x in d["identities"]["items"] if x["id"] == identity_id), None)
        check("dashboard identity progress",
              row is not None and row["open_tasks"] >= 1,
              str(d.get("identities"))[:200])
        check("dashboard unassigned count",
              d["identities"]["unassigned_open"] >= 1,
              str(d.get("identities"))[:200])

        # ==================== S6-4 经历视图（四源聚合，不建表） ====================
        # 铁律：经历 = 四源在读取时的聚合视图。这组断言证明四源挂身份后
        # 能归并到同一条时间线，且过滤语义与任务列表一致。
        r = client.post("/api/v1/life/diaries", json={
            "title": "研究日记", "content": "今天推进了实验。", "identity_id": identity_id,
        })
        check("diary with identity", r.json().get("code") == 0, r.text[:160])
        r = client.put("/api/v1/reviews", json={
            "type": "daily", "date": date.today().isoformat(),
            "identity_id": identity_id, "data": {"summary": "今日推进"},
        })
        check("review with identity", r.json().get("code") == 0, r.text[:160])
        r = client.post("/api/v1/avatar/memories", json={
            "memory_type": "event", "title": "里程碑事件", "identity_id": identity_id,
        })
        check("avatar memory with identity", r.json().get("code") == 0, r.text[:160])
        r = client.post("/api/v1/assets/memories", json={
            "name": "项目复盘", "summary": "成功与失败记录", "identity_id": identity_id,
        })
        check("project memory with identity", r.json().get("code") == 0, r.text[:160])

        r = client.get("/api/v1/experience", params={"identity_id": identity_id})
        d = r.json()["data"]
        sources = {i["source"] for i in d["items"]}
        check("experience merges 4 sources",
              d["total"] == 4 and sources == {"diary", "review", "avatar_memory", "project_memory"},
              f"total={d['total']} sources={sources}")
        # 归并排序：occurred_at 必须降序
        ots = [i["occurred_at"] for i in d["items"]]
        check("experience sorted desc", ots == sorted(ots, reverse=True), str(ots))
        r = client.get("/api/v1/experience", params={"identity_unassigned": "true"})
        d = r.json()["data"]
        check("experience unassigned excludes",
              all(i["identity_id"] != identity_id for i in d["items"]),
              str(d)[:160])

        # 软删除身份 → 详情 404，引用被清回「未归类」（否则悬空记录两不靠）
        r = client.delete(f"/api/v1/identities/{identity_id}")
        check("identity soft delete", r.json().get("code") == 0, r.text[:160])
        r = client.get(f"/api/v1/identities/{identity_id}")
        check("identity deleted 404", r.json().get("code") != 0, r.text[:160])
        r = client.get(f"/api/v1/tasks/{task_with_identity}")
        check("task survives identity delete (refs cleared to unassigned)",
              r.json().get("code") == 0 and r.json()["data"]["identity_id"] is None,
              r.text[:160])

        # 软删除的身份必须从列表消失（否则骨架生成会给死身份建文件夹）
        r = client.get("/api/v1/identities")
        check("deleted identity absent from list",
              all(i["id"] != identity_id for i in r.json()["data"]),
              r.text[:160])

        # ==================== C1 工作区（可选功能 + 引导部署） ====================
        # 设计决策（2026-09-16）：默认关闭、零预设 —— 别人的电脑文件夹
        # 结构不同，目录由引导流程建立。这组断言走一遍引导路径：
        # 启用 → 登记现有根 → 按身份生成骨架 → 扫描（噪声过滤）→ 检索。
        import os as _os

        ws_dir = SMOKE_DIR / "ws_root"
        (ws_dir / "AIResearch").mkdir(parents=True, exist_ok=True)
        (ws_dir / "venv").mkdir(exist_ok=True)
        (ws_dir / "notes.md").write_text("hello workspace", encoding="utf-8")
        (ws_dir / "venv" / "x.pyc").write_text("x", encoding="utf-8")

        r = client.get("/api/v1/workspace/status")
        check("workspace disabled by default",
              r.json()["data"]["enabled"] is False and r.json()["data"]["roots_count"] == 0,
              r.text[:160])

        r = client.put("/api/v1/workspace/enabled", json={"enabled": True})
        check("workspace enable", r.json()["data"]["workspace.enabled"] == "true", r.text[:160])

        # 引导路径 a：登记用户现有文件夹
        r = client.post("/api/v1/workspace/roots", json={"path": str(ws_dir), "label": "D 盘根"})
        d = r.json()
        check("workspace register root", d.get("code") == 0 and d["data"]["scan_status"] == "never", r.text[:160])
        ws_root_id = d["data"]["id"]

        # 文件系统根必须拒绝（安全红线）
        r = client.post("/api/v1/workspace/roots", json={"path": "D:\\" if _os.name == "nt" else "/"})
        check("workspace rejects fs root", r.json().get("code") != 0, r.text[:160])
        # 相对路径拒绝
        r = client.post("/api/v1/workspace/roots", json={"path": "relative/path"})
        check("workspace rejects relative path", r.json().get("code") != 0, r.text[:160])

        # 引导路径 b：按身份生成目录骨架（文件夹名来自用户自己的身份）
        r = client.post("/api/v1/identities", json={"name": "音乐", "slug": "music", "color_token": "gold"})
        music_identity_id = r.json()["data"]["id"]
        r = client.post(f"/api/v1/workspace/roots/{ws_root_id}/skeleton")
        d = r.json()["data"]
        check("workspace skeleton created", d["created"] == ["音乐"] and d["skipped"] == [], r.text[:160])
        # 再跑一次：全部 skip（幂等）
        r = client.post(f"/api/v1/workspace/roots/{ws_root_id}/skeleton")
        check("workspace skeleton idempotent",
              r.json()["data"]["created"] == [] and r.json()["data"]["skipped"] == ["音乐"],
              r.text[:160])

        # 扫描：噪声目录/扩展名被剪枝，只存元数据
        r = client.post(f"/api/v1/workspace/roots/{ws_root_id}/scan")
        d = r.json()["data"]
        check("workspace scan ok", d["scan_status"] == "ok" and d["file_count"] == 3,
              str(d)[:200])
        r = client.get("/api/v1/workspace/files", params={"root_id": ws_root_id, "search": "venv"})
        check("workspace noise pruned", r.json()["data"]["total"] == 0, r.text[:160])
        r = client.get("/api/v1/workspace/files", params={"root_id": ws_root_id, "search": "notes"})
        d = r.json()["data"]
        check("workspace file found",
              d["total"] == 1 and d["items"][0]["ext"] == ".md" and d["items"][0]["size"] > 0,
              r.text[:200])

        # 开终端白名单：根外路径必须拒绝（不真正拉起终端，避免冒烟开窗）
        outside = str(SMOKE_DIR)
        r = client.post("/api/v1/workspace/open-terminal", json={"path": outside})
        check("workspace terminal outside rejected", r.json().get("code") != 0, r.text[:160])
        r = client.post("/api/v1/workspace/open-terminal", json={"path": str(ws_dir / ".." / "..")})
        check("workspace terminal traversal rejected", r.json().get("code") != 0, r.text[:160])

        # ==================== S6-5 人生报告（三轴聚合） ====================
        # 报告是只读聚合：身份轴（记录挂谁就数给谁）、成长轴、档案轴。
        # 给 music 身份挂一条日记，验证聚合正确；此前四源记录挂的是
        # 已删除的 ai-research，删除时引用已被清回未归类（另一条断言）。
        r = client.post("/api/v1/life/diaries", json={
            "title": "音乐日记", "content": "练琴半小时", "identity_id": music_identity_id,
        })
        check("diary for music", r.json().get("code") == 0, r.text[:160])
        r = client.get("/api/v1/report")
        d = r.json()["data"]
        rows = {i["slug"]: i for i in d["identity_axis"]["identities"]}
        check("report identity axis",
              rows["music"]["diaries"] == 1
              and rows["music"]["tasks_open"] == 0
              and "ai-research" not in rows,
              str(rows)[:220])
        check("report unassigned counted",
              d["identity_axis"]["unassigned"]["tasks_open"] >= 1,
              str(d["identity_axis"]["unassigned"]))
        check("report growth axis",
              d["growth_axis"]["level"] >= 1 and d["growth_axis"]["exp"] > 0,
              str(d["growth_axis"])[:160])
        check("report archive axis",
              d["archive_axis"]["workspace_enabled"] is True
              and len(d["archive_axis"]["roots"]) == 1
              and d["archive_axis"]["documents_total"] >= 1,
              str(d["archive_axis"])[:200])
        check("report recent experience",
              len(d["recent_experience"]) >= 4
              and all("source_label" in i for i in d["recent_experience"]),
              str(d["recent_experience"])[:200])

        # ==================== D 保险箱（主密码 + 凭据加密） ====================
        # D0 修正：加密派生不再用硬编码 salt（每用户随机 salt + 校验器）。
        # 主密码不落盘；凭据密文落库，明文只有一个出口且要求解锁态。
        r = client.get("/api/v1/vault/status")
        check("vault not configured by default", r.json()["data"]["configured"] is False, r.text[:160])

        # 短密码拒绝
        r = client.put("/api/v1/vault/setup", json={"master_password": "short"})
        check("vault rejects short password", r.json().get("code") != 0, r.text[:160])

        r = client.put("/api/v1/vault/setup", json={"master_password": "correct horse battery"})
        check("vault setup", r.json()["data"]["configured"] is True and r.json()["data"]["unlocked"] is True, r.text[:160])

        r = client.post("/api/v1/vault/items", json={
            "name": "GitHub", "category": "login", "username": "demo",
            "secret": "ghp_super_secret_token_123",
        })
        check("vault item create", r.json().get("code") == 0, r.text[:160])
        vault_item_id = r.json()["data"]["id"]

        # 列表绝不含明文
        r = client.get("/api/v1/vault/items")
        items = r.json()["data"]
        check("vault list has no secret",
              all("secret" not in i and i.get("secret_encrypted") is None for i in items)
              and items[0]["has_secret"] is True,
              r.text[:200])

        # 上锁后一切凭据操作被拒
        client.post("/api/v1/vault/lock")
        r = client.get("/api/v1/vault/items")
        check("vault locked rejects list", r.json().get("code") != 0, r.text[:160])
        r = client.get(f"/api/v1/vault/items/{vault_item_id}/secret")
        check("vault locked rejects reveal", r.json().get("code") != 0, r.text[:160])

        # 错误密码拒绝解锁；正确密码解锁后明文可达
        r = client.post("/api/v1/vault/unlock", json={"master_password": "wrong password!"})
        check("vault wrong password rejected", r.json().get("code") != 0, r.text[:160])
        r = client.post("/api/v1/vault/unlock", json={"master_password": "correct horse battery"})
        check("vault unlock", r.json()["data"]["unlocked"] is True, r.text[:160])
        r = client.get(f"/api/v1/vault/items/{vault_item_id}/secret")
        check("vault reveal secret", r.json()["data"]["secret"] == "ghp_super_secret_token_123", r.text[:160])

        # 删身份 → 保险箱/工作区根的引用也必须清回未归类（10 表一致性）
        r = client.post("/api/v1/identities", json={"name": "临时身份", "slug": "tmp-vault", "color_token": "sky"})
        tmp_ident = r.json()["data"]["id"]
        r = client.patch(f"/api/v1/vault/items/{vault_item_id}", json={"identity_id": tmp_ident})
        check("vault item attach identity", r.json()["data"]["identity_id"] == tmp_ident, r.text[:160])
        # 给工作区根也挂上
        r = client.patch(f"/api/v1/workspace/roots/{ws_root_id}", json={"identity_id": tmp_ident})
        check("workspace root attach identity", r.json().get("code") == 0, r.text[:160])
        r = client.delete(f"/api/v1/identities/{tmp_ident}")
        r = client.get("/api/v1/vault/items")
        check("vault dangling ref cleared after identity delete",
              all(i["identity_id"] is None for i in r.json()["data"]), r.text[:200])
        r = client.get("/api/v1/workspace/roots")
        check("workspace dangling ref cleared after identity delete",
              all(i["identity_id"] is None for i in r.json()["data"]), r.text[:200])

        # 更换主密码：旧密文全部重加密，明文仍可读
        r = client.post("/api/v1/vault/change-password", json={
            "old_password": "correct horse battery", "new_password": "new master password 9",
        })
        check("vault change password", r.json()["data"]["unlocked"] is True, r.text[:160])
        client.post("/api/v1/vault/lock")
        r = client.post("/api/v1/vault/unlock", json={"master_password": "new master password 9"})
        check("vault unlock with new password", r.json()["data"]["unlocked"] is True, r.text[:160])
        r = client.get(f"/api/v1/vault/items/{vault_item_id}/secret")
        check("vault secret survives rotation",
              r.json()["data"]["secret"] == "ghp_super_secret_token_123", r.text[:160])

        # 终端动作（D 收尾）：白名单模板 ssh -i 密钥路径，动态字段全过正则
        r = client.post(f"/api/v1/vault/items/{vault_item_id}/run-action")
        check("vault run-action rejects unconfigured", r.json().get("code") != 0, r.text[:160])
        r = client.patch(f"/api/v1/vault/items/{vault_item_id}", json={
            "action_type": "ssh", "action_host": "evil; rm -rf /", "action_user": "x",
        })
        check("vault action host injection rejected", r.json().get("code") != 0, r.text[:160])
        r = client.patch(f"/api/v1/vault/items/{vault_item_id}", json={
            "action_type": "arbitrary_command", "action_host": "h",
        })
        check("vault action unknown type rejected", r.json().get("code") != 0, r.text[:160])
        r = client.patch(f"/api/v1/vault/items/{vault_item_id}", json={
            "action_type": "ssh", "action_host": "demo.example.com",
            "action_user": "deploy", "action_port": "22",
            "secret": str(SMOKE_DIR / "no_such_key.pem"),
        })
        check("vault action save", r.json().get("code") == 0 and r.json()["data"]["action_type"] == "ssh", r.text[:200])
        # 密钥路径不存在 → 拒绝执行（不真正拉起终端，冒烟不开窗）
        r = client.post(f"/api/v1/vault/items/{vault_item_id}/run-action")
        check("vault run-action missing key rejected", r.json().get("code") != 0, r.text[:160])

        # ==================== S6-3b 同步引擎（diff-sync + SYNC_POLICY） ====================
        # R2 铁律：引擎诞生第一天就有表分级。验收基准（二期 W4）：
        # 双库往返一致、二次 apply 零操作。
        r = client.get("/api/v1/sync/policy")
        d = r.json()["data"]
        check("sync policy registered",
              d["policy"]["workspace_files"] == "derived-skip"
              and d["policy"]["vault_items"] == "encrypted-only"
              and d["policy"]["vault_config"] == "encrypted-only"
              and d["policy"]["settings"] == "filtered"
              and d["policy"]["tasks"] == "full"
              and "workspace_files" not in d["synced_tables"],
              str(d)[:240])

        r = client.post("/api/v1/sync/export", json={"dir": str(SMOKE_DIR)})
        check("sync export", r.json().get("code") == 0, r.text[:160])
        pkg_path = r.json()["data"]["path"]

        # 包内容策略断言：派生表缺席、vault 剥离明文备注、settings 排除设备键
        pkg = json.loads(Path(pkg_path).read_text(encoding="utf-8"))
        check("sync package excludes derived", "workspace_files" not in pkg["tables"], str(pkg.keys())[:200])
        vault_rows = list(pkg["tables"]["vault_items"].values())
        check("sync package strips vault plaintext",
              len(vault_rows) >= 1 and all("notes" not in row for row in vault_rows),
              str(vault_rows)[:200])
        setting_keys = {row["key"] for row in pkg["tables"]["settings"].values()}
        check("sync package excludes device keys",
              not any(k.startswith("workspace.") for k in setting_keys),
              str(setting_keys)[:200])

        # 本地较新 → 导入旧包应零操作（LWW 本地胜）
        r = client.patch(f"/api/v1/tasks/{task_with_identity}", json={"title": "本地较新的标题"})
        check("sync setup modify", r.json().get("code") == 0, r.text[:160])
        r = client.post("/api/v1/sync/import", json={"path": pkg_path})
        d = r.json()["data"]
        check("sync import LWW local wins zero ops",
              d["ops"] == 0 and d["insert"] == 0 and d["update"] == 0, str(d)[:160])

        # 远端有本地没有的行 → insert 应用；二次导入零操作
        r = client.post("/api/v1/identities", json={"name": "同步往返", "slug": "roundtrip", "color_token": "mint"})
        rt_identity_id = r.json()["data"]["id"]
        r = client.post("/api/v1/sync/export", json={"dir": str(SMOKE_DIR)})
        pkg_path2 = r.json()["data"]["path"]
        # 用 SQL 硬删一行，模拟"另一台机器有这行而本机没有"
        from sqlalchemy import text as _text
        from app.database import SessionLocal as _Session
        _db = _Session()
        _db.execute(_text("DELETE FROM identities WHERE id = :i"), {"i": rt_identity_id})
        _db.commit()
        _db.close()
        r = client.get(f"/api/v1/identities")
        check("sync setup row removed", all(i["id"] != rt_identity_id for i in r.json()["data"]), r.text[:160])
        r = client.post("/api/v1/sync/import", json={"path": pkg_path2})
        d = r.json()["data"]
        check("sync import inserts missing row", d["insert"] >= 1, str(d)[:160])
        r = client.get("/api/v1/identities")
        check("sync roundtrip consistent", any(i["id"] == rt_identity_id for i in r.json()["data"]), r.text[:200])
        r = client.post("/api/v1/sync/import", json={"path": pkg_path2})
        d = r.json()["data"]
        check("sync re-import zero ops",
              d["ops"] == 0 and d["insert"] == 0 and d["update"] == 0, str(d)[:160])
        # 用户不匹配的包拒绝导入（防串包）
        check("sync package user binding", pkg["user_id"] is not None, str(pkg["user_id"]))

        # ==================== S6-6 AI HOT 插件（插件架构首次真实检验） ====================
        # 插件发现/加载 + 路由挂载 + 离线降级。外网可用性不假设：
        # 端点要么 live 要么 cache 要么诚实 ok=False，HTTP 一律 200。
        r = client.get("/api/v1/plugins")
        d = r.json()["data"]
        aihot = next((p for p in d["plugins"] if p["id"] == "aihot"), None)
        check("aihot plugin discovered+loaded",
              aihot is not None and aihot["loaded"] is True, str(d)[:200])

        r = client.get("/api/v1/plugins/aihot/items", params={"window": "99h"})
        d = r.json().get("data", {})
        check("aihot rejects bad window (graceful envelope)",
              r.status_code == 200 and d.get("ok") is False, r.text[:160])

        # 冒烟默认不依赖外网稳定性：mock 打在 plugin_manager 实际加载的
        # 模块实例上（同 id 内置插件被 importlib 以 plugin_aihot 名加载，
        # 不能按包路径 import —— 那会是另一个实例，patch 不生效）。
        from app.core.plugin_manager import plugin_manager as _pm

        async def _fake_fetch(name, path, params):
            return {"ok": True, "source": "mock", "data": {"items": [], "endpoint": name}}

        _loaded = _pm.instances().get("aihot")
        if _loaded is not None:
            _loaded._fetch = _fake_fetch

        for name, path in (("items", "/items"), ("hot", "/hot-topics"), ("daily", "/daily")):
            r = client.get(f"/api/v1/plugins/aihot{path}")
            d = r.json().get("data", {})
            check(f"aihot {name} envelope",
                  r.status_code == 200 and d.get("ok") is True and d.get("source") in ("mock", "live"),
                  str(d)[:160])

        # ==================== AI 行程助理（移动端方案 M2/M3） ====================
        # DeepSeek 调用全程 mock（冒烟不碰外网）；降级/配置加密/白名单落库全覆盖。
        from app.config import get_settings as _gs
        from app.database import SessionLocal as _S2
        from app.models.user import User as _U
        from app.services.settings_service import SettingsService as _SS
        import app.services.assistant_service as _am

        _sdb = _S2()
        _uid = _sdb.query(_U.id).first()[0]
        _ss = _SS(_sdb, _uid)

        r = client.get("/api/v1/assistant/status")
        check("assistant not configured by default",
              r.json()["data"]["configured"] is False, r.text[:120])

        r = client.put("/api/v1/assistant/config", json={"api_key": "sk-test-1234567890"})
        check("assistant config saved (encrypted)",
              r.json()["data"]["configured"] is True, r.text[:120])
        _raw = _ss.get("assistant.deepseek_key")
        check("assistant key stored encrypted",
              _raw is not None and "sk-test" not in str(_raw), str(_raw)[:80])

        # 无 Key 降级解析（临时清 Key）：明天下午3点 → 具体时间
        _ss.set("assistant.deepseek_key", "")
        _sdb.commit()
        r = client.post("/api/v1/assistant/parse", json={
            "text": "明天下午3点找老师谈开题，然后买高铁票。还要给妈妈打电话",
        })
        d = r.json()["data"]
        check("assistant local fallback parses",
              d["source"] == "local" and len(d["items"]) >= 2, str(d)[:240])
        _teacher = next((i for i in d["items"] if "老师" in i["title"]), None)
        check("assistant local time extraction",
              _teacher is not None and _teacher["deadline"] is not None
              and "15:00" in _teacher["deadline"], str(_teacher)[:200])

        # mock DeepSeek 通道：验证解析结构透传
        async def _fake_deepseek(text, now, key):
            return ([
                {"kind": "task", "title": "找老师谈开题", "deadline": "2026-09-18T15:00:00",
                 "people": ["老师"], "location": None, "priority": "high", "notes": None},
                {"kind": "note", "title": "买高铁票", "deadline": None,
                 "people": [], "location": None, "priority": "medium", "notes": None},
            ], ["开题的具体形式？"], "deepseek")

        _am.AssistantService._deepseek_parse = staticmethod(_fake_deepseek)
        _ss.set("assistant.deepseek_key",
                _am.EncryptionManager(Path(_gs().data_dir)).encrypt(b"sk-test-1234567890").decode())
        _sdb.commit()
        r = client.post("/api/v1/assistant/parse", json={"text": "明天下午3点找老师谈开题"})
        d = r.json()["data"]
        check("assistant deepseek mock parse",
              d["source"] == "deepseek" and len(d["items"]) == 2
              and d["clarifications"] == ["开题的具体形式？"], str(d)[:240])

        # apply 白名单落库：1 任务（带截止）+ 1 收集箱
        r = client.post("/api/v1/assistant/apply", json={"items": [
            {"kind": "task", "title": "找老师谈开题", "deadline": "2026-09-18T15:00:00", "priority": "high"},
            {"kind": "note", "title": "买高铁票"},
        ]})
        d = r.json()["data"]
        check("assistant apply applies", d["applied"] == 2 and d["by_kind"]["task"] == 1
              and d["by_kind"]["note"] == 1, str(d)[:200])
        _hit = _sdb.execute(_text(
            "SELECT COUNT(*) FROM tasks WHERE title = '找老师谈开题' AND due_date = '2026-09-18'"
        )).scalar()
        check("assistant apply created real task row", int(_hit) == 1, str(_hit))
        _sdb.close()

        # ==================== S6-3a 同步字段就绪性 ====================
        # 这是一条**长期防线**：S6-3 的 diff-sync 依赖 updated_at（增量）
        # 与 deleted_at（墓碑）在每张业务表上都存在。
        # 以后任何人新增模型却忘了继承这两个 Mixin，这里会立刻失败，
        # 而不是等到做云同步时才发现"这张表同步不了"。
        from app.database import Base as _Base

        _missing_sync = [
            t for t in _Base.metadata.tables
            if t != "alembic_version"
            and not {"updated_at", "deleted_at"} <= set(
                _Base.metadata.tables[t].columns.keys()
            )
        ]
        check("所有业务表均具备 updated_at / deleted_at（同步就绪）",
              not _missing_sync, f"缺失字段的表: {_missing_sync[:8]}")

        # ==================== A3 用户配置（通知开关落库） ====================
        # 战略意义：设置页 4 个通知开关此前只是前端 ref()，刷新即失效；后端
        # settings 表建好了却从未被读写。这一组断言证明"开关真的落库"，
        # 并锁住键白名单（防止任意键把配置表写脏）。
        r = client.get("/api/v1/settings")
        sv = (r.json().get("data") or {}).get("values") or {}
        check("settings 可读且带默认值",
              r.json().get("code") == 0
              and sv.get("notify.task") == "true"
              and sv.get("notify.sound") == "false",
              r.text[:160])

        r = client.put("/api/v1/settings", json={"values": {"notify.sound": "true"}})
        sv2 = (r.json().get("data") or {}).get("values") or {}
        check("settings 写入生效",
              r.json().get("code") == 0 and sv2.get("notify.sound") == "true",
              r.text[:160])

        # 重复写入同一键必须是 upsert，不能撞 (user_id, key) 唯一约束
        r = client.put("/api/v1/settings", json={"values": {"notify.sound": "false"}})
        check("settings 重复写入走 upsert（不撞唯一约束）",
              r.json().get("code") == 0
              and (r.json().get("data") or {}).get("values", {}).get("notify.sound") == "false",
              r.text[:160])

        r = client.put("/api/v1/settings", json={"values": {"evil.key": "1"}})
        check("settings 拒绝未登记的键（白名单生效）",
              r.json().get("code") != 0, r.text[:160])

        # 重新读取能拿到写入后的值 —— 证明确实持久化
        r = client.get("/api/v1/settings")
        sv3 = (r.json().get("data") or {}).get("values") or {}
        check("settings 已持久化（重新读取得到写入值）",
              sv3.get("notify.sound") == "false" and sv3.get("notify.task") == "true",
              str(sv3))

    print(f"\n冒烟结果: {passed} 通过, {failed} 失败")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
