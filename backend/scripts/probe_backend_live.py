# -*- coding: utf-8 -*-
"""启明星后端 · 真机端到端探针（LIVE：打真实 uvicorn 服务 + 真实 SQLite 库）

与另外两个入口的分工：
  · tests/            —— pytest，进程内 TestClient（快，覆盖广）
  · scripts/smoke_backend.py —— TestClient 端到端（不启服务）
  · 本脚本            —— **真的起一个服务、发真的 HTTP、落真的库文件**
    它守的是「用户路径」：迁移能不能从 0001 一路走到最新、种子灌没灌、
    接口在真实网络栈上是否真的可用。前两者都做不到这一点。

为什么需要它（2026-10-11 立项）：
  项目铁律「完成 = 双击 → 服务真的起来 → 关键接口非空」，而仅靠
  TestClient 的冒烟测试，历史上出现过「全绿但用户打不开」。本脚本用
  独立临时数据目录起全新库，把「全新安装 → 全部迁移 → 种子 → 接口」
  这条最容易翻车的路径整条走一遍。

用法（必须先起服务；务必用临时数据目录，别拿真实库跑 —— 里面有
「全新库 configured=False」「重复 setup 被拒绝」这类只对空库成立的断言）：

    # 终端 1：起服务（指向临时目录，绝不碰 backend/data/app.db）
    cd backend
    VENUSTECH_DATA_DIR="C:/Users/<你>/AppData/Local/Temp/venustech_probe" \
        .venv/Scripts/python.exe -m uvicorn app.main:app --port 8765

    # 终端 2：跑探针
    cd backend && .venv/Scripts/python.exe scripts/probe_backend_live.py

退出码 0 = 全部断言通过；1 = 有失败；2 = 服务未就绪。
可用环境变量 VENUSTECH_PROBE_BASE 覆盖服务地址（默认 127.0.0.1:8765）。
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta

BASE = os.environ.get("VENUSTECH_PROBE_BASE", "http://127.0.0.1:8765")
API = BASE + "/api/v1"
R: list[tuple[bool, str, str]] = []


def call(method: str, path: str, body=None, timeout: float = 20):
    """发一次请求，返回 (status_code, 解析后的 JSON)。传输失败返回 (None, {...})。"""
    url = API + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        try:
            return e.code, json.loads(raw)
        except Exception:  # noqa: BLE001
            return e.code, {"_raw": raw[:300]}
    except Exception as e:  # noqa: BLE001
        return None, {"_err": f"{type(e).__name__}: {e}"}


def D(resp):
    """取统一响应体 {code,message,data} 里的 data。"""
    _, p = resp
    if isinstance(p, dict) and "data" in p:
        return p["data"]
    return p


def check(name: str, cond, detail="") -> None:
    ok = bool(cond)
    R.append((ok, name, str(detail)))
    print(("  [PASS] " if ok else "  [FAIL] ") + name + (f"   <{detail}>" if detail else ""))


def section(title: str) -> None:
    print("\n" + "=" * 64)
    print("  " + title)
    print("=" * 64)


def pick_list(d):
    """兼容 {list:[...]} / {items:[...]} / 裸数组 三种列表返回形态。"""
    if isinstance(d, list):
        return d
    if isinstance(d, dict):
        for k in ("list", "items"):
            if isinstance(d.get(k), list):
                return d[k]
    return []


def wait_ready(max_wait: float = 120.0):
    t0 = time.time()
    while time.time() - t0 < max_wait:
        c, _ = call("GET", "/health", timeout=3)
        if c == 200:
            return time.time() - t0
        time.sleep(1)
    return None


def main() -> int:
    print("启明星后端 · 真机端到端探针（LIVE）")
    print("目标:", BASE)

    elapsed = wait_ready()
    if elapsed is None:
        print("!! 服务 120s 内未就绪，探针中止（请先按文件头说明起服务）")
        return 2
    print(f"[就绪] 服务响应耗时 {elapsed:.1f}s")

    # ---------------------------------------------------------------- 1
    section("1. 基础设施 / 全新库启动链路")
    c, p = call("GET", "/health")
    check("GET /health 返回 200", c == 200, f"HTTP {c}")
    d = D((c, p))
    check("health.status == ok", isinstance(d, dict) and d.get("status") == "ok",
          f"status={d.get('status') if isinstance(d, dict) else d}")

    c, p = call("GET", "/health/detailed")
    d = D((c, p))
    db = d.get("database", {}) if isinstance(d, dict) else {}
    check("GET /health/detailed 返回 200", c == 200, f"HTTP {c}")
    check("数据库连接 connected=True", db.get("connected") is True, f"connected={db.get('connected')}")
    check("库文件大小 > 0 MB（证明真建库并落盘）", (db.get("size_mb") or 0) > 0,
          f"size_mb={db.get('size_mb')}")

    c, p = call("GET", "/system/info")
    check("GET /system/info 返回 200", c == 200, f"HTTP {c}")

    # ---------------------------------------------------------------- 2
    section("2. 左侧面板 / 快速待办 / 提醒")
    c, p = call("GET", "/panel")
    d = D((c, p))
    check("GET /panel 返回 200", c == 200, f"HTTP {c}")
    check("面板含 greeting/stats/quick_todos/reminders",
          isinstance(d, dict) and all(k in d for k in ("greeting", "stats", "quick_todos", "reminders")),
          ("keys=" + ",".join(d.keys())) if isinstance(d, dict) else "")

    c, p = call("POST", "/quick-todos", {"title": "真机探针待办"})
    d = D((c, p))
    todo_id = d.get("id") if isinstance(d, dict) else None
    check("POST /quick-todos 创建成功", c == 200 and todo_id, f"HTTP {c} id={todo_id}")

    if todo_id:
        c, p = call("PATCH", f"/quick-todos/{todo_id}", {"completed": True})
        d = D((c, p))
        check("PATCH completed=true 生效",
              c == 200 and isinstance(d, dict) and d.get("completed") is True, f"HTTP {c}")

        # 回归 2026-10-11：显式 null 写 NOT NULL 列，修复前未捕获 → 500
        c, p = call("PATCH", f"/quick-todos/{todo_id}", {"title": None})
        check("【缺陷回归】PATCH title=null → 400（修复前 500 NOT NULL）", c == 400, f"HTTP {c}")

        c, p = call("DELETE", f"/quick-todos/{todo_id}")
        check("DELETE /quick-todos/{id} 成功", c == 200, f"HTTP {c}")

    remind_at = (datetime.now() + timedelta(hours=2)).isoformat()
    c, p = call("POST", "/reminders", {"title": "探针提醒", "remind_at": remind_at, "type": "custom"})
    d = D((c, p))
    rid = d.get("id") if isinstance(d, dict) else None
    check("POST /reminders 创建成功（type=custom 合法）", c == 200 and rid, f"HTTP {c}")

    # 回归 2026-10-11：枚举只有注释、无校验 → 写错值不报错
    c, p = call("POST", "/reminders", {"title": "非法类型", "remind_at": remind_at, "type": "bogus"})
    check("【缺陷回归】非法 reminder.type → 400（白名单生效）", c == 400, f"HTTP {c}")

    c, p = call("POST", "/reminders", {"title": "非法重复", "remind_at": remind_at, "repeat": "hourly"})
    check("【缺陷回归】非法 reminder.repeat → 400（白名单生效）", c == 400, f"HTTP {c}")

    if rid:
        c, p = call("PATCH", f"/reminders/{rid}", {"dismissed": True})
        check("PATCH /reminders/{id} dismissed 生效", c == 200, f"HTTP {c}")

    # ---------------------------------------------------------------- 3
    section("3. 资源中心（content_type 白名单 / batch-process 契约）")
    c, p = call("POST", "/resource/inbox", {"content_type": "text", "title": "探针收集"})
    d = D((c, p))
    iid = d.get("id") if isinstance(d, dict) else None
    check("POST /resource/inbox（content_type=text）创建成功", c == 200 and iid, f"HTTP {c}")

    c, p = call("POST", "/resource/inbox", {"content_type": "link", "title": "链接条目"})
    d = D((c, p))
    iid2 = d.get("id") if isinstance(d, dict) else None
    check("content_type='link'（前端与演示种子实际取值）被接受", c == 200 and iid2, f"HTTP {c}")

    # 回归 2026-10-11：模型注释写 url、前端与种子用 link，无白名单 → 静默不匹配
    c, p = call("POST", "/resource/inbox", {"content_type": "url", "title": "旧注释里的错值"})
    check("【缺陷回归】content_type='url'（模型注释错值）→ 400", c == 400, f"HTTP {c}")

    ids = [x for x in (iid, iid2) if x]
    c, p = call("POST", "/resource/inbox/batch-process", {"item_ids": ids, "action": "archive"})
    d = D((c, p))
    check("【缺陷回归】batch-process 收 {item_ids, action} 对象体 → 200（修复前恒定 400）",
          c == 200, f"HTTP {c}")
    check("batch-process 返回计数",
          isinstance(d, dict) and (d.get("success") or 0) >= 1,
          json.dumps(d, ensure_ascii=False)[:100] if isinstance(d, dict) else str(d)[:100])

    c, p = call("GET", "/resource/inbox?status=archived")
    check("GET /resource/inbox?status=archived 合法筛选返回 200", c == 200, f"HTTP {c}")
    c, p = call("GET", "/resource/inbox?status=bogus")
    check("【缺陷回归】非法 status 筛选 → 400（白名单）", c == 400, f"HTTP {c}")

    c, p = call("GET", "/resource/inbox/no-such-id")
    check("不存在的收集箱 id → 404", c == 404, f"HTTP {c}")

    # ---------------------------------------------------------------- 4
    section("4. 桌宠（mass-assignment / 归属 IDOR）")
    c, p = call("GET", "/pet/config")
    check("GET /pet/config 返回 200", c == 200, f"HTTP {c}")

    c, p = call("POST", "/pet/avatars", {"name": "探针形象", "mode": "simple"})
    d = D((c, p))
    aid = d.get("id") if isinstance(d, dict) else None
    check("POST /pet/avatars 创建成功", c == 200 and aid, f"HTTP {c}")

    if aid:
        c, p = call("PATCH", f"/pet/avatars/{aid}", {"name": "改名成功"})
        d = D((c, p))
        check("PATCH 合法字段 name 生效",
              c == 200 and isinstance(d, dict) and d.get("name") == "改名成功", f"HTTP {c}")

        # 回归 2026-10-11：裸 dict → setattr 可改 user_id（把形象送给别人）
        c, p = call("PATCH", f"/pet/avatars/{aid}",
                    {"name": "改名2", "user_id": "attacker-id", "avatar_type": "hacked"})
        d = D((c, p))
        ok_id = isinstance(d, dict) and d.get("id") == aid
        ok_owner = isinstance(d, dict) and d.get("user_id") != "attacker-id"
        check("【缺陷回归】PATCH 传 user_id/avatar_type 被忽略（mass-assignment 已封堵）",
              c == 200 and ok_id and ok_owner,
              f"HTTP {c} id={d.get('id') if isinstance(d, dict) else None} "
              f"user_id={d.get('user_id') if isinstance(d, dict) else None}")

        c, p = call("POST", f"/pet/avatars/{aid}/activate")
        check("POST /pet/avatars/{id}/activate 成功", c == 200, f"HTTP {c}")

    c, p = call("DELETE", "/pet/avatars/no-such-avatar")
    check("【缺陷回归】不存在/他人的形象 id → 404（不泄漏存在性）", c == 404, f"HTTP {c}")

    if aid:
        c, p = call("DELETE", f"/pet/avatars/{aid}")
        check("DELETE 自己的形象成功", c == 200, f"HTTP {c}")

    c, p = call("GET", "/pet/state")
    check("GET /pet/state 返回 200（状态感知）", c == 200, f"HTTP {c}")
    c, p = call("GET", "/pet/stats")
    check("GET /pet/stats 返回 200（四维数值）", c == 200, f"HTTP {c}")

    # ---------------------------------------------------------------- 5
    section("5. 保险箱（主密码生命周期 / 加解密 / 解锁门槛）")
    MP = "probe-master-2026"
    c, p = call("GET", "/vault/status")
    d = D((c, p))
    check("GET /vault/status 返回 200", c == 200, f"HTTP {c}")
    check("全新库 configured=False", isinstance(d, dict) and d.get("configured") is False,
          f"configured={d.get('configured') if isinstance(d, dict) else d}")

    c, p = call("PUT", "/vault/setup", {"master_password": MP})
    check("PUT /vault/setup 初始化主密码成功", c == 200, f"HTTP {c}")

    c, p = call("GET", "/vault/status")
    d = D((c, p))
    check("setup 后即处于解锁态（设计行为：设完密码马上要录凭据）",
          isinstance(d, dict) and d.get("unlocked") is True,
          f"unlocked={d.get('unlocked') if isinstance(d, dict) else d}")

    c, p = call("PUT", "/vault/setup", {"master_password": "another-pass-123"})
    check("重复 setup 被拒绝（不覆盖已有主密码）", c in (400, 409), f"HTTP {c}")

    MARK = "s3cr3t-PLAINTEXT-marker"
    c, p = call("POST", "/vault/items", {"name": "探针凭据", "category": "login", "secret": MARK})
    d = D((c, p))
    vid = d.get("id") if isinstance(d, dict) else None
    check("POST /vault/items 新增凭据成功", c == 200 and vid, f"HTTP {c}")

    c, p = call("GET", "/vault/items")
    d = D((c, p))
    check("【安全】凭据列表不含明文（密文不出现在列表接口）",
          c == 200 and MARK not in json.dumps(d, ensure_ascii=False), f"HTTP {c}")

    c, p = call("POST", "/vault/unlock", {"master_password": "wrong-password"})
    check("【安全】错误主密码解锁被拒绝", c in (400, 401), f"HTTP {c}")

    c, p = call("POST", "/vault/lock")
    check("POST /vault/lock 上锁成功", c == 200, f"HTTP {c}")

    c, p = call("GET", "/vault/status")
    d = D((c, p))
    check("上锁后 status.unlocked=False", isinstance(d, dict) and d.get("unlocked") is False,
          f"unlocked={d.get('unlocked') if isinstance(d, dict) else d}")

    # _require_unlocked 抛 BusinessException → HTTP 409（不是 400/403）
    if vid:
        c, p = call("GET", f"/vault/items/{vid}/secret")
        check("【安全】上锁后读明文被拒绝（BusinessException → 409）", c == 409, f"HTTP {c}")

    c, p = call("GET", "/vault/items")
    check("【安全】上锁后凭据列表同样被拒绝（解锁门槛统一）", c == 409, f"HTTP {c}")

    c, p = call("POST", "/vault/unlock", {"master_password": MP})
    check("正确主密码解锁成功", c == 200, f"HTTP {c}")

    if vid:
        c, p = call("GET", f"/vault/items/{vid}/secret")
        d = D((c, p))
        check("解锁后取回明文且与写入完全一致（加解密往返正确）",
              MARK in json.dumps(d, ensure_ascii=False), f"HTTP {c} data={str(d)[:90]}")

    c, p = call("POST", "/vault/lock")
    check("收尾上锁", c == 200, f"HTTP {c}")

    # ---------------------------------------------------------------- 6
    section("6. 长期资产库 / 工作流（应用引擎 · status 回归）")
    for path, label in [("/assets/sops", "SOP"), ("/assets/prompts", "Prompt"),
                        ("/assets/skills", "技能"), ("/assets/memories", "项目记忆")]:
        c, p = call("GET", path)
        check(f"GET {path}（{label}）返回 200", c == 200, f"HTTP {c}")

    # 注意：启动种子（app/seed.py）不灌工作流预设，全新库的 presets 为空是现状，
    # 不是缺陷。这里改为「自建工作流 → 应用」，才能真正测到应用引擎。
    c, p = call("GET", "/workflows/presets")
    d = D((c, p))
    check("GET /workflows/presets 返回 200", c == 200, f"HTTP {c}")
    check("presets 返回 {list,total} 结构",
          isinstance(d, dict) and "list" in d and "total" in d,
          f"keys={list(d.keys()) if isinstance(d, dict) else d}")

    c, p = call("GET", "/workflows?page_size=50")
    check("GET /workflows 返回 200", c == 200, f"HTTP {c}")

    wf_payload = {
        "name": "探针工作流",
        "category": "测试",
        "config": {
            "tag_system": {"探针": ["探针标签A", "探针标签B"]},
            "doc_templates": ["探针模板"],
            "task_templates": [
                {"name": "准备阶段", "steps": ["收集材料", "列提纲"]},
                {"name": "执行阶段", "steps": ["撰写", "校对"]},
            ],
        },
    }
    c, p = call("POST", "/workflows", wf_payload)
    d = D((c, p))
    wid = d.get("id") if isinstance(d, dict) else None
    check("POST /workflows 创建自定义工作流成功", c == 200 and wid, f"HTTP {c} id={wid}")

    if wid:
        c, p = call("POST", f"/workflows/{wid}/apply", {"params": {"name": "探针项目"}})
        d = D((c, p))
        check("POST /workflows/{id}/apply 应用成功", c == 200, f"HTTP {c}")
        check("应用引擎创建了 2 个任务",
              isinstance(d, dict) and (d.get("tasks_created") or 0) == 2,
              f"tasks_created={d.get('tasks_created') if isinstance(d, dict) else None}")
        check("应用引擎创建了标签（domains）与文档模板",
              isinstance(d, dict) and (d.get("domains_created") or 0) == 2
              and (d.get("templates_created") or 0) == 1,
              f"domains={d.get('domains_created') if isinstance(d, dict) else None} "
              f"templates={d.get('templates_created') if isinstance(d, dict) else None}")

        c, p = call("GET", "/tasks?page_size=100")
        d = D((c, p))
        tasks = pick_list(d)
        statuses = sorted({t.get("status") for t in tasks if isinstance(t, dict)})
        titles = [t.get("title") or "" for t in tasks if isinstance(t, dict)]
        check("任务列表可取到数据（应用工作流真的写了库）", len(tasks) > 0, f"共 {len(tasks)} 条")
        # 回归 2026-10-11：生成任务曾写成 status="todo"（非法值）→
        # STATUS_TRANSITIONS.get("todo") 为空集 → 任何流转报 3001，任务永久卡死。
        check("【缺陷回归】生成的任务状态合法（不含非法值 'todo'）",
              "todo" not in statuses, f"状态集={statuses}")
        check("【缺陷回归】生成的任务处于 pending（修复前卡死在非法状态）",
              "pending" in statuses, f"状态集={statuses}")
        check("生成的任务标题含项目名前缀「探针项目」",
              any("探针项目" in t for t in titles),
              f"命中 {sum('探针项目' in t for t in titles)} 条")

        c, p = call("GET", "/workflows/applications/history")
        check("GET /workflows/applications/history 返回 200（路由未被 /{id} 吞掉）",
              c == 200, f"HTTP {c}")

        c, p = call("GET", "/workflows/no-such-workflow")
        check("不存在的工作流 id → 404", c == 404, f"HTTP {c}")

    # ---------------------------------------------------------------- 7
    section("7. 汇总")
    total = len(R)
    passed = sum(1 for ok, *_ in R if ok)
    print(f"共 {total} 项断言 | 通过 {passed} | 失败 {total - passed}")
    if passed != total:
        print("\n失败明细：")
        for ok, name, detail in R:
            if not ok:
                print(f"  - {name}   {detail}")
    print("\n结论:", "全部通过" if passed == total else f"存在 {total - passed} 项失败")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
