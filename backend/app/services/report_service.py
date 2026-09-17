# ============================================================
# 人生报告服务（S6-5 · 身份 × 成长 × 档案 三轴聚合）
#
# 只读聚合：从已有模块的表里数数，不新增任何写入。
# 前端把 ReportOut 渲染为单文件 HTML 供下载留存
# （内联样式、零外部依赖 —— 数据主权：报告归用户自己所有）。
# ============================================================
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.base import utcnow
from app.models.asset import ProjectMemory, PromptTemplate, Skill as SkillAsset, SOP
from app.models.avatar import AvatarMemory
from app.models.document import Document
from app.models.identity import Identity
from app.models.life import Diary
from app.models.review import Review
from app.models.task import Task
from app.repositories import IdentityRepository
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

    def get(self) -> ReportOut:
        identity_axis = self._identity_axis()
        growth_axis = self._growth_axis()
        archive_axis = self._archive_axis()
        recent = self._recent_experience()

        growth_axis.tasks_completed_total = self._count(Task, Task.status == "completed")
        growth_axis.diaries_total = self._count(Diary)
        growth_axis.reviews_total = self._count(Review)

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
        identities = IdentityRepository(self.db).list_user(self.user_id)
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
        for rid, cnt in self._group_counts(Task.identity_id, Task.status != "completed"):
            if rid in index:
                index[rid].tasks_open = cnt
        for rid, cnt in self._group_counts(Task.identity_id, Task.status == "completed"):
            if rid in index:
                index[rid].tasks_completed = cnt
        for rid, cnt in self._group_counts(Document.identity_id):
            if rid in index:
                index[rid].documents = cnt
        for rid, cnt in self._group_counts(Diary.identity_id):
            if rid in index:
                index[rid].diaries = cnt
        for rid, cnt in self._group_counts(Review.identity_id):
            if rid in index:
                index[rid].reviews = cnt
        avatar_counts = dict(self._group_counts(AvatarMemory.identity_id))
        pm_counts = dict(self._group_counts(ProjectMemory.identity_id))
        for rid in index:
            index[rid].memories = avatar_counts.get(rid, 0) + pm_counts.get(rid, 0)

        unassigned = UnassignedStat(
            tasks_open=self._count(Task, Task.identity_id.is_(None), Task.status != "completed"),
            documents=self._count(Document, Document.identity_id.is_(None)),
            diaries=self._count(Diary, Diary.identity_id.is_(None)),
            reviews=self._count(Review, Review.identity_id.is_(None)),
            memories=(
                self._count(AvatarMemory, AvatarMemory.identity_id.is_(None))
                + self._count(ProjectMemory, ProjectMemory.identity_id.is_(None))
            ),
        )
        return IdentityAxis(identities=rows, unassigned=unassigned)

    def _group_counts(self, col, *extra):
        """按 identity_id 分组计数（跳过 NULL）。"""
        q = select(col, func.count()).where(
            getattr(col.parent.class_, "user_id") == self.user_id,
            col.is_not(None),
            *extra,
        ).group_by(col)
        return [(rid, int(c)) for rid, c in self.db.execute(q).all()]

    def _count(self, model, *extra) -> int:
        q = select(func.count()).select_from(model).where(
            model.user_id == self.user_id, *extra
        )
        return int(self.db.scalar(q) or 0)

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
            documents_total=self._count(Document),
            sops_total=self._count(SOP),
            prompts_total=self._count(PromptTemplate),
            skills_total=self._count(SkillAsset),
            project_memories_total=self._count(ProjectMemory),
            avatar_memories_total=self._count(AvatarMemory),
        )

    # ---------- 近期经历（报告的叙事面） ----------

    def _recent_experience(self, limit: int = 10) -> list[ExperienceRecentItem]:
        out = ExperienceService(self.db, self.user_id).list(page=1, page_size=limit)
        names = {
            i.id: i.name
            for i in self.db.scalars(
                select(Identity).where(
                    Identity.user_id == self.user_id, Identity.deleted_at.is_(None)
                )
            )
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
