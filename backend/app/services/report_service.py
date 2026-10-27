# ============================================================
# 人生报告服务（S6-5 · 身份 × 成长 × 档案 三轴聚合）
#
# 只读聚合：从已有模块的表里数数，不新增任何写入。
# 前端把 ReportOut 渲染为单文件 HTML 供下载留存
# （内联样式、零外部依赖 —— 数据主权：报告归用户自己所有）。
#
# D-06 收口说明（聚合服务如何不直连 ORM）：
#   本服务是 insight 领域的**只读聚合器**，需要跨 7 个域取数。
#   收口后的规则是：跨域读也必须经各域 Repository 的公开方法，
#   service 里不再出现 select()/db.execute()。为此各域 repo 增补了
#   语义化方法（如 identity_counts / count_identity_unassigned /
#   count_by_user），本文件只做编排与组装。
# ============================================================
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.base import utcnow
from app.repositories import (
    AvatarMemoryRepository,
    DiaryRepository,
    DocumentRepository,
    IdentityRepository,
    ProjectMemoryRepository,
    PromptRepository,
    ReviewRepository,
    SOPRepository,
    SkillRepository,
    TaskRepository,
)
from app.schemas.report import (
    ArchiveAxis,
    ExperienceRecentItem,
    GrowthAxis,
    IdentityAxis,
    IdentityStat,
    ReportOut,
    SkillStatOut,
    UnassignedStat,
    WorkspaceRootStat,
)
from app.services.experience_service import SOURCE_LABELS, ExperienceService
from app.services.growth_service import GrowthService


class ReportService:
    def __init__(self, db: Session, user_id: str, nickname: str):
        self.db = db
        self.user_id = user_id
        self.nickname = nickname
        # 各域只读 Repository（跨域读的唯一入口）
        self.identity_repo = IdentityRepository(db)
        self.task_repo = TaskRepository(db)
        self.doc_repo = DocumentRepository(db)
        self.diary_repo = DiaryRepository(db)
        self.review_repo = ReviewRepository(db)
        self.avatar_memory_repo = AvatarMemoryRepository(db)
        self.project_memory_repo = ProjectMemoryRepository(db)
        self.sop_repo = SOPRepository(db)
        self.prompt_repo = PromptRepository(db)
        self.skill_repo = SkillRepository(db)

    def get(self) -> ReportOut:
        identity_axis = self._identity_axis()
        growth_axis = self._growth_axis()
        archive_axis = self._archive_axis()
        recent = self._recent_experience()

        growth_axis.tasks_completed_total = self.task_repo.count_user(
            self.user_id, status="completed"
        )
        growth_axis.diaries_total = self.diary_repo.count_by_user(self.user_id)
        growth_axis.reviews_total = self.review_repo.count_user(self.user_id)

        return ReportOut(
            generated_at=utcnow(),
            nickname=self.nickname,
            identity_axis=identity_axis,
            growth_axis=growth_axis,
            archive_axis=archive_axis,
            recent_experience=recent,
        )

    # ---------- 身份轴 ----------

    def _identity_axis(self) -> IdentityAxis:
        identities = self.identity_repo.list_user(self.user_id)
        rows = [
            IdentityStat(
                id=i.id, name=i.name, slug=i.slug,
                color_token=i.color_token, icon=i.icon,
                is_archived=not i.is_active,
            )
            for i in identities
        ]
        index = {r.id: r for r in rows}

        # 每张源表一次 GROUP BY（个人规模，6 次轻查询可忽略）
        for rid, cnt in self.task_repo.identity_counts(
            self.user_id, completed=False
        ).items():
            if rid in index:
                index[rid].tasks_open = cnt
        for rid, cnt in self.task_repo.identity_counts(
            self.user_id, completed=True
        ).items():
            if rid in index:
                index[rid].tasks_completed = cnt
        for rid, cnt in self.doc_repo.identity_counts(self.user_id).items():
            if rid in index:
                index[rid].documents = cnt
        for rid, cnt in self.diary_repo.identity_counts(self.user_id).items():
            if rid in index:
                index[rid].diaries = cnt
        for rid, cnt in self.review_repo.identity_counts(self.user_id).items():
            if rid in index:
                index[rid].reviews = cnt
        avatar_counts = self.avatar_memory_repo.identity_counts(self.user_id)
        pm_counts = self.project_memory_repo.identity_counts(self.user_id)
        for rid in index:
            index[rid].memories = avatar_counts.get(rid, 0) + pm_counts.get(rid, 0)

        unassigned = UnassignedStat(
            tasks_open=self.task_repo.count_identity_unassigned(
                self.user_id, completed=False
            ),
            documents=self.doc_repo.count_identity_unassigned(self.user_id),
            diaries=self.diary_repo.count_identity_unassigned(self.user_id),
            reviews=self.review_repo.count_identity_unassigned(self.user_id),
            memories=(
                self.avatar_memory_repo.count_identity_unassigned(self.user_id)
                + self.project_memory_repo.count_identity_unassigned(self.user_id)
            ),
        )
        return IdentityAxis(identities=rows, unassigned=unassigned)

    # ---------- 成长轴 ----------

    def _growth_axis(self) -> GrowthAxis:
        growth = GrowthService(self.db)
        state = growth.get_state(self.user_id)
        tree = growth.get_skill_tree(self.user_id)
        return GrowthAxis(
            level=state["level"],
            exp=state["exp"],
            percent=state["percent"],
            skills=[SkillStatOut(name=s["name"], count=s["count"]) for s in tree],
        )

    # ---------- 档案轴 ----------

    def _archive_axis(self) -> ArchiveAxis:
        from app.services.workspace_service import WorkspaceService

        svc = WorkspaceService(self.db, self.user_id)
        enabled = svc.is_enabled()
        roots = (
            [
                WorkspaceRootStat(
                    path=r["path"], label=r["label"],
                    file_count=r["file_count"], total_size=r["total_size"],
                )
                for r in svc.list_roots()
            ]
            if enabled
            else []
        )
        return ArchiveAxis(
            workspace_enabled=enabled,
            roots=roots,
            documents_total=self.doc_repo.count_by_user(self.user_id),
            sops_total=self.sop_repo.count_by_user(self.user_id),
            prompts_total=self.prompt_repo.count_by_user(self.user_id),
            skills_total=self.skill_repo.count_by_user(self.user_id),
            project_memories_total=self.project_memory_repo.count_by_user(self.user_id),
            avatar_memories_total=self.avatar_memory_repo.count_by_user(self.user_id),
        )

    # ---------- 近期经历（报告的叙事面） ----------

    def _recent_experience(self, limit: int = 10) -> list[ExperienceRecentItem]:
        out = ExperienceService(self.db, self.user_id).list(page=1, page_size=limit)
        names = {
            i.id: i.name
            for i in self.identity_repo.list_user(self.user_id)
        }
        return [
            ExperienceRecentItem(
                source=it.source,
                source_label=SOURCE_LABELS[it.source],
                title=it.title,
                identity_name=names.get(it.identity_id) if it.identity_id else None,
                occurred_at=it.occurred_at,
            )
            for it in out.items
        ]
