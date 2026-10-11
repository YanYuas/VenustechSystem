# ============================================================
# 测试数据工厂
#
# 两种用法：
#   1. Service 层单元测试：传入 db_session，直接造 ORM 对象
#      task = make_task(db_session, title="xxx", status="in_progress")
#
#   2. API 层集成测试：传入 client，通过 HTTP 造数据
#      task = make_task_via_api(client, title="xxx")
#
# 工厂只负责「造一条最小可用数据」，不做断言。
# 每个工厂返回创建后的对象 / 响应 data 字段。
# ============================================================
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# ============================================================
# Task 相关工厂（Service 层，直接写 ORM）
# ============================================================
def make_task(
    db: "Session",
    user_id: str,
    *,
    title: str = "测试任务",
    status: str = "pending",
    priority: str = "medium",
    description: str | None = None,
    project_tag: str | None = None,
    project_id: str | None = None,
    due_date=None,
    is_focus: bool = False,
    recurrence: dict | None = None,
):
    """直接在 db 中创建一条 Task，返回 ORM 对象（已 flush，未 commit）。"""
    from app.models.task import Task

    task = Task(
        user_id=user_id,
        title=title,
        status=status,
        priority=priority,
        description=description,
        project_tag=project_tag,
        project_id=project_id,
        due_date=due_date,
        is_focus=is_focus,
        recurrence=recurrence,
    )
    db.add(task)
    db.flush()
    return task


def make_document(
    db: "Session",
    user_id: str,
    *,
    title: str = "测试文档",
    content: str | None = None,
    folder_id: str | None = None,
    tags: list | None = None,
    project_id: str | None = None,
    identity_id: str | None = None,
):
    """直接在 db 中创建一条 Document，返回 ORM 对象（已 flush，未 commit）。"""
    from app.models.document import Document

    doc = Document(
        user_id=user_id,
        title=title,
        content=content,
        folder_id=folder_id,
        tags=tags or [],
        project_id=project_id,
        identity_id=identity_id,
        word_count=len(content.replace(" ", "")) if content else 0,
    )
    db.add(doc)
    db.flush()
    return doc


def make_subtask(
    db: "Session",
    task_id: str,
    *,
    title: str = "子任务",
    completed: bool = False,
    sort_order: int = 0,
):
    """直接在 db 中创建一条 Subtask，返回 ORM 对象（已 flush）。"""
    from app.models.task import Subtask

    sub = Subtask(
        task_id=task_id,
        title=title,
        completed=completed,
        sort_order=sort_order,
    )
    db.add(sub)
    db.flush()
    return sub


def make_focus_session(
    db: "Session",
    user_id: str,
    task_id: str,
    *,
    start_time=None,
    end_time=None,
    duration: int = 0,
):
    """直接在 db 中创建一条 FocusSession，返回 ORM 对象（已 flush）。"""
    from datetime import datetime, timezone

    from app.models.task import FocusSession
    from app.models.base import utcnow

    session = FocusSession(
        user_id=user_id,
        task_id=task_id,
        start_time=start_time or utcnow(),
        end_time=end_time,
        duration=duration,
    )
    db.add(session)
    db.flush()
    return session


# ============================================================
# Task 相关工厂（API 层，通过 TestClient）
# ============================================================
def make_task_via_api(client, *, title: str = "API测试任务", **kwargs):
    """通过 POST /api/v1/tasks 创建任务，返回响应 data 字段。"""
    payload = {"title": title}
    payload.update(kwargs)
    r = client.post("/api/v1/tasks", json=payload)
    assert r.status_code == 200, f"创建任务失败: {r.text}"
    return r.json()["data"]


def make_subtask_via_api(client, task_id: str, *, title: str = "API子任务"):
    """通过 POST /api/v1/tasks/{id}/subtasks 创建子任务，返回响应 data。"""
    r = client.post(f"/api/v1/tasks/{task_id}/subtasks", json={"title": title})
    assert r.status_code == 200, f"创建子任务失败: {r.text}"
    return r.json()["data"]


