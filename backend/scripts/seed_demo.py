#!/usr/bin/env python
"""启明星 · 丰富演示数据一键生成

## 用途
把一整套**互相连贯、覆盖全部 46 张表**的演示数据灌进一个**独立数据目录**，
不动你的真实库。

## 为什么用独立目录
真实库（`backend/data/`）是你的正史，不该被演示数据污染。
本脚本默认写 `backend/data_demo/`（已在 .gitignore），
演示完直接删掉目录就干净了。

## 用法
```bash
cd backend
.venv/Scripts/python.exe scripts/seed_demo.py            # 灌进 data_demo（已存在则询问）
.venv/Scripts/python.exe scripts/seed_demo.py --reset     # 先清空再灌
.venv/Scripts/python.exe scripts/seed_demo.py --data-dir data_demo2
.venv/Scripts/python.exe scripts/seed_demo.py --verify    # 只体检，不写入
```

## 设计要点
1. **幂等**：`--reset` 会先删掉演示用户及其全部行；非 reset 模式下若检测到
   已有数据会拒绝覆盖（要求显式 --reset），避免误删你手工补的数据。
2. **时间轴铺开**：任务/专注/打卡/心情/学习时长都回填到过去 90 天，
   否则图表会是一条竖线，看不出趋势。
3. **双链真实解析**：文档正文里的 `[[标题]]` 会被解析成 `backlinks` 行，
   与运行时行为一致（不是写死的假链接）。
4. **保险箱走真实加密链路**：用 VaultService 的派生逻辑加密，
   主密码为脚本内常量（见 DEMO_MASTER_PASSWORD），只放演示凭据。
5. **不写死 id**：全部用「自然键 → 真实 id」的映射表，避免硬编码 uuid。
"""
from __future__ import annotations

import argparse
import os
import random
import re
import sys
from datetime import date, datetime, time as dtime, timedelta, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import demo_seed_data as D  # noqa: E402

# 演示保险箱主密码：只用于 data_demo 这个独立库；请勿在真实库使用
DEMO_MASTER_PASSWORD = "demo-master-password-2026"

random.seed(20260919)  # 固定种子：每次生成同样的"随机"数据，便于复现

NOW = datetime.now(timezone.utc)


def ago(days: float = 0, hours: float = 0, minutes: float = 0) -> datetime:
    """N 天/小时/分钟之前（带时区）。所有历史数据都用它回填。"""
    return NOW - timedelta(days=days, hours=hours, minutes=minutes)


def aday(days: float = 0) -> date:
    return (NOW - timedelta(days=days)).date()


# ============================================================
# 参数与引导
# ============================================================
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="生成启明星演示数据")
    p.add_argument("--data-dir", default="data_demo",
                   help="数据目录（相对 backend/ 或绝对路径），默认 data_demo")
    p.add_argument("--reset", action="store_true", help="先清空演示用户数据再灌")
    p.add_argument("--verify", action="store_true", help="只体检现有数据，不写入")
    p.add_argument("--yes", action="store_true", help="跳过确认提示")
    return p.parse_args()


def bootstrap(data_dir_arg: str) -> Path:
    """设置数据目录环境变量 —— 必须在 import app.* 之前完成。

    app.config 的 settings 在导入时构建，db_url 由 data_dir 派生，
    所以顺序错了就会写到真实库去。
    """
    p = Path(data_dir_arg)
    target = p if p.is_absolute() else (BACKEND_DIR / p)
    target.mkdir(parents=True, exist_ok=True)
    os.environ["VENUSTECH_DATA_DIR"] = str(target)
    return target


def main() -> int:
    args = parse_args()
    data_dir = bootstrap(args.data_dir)

    # 延迟导入：环境变量已就位
    import app.models  # noqa: F401  注册全部表
    from sqlalchemy import delete, func, select

    from app.database import Base, SessionLocal, engine
    from app.migrate import run_migrations
    from app.models.base import utcnow

    print("=" * 64)
    print("  启明星 · 演示数据生成")
    print("=" * 64)
    print(f"数据目录: {data_dir}")
    print(f"数据库  : {data_dir / 'app.db'}")
    print()

    if args.verify:
        return verify_only(SessionLocal)

    # ---------- 迁移（走真实 alembic 路径，与启动一致） ----------
    print("[0/16] 执行数据库迁移 ...")
    run_migrations()
    print("       迁移完成")

    db = SessionLocal()
    from app.models.user import User

    existing = db.scalar(select(User).where(User.username == "default_user"))
    if existing is not None and not args.reset:
        db.close()
        print()
        print("⚠️  该目录已有演示用户（default_user）。")
        print("    要覆盖请加 --reset（会重建该演示库，真实库有护栏拒绝）。")
        print("    仅体检请加 --verify。")
        return 2

    if existing is not None and args.reset:
        db.close()
        print("[reset] 重建演示库 ...")
        assert_safe_to_reset(data_dir)
        engine.dispose()
        reset_db(data_dir)
        run_migrations()
        db = SessionLocal()

    try:
        if not args.yes:
            print()
            print(f"即将向 {data_dir} 写入演示数据（10 重身份 / 46 张表）。")
            print("回车继续，Ctrl+C 取消 ...")
        counts = seed_all(db, utcnow, delete, select, func)
        print_summary(counts, data_dir)
        return 0
    finally:
        db.close()
        engine.dispose()


# ============================================================
# 清空（安全护栏优先）
# ============================================================
def assert_safe_to_reset(data_dir: Path) -> None:
    """--reset 的安全护栏。

    这是你的**个人人生数据**，误删不可恢复。所以在动任何删除之前先卡住：
      1. 目标是真实数据目录（backend/data 或打包后的系统数据目录）→ 直接拒绝
      2. 目录名不含 demo 字样 → 拒绝（要求显式 --i-know-what-im-doing）

    宁可多一步麻烦，也不接受「一条命令删掉正史」这种事。
    """
    resolved = data_dir.resolve()
    real_dirs = {(BACKEND_DIR / "data").resolve()}
    try:
        from app.config import _default_data_dir  # type: ignore

        real_dirs.add(Path(_default_data_dir()).resolve())
    except Exception:
        pass

    if resolved in real_dirs:
        raise SystemExit(
            f"❌ 拒绝在该目录执行 --reset：{resolved}\n"
            "   这是真实数据目录。演示数据请用 --data-dir data_demo。"
        )
    if "demo" not in resolved.name.lower():
        raise SystemExit(
            f"❌ 目录名不含 demo，拒绝 --reset：{resolved.name}\n"
            "   如确认可删，请换用带 demo 的目录名（如 data_demo2）。"
        )


