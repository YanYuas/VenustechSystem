# ============================================================
# 仪表盘聚合服务（PRD §13.7 / M1 首页 + 参考UI模块丰富度）
# 已实现模块返回真实数据，待开发模块返回占位+status="planned"
# ============================================================
from __future__ import annotations

import logging
from datetime import date, datetime

from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.utils import greeting_by_hour, local_day_bounds_utc
from app.models.user import User
from app.repositories import DocumentRepository, TaskRepository
from app.repositories import (
    DomainRepository,
    FlashcardRepository,
    HabitRepository,
    InboxItemRepository,
    ProjectMemoryRepository,
    PromptRepository,
    SkillRepository,
    SOPRepository,
    TemplateRepository,
)
from app.schemas.dashboard import (
    StreakData,
    WeekProgress,
    AIAssistantStatus,
    AssetsSection,
    AssetCategory,
    DashboardDataOut,
    DashboardUser,
    ExecutionGroup,
    IdentitiesSection,
    IdentityProgress,
    LearningSection,
    LearningItem,
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
from app.services.resource_service import ResourceService
from app.services.learning_service import LearningService
from app.services.life_service import LifeService
from app.services.asset_service import AssetService

logger = logging.getLogger("app.dashboard")


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
# 修复 R-02（2026-09-15）：三个"新建"入口原先只跳到列表页，用户还得再点一次"新建"
# 按钮 —— 点了"新建"却没新建。现在带上 ?action=new，由列表页的 useQueryAction
# 消费后直接打开新建弹窗。非新建类入口（收集箱/工作流等）保持纯路由跳转。
QUICK_ACTIONS = [
    QuickAction(id="new_task", name="新建任务", icon="plus", action="/tasks?action=new"),
    QuickAction(id="new_doc", name="新建笔记", icon="doc", action="/documents?action=new"),
    QuickAction(id="new_project", name="新建项目", icon="folder", action="/projects?action=new", status="ready"),
    QuickAction(id="inbox", name="收集箱", icon="inbox", action="/resource-center", status="ready"),
    QuickAction(id="workflow", name="工作流", icon="workflow", action="/workflows", status="ready"),
    QuickAction(id="avatar", name="第二分身", icon="robot", action="/avatar", status="ready"),
    QuickAction(id="aihot", name="AI 资讯", icon="spark", action="/aihot", status="ready"),
    QuickAction(id="pet", name="桌宠设置", icon="pet", action="/pet", status="ready"),
    QuickAction(id="voice", name="语音记录", icon="mic", action="voice_record", status="planned"),
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
        self.resource_svc = ResourceService(db)
        self.learning_svc = LearningService(db)
        self.life_svc = LifeService(db)
        self.asset_svc = AssetService(db)
        # 计数直连 Repository：首页只需要"数量"的模块走 COUNT。
        # 原先用 list_x(page=1, page_size=1)["total"] 取值，paginate 会执行
        # SELECT + COUNT 两条 SQL 并 hydrated 1 行 ORM 对象，纯粹为读一个数字。
        self.inbox_repo = InboxItemRepository(db)
        self.template_repo = TemplateRepository(db)
        self.domain_repo = DomainRepository(db)
        self.flashcard_repo = FlashcardRepository(db)
        self.habit_repo = HabitRepository(db)
        self.sop_repo = SOPRepository(db)
        self.prompt_repo = PromptRepository(db)
        self.skill_repo = SkillRepository(db)
        self.memory_repo = ProjectMemoryRepository(db)

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
        today_execution = self._build_today_execution(all_tasks, today)

        # 身份进度（三期 B：复用 all_tasks 内存聚合，不新增查询）
        identities_section = self._build_identities(all_tasks, day_start, day_end)

        # 当前项目（内存分组，复用 all_tasks）
        projects = self._build_projects(all_tasks)

        # 资源中心（真实数据）
        try:
            inbox_count = self.inbox_repo.count(user_id=self.user.id, status="pending")
            template_count = self.template_repo.count(user_id=self.user.id)
            domain_count = self.domain_repo.count(user_id=self.user.id)
            resource_categories = [
                ResourceCategory(id="inbox", name="收集箱", count=inbox_count, icon="inbox"),
                ResourceCategory(id="template", name="模板库", count=template_count, icon="layout"),
                ResourceCategory(id="domain", name="领域库", count=domain_count, icon="book"),
            ]
            resource_center = ResourceCenter(categories=resource_categories, status="ready")
        except Exception:
            # 降级为占位（前端会显示为「待开发」）。必须打日志，否则模块真实报错
            # 会被伪装成"功能未上线"，掩盖 bug。
            logger.warning("资源中心数据聚合失败，降级为占位", exc_info=True)
            resource_center = ResourceCenter(categories=RESOURCE_CATEGORIES, status="planned")

        # 学习成长（真实数据）
        try:
            plans_data = self.learning_svc.list_plans(self.user.id, page=1, page_size=3)
            card_count = self.flashcard_repo.count_by_user(self.user.id)
            today_review = self.flashcard_repo.count_due_today(self.user.id, date.today())
            plan_items = [
                LearningItem(id=p["id"], title=p["name"], progress=p.get("progress", 0), type="plan")
                for p in plans_data["list"]
            ]
            today_item = LearningItem(
                id="today", title=f"今日复习 {today_review} 张",
                progress=0, type="review"
            ) if today_review > 0 else None
            learning = LearningSection(
                status="ready",
                today_study=today_item,
                plans=plan_items,
                cards_count=card_count,
            )
        except Exception:
            logger.warning("学习成长数据聚合失败，降级为占位", exc_info=True)
            learning = LearningSection(status="planned")

        # 生活记录（真实数据）
        try:
            habit_count = self.habit_repo.count(user_id=self.user.id)
            mood_stats = self.life_svc.get_mood_stats(self.user.id, days=7)
            avg_score = mood_stats.get('avg_score', 0)
            mood_value = f"近7天均分{avg_score:.1f}" if mood_stats.get('count', 0) > 0 else "暂无记录"
            life_categories = [
                LifeCategory(id="habit", name=f"习惯 {habit_count}项", value="坚持打卡", icon="activity"),
                LifeCategory(id="mood", name="心情", value=mood_value, icon="heart"),
                LifeCategory(id="diary", name="日记", value="记录生活点滴", icon="book"),
                LifeCategory(id="growth", name="成长", value="每天进步一点点", icon="trending-up"),
            ]
            life = LifeSection(categories=life_categories, status="ready")
        except Exception:
            logger.warning("生活记录数据聚合失败，降级为占位", exc_info=True)
            life = LifeSection(categories=LIFE_CATEGORIES, status="planned")

        # 长期资产库（真实数据）
        try:
            sop_count = self.sop_repo.count(user_id=self.user.id)
            prompt_count = self.prompt_repo.count(user_id=self.user.id)
            skill_count = self.skill_repo.count(user_id=self.user.id)
            memory_count = self.memory_repo.count(user_id=self.user.id)
            asset_categories = [
                AssetCategory(id="sop", name="SOP", count=sop_count, icon="book"),
                AssetCategory(id="prompt", name="Prompt", count=prompt_count, icon="sparkles"),
                AssetCategory(id="skill", name="Skill", count=skill_count, icon="zap"),
                AssetCategory(id="memory", name="项目记忆", count=memory_count, icon="database"),
            ]
            assets = AssetsSection(categories=asset_categories, status="ready")
        except Exception:
            logger.warning("长期资产库数据聚合失败，降级为占位", exc_info=True)
            assets = AssetsSection(categories=ASSET_CATEGORIES, status="planned")

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
            identities=identities_section,
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

    # 优先级排序权重（数值越小越靠前）
    _PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}

    def _build_identities(
        self, all_tasks: list, day_start, day_end
    ) -> IdentitiesSection:
        """身份进度区（三期 B）。

        回答「我在推进哪一条线」：每个身份一行，看未完成任务数、
        进行中、今日完成。数据全部来自已加载的 all_tasks（内存过滤），
        身份列表一次查询 —— 不为聚合新增 N 次任务查询。
        """
        from app.repositories import IdentityRepository

        rows = IdentityRepository(self.db).list_user(self.user.id, include_archived=True)
        items: list[IdentityProgress] = []
        for r in rows:
            ts = [t for t in all_tasks if t.identity_id == r.id]
            items.append(
                IdentityProgress(
                    id=r.id, name=r.name, slug=r.slug,
                    color_token=r.color_token, icon=r.icon,
                    open_tasks=sum(1 for t in ts if t.status != "completed"),
                    in_progress=sum(1 for t in ts if t.status == "in_progress"),
                    completed_today=sum(
                        1 for t in ts
                        if t.status == "completed" and t.completed_at
                        and day_start <= t.completed_at < day_end
                    ),
                    is_archived=not r.is_active,
                )
            )
        unassigned_open = sum(
            1 for t in all_tasks
            if t.identity_id is None and t.status != "completed"
        )
        return IdentitiesSection(items=items, unassigned_open=unassigned_open)

    @staticmethod
    def _is_actionable_today(t, today: date) -> bool:
        """任务今天是否需要动手。

        - 进行中 / 等待处理：本身就代表"当下正在处理"，无论截止日期
        - 待办：仅当已到期（今日到期或已逾期）才算今日执行；
          无截止日期的待办属于"以后再说"，不计入
        """
        if t.status in ("in_progress", "waiting"):
            return True
        if t.status == "pending":
            return t.due_date is not None and t.due_date <= today
        return False

    def _build_today_execution(self, all_tasks: list, today: date) -> TodayExecution:
        """今日执行：按状态分组。

        2026-09-15 修正两处缺陷：
        1. 原实现 total=len(all_tasks)、分组 count=全体同状态任务数，与"今日执行"
           语义不符，且与 today_stats.must_do 口径矛盾（同屏一个数今日、一个数全部，
           用户看到的"共 N 项"远大于分组之和）。
           → 现在只统计"今天需要动手"的任务，且 total === 各分组 count 之和。
        2. 原实现无排序，取"前 5 条"是数据库返回的任意顺序，逾期任务可能被挤掉。
           → 现在逾期优先、其次今日到期，再按优先级。
        """
        actionable = [t for t in all_tasks if self._is_actionable_today(t, today)]

        def sort_key(t):
            # 0=已逾期（最紧急） 1=今日到期 2=无截止日期 3=未来到期
            if t.due_date is None:
                urgency = 2
            elif t.due_date < today:
                urgency = 0
            elif t.due_date == today:
                urgency = 1
            else:
                urgency = 3
            return (urgency, self._PRIORITY_RANK.get(t.priority, 1), t.due_date or date.max)

        actionable.sort(key=sort_key)

        groups_map = {
            "pending": {"label": "必须完成", "tasks": []},
            "in_progress": {"label": "进行中", "tasks": []},
            "waiting": {"label": "等待处理", "tasks": []},
        }
        counts = dict.fromkeys(groups_map, 0)

        for t in actionable:
            if t.status not in groups_map:
                continue
            counts[t.status] += 1
            if len(groups_map[t.status]["tasks"]) < 5:
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
                count=counts[status],
                tasks=info["tasks"],
            )
            for status, info in groups_map.items()
        ]
        return TodayExecution(groups=groups, total=sum(counts.values()))

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
            # 降级到 project_tag 聚合属预期路径（老数据无 project_id），但失败原因仍需可观测。
            logger.warning("Project 实体加载失败，降级为 project_tag 聚合", exc_info=True)

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

        return ProjectsSection(items=items, status="planned")


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