# ============================================================
# 通用工具
# ============================================================
def count_rows(db: "Session", table_name: str, **where) -> int:
    """统计指定表行数（可选过滤条件）。用于断言副作用。"""
    from sqlalchemy import func, select, text

    query = select(func.count()).select_from(text(table_name))
    for col, val in where.items():
        query = query.where(text(f"{table_name}.{col} = :{col}")).params(**{col: val})
    return int(db.scalar(query))


# ============================================================
# 生产级夹具：真实业务形态的任务集
#
# 形状契约（写死，断言靠它）：
#   · 10 条任务：pending 3 / in_progress 2 / waiting 2 / completed 3
#   · 优先级：urgent 1 / high 2 / medium 5 / low 2
#   · 7 条子任务：分属 3 条任务（3+2+2），其中 3 条已完成
#   · 1 条焦点任务（pending, high, 带截止日=今天）
#   · 2 条带截止日（今天、明天）
#   · 1 条 daily 重复任务（due_date=昨天，用于测惰性生成）
#   · 1 条 completed 任务带 completed_at
# ============================================================
def seed_task_fixture(db: "Session", user_id: str) -> dict:
    """造一份真实业务形态的任务集，返回各任务的引用（按语义命名）。

    为什么不用 make_task 循环造：每条任务的字段组合是有业务含义的
    （比如"焦点任务必须是 high + 今天截止"），循环造不出这种形态。
    """
    from datetime import date, timedelta

    from app.models.base import utcnow
    from app.models.task import Subtask, Task

    today = date.today()
    tasks = {}

    # ── pending 3 条 ──
    tasks["focus_pending"] = Task(
        user_id=user_id, title="今日最重要（写周报）", status="pending",
        priority="high", description="本周完成度汇总 + 下周计划",
        due_date=today, is_focus=True,
        estimated_minutes=60, acceptance_criteria="周报提交且导师回复",
    )
    tasks["pending_medium_no_due"] = Task(
        user_id=user_id, title="整理数模论文分类", status="pending",
        priority="medium", project_tag="数学建模",
    )
    tasks["pending_low_tomorrow"] = Task(
        user_id=user_id, title="买洗衣液", status="pending",
        priority="low", due_date=today + timedelta(days=1),
    )

    # ── in_progress 2 条 ──
    tasks["in_progress_high"] = Task(
        user_id=user_id, title="最小覆盖圆论文 v9.9.0 修订", status="in_progress",
        priority="high", project_tag="科研",
        description="补灵敏度分析章节",
        estimated_minutes=120,
    )
    tasks["in_progress_medium_recurring"] = Task(
        user_id=user_id, title="每日英语阅读", status="in_progress",
        priority="medium", recurrence={"type": "daily", "interval": 1},
        due_date=today - timedelta(days=1),  # 昨天到期，用于测重复生成
    )

    # ── waiting 2 条 ──
    tasks["waiting_medium"] = Task(
        user_id=user_id, title="等导师反馈选题", status="waiting",
        priority="medium", project_tag="科研",
    )
    tasks["waiting_low"] = Task(
        user_id=user_id, title="等快递（显示器支架）", status="waiting",
        priority="low",
    )

    # ── completed 3 条 ──
    tasks["completed_urgent"] = Task(
        user_id=user_id, title="提交成绩复核申请", status="completed",
        priority="urgent", completed_at=utcnow(),
    )
    tasks["completed_medium_with_subs"] = Task(
        user_id=user_id, title="搭建测试体系", status="completed",
        priority="medium", completed_at=utcnow(),
    )
    tasks["completed_medium"] = Task(
        user_id=user_id, title="修复 venv 环境", status="completed",
        priority="medium", completed_at=utcnow(),
    )

    for t in tasks.values():
        db.add(t)
    db.flush()

    # ── 子任务 7 条：分属 3 条任务 ──
    subtasks = {}
    # "搭建测试体系" 带 3 条子任务（2完成+1未完成）
    subs_build = [
        ("写 conftest 夹具", True, 0),
        ("写 factories 工厂", True, 1),
        ("写 task 用例", False, 2),
    ]
    for i, (title, done, order) in enumerate(subs_build):
        s = Subtask(task_id=tasks["completed_medium_with_subs"].id,
                    title=title, completed=done, sort_order=order)
        db.add(s)
        subtasks[f"build_{i}"] = s

    # "最小覆盖圆论文" 带 2 条子任务（1完成+1未完成）
    subs_paper = [
        ("查 CGTA 投稿格式", True, 0),
        ("写灵敏度分析", False, 1),
    ]
    for i, (title, done, order) in enumerate(subs_paper):
        s = Subtask(task_id=tasks["in_progress_high"].id,
                    title=title, completed=done, sort_order=order)
        db.add(s)
        subtasks[f"paper_{i}"] = s

    # "整理数模论文分类" 带 2 条未完成子任务
    subs_math = [
        ("按优化模型分类", False, 0),
        ("按评价模型分类", False, 1),
    ]
    for i, (title, done, order) in enumerate(subs_math):
        s = Subtask(task_id=tasks["pending_medium_no_due"].id,
                    title=title, completed=done, sort_order=order)
        db.add(s)
        subtasks[f"math_{i}"] = s

    db.flush()
    return {"tasks": tasks, "subtasks": subtasks}


