# ============================================================
# 经历视图服务（S6-4 · 视图不建表）
#
# 定位（总路线 R1，勿改方向）：
#   二期 S6-4 卡在「概念归并」—— Diary / Review / AvatarMemory /
#   ProjectMemory 已四处记「发生过什么」，再建经历表 = 同一件事记五遍。
#   身份轴（0015）落地后，四源都挂 identity_id，「经历」就可以定义为
#   **读取时的聚合视图**：本服务按身份过滤四源、归并排序、内存分页。
#
#   - 严禁在本服务里写入任何经历数据（它是只读视图）
#   - 严禁新建经历表；将来性能不够再考虑物化，原则不变
#
# 性能说明：个人本地库四源总量在千级，每次全量拉取后内存归并的开销
# 可忽略；若将来单源过万，再下推到 SQL（ORDER BY + LIMIT OFFSET）。
# ============================================================
from __future__ import annotations

from datetime import date, datetime, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.asset import ProjectMemory
from app.models.avatar import AvatarMemory
from app.models.life import Diary
from app.models.review import Review
from app.schemas.experience import ExperienceItem, ExperienceOut

# 单源拉取上限：防御性 cap，个人规模远达不到
_PER_SOURCE_CAP = 500

SOURCE_LABELS = {
    "diary": "日记",
    "review": "复盘",
    "avatar_memory": "分身记忆",
    "project_memory": "项目记忆",
}


def _as_datetime(d: date | datetime | None, fallback: datetime) -> datetime:
    """date（日记/复盘的业务日期）归一为 datetime；None 回退 created_at。"""
    if d is None:
        return fallback
    if isinstance(d, datetime):
        return d
    return datetime.combine(d, time.min)


class ExperienceService:
    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id

    def list(
        self,
        identity_id: str | None = None,
        identity_unassigned: bool = False,
        page: int = 1,
        page_size: int = 30,
    ) -> ExperienceOut:
        """四源归并时间线。

        过滤语义与任务列表一致：
          identity_id 有值 → 只看该身份；
          identity_unassigned=True → 只看未归类；
          两者都不传 → 全部。
        """
        rows: list[ExperienceItem] = []
        counts: dict[str, int] = {}

        # ---------- 日记（occurred_at = diary_date）----------
        q = select(Diary).where(Diary.user_id == self.user_id)
        rows.extend(
            ExperienceItem(
                id=d.id, source="diary", source_label=SOURCE_LABELS["diary"],
                title=d.title or "日记",
                snippet=(d.content or "")[:120] or None,
                identity_id=d.identity_id,
                occurred_at=_as_datetime(d.diary_date, d.created_at),
            )
            for d in self.db.scalars(q.limit(_PER_SOURCE_CAP))
        )

        # ---------- 复盘（occurred_at = review_date）----------
        q = select(Review).where(Review.user_id == self.user_id)
        rows.extend(
            ExperienceItem(
                id=r.id, source="review", source_label=SOURCE_LABELS["review"],
                title=f"复盘（{r.type or 'daily'}）",
                snippet=str((r.data or {}).get("summary") or "")[:120] or None,
                identity_id=r.identity_id,
                occurred_at=_as_datetime(r.review_date, r.created_at),
            )
            for r in self.db.scalars(q.limit(_PER_SOURCE_CAP))
        )

        # ---------- 分身记忆（occurred_at = created_at）----------
        q = select(AvatarMemory).where(AvatarMemory.user_id == self.user_id)
        rows.extend(
            ExperienceItem(
                id=m.id, source="avatar_memory", source_label=SOURCE_LABELS["avatar_memory"],
                title=m.title,
                snippet=(m.content or "")[:120] or None,
                identity_id=m.identity_id,
                occurred_at=m.created_at,
            )
            for m in self.db.scalars(q.limit(_PER_SOURCE_CAP))
        )

        # ---------- 项目记忆（occurred_at = created_at）----------
        q = select(ProjectMemory).where(ProjectMemory.user_id == self.user_id)
        rows.extend(
            ExperienceItem(
                id=m.id, source="project_memory", source_label=SOURCE_LABELS["project_memory"],
                title=m.name,
                snippet=(m.summary or "")[:120] or None,
                identity_id=m.identity_id,
                occurred_at=m.created_at,
            )
            for m in self.db.scalars(q.limit(_PER_SOURCE_CAP))
        )

        # ---------- 过滤 + 归并（内存；数据量个人规模可忽略）----------
        if identity_id:
            rows = [r for r in rows if r.identity_id == identity_id]
        elif identity_unassigned:
            rows = [r for r in rows if r.identity_id is None]

        rows.sort(key=lambda r: r.occurred_at, reverse=True)

        for r in rows:
            counts[r.source] = counts.get(r.source, 0) + 1

        total = len(rows)
        start = (page - 1) * page_size
        return ExperienceOut(
            items=rows[start:start + page_size],
            total=total,
            page=page,
            page_size=page_size,
            source_counts=counts,
        )
