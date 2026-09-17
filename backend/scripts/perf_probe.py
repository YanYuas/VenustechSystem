# 性能探针：临时数据目录 + 演示种子，测关键端点延迟（一次 性能体检）
# 用法：VENUSTECH_DATA_DIR=<temp> python scripts/perf_probe.py
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BACKEND_DIR = Path(__file__).resolve().parent.parent
os.environ["VENUSTECH_DEV"] = "false"
os.environ["VENUSTECH_DEMO_SEED"] = "true"

import shutil  # noqa: E402
import tempfile  # noqa: E402

# 放系统临时目录：仓库目录被同步客户端锁 SQLite（见 smoke_backend 注释）
DATA_DIR = Path(tempfile.gettempdir()) / "venustech_perf_probe"
os.environ["VENUSTECH_DATA_DIR"] = str(DATA_DIR)
os.environ["VENUSTECH_DEV"] = "false"
os.environ["VENUSTECH_DEMO_SEED"] = "true"

sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402


def bench(name: str, method: str, path: str, json_body=None, repeat: int = 5) -> float:
    times = []
    for _ in range(repeat):
        t0 = time.perf_counter()
        if method == "GET":
            r = client.get(path, headers=H)
        else:
            r = client.post(path, headers=H, json=json_body)
        dt = (time.perf_counter() - t0) * 1000
        times.append(dt)
        if r.status_code != 200:
            print(f"  !! {name} -> HTTP {r.status_code}")
            break
    avg = sum(times) / len(times)
    mx = max(times)
    print(f"{name:<28} avg {avg:8.1f} ms   max {mx:8.1f} ms")
    return avg


with TestClient(app) as client:  # with 上下文才触发 lifespan（迁移+种子）
    H: dict = {}  # 冒烟/探针模式下鉴权由 get_current_user 兜底（同 smoke_backend）

    print(f"\n数据目录: {DATA_DIR}")
    print("=" * 60)
    bench("GET /dashboard", "GET", "/api/v1/dashboard")
    bench("GET /tasks", "GET", "/api/v1/tasks")
    bench("GET /identities", "GET", "/api/v1/identities")
    bench("GET /experience", "GET", "/api/v1/experience")
    bench("GET /report", "GET", "/api/v1/report")
    bench("GET /growth/skills", "GET", "/api/v1/growth/skills")
    bench("GET /reviews", "GET", "/api/v1/reviews")
    bench("GET /documents", "GET", "/api/v1/documents")
    bench("GET /assets/sops", "GET", "/api/v1/assets/sops")

    # ---------- 大数据量压测：2000 条任务 ----------
    from sqlalchemy import insert

    from app.database import SessionLocal
    from app.models.task import Task
    from app.models.user import User

    db = SessionLocal()
    uid = db.scalar(__import__("sqlalchemy").select(User.id).limit(1))
    now = time.time()
    rows = [
        {
            "user_id": uid, "title": f"压测任务 {i}", "status": "todo",
            "priority": "medium", "sort_order": i,
            "created_at": __import__("datetime").datetime.now(),
            "updated_at": __import__("datetime").datetime.now(),
        }
        for i in range(2000)
    ]
    db.execute(insert(Task), rows)
    db.commit()
    print(f"[bulk] 2000 tasks inserted in {time.time() - now:.2f}s")
    db.close()

    bench("[bulk] GET /tasks", "GET", "/api/v1/tasks")
    bench("[bulk] GET /dashboard", "GET", "/api/v1/dashboard")
    bench("[bulk] GET /experience", "GET", "/api/v1/experience")
    bench("[bulk] GET /report", "GET", "/api/v1/report")

    from app.core.sync import SyncEngine

    eng = SyncEngine(db, uid)
    t0 = time.perf_counter()
    pkg = eng.export_to(Path(tempfile.gettempdir()))
    print(f"[bulk] sync export            {(time.perf_counter() - t0) * 1000:8.1f} ms")
    t0 = time.perf_counter()
    ops = eng.diff(SyncEngine.load_package(pkg)["tables"])
    print(f"[bulk] sync diff (zero-op)    {(time.perf_counter() - t0) * 1000:8.1f} ms   ops={len(ops)}")
    print("=" * 60)
shutil.rmtree(DATA_DIR, ignore_errors=True)