# 夹具形状契约常量（断言用，避免魔法数字散落各处）
FIXTURE_TASK_COUNT = 10
FIXTURE_SUBTASK_COUNT = 7
FIXTURE_STATUS_COUNTS = {"pending": 3, "in_progress": 2, "waiting": 2, "completed": 3}
FIXTURE_PRIORITY_COUNTS = {"urgent": 1, "high": 2, "medium": 5, "low": 2}
FIXTURE_FOCUS_COUNT = 1
FIXTURE_RECURRING_COUNT = 1
FIXTURE_DUE_TODAY_COUNT = 1


# ============================================================
# 生产级夹具：真实业务形态的文档集
#
# 形状契约：
#   · 2 个自定义文件夹（数学建模 / 科研笔记）+ 1 个收集箱（自动创建）
#   · 5 篇文档：收集箱 3 / 数学建模 1 / 科研笔记 1
#   · 标签：3 篇有标签，2 篇无标签
#   · 1 篇内容含 [[最小覆盖圆算法]] 链接（用于测反向链接）
#   · 1 篇关联 project_id
# ============================================================
def seed_document_fixture(db: "Session", user_id: str) -> dict:
    """造一份真实业务形态的文档集，返回各文档/文件夹的引用（按语义命名）。"""
    from app.models.document import Document
    from app.models.folder import Folder

    folders = {}
    folders["inbox"] = Folder(
        user_id=user_id, name="收集箱", is_inbox=True, sort_order=0,
    )
    folders["math_modeling"] = Folder(
        user_id=user_id, name="数学建模", sort_order=1,
    )
    folders["research"] = Folder(
        user_id=user_id, name="科研笔记", sort_order=2,
    )
    for f in folders.values():
        db.add(f)
    db.flush()

    docs = {}
    docs["classification_plan"] = Document(
        user_id=user_id, title="数模论文分类方案",
        content="参考 [[最小覆盖圆算法]] 的分类思路，按优化模型和评价模型分类。",
        folder_id=None,  # 收集箱
        tags=["数模", "整理"],
        word_count=20,
    )
    docs["mec_algorithm"] = Document(
        user_id=user_id, title="最小覆盖圆算法",
        content="Welzl 算法的增量维护优化，基于支撑点速度预测。",
        folder_id=folders["research"].id,
        tags=["算法", "科研"],
        word_count=18,
    )
    docs["algebra_notes"] = Document(
        user_id=user_id, title="高等代数笔记",
        content="线性空间的基与维数，Jordan 标准型。",
        folder_id=folders["math_modeling"].id,
        tags=["代数"],
        word_count=15,
    )
    docs["daily_essay"] = Document(
        user_id=user_id, title="每日随笔",
        content="今天学了很多东西。",
        folder_id=None,  # 收集箱
        tags=[],
        word_count=8,
    )
    docs["project_plan"] = Document(
        user_id=user_id, title="启明星系统三期计划",
        content="模块化优化，身份轴横切。",
        folder_id=None,  # 收集箱
        tags=[],
        word_count=12,
    )
    for d in docs.values():
        db.add(d)
    db.flush()

    return {"folders": folders, "docs": docs}