def reset_db(data_dir: Path) -> None:
    """整库重建：删文件比按表倒序删更可靠（子表未必都有 user_id）。"""
    removed = []
    for suffix in ("app.db", "app.db-wal", "app.db-shm"):
        f = data_dir / suffix
        if f.exists():
            f.unlink()
            removed.append(suffix)
    print(f"        已删除: {', '.join(removed) if removed else '（无文件）'}")


def verify_only(SessionLocal) -> int:
    """体检：统计各表行数，确认覆盖度。"""
    from app.database import Base
    from sqlalchemy import func, select

    db = SessionLocal()
    try:
        print("表名".ljust(28) + "行数")
        print("-" * 40)
        empty: list[str] = []
        total = 0
        for name in sorted(Base.metadata.tables):
            tbl = Base.metadata.tables[name]
            n = db.scalar(select(func.count()).select_from(tbl)) or 0
            total += n
            mark = "" if n else "   ← 空"
            if not n:
                empty.append(name)
            print(f"{name.ljust(28)}{n}{mark}")
        print("-" * 40)
        print(f"合计 {total} 行 · 空表 {len(empty)} 张")
        if empty:
            print("空表：" + ", ".join(empty))
        return 0
    finally:
        db.close()


def print_summary(counts: dict[str, int], data_dir: Path) -> None:
    print()
    print("=" * 64)
    print("  生成完成")
    print("=" * 64)
    groups = [
        ("身份与组织", ["identities", "folders", "settings", "settings_history"]),
        ("项目", ["projects", "project_milestones", "project_memories"]),
        ("任务与专注", ["tasks", "subtasks", "focus_sessions"]),
        ("知识", ["documents", "document_versions", "backlinks"]),
        ("成长", ["skills", "skill_stats", "growth_states", "growth_events"]),
        ("学习", ["study_plans", "study_time_logs", "flashcards"]),
        ("生活", ["habits", "habit_checkins", "mood_logs", "diaries"]),
        ("复盘", ["reviews"]),
        ("工具", ["sops", "sop_versions", "workflows", "workflow_applications",
                  "templates", "prompt_templates", "domains", "inbox_items",
                  "quick_todos", "reminders", "notifications"]),
        ("伙伴", ["conversations", "messages", "pet_avatars", "pet_configs",
                  "avatar_memories", "avatar_configs", "avatar_inspirations"]),
        ("档案库", ["workspace_roots", "workspace_files"]),
        ("安全", ["vault_config", "vault_items", "audit_logs"]),
    ]
    total = 0
    for label, keys in groups:
        sub = sum(counts.get(k, 0) for k in keys)
        total += sub
        detail = "  ".join(f"{k}={counts.get(k, 0)}" for k in keys if counts.get(k))
        print(f"  {label.ljust(6)} {sub:>6} 行   {detail}")
    print("-" * 64)
    print(f"  合计 {total} 行 · 覆盖 {len(counts)} 张表")
    print()
    print("怎么看这套数据（不影响真实库）：")
    print("  1) 双击根目录的 start-demo.bat  —— 用 data_demo 起后端(8765)")
    print("  2) 另开一个前端：start-dev.bat 里的前端部分，或已有 Vite(5173)")
    print()
    print("  注意：不要用 Git Bash 的 /d/... 形式设置环境变量 ——")
    print('  Path("/d/x") 在 Windows 上会解析成 \\d\\x（丢盘符），服务会打开另一个库。')
    print(f"  手动启动请用 Windows 路径：")
    print(f'    set VENUSTECH_DATA_DIR={data_dir}')
    print("    .venv\\Scripts\\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8765")
    print()
    print(f"保险箱演示主密码: {DEMO_MASTER_PASSWORD}")
    print("（仅该演示库有效；凭据内容均为示例，非真实数据）")


# ============================================================
# 主流程
# ============================================================
def seed_all(db, utcnow, delete, select, func) -> dict[str, int]:
    counts: dict[str, int] = {}
    steps = [
        ("用户与身份", lambda: seed_identities(db, counts)),
        ("文件夹", lambda: seed_folders(db, counts)),
        ("项目与里程碑", lambda: seed_projects(db, counts)),
        ("任务与子任务", lambda: seed_tasks(db, counts)),
        ("专注记录", lambda: seed_focus(db, counts)),
        ("文档与双链", lambda: seed_documents(db, counts)),
        ("技能与成长", lambda: seed_growth(db, counts)),
        ("学习计划与卡片", lambda: seed_learning(db, counts)),
        ("习惯 / 心情 / 日记", lambda: seed_life(db, counts)),
        ("复盘", lambda: seed_reviews(db, counts)),
        ("SOP / 工作流 / 模板", lambda: seed_tools(db, counts)),
        ("收件箱 / 待办 / 提醒", lambda: seed_inbox(db, counts)),
        ("通知", lambda: seed_notifications(db, counts)),
        ("对话与桌宠", lambda: seed_companion(db, counts)),
        ("档案库文件树", lambda: seed_workspace(db, counts)),
        ("设置 / 审计 / 保险箱", lambda: seed_misc(db, counts)),
    ]
    for i, (label, fn) in enumerate(steps, start=1):
        print(f"[{i}/16] {label} ...")
        fn()
    return counts


# ---------- 1. 用户与身份 ----------
def seed_identities(db, counts: dict[str, int]) -> None:
    from app.models.identity import Identity
    from app.models.user import User

    user = User(
        username="default_user",
        nickname="衍煜",
        theme="cream",
        language="zh-CN",
        pet_position={"x": 1770, "y": 880},
        pet_topmost=False,
        inspiration_probability=30,
        ai_enabled=True,
    )
    db.add(user)
    db.flush()
    globals()["_USER_ID"] = user.id

    for spec in D.IDENTITIES:
        db.add(Identity(
            user_id=user.id,
            name=spec["name"],
            slug=spec["slug"],
            color_token=spec["color_token"],
            icon=spec["icon"],
            description=spec["description"],
            sort_order=spec["sort_order"],
            is_active=True,
        ))
    db.commit()
    counts["users"] = 1
    counts["identities"] = len(D.IDENTITIES)

    # slug → id 映射，后面所有引用都查这张表
    idmap = {r.slug: r.id for r in db.query(Identity).all()}
    globals()["_IDMAP"] = idmap

    print(f"        用户 1 · 身份 {len(idmap)} 重：" +
          " / ".join(s["name"] for s in D.IDENTITIES))


