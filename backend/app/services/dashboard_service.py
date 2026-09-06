# ============================================================
# 仪表盘聚合服务（PRD §13.7 / M1 首页 + 参考UI模块丰富度）
# 已实现模块返回真实数据，待开发模块返回占位+status="planned"
# ============================================================
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.utils import greeting_by_hour, local_day_bounds_utc
from app.models.user import User
from app.repositories import DocumentRepository, TaskRepository
from app.schemas.dashboard import (
    StreakData,
    WeekProgress,
    AIAssistantStatus,
    AssetsSection,
    AssetCategory,
    DashboardDataOut,
    DashboardUser,
    ExecutionGroup,
    LearningSection,
    LifeCategory,
    LifeSection,
    ModuleStatusItem,
    ProjectItem,
    ProjectsSection,
    QuickAction,
    QuickActions,
    RecentDocument,
    ResourceCategory,
    ResourceCenter,
    TodayExecution,
)
from app.schemas.task import TodayStatsOut
from app.services.task_service import TaskService


# ---------- 模块开发状态清单（供前端灰度判断） ----------
MODULES_STATUS = [
    ModuleStatusItem(id="dashboard", name="首页", status="ready", description="今日概览与聚焦"),
    ModuleStatusItem(id="tasks", name="任务", status="ready", description="任务管理与看板"),
    ModuleStatusItem(id="documents", name="知识", status="ready", description="文档与知识库"),
    ModuleStatusItem(id="conversation", name="第二分身", status="ready", description="AI对话与灵感"),
    ModuleStatusItem(id="review", name="复盘", status="ready", description="日周月复盘"),
    ModuleStatusItem(id="projects", name="项目", status="beta", description="项目聚合与进度"),
    ModuleStatusItem(id="resource_center", name="资源中心", status="beta", description="收集箱/领域库/模板库"),
    ModuleStatusItem(id="learning", name="学习与成长", status="beta", description="学习计划/知识卡片"),
    ModuleStatusItem(id="life", name="生活与自我", status="beta", description="健康/精力/习惯追踪"),
    ModuleStatusItem(id="assets", name="长期资产库", status="beta", description="SOP/Prompt/Skill沉淀"),
]

# ---------- 快速入口（配置化） ----------
QUICK_ACTIONS = [
    QuickAction(id="new_task", name="新建任务", icon="plus", action="/tasks"),
    QuickAction(id="new_doc", name="新建笔记", icon="doc", action="/documents"),
    QuickAction(id="new_project", name="新建项目", icon="folder", action="/projects", status="ready"),
    QuickAction(id="voice", name="语音记录", icon="mic", action="voice_record", status="planned"),
    QuickAction(id="inbox", name="收集箱", icon="inbox", action="resource_center_inbox", status="planned"),
]

# ---------- 资源中心占位（待开发） ----------
RESOURCE_CATEGORIES = [
    ResourceCategory(id="inbox", name="收集箱", count=0, icon="inbox"),
    ResourceCategory(id="domain", name="领域库", count=0, icon="book"),
    ResourceCategory(id="project_lib", name="项目库", count=0, icon="folder"),
    ResourceCategory(id="study", name="学习库", count=0, icon="graduation"),
    ResourceCategory(id="knowledge", name="知识库", count=0, icon="brain"),
    ResourceCategory(id="command", name="指令库", count=0, icon="terminal"),
    ResourceCategory(id="template", name="模板库", count=0, icon="layout"),
]

# ---------- 生活与自我占位（待开发） ----------
LIFE_CATEGORIES = [
    LifeCategory(id="family", name="家庭", value="陪伴是最好的礼物", icon="heart"),
    LifeCategory(id="health", name="健康", value="运动 + 睡眠 + 饮食", icon="activity"),
    LifeCategory(id="energy", name="精力", value="专注创造高质量输出", icon="zap"),
    LifeCategory(id="growth", name="成长", value="每天进步一点点", icon="trending-up"),
]

# ---------- 长期资产库占位（待开发） ----------
ASSET_CATEGORIES = [
    AssetCategory(id="sop", name="SOP", count=0, icon="book"),
    AssetCategory(id="prompt", name="Prompt", count=0, icon="message"),
    AssetCategory(id="skill", name="Skill", count=0, icon="award"),
    AssetCategory(id="memory", name="项目记忆", count=0, icon="database"),
]