# 文档夹具形状契约常量
FIXTURE_DOCUMENT_COUNT = 5
FIXTURE_DOCUMENT_FOLDER_COUNT = 2  # 自定义文件夹（不含收集箱）
FIXTURE_DOCUMENT_TAGS_COUNT = 3    # 有标签的文档数


# ============================================================
# 身份 / 经历视图（S6-4）/ 人生报告（S6-5）工厂
#
# 四源：日记 diaries / 复盘 reviews / 分身记忆 avatar_memories /
#       项目记忆 project_memories —— 都不建「经历表」，只在读取时聚合。
# 工厂用**显式 naive datetime**（SQLite 落库后回来就是 naive UTC，见
# test_zz 探针实证），避免测试里混入 aware 造成不可比。
# ============================================================
def make_identity(
    db: "Session",
    user_id: str,
    *,
    name: str = "测试身份",
    slug: str | None = None,
    color_token: str = "primary",
    icon: str = "star",
    description: str | None = None,
    sort_order: int = 0,
    is_active: bool = True,
):
    """创建一条 Identity（默认启用）。slug 不传则用随机值避免唯一约束冲突。"""
    import uuid as _uuid

    from app.models.identity import Identity

    row = Identity(
        user_id=user_id, name=name, slug=slug or f"id-{_uuid.uuid4().hex[:8]}",
        color_token=color_token, icon=icon, description=description,
        sort_order=sort_order, is_active=is_active,
    )
    db.add(row)
    db.flush()
    return row


def make_diary(
    db: "Session",
    user_id: str,
    *,
    title: str | None = "测试日记",
    content: str | None = "日记正文",
    diary_date=None,
    dimension: str | None = None,
    identity_id: str | None = None,
):
    """创建一条 Diary（四维日记）。diary_date 不传则用今天。"""
    from datetime import date

    from app.models.life import Diary

    row = Diary(
        user_id=user_id, title=title, content=content,
        diary_date=diary_date or date.today(), dimension=dimension,
        identity_id=identity_id, tags=[],
    )
    db.add(row)
    db.flush()
    return row


def make_review(
    db: "Session",
    user_id: str,
    *,
    type_: str = "daily",
    review_date=None,
    data: dict | None = None,
    identity_id: str | None = None,
):
    """创建一条 Review。(user_id, type, review_date) 有唯一约束，注意别撞。"""
    from datetime import date

    from app.models.review import Review

    row = Review(
        user_id=user_id, type=type_, review_date=review_date or date.today(),
        data=data if data is not None else {"summary": "复盘摘要"},
        identity_id=identity_id,
    )
    db.add(row)
    db.flush()
    return row


def make_avatar_memory(
    db: "Session",
    user_id: str,
    *,
    title: str = "分身记忆",
    content: str | None = "记忆内容",
    memory_type: str = "event",
    category: str | None = None,
    identity_id: str | None = None,
    created_at=None,
):
    """创建一条 AvatarMemory。created_at 不传则用模型默认（utcnow）。"""
    from app.models.avatar import AvatarMemory

    kwargs = dict(
        user_id=user_id, title=title, content=content, memory_type=memory_type,
        category=category, identity_id=identity_id, tags=[],
    )
    if created_at is not None:
        kwargs["created_at"] = created_at
    row = AvatarMemory(**kwargs)
    db.add(row)
    db.flush()
    return row