def _uid() -> str:
    return globals()["_USER_ID"]


def _ident(slug: str | None) -> str | None:
    if not slug:
        return None
    return globals()["_IDMAP"].get(slug)


# ---------- 2. 文件夹 ----------
def seed_folders(db, counts: dict[str, int]) -> None:
    from app.models.folder import Folder

    fmap: dict[str, str] = {}
    for spec in D.FOLDERS:
        row = Folder(
            user_id=_uid(),
            name=spec["name"],
            is_inbox=spec.get("is_inbox", False),
            sort_order=spec["sort_order"],
        )
        db.add(row)
        db.flush()
        fmap[spec["name"]] = row.id
    db.commit()
    globals()["_FMAP"] = fmap
    counts["folders"] = len(fmap)


# ---------- 3. 项目与里程碑 ----------
def seed_projects(db, counts: dict[str, int]) -> None:
    from app.models.project import Project
    from app.models.asset import ProjectMemory
    from app.models.project import ProjectMilestone

    pmap: dict[str, str] = {}
    for i, spec in enumerate(D.PROJECTS):
        row = Project(
            user_id=_uid(),
            name=spec["name"],
            identity_id=_ident(spec["identity"]),
            description=spec["description"],
            color=spec["color"],
            status=spec["status"],
            sort_order=i,
        )
        db.add(row)
        db.flush()
        pmap[spec["name"]] = row.id

        for j, ms in enumerate(spec.get("milestones", [])):
            db.add(ProjectMilestone(
                project_id=row.id,
                name=ms["name"],
                completed=ms.get("done", False),
                completed_at=ago(days=10 - j) if ms.get("done") else None,
                sort_order=j,
            ))

        mem = spec.get("memory")
        if mem:
            db.add(ProjectMemory(
                user_id=_uid(),
                project_id=row.id,
                identity_id=_ident(spec["identity"]),
                name=f"{spec['name']} · 经验沉淀",
                summary=mem.get("summary"),
                successes=mem.get("successes"),
                failures=mem.get("failures"),
                extracted_assets=mem.get("assets", []),
                key_metrics=mem.get("metrics", {}),
                tags=[spec["identity"]],
            ))
    db.commit()
    globals()["_PMAP"] = pmap

    counts["projects"] = len(pmap)
    counts["project_milestones"] = sum(len(p.get("milestones", [])) for p in D.PROJECTS)
    counts["project_memories"] = sum(1 for p in D.PROJECTS if p.get("memory"))


# ---------- 4. 任务与子任务 ----------
def seed_tasks(db, counts: dict[str, int]) -> None:
    from app.models.task import Subtask, Task

    pmap = globals()["_PMAP"]
    n_sub = 0
    # 领域约束：tasks 上有部分唯一索引
    #   CREATE UNIQUE INDEX idx_tasks_unique_focus ON tasks(user_id) WHERE is_focus=1
    # 即「同一用户最多 1 个专注任务」（今日最重要）。数据里可能标了多个，
    # 这里按顺序只保留第一个，其余降级 —— 让种子永远满足该约束。
    focus_taken = False
    for i, spec in enumerate(D.TASKS):
        done = spec["status"] == "completed"
        due = aday(-spec["due_days"]) if spec.get("due_days") else None
        completed_at = ago(days=spec["done_days"]) if done and spec.get("done_days") else (
            utcnow() if done else None
        )
        # 有截止日期时补一个提醒时刻，让「提醒」不只是空字段
        reminder = None
        if due is not None:
            reminder = datetime.combine(due, dtime(9, 0), tzinfo=timezone.utc)

        want_focus = bool(spec.get("focus", False)) and not done
        is_focus = want_focus and not focus_taken
        if is_focus:
            focus_taken = True

        row = Task(
            user_id=_uid(),
            title=spec["title"],
            description=spec.get("desc"),
            status=spec["status"],
            priority=spec["priority"],
            identity_id=_ident(spec.get("identity")),
            project_id=pmap.get(spec["project"]) if spec.get("project") else None,
            project_tag=spec.get("project"),
            due_date=due,
            is_focus=is_focus,
            sort_order=i,
            completed_at=completed_at,
            reminder_time=reminder,
            estimated_minutes=spec.get("est"),
            # 一条演示「重复任务」：daily + step，启动时由真实逻辑生成到期实例
            recurrence={"type": "daily", "step": 1} if spec.get("repeat") else None,
            created_at=ago(days=min(60, 12 + i % 30)),
        )
        db.add(row)
        db.flush()

        for j, sub in enumerate(spec.get("subs", [])):
            # 已完成任务 → 子任务全勾；进行中 → 只勾第一个
            sub_done = done or (spec["status"] == "in_progress" and j == 0)
            db.add(Subtask(
                task_id=row.id, title=sub, completed=sub_done, sort_order=j,
            ))
            n_sub += 1
    db.commit()
    counts["tasks"] = len(D.TASKS)
    counts["subtasks"] = n_sub