class DashboardService:
    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user
        self.task_svc = TaskService(db)
        self.task_repo = TaskRepository(db)
        self.doc_repo = DocumentRepository(db)

    def get(self) -> DashboardDataOut:
        now = datetime.now()
        today = now.date()

        # 一次查询所有任务，内存分组（避免多次全量查询）
        all_tasks = self.task_repo.list_user_tasks(self.user.id)
        focus_task = next((t for t in all_tasks if t.is_focus), None)
        focus_out = self.task_svc._to_focus_out(focus_task) if focus_task else None

        # 今日统计（内存计算；completed_at 为 UTC，本地日边界须换算后比较）
        day_start, day_end = local_day_bounds_utc(today)
        today_stats = TodayStatsOut(
            must_do=sum(1 for t in all_tasks if t.due_date == today and t.status != "completed"),
            in_progress=sum(1 for t in all_tasks if t.status == "in_progress"),
            waiting=sum(1 for t in all_tasks if t.status == "waiting"),
            completed_today=sum(
                1 for t in all_tasks
                if t.status == "completed" and t.completed_at
                and day_start <= t.completed_at < day_end
            ),
        )

        # 最近文档
        recent_docs = [
            RecentDocument(
                id=d.id, title=d.title, updated_at=d.updated_at, tags=list(d.tags or [])
            )
            for d in self.doc_repo.recent(self.user.id, limit=5)
        ]

        # 今日执行（内存分组，复用 all_tasks）
        today_execution = self._build_today_execution(all_tasks)

        # 当前项目（内存分组，复用 all_tasks）
        projects = self._build_projects(all_tasks)

        # 待开发模块占位
        resource_center = ResourceCenter(categories=RESOURCE_CATEGORIES, status="beta")
        learning = LearningSection(status="beta")
        life = LifeSection(categories=LIFE_CATEGORIES, status="beta")
        assets = AssetsSection(categories=ASSET_CATEGORIES, status="beta")
        quick_actions = QuickActions(items=QUICK_ACTIONS)

        # 本周进度环（M01 F04）
        week_progress = self._build_week_progress(all_tasks)

        # 连续打卡徽章（M01 F05）
        streak = self._build_streak()
        # AI 助手状态
        settings = get_settings()
        ai_assistant = AIAssistantStatus(
            enabled=bool(self.user.api_key_encrypted) and self.user.ai_enabled,
            model=settings.ai_model,
            status="ready",
            quick_prompts=["帮我总结今天", "生成明日计划", "头脑风暴"],
        )

        return DashboardDataOut(
            focus_task=focus_out,
            today_stats=today_stats,
            recent_documents=recent_docs,
            user=DashboardUser(nickname=self.user.nickname, greeting=greeting_by_hour(now.hour)),
            today_execution=today_execution,
            projects=projects,
            resource_center=resource_center,
            learning=learning,
            life=life,
            assets=assets,
            quick_actions=quick_actions,
            week_progress=week_progress,
            streak=streak,
            ai_assistant=ai_assistant,
            modules_status=MODULES_STATUS,
        )

    def _build_today_execution(self, all_tasks: list) -> TodayExecution:
        """今日执行：按状态分组任务（取前5条，复用已查询的任务列表）"""
        groups_map = {
            "pending": {"label": "必须完成", "tasks": []},
            "in_progress": {"label": "进行中", "tasks": []},
            "waiting": {"label": "等待处理", "tasks": []},
        }
        for t in all_tasks:
            if t.status in groups_map and len(groups_map[t.status]["tasks"]) < 5:
                groups_map[t.status]["tasks"].append({
                    "id": t.id,
                    "title": t.title,
                    "priority": t.priority,
                    "due_date": t.due_date.isoformat() if t.due_date else None,
                })

        groups = [
            ExecutionGroup(
                status=status,
                label=info["label"],
                count=sum(1 for t in all_tasks if t.status == status),
                tasks=info["tasks"],
            )
            for status, info in groups_map.items()
        ]
        return TodayExecution(groups=groups, total=len(all_tasks))

    def _build_projects(self, all_tasks: list) -> ProjectsSection:
        """当前项目：优先使用真实 Project 实体，降级到 project_tag 聚合"""
        try:
            from app.services.project_service import ProjectService
            projects = ProjectService(self.db).list(self.user.id)
            items = []
            for p in projects[:5]:
                items.append(ProjectItem(
                    id=p["id"],
                    name=p["name"],
                    progress=p["progress"],
                    task_count=p["task_count"],
                    completed_count=p["completed_count"],
                    color=p.get("color", "#7c5cff"),
                    status="ready",
                ))
            if items:
                return ProjectsSection(items=items, status="ready")
        except Exception:
            pass

        # 降级：基于 project_tag 聚合
        project_map: dict[str, list] = {}
        for t in all_tasks:
            if t.project_tag:
                project_map.setdefault(t.project_tag, []).append(t)

        items = []
        for tag, tasks in sorted(project_map.items(), key=lambda x: -len(x[1]))[:3]:
            total = len(tasks)
            done = sum(1 for t in tasks if t.status == "completed")
            progress = round(done / total * 100) if total else 0
            items.append(ProjectItem(
                id=tag,
                name=tag,
                progress=progress,
                task_count=total,
                completed_count=done,
                status="beta",
            ))

        return ProjectsSection(items=items, status="beta")


    def _build_week_progress(self, all_tasks: list) -> WeekProgress:
        """本周任务完成进度（周一至周日）"""
        from datetime import timedelta
        today = datetime.now().date()
        monday = today - timedelta(days=today.weekday())
        sunday = monday + timedelta(days=6)
        week_tasks = [t for t in all_tasks if t.due_date and monday <= t.due_date <= sunday]
        total = len(week_tasks)
        completed = sum(1 for t in week_tasks if t.status == "completed")
        percentage = round(completed / total * 100) if total else 0
        return WeekProgress(completed=completed, total=total, percentage=percentage)

    def _build_streak(self) -> StreakData:
        """连续打卡：基于复盘记录统计连续天数 + 本周7天打卡情况"""
        from datetime import timedelta
        from sqlalchemy import select
        from app.models.review import Review

        today = datetime.now().date()
        # 查最近30天的复盘日期
        rows = self.db.scalars(
            select(Review.review_date).where(
                Review.user_id == self.user.id,
                Review.review_date >= today - timedelta(days=30),
            ).order_by(Review.review_date.desc())
        )
        review_dates = {r for r in rows if r}

        # 计算连续打卡天数（从今天往前数）
        streak_days = 0
        check_date = today
        while check_date in review_dates:
            streak_days += 1
            check_date -= timedelta(days=1)

        # 本周7天打卡情况（周一至周日）
        monday = today - timedelta(days=today.weekday())
        week_checkins = [(monday + timedelta(days=i)) in review_dates for i in range(7)]

        return StreakData(days=streak_days, week_checkins=week_checkins)