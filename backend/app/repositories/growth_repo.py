# ============================================================
# 成长体系 Repository（S6-2 · D-06 收口）
#
# models/growth.py 有三张表，各司其职，因此三个 Repository 分列：
#   growth_states —— 当前状态（每用户一条，唯一索引兜底）
#   growth_events —— EXP 流水账本（带幂等键 source_key）
#   skill_stats   —— 技能分类累计计数（技能树数据源）
#
# 事务语义：只 flush，不 commit（由 service / get_db 闭合，见基类注释）。
# ============================================================
from __future__ import annotations

from sqlalchemy import select

from app.models.growth import GrowthEvent, GrowthState, SkillStat
from app.repositories.base import BaseRepository


class GrowthStateRepository(BaseRepository[GrowthState]):
    """成长状态（只读查询；写入走 create / 实体赋值）。"""

    model = GrowthState

    def get_by_user(self, user_id: str) -> GrowthState | None:
        """取用户的成长状态（排除软删除）。"""
        return self.db.scalar(
            select(GrowthState).where(
                GrowthState.user_id == user_id,
                GrowthState.deleted_at.is_(None),
            )
        )


class GrowthEventRepository(BaseRepository[GrowthEvent]):
    """EXP 流水（幂等账本）。"""

    model = GrowthEvent

    def get_by_source_key(self, user_id: str, source_key: str) -> GrowthEvent | None:
        """按幂等键取流水 —— (user_id, source_key) 上有唯一索引。"""
        return self.db.scalar(
            select(GrowthEvent).where(
                GrowthEvent.user_id == user_id,
                GrowthEvent.source_key == source_key,
            )
        )

    def list_user(self, user_id: str, limit: int = 20) -> list[GrowthEvent]:
        """最近 N 条流水（按发生时间倒序）。"""
        q = (
            select(GrowthEvent)
            .where(GrowthEvent.user_id == user_id)
            .order_by(GrowthEvent.created_at.desc())
            .limit(limit)
        )
        return list(self.db.scalars(q))


class SkillStatRepository(BaseRepository[SkillStat]):
    """技能分类累计计数。"""

    model = SkillStat

    def get_by_category(self, user_id: str, category_id: str) -> SkillStat | None:
        """取某技能分类的累计行（(user_id, category_id) 唯一）。"""
        return self.db.scalar(
            select(SkillStat).where(
                SkillStat.user_id == user_id,
                SkillStat.category_id == category_id,
            )
        )

    def list_counted(self, user_id: str) -> list[SkillStat]:
        """技能树数据源：只取计数 > 0 的分类（零计数不进树）。"""
        q = select(SkillStat).where(
            SkillStat.user_id == user_id,
            SkillStat.count > 0,
        )
        return list(self.db.scalars(q))