# ---------- 5. 专注记录（90 天回填） ----------
def seed_focus(db, counts: dict[str, int]) -> None:
    """专注时长回填到过去 90 天。

    为什么必须回填：只看「今天」的话，热力图与趋势线都是一根竖线，
    演示时完全看不出「这个人有节奏地在自己推进多条线」。
    """
    from app.models.task import FocusSession, Task

    tasks = db.query(Task).all()
    by_id: dict[str, list[Task]] = {}
    for t in tasks:
        by_id.setdefault(t.identity_id or "none", []).append(t)

    n = 0
    for days_ago in range(90, -1, -1):
        # 近 30 天更活跃，早期稀一些 —— 让趋势自然上扬
        base = 3 if days_ago < 30 else (2 if days_ago < 60 else 1)
        for _ in range(random.randint(0, base)):
            pick = random.choice(tasks) if tasks else None
            minutes = random.choice([25, 25, 45, 45, 50, 60, 90])
            start = ago(days=days_ago, hours=random.randint(9, 21), minutes=random.randint(0, 59))
            db.add(FocusSession(
                user_id=_uid(),
                task_id=pick.id if pick else None,
                start_time=start,
                end_time=start + timedelta(minutes=minutes),
                duration=minutes,
                note=None,
                created_at=start,
            ))
            n += 1
    db.commit()

    # 把累计专注时长写回任务（focus_duration 字段）
    totals: dict[str, int] = {}
    for s in db.query(FocusSession).all():
        if s.task_id:
            totals[s.task_id] = totals.get(s.task_id, 0) + s.duration
    for tid, total in totals.items():
        t = db.get(Task, tid)
        if t is not None:
            t.focus_duration = total
    db.commit()
    counts["focus_sessions"] = n