def make_project_memory(
    db: "Session",
    user_id: str,
    *,
    name: str = "项目记忆",
    summary: str | None = "项目摘要",
    identity_id: str | None = None,
    project_id: str | None = None,
    created_at=None,
):
    """创建一条 ProjectMemory。created_at 不传则用模型默认（utcnow）。"""
    from app.models.asset import ProjectMemory

    kwargs = dict(
        user_id=user_id, name=name, summary=summary, identity_id=identity_id,
        project_id=project_id, tags=[], key_metrics={}, extracted_assets=[],
    )
    if created_at is not None:
        kwargs["created_at"] = created_at
    row = ProjectMemory(**kwargs)
    db.add(row)
    db.flush()
    return row


def seed_four_sources(
    db: "Session", user_id: str, *, identity_id: str | None = None, day_offset: int = 0,
):
    """四源各造一条（用于经历视图/报告的聚合断言），返回各条引用。

    形状契约（断言靠它）：
      · diary           occurred_at = base+0 00:00（取 diary_date）
      · review          occurred_at = base+1 00:00（取 review_date）
      · avatar_memory   occurred_at = base+2 12:00（取 created_at）
      · project_memory  occurred_at = base+3 12:00（取 created_at）
    归并降序应为：project_memory → avatar_memory → review → diary

    `day_offset` 用来给同一用户的多次调用错开日期 —— reviews 上有
    `UniqueConstraint(user_id, type, review_date)`，同一天同类型会直接
    撞唯一约束（实测 IntegrityError）。
    """
    from datetime import date, datetime, time, timedelta

    base = date(2026, 3, 1) + timedelta(days=day_offset)
    return {
        "diary": make_diary(
            db, user_id, title="日记标题", content="日记正文内容",
            diary_date=base, identity_id=identity_id,
        ),
        "review": make_review(
            db, user_id, type_="weekly", review_date=base + timedelta(days=1),
            data={"summary": "复盘摘要内容"}, identity_id=identity_id,
        ),
        "avatar_memory": make_avatar_memory(
            db, user_id, title="分身记忆标题", content="分身记忆内容",
            identity_id=identity_id,
            created_at=datetime.combine(base + timedelta(days=2), time(12, 0)),
        ),
        "project_memory": make_project_memory(
            db, user_id, name="项目记忆标题", summary="项目记忆摘要",
            identity_id=identity_id,
            created_at=datetime.combine(base + timedelta(days=3), time(12, 0)),
        ),
    }


# 四源归并降序的期望顺序（形状契约）
FIXTURE_EXPERIENCE_DESC_ORDER = ["project_memory", "avatar_memory", "review", "diary"]


def make_sop(db: "Session", user_id: str, *, name: str = "测试SOP", category: str | None = None):
    """创建一条 SOP（资产库 · 档案轴计数用）。"""
    from app.models.asset import SOP

    row = SOP(user_id=user_id, name=name, category=category,
              steps=[], checklist=[], tags=[])
    db.add(row)
    db.flush()
    return row


def make_prompt(db: "Session", user_id: str, *, name: str = "测试Prompt"):
    """创建一条 PromptTemplate。"""
    from app.models.asset import PromptTemplate

    row = PromptTemplate(user_id=user_id, name=name, variables=[])
    db.add(row)
    db.flush()
    return row


def make_skill(db: "Session", user_id: str, *, name: str = "测试Skill",
               proficiency: str = "beginner"):
    """创建一条 Skill。"""
    from app.models.asset import Skill

    row = Skill(user_id=user_id, name=name, proficiency=proficiency, tags=[])
    db.add(row)
    db.flush()
    return row


def make_workspace_root(
    db: "Session",
    user_id: str,
    *,
    path: str = "D:/tmp/ws-test",
    label: str | None = "测试根",
    identity_id: str | None = None,
    enabled: bool = True,
    file_count: int = 0,
    total_size: int = 0,
):
    """创建一条 WorkspaceRoot（不触发任何磁盘扫描）。"""
    from app.models.workspace import WorkspaceRoot

    row = WorkspaceRoot(
        user_id=user_id, path=path, label=label, identity_id=identity_id,
        enabled=enabled, file_count=file_count, total_size=total_size,
    )
    db.add(row)
    db.flush()
    return row