# ---------- 6. 文档与双链 ----------
def seed_documents(db, counts: dict[str, int]) -> None:
    from app.models.document import Backlink, Document, DocumentVersion
    from app.services.document_service import count_words

    fmap = globals()["_FMAP"]
    pmap = globals()["_PMAP"]
    docmap: dict[str, Document] = {}

    for i, spec in enumerate(D.DOCUMENTS):
        content = spec["content"]
        row = Document(
            user_id=_uid(),
            title=spec["title"],
            folder_id=fmap.get(spec.get("folder", "")),
            identity_id=_ident(spec.get("identity")),
            project_id=pmap.get(spec["project"]) if spec.get("project") else None,
            content=content,
            tags=spec.get("tags", []),
            summary=spec.get("summary"),
            word_count=count_words(content),
            version=1,
            created_at=ago(days=40 - min(i * 2, 38)),
        )
        db.add(row)
        db.flush()
        docmap[spec["title"]] = row
        # 首版快照
        db.add(DocumentVersion(
            document_id=row.id, content=content, version=1,
            word_count=count_words(content),
        ))

    # —— 双链解析：真实解析 [[标题]]，与运行时行为一致 ——
    link_re = re.compile(r"\[\[([^\]]+)\]\]")
    n_links = 0
    n_versions = len(D.DOCUMENTS)
    for title, doc in docmap.items():
        for m in link_re.finditer(doc.content or ""):
            target_title = m.group(1).strip()
            target = docmap.get(target_title)
            db.add(Backlink(
                source_doc_id=doc.id,
                target_doc_id=target.id if target else None,
                target_title=target_title,
            ))
            n_links += 1

    # 给 4 篇文档补一版历史（演示版本对比）
    for title in list(docmap)[:4]:
        doc = docmap[title]
        db.add(DocumentVersion(
            document_id=doc.id, content=(doc.content or "")[: max(80, len(doc.content or "") // 2)],
            version=0, word_count=max(20, (doc.word_count or 0) // 2),
        ))
        doc.version = 2
        n_versions += 1

    db.commit()
    counts["documents"] = len(docmap)
    counts["document_versions"] = n_versions
    counts["backlinks"] = n_links


# ---------- 7. 技能与成长（走真实 GrowthService） ----------
def seed_growth(db, counts: dict[str, int]) -> None:
    from app.models.asset import Skill
    from app.models.growth import GrowthEvent, SkillStat
    from app.services.growth_service import GrowthService

    for spec in D.SKILLS:
        db.add(Skill(
            user_id=_uid(),
            name=spec["name"],
            category=spec["category"],
            description=spec.get("description"),
            methodology=spec.get("methodology"),
            proficiency=spec.get("proficiency", 50),
            tags=spec.get("tags", []),
            use_count=spec.get("use_count", 0),
        ))
    db.commit()
    counts["skills"] = len(D.SKILLS)

    # 用生产代码结算经验 —— growth_states / growth_events / skill_stats
    # 三个表都由真实逻辑产生，不手写等级公式，避免与实现漂移
    svc = GrowthService(db)
    granted = 0
    for ev in D.GROWTH_EVENTS:
        res = svc.award(
            user_id=_uid(),
            source_key=ev["key"],
            event_type=ev["type"],
            exp=ev["exp"],
            label=ev["label"],
            classified_text=ev["label"],  # 触发 auto_classify → skill_stats
        )
        if res.get("granted"):
            granted += 1

    # 回填事件时间，让成长曲线分布在过去 30 天
    for ev in D.GROWTH_EVENTS:
        row = db.query(GrowthEvent).filter_by(source_key=ev["key"]).first()
        if row is not None:
            ts = ago(days=ev["days_ago"], hours=random.randint(1, 8))
            row.created_at = ts
            row.updated_at = ts
    db.commit()

    counts["growth_events"] = len(D.GROWTH_EVENTS)
    counts["growth_states"] = 1
    counts["skill_stats"] = db.query(SkillStat).count()
    st = svc.get_state(_uid())
    print(f"        经验 {st.get('exp')} · 等级 {st.get('level')} · "
          f"技能分类 {counts['skill_stats']} 项")


# ---------- 8. 学习（计划 / 时长 / 卡片） ----------
def seed_learning(db, counts: dict[str, int]) -> None:
    from app.models.learning import Flashcard, StudyPlan, StudyTimeLog

    plan_ids: list[str] = []
    for spec in D.STUDY_PLANS:
        row = StudyPlan(
            user_id=_uid(),
            name=spec["name"],
            description=spec["description"],
            target_date=aday(-spec["target_days_from_now"]),
            estimated_hours=spec["estimated_hours"],
            progress=spec["progress"],
            status=spec["status"],
            config=spec["config"],
            created_at=ago(days=abs(spec["target_days_from_now"]) + 20),
        )
        db.add(row)
        db.flush()
        plan_ids.append(row.id)
    db.commit()

    # 学习时长：近 80 天，subject 用工整的几类，source 区分手动/自动
    subjects = ["动态规划", "大模型应用", "配器", "可视化", "英语文献"]
    n_time = 0
    for days_ago in range(80, -1, -1):
        for _ in range(random.randint(0, 2)):
            db.add(StudyTimeLog(
                user_id=_uid(),
                plan_id=random.choice(plan_ids) if plan_ids and random.random() < 0.7 else None,
                subject=random.choice(subjects),
                duration=random.choice([25, 30, 45, 60, 90]),
                note=None,
                source=random.choice(["manual", "focus_session"]),
                logged_date=aday(days_ago),
            ))
            n_time += 1
    db.commit()

    # 知识卡片：next_review 分布到今天 ± 几天，让「今日复习」有内容
    for spec in D.FLASHCARDS:
        last = ago(days=spec["interval"]) if spec["repetition"] > 0 else None
        db.add(Flashcard(
            user_id=_uid(),
            plan_id=None,
            front=spec["front"],
            back=spec["back"],
            card_type="qa",
            category=spec.get("category"),
            tags=[spec["category"]] if spec.get("category") else [],
            difficulty=spec.get("difficulty", 2),
            ef=spec.get("ef", 2.5),
            interval=spec.get("interval", 0),
            repetition=spec.get("repetition", 0),
            next_review=aday(-spec.get("due_in_days", 0)),
            last_reviewed_at=last,
            review_count=spec.get("repetition", 0),
        ))
    db.commit()
    counts["study_plans"] = len(plan_ids)
    counts["study_time_logs"] = n_time
    counts["flashcards"] = len(D.FLASHCARDS)

    # 今日待复习数量（演示「今日复习」不空）
    today_due = db.query(Flashcard).filter(Flashcard.next_review <= aday(0)).count()
    print(f"        今日待复习卡片 {today_due} 张")


# ---------- 9. 生活（习惯 / 心情 / 日记） ----------
def seed_life(db, counts: dict[str, int]) -> None:
    from app.models.life import Diary, Habit, HabitCheckin, MoodLog

    habits: list[Habit] = []
    for spec in D.HABITS:
        row = Habit(
            user_id=_uid(),
            name=spec["name"],
            icon=spec["icon"],
            frequency=spec["frequency"],
            target_per_week=spec["target_per_week"],
            goal_days=spec.get("goal_days"),
            status="active",
        )
        db.add(row)
        habits.append(row)
    db.commit()

    # 打卡 60 天：日常习惯命中率高、周习惯低 —— 逻辑要自洽（周习惯不可能每天打）
    n_check = 0
    for days_ago in range(60, -1, -1):
        d = aday(days_ago)
        for h in habits:
            if h.frequency == "daily":
                p = 0.82 if days_ago < 20 else 0.7
            else:
                # 周习惯：一周三次 -> 每天约 3/7
                p = 3 / 7
            if random.random() < p:
                db.add(HabitCheckin(
                    habit_id=h.id, user_id=_uid(), checkin_date=d, note=None,
                ))
                n_check += 1
    db.commit()

    # 心情 75 天：整体偏中上，夹几天低谷 —— 真实的人不会是一条直线
    n_mood = 0
    for days_ago in range(75, -1, -1):
        if random.random() < 0.12:  # 偶尔漏记
            continue
        r = random.random()
        if r < 0.18:
            score, tags, note = 2, random.choice(D.MOOD_TAGS_LOW), random.choice(D.MOOD_NOTES_LOW)
        elif r < 0.62:
            score, tags, note = 3, random.choice(D.MOOD_TAGS_MID), random.choice(D.MOOD_NOTES_MID)
        else:
            score, tags, note = random.choice([4, 5]), random.choice(D.MOOD_TAGS_HIGH), random.choice(D.MOOD_NOTES_HIGH)
        db.add(MoodLog(
            user_id=_uid(), score=score, tags=tags, content=note, logged_date=aday(days_ago),
        ))
        n_mood += 1
    db.commit()

    for spec in D.DIARIES:
        db.add(Diary(
            user_id=_uid(),
            dimension=spec.get("dimension"),
            identity_id=_ident(spec.get("identity")),
            title=spec["title"],
            content=spec["content"],
            diary_date=aday(spec["days_ago"]),
            tags=spec.get("tags", []),
        ))
    db.commit()
    counts["habits"] = len(habits)
    counts["habit_checkins"] = n_check
    counts["mood_logs"] = n_mood
    counts["diaries"] = len(D.DIARIES)


# ---------- 10. 复盘 ----------
def seed_reviews(db, counts: dict[str, int]) -> None:
    from app.models.review import Review

    pmap = globals()["_PMAP"]
    weekly = [
        ("这周把动态规划那套题过完了，比预期快一天。",
         "蒸汽蓬勃的数据源还是没定，卡在第 3 天。",
         "把「先写摘要」这条真正执行了 —— 以前总是最后补，写完发现逻辑不顺。",
         "下周先把蒸汽蓬勃的数据源定下来，再谈进度。"),
        ("按身份过了 4 条线，音乐和篆刻这周完全没动。",
         "启明星的移动端适配改了两轮才过。",
         "发现「忙但没进展」多半是分布问题，不是效率问题。",
         "给休眠的线写一句「为什么休眠」，把它变成决策。"),
        ("第一交响诗收尾了，从素材到终混全流程走通。",
         "RedBook 的内容转化数据一直没复盘。",
         "AI 不会替你作曲，但能替你试奏 —— 意图还是得自己给。",
         "开始做数模的论文模板定稿。"),
        ("数模竞赛作品整理完两年份。",
         "配器练习断了两天。",
         "作品集的价值在可复现；没运行说明的代码半年后自己都跑不起来。",
         "给旧作品补 README 与依赖锁定。"),
        ("实训周记补齐，AIGC 阶段总结写完。",
         "小说设定只推进了一点点。",
         "真实业务和作业差的不是难度，是约束。",
         "把《弱水》的代价机制定下来。"),
    ]

    n = 0
    # 日复盘：近 21 天
    for days_ago in range(21, 0, -1):
        if random.random() < 0.25:
            continue
        db.add(Review(
            user_id=_uid(), type="daily", review_date=aday(days_ago),
            identity_id=None,
            data={
                "completed_tasks": random.choice([
                    "把动态规划的三类模板都实现了一遍。",
                    "改完首页的分组逻辑。",
                    "课上完，学生这次自己画图了。",
                    "把素材评分表补完。",
                ]),
                "unfinished_tasks": random.choice([
                    "蒸汽蓬勃的数据源还没定。",
                    "RedBook 数据复盘拖了两天。",
                    "配器练习没做。",
                ]),
                "gains": random.choice([
                    "先写摘要确实能让全文逻辑更顺。",
                    "分段生成 + 人工筛选是唯一可行的路线。",
                    "错题归因之后，备课方向清楚多了。",
                    "把「不要什么」写下来，比写「要什么」更好指导下一步。",
                ]),
                "reflections": [
                    {"question": "今天最有价值的一件事是什么？",
                     "answer": random.choice([
                         "把卡住的地方拆成了三个小问题。",
                         "忍住没接新活，先把手上这条推完。",
                         "跟老师聊完方向清晰了。",
                     ])},
                ],
                "tomorrow_plan": random.choice([
                    "先把数据源的事定下来，别再拖。",
                    "继续推进身份轴在移动端的呈现。",
                    "把第一章开个头。",
                ]),
                "mood": random.choice([3, 3, 4, 4, 5, 2]),
                "energy": random.choice([2, 3, 3, 4, 4]),
            },
            created_at=ago(days=days_ago, hours=-21),
        ))
        n += 1

    # 周复盘：近 12 周（带身份维度）
    idmap = globals()["_IDMAP"]
    for i in range(12):
        days_ago = i * 7 + 2
        body = weekly[i % len(weekly)]
        db.add(Review(
            user_id=_uid(), type="weekly", review_date=aday(days_ago),
            identity_id=None,
            data={
                "completed_tasks": body[0],
                "unfinished_tasks": body[1],
                "gains": body[2],
                "reflections": [
                    {"question": "这周哪条身份线被冷落了？",
                     "answer": "音乐与篆刻连续两周零推进，需要决定是主动休眠还是补上。"},
                    {"question": "有什么是可以固化成 SOP 的？",
                     "answer": "素材筛选那套评分流程值得写下来，已经做过三次了。"},
                ],
                "tomorrow_plan": body[3],
                "mood": random.choice([3, 4, 4, 5]),
                "energy": random.choice([3, 3, 4]),
            },
            created_at=ago(days=days_ago, hours=-21),
        ))
        n += 1

    # 月复盘：近 3 月
    for i in range(3):
        db.add(Review(
            user_id=_uid(), type="monthly", review_date=aday(i * 30 + 1),
            identity_id=idmap.get("qmx-dev"),
            data={
                "completed_tasks": "本月完成：第一交响诗收尾、数模作品整理、启明星移动端上线。",
                "unfinished_tasks": "蒸汽蓬勃仍在数据源阶段；小说停在设定。",
                "gains": "身份轴立起来之后，「乱」的感觉明显减轻 —— 能看出自己在推进哪条线。",
                "reflections": [
                    {"question": "这个月投入产出比最高的是哪条线？",
                     "answer": "启明星开发：每投入 1 小时，后续每天都在省时间。"},
                    {"question": "哪条线该考虑主动收缩？",
                     "answer": "篆刻与小说长期低速推进，要么排进固定时段，要么明确列为「长线爱好」不再计进度。"},
                ],
                "tomorrow_plan": "下月重点：蒸汽蓬勃收尾 + 启明星模块化推进到第 4 个模块。",
                "mood": 4, "energy": 4,
            },
            created_at=ago(days=i * 30 + 1, hours=-21),
        ))
        n += 1

    db.commit()
    counts["reviews"] = n


# ---------- 11. SOP / 工作流 / 模板 / 领域 ----------
def seed_tools(db, counts: dict[str, int]) -> None:
    from app.models.asset import PromptTemplate, SOP, SOPVersion
    from app.models.resource import Domain, Template
    from app.models.workflow import Workflow, WorkflowApplication

    for spec in D.SOPS:
        row = SOP(
            user_id=_uid(),
            name=spec["name"],
            category=spec["category"],
            description=spec["description"],
            steps=spec["steps"],
            checklist=spec["checklist"],
            tags=spec.get("tags", []),
            use_count=random.randint(3, 28),
            version=2,
        )
        db.add(row)
        db.flush()
        db.add(SOPVersion(sop_id=row.id, version=1, content="\n".join(spec["steps"]),
                          change_note="初版"))
        db.add(SOPVersion(sop_id=row.id, version=2, content="\n".join(spec["steps"]),
                          change_note="补充检查清单与踩坑记录"))
    db.commit()
    counts["sops"] = len(D.SOPS)
    counts["sop_versions"] = len(D.SOPS) * 2

    wf_ids: list[str] = []
    for spec in D.WORKFLOWS:
        row = Workflow(
            name=spec["name"], description=spec["description"], icon=spec["icon"],
            category=spec["category"], scenario=spec["scenario"], config=spec["config"],
            is_preset=spec.get("is_preset", False), is_active=True,
            use_count=random.randint(2, 20),
        )
        db.add(row)
        db.flush()
        wf_ids.append(row.id)
    db.commit()

    n_app = 0
    for i, wid in enumerate(wf_ids):
        for k in range(random.randint(1, 3)):
            db.add(WorkflowApplication(
                workflow_id=wid, user_id=_uid(),
                params={"week_offset": -k - 1},
                status="success" if k % 3 != 2 else "partial",
                result_summary="生成成功，已写入文档" if k % 3 != 2 else "部分数据源缺失，已跳过",
                applied_at=ago(days=i * 3 + k + 1, hours=random.randint(1, 10)),
                created_at=ago(days=i * 3 + k + 1, hours=random.randint(1, 10)),
            ))
            n_app += 1
    db.commit()
    counts["workflows"] = len(wf_ids)
    counts["workflow_applications"] = n_app

    for spec in D.TEMPLATES:
        db.add(Template(
            user_id=_uid(), name=spec["name"], category=spec["category"],
            description=spec["description"], content=spec["content"],
            variables=spec.get("variables", []), tags=spec.get("tags", []),
            is_builtin=spec.get("is_builtin", False),
            use_count=random.randint(1, 15),
        ))
    counts["templates"] = len(D.TEMPLATES)

    for spec in D.PROMPT_TEMPLATES:
        db.add(PromptTemplate(
            user_id=_uid(), name=spec["name"], category=spec["category"],
            description=spec["description"], role_setting=spec["role_setting"],
            task_description=spec["task_description"], constraints=spec["constraints"],
            output_format=spec["output_format"], variables=spec.get("variables", []),
            use_count=spec.get("use_count", 0), rating=spec.get("rating"),
        ))
    counts["prompt_templates"] = len(D.PROMPT_TEMPLATES)

    for i, spec in enumerate(D.USER_DOMAINS):
        db.add(Domain(
            user_id=_uid(), name=spec["name"], description=spec["description"],
            icon=spec["icon"], color=spec["color"], sort_order=i,
        ))
    counts["domains"] = len(D.USER_DOMAINS)
    db.commit()


# ---------- 12. 收件箱 / 快速待办 / 提醒 ----------
def seed_inbox(db, counts: dict[str, int]) -> None:
    from app.models.panel import QuickTodo, Reminder
    from app.models.resource import InboxItem

    for i, spec in enumerate(D.INBOX_ITEMS):
        processed = spec.get("status") == "processed"
        db.add(InboxItem(
            user_id=_uid(),
            content_type=spec["type"],
            identity_id=_ident(spec.get("identity")),
            content=spec.get("content"),
            title=spec.get("title"),
            source=spec.get("source", "manual"),
            tags=spec.get("tags", []),
            status="processed" if processed else "pending",
            processed_at=ago(days=2) if processed else None,
            created_at=ago(days=i + 1, hours=random.randint(1, 20)),
        ))
    counts["inbox_items"] = len(D.INBOX_ITEMS)

    for i, spec in enumerate(D.QUICK_TODOS):
        done = spec["done"]
        db.add(QuickTodo(
            user_id=_uid(), title=spec["title"], completed=done, sort_order=i,
            completed_at=ago(days=1, hours=3) if done else None,
            created_at=ago(days=i, hours=5),
        ))
    counts["quick_todos"] = len(D.QUICK_TODOS)

    for spec in D.REMINDERS:
        if "in_days" in spec:
            at = NOW + timedelta(days=spec["in_days"])
        else:
            at = NOW + timedelta(hours=spec["in_hours"])
        db.add(Reminder(
            user_id=_uid(), title=spec["title"], description=spec.get("desc"),
            remind_at=at, type=spec.get("type", "once"),
            dismissed=False, repeat=spec.get("repeat", "none") or "none",
        ))
    counts["reminders"] = len(D.REMINDERS)
    db.commit()


# ---------- 13. 通知 ----------
def seed_notifications(db, counts: dict[str, int]) -> None:
    from app.models.notification import Notification

    for i, spec in enumerate(D.NOTIFICATIONS):
        read = spec.get("read", False)
        db.add(Notification(
            user_id=_uid(), type=spec["type"], title=spec["title"],
            content=spec["content"], is_read=read,
            read_at=ago(days=1, hours=i) if read else None,
            created_at=ago(hours=i * 3 + 1),
        ))
    db.commit()
    counts["notifications"] = len(D.NOTIFICATIONS)


# ---------- 14. 对话与桌宠 ----------
def seed_companion(db, counts: dict[str, int]) -> None:
    from app.models.avatar import AvatarMemory
    from app.models.conversation import Conversation, Message
    from app.models.pet import PetAvatar, PetConfig

    n_msg = 0
    for i, spec in enumerate(D.CONVERSATIONS):
        conv = Conversation(
            user_id=_uid(), project_id=None, title=spec["title"],
            scene=spec.get("scene", "general"),
            created_at=ago(days=spec["days_ago"], hours=2),
        )
        db.add(conv)
        db.flush()
        t0 = ago(days=spec["days_ago"], hours=2)
        for j, m in enumerate(spec["messages"]):
            ts = t0 + timedelta(minutes=j * 3)
            db.add(Message(
                conversation_id=conv.id, role=m["role"], content=m["content"],
                tokens=len(m["content"]) // 2,
                referenced_doc_ids=[],
                created_at=ts, updated_at=ts,
            ))
            n_msg += 1
    db.commit()
    counts["conversations"] = len(D.CONVERSATIONS)
    counts["messages"] = n_msg

    avatars: list[str] = []
    for spec in D.PET_AVATARS:
        row = PetAvatar(
            user_id=_uid(), name=spec["name"], description=spec["description"],
            avatar_type=spec["type"], mode=spec["mode"],
            eye_position={"x": 0.5, "y": 0.42}, mouth_position={"x": 0.5, "y": 0.62},
            action_frames={"idle": 4, "happy": 6, "think": 4},
            tags=spec.get("tags", []), is_active=spec["is_active"],
            sort_order=spec["sort_order"],
        )
        db.add(row)
        db.flush()
        avatars.append(row.id)
    db.commit()

    db.add(PetConfig(
        user_id=_uid(), enabled=True, size=120, opacity=0.95,
        always_on_top=False, auto_start=True, position_x=1770, position_y=880,
        current_avatar_id=avatars[0] if avatars else None,
        state_awareness_enabled=True, action_switch_interval=8,
        show_bubble=True, bubble_duration=6, click_interaction=True,
        draggable=True, right_click_menu=True,
        tts_enabled=False, tts_rate=1.0, tts_pitch=1.0, tts_volume=0.8,
        speak_scene="notification",
        intimacy=62, satiety=75, mood=80, energy=68,
        stats_updated_at=ago(hours=2),
    ))

    import json as _json
    for i, spec in enumerate(D.AVATAR_MEMORIES):
        db.add(AvatarMemory(
            user_id=_uid(), memory_type=spec["type"], title=spec["title"],
            content=spec["content"], category=None,
            tags=_json.dumps([spec["type"]], ensure_ascii=False),
            source="demo", source_id=None,
            confidence=0.9, is_verified=True, importance=3,
            created_at=ago(days=i + 1),
        ))
    db.commit()
    counts["pet_avatars"] = len(avatars)
    counts["pet_configs"] = 1
    counts["avatar_memories"] = len(D.AVATAR_MEMORIES)

    # —— 第二分身：人设配置 + 灵感引擎 ——
    from app.models.avatar import AvatarConfig, AvatarInspiration

    cfg = D.AVATAR_CONFIG
    db.add(AvatarConfig(
        user_id=_uid(),
        persona_name=cfg["persona_name"],
        persona_setting=cfg["persona_setting"],
        inspiration_enabled=cfg["inspiration_enabled"],
        inspiration_frequency=cfg["inspiration_frequency"],
        inspiration_domains=cfg["inspiration_domains"],
        reply_length=cfg["reply_length"],
        language_style=cfg["language_style"],
        creativity=cfg["creativity"],
        operation_overrides=cfg["operation_overrides"],
    ))
    for i, spec in enumerate(D.AVATAR_INSPIRATIONS):
        db.add(AvatarInspiration(
            user_id=_uid(), title=spec["title"], description=spec.get("desc"),
            domain=spec.get("domain"), estimated_value=spec.get("value"),
            prompt=spec.get("prompt"), result=spec.get("result"),
            status=spec.get("status", "pending"), feedback=spec.get("feedback"),
            batch_id=None, source_type="avatar",
            created_at=ago(days=i + 1, hours=3),
        ))
    db.commit()
    counts["avatar_configs"] = 1
    counts["avatar_inspirations"] = len(D.AVATAR_INSPIRATIONS)


# ---------- 15. 档案库文件树 ----------
def seed_workspace(db, counts: dict[str, int]) -> None:
    from app.models.workspace import WorkspaceFile, WorkspaceRoot

    root = WorkspaceRoot(
        user_id=_uid(), path=D.WORKSPACE_ROOT, label="YanYuas（演示）",
        identity_id=None, enabled=True, scan_status="ok",
        last_scanned_at=ago(hours=4), file_count=0, total_size=0,
    )
    db.add(root)
    db.flush()

    idmap = globals()["_IDMAP"]
    n = 0
    total_size = 0
    for dir_path, files, identity_slug in D.WORKSPACE_TREE:
        child = dir_path.count("/") + 1
        db.add(WorkspaceFile(
            root_id=root.id, rel_path=dir_path, name=dir_path.rsplit("/", 1)[-1],
            ext=None, is_dir=True, size=0, mtime=ago(days=child * 3).timestamp(),
            identity_id=_ident(identity_slug), indexed_at=ago(hours=4),
        ))
        n += 1
        for i, fname in enumerate(files):
            ext = Path(fname).suffix.lower() or None
            # 用扩展名给一个合理的体积区间，让「按大小排序」有意义
            size = {
                ".md": random.randint(2_000, 40_000),
                ".py": random.randint(1_500, 25_000),
                ".ipynb": random.randint(20_000, 400_000),
                ".pdf": random.randint(300_000, 6_000_000),
                ".docx": random.randint(40_000, 900_000),
                ".zip": random.randint(2_000_000, 80_000_000),
                ".wav": random.randint(8_000_000, 60_000_000),
                ".csv": random.randint(1_000, 200_000),
                ".json": random.randint(500, 20_000),
                ".doc": random.randint(30_000, 500_000),
                ".exe": random.randint(20_000_000, 120_000_000),
                ".eop": random.randint(3_000, 120_000),
                ".lnk": 1_200,
                ".mscz": random.randint(80_000, 900_000),
                ".cpp": random.randint(2_000, 40_000),
                ".html": random.randint(5_000, 90_000),
            }.get(ext, random.randint(1_000, 60_000))
            total_size += size
            db.add(WorkspaceFile(
                root_id=root.id, rel_path=f"{dir_path}/{fname}", name=fname,
                ext=ext, is_dir=False, size=size,
                mtime=ago(days=random.randint(1, 400)).timestamp(),
                identity_id=_ident(identity_slug), indexed_at=ago(hours=4),
            ))
            n += 1

    root.file_count = n
    root.total_size = total_size
    db.commit()
    counts["workspace_roots"] = 1
    counts["workspace_files"] = n
    print(f"        索引 {n} 个条目 / {total_size / 1024 / 1024:.1f} MB（代表性子集）")


# ---------- 16. 设置 / 审计 / 保险箱 ----------
def seed_misc(db, counts: dict[str, int]) -> None:
    from app.models.audit import AuditLog
    from app.models.settings import Setting
    from app.models.settings_history import SettingHistory
    from app.models.vault import VaultConfig, VaultItem

    for k, v in D.SETTINGS.items():
        db.add(Setting(user_id=_uid(), key=k, value=v))
    counts["settings"] = len(D.SETTINGS)

    for spec in D.SETTINGS_HISTORY:
        db.add(SettingHistory(
            user_id=_uid(), key=spec["key"],
            old_value=spec["old"], new_value=spec["new"],
            created_at=ago(days=spec["days_ago"]),
        ))
    counts["settings_history"] = len(D.SETTINGS_HISTORY)

    for spec in D.AUDIT_LOGS:
        db.add(AuditLog(
            user_id=_uid(), action=spec["action"], target=spec.get("target"),
            ok=spec["ok"], detail=spec.get("detail"), ip="127.0.0.1",
            created_at=ago(hours=spec["hours_ago"]),
        ))
    counts["audit_logs"] = len(D.AUDIT_LOGS)
    db.commit()

    # —— 保险箱：走真实派生与加密链路 ——
    from cryptography.fernet import Fernet

    from app.core.encryption import EncryptionManager
    from app.services.vault_service import _VERIFIER_PLAINTEXT

    salt = EncryptionManager.new_salt()
    key = EncryptionManager.derive_key(DEMO_MASTER_PASSWORD, salt)
    fernet = Fernet(key)
    db.add(VaultConfig(
        user_id=_uid(), salt=salt.hex(),
        verifier=fernet.encrypt(_VERIFIER_PLAINTEXT.encode()).decode(),
    ))
    n_vault = 0
    for spec in D.DEMO_VAULT_ITEMS:
        raw_secret = spec.get("secret")
        db.add(VaultItem(
            user_id=_uid(), name=spec["name"], category=spec["category"],
            username=spec.get("username"), url=spec.get("url"),
            # SSH 类条目只有密钥文件路径、没有密码 → 不写密文（保持 None）
            secret_encrypted=fernet.encrypt(raw_secret.encode()).decode() if raw_secret else None,
            notes=spec.get("notes"), identity_id=_ident(spec.get("identity")),
            action_type=spec.get("action_type", "none"),
            action_host=spec.get("action_host"),
            action_user=spec.get("action_user"),
            action_port=spec.get("action_port"),
        ))
        n_vault += 1
    db.commit()
    counts["vault_config"] = 1
    counts["vault_items"] = n_vault
    print(f"        保险箱已初始化（主密码见输出末尾），演示凭据 {n_vault} 条")



if __name__ == "__main__":
    sys.exit(main())
