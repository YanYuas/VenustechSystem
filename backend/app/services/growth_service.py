# ============================================================
# 成长体系（S6-2）：经验值 / 等级 / 技能树
#
# 目标：让启明星从「13 个各自为政的工具箱」变成「一个有进度条的人生」。
#
# 最漂亮的一点：**不需要改任何现有模块的代码**。
# 启明星已有 28 种事件的 event_bus，其中 18 种可直接挂载经验值。
# 用户在 Task 勾掉任务、在 Learning 复习卡片、在 Life 打卡 ——
# 这些模块一行都不用动，EXP 由订阅者自动结算。这是架构给的红利。
#
# ------------------------------------------------------------
# 权重重标定：本模块最重要的设计决策（不是技术活，是产品判断）
#
# 交付物 A 里「记录一段经历」是主行为（30~65 EXP，高反思成本）；
# 而在启明星，`task.completed` 一天可以触发十几次（勾一个复选框，
# 机械成本极低）。若照搬权重，**勾选任务会和写一段经历赚得一样多**，
# EXP 就从「衡量成长」退化成「衡量点击量」。
#
# 因此本表把行为分成两类，并让两类的量级明显拉开：
#
#   沉淀类（写、反思、沉淀资产）：20 ~ 35 EXP
#     高认知成本、低频、产出可复用 —— 这是真正带来成长的行为
#   处理类（勾选、保存、记录）：1 ~ 8 EXP
#     低认知成本、高频、机械 —— 有反馈价值，但不应主导进度条
#
# 标定后的直觉：写一段复盘 ≈ 5 个勾任务；沉淀一条项目记忆 ≈ 7 个勾任务。
# 这个比例是本模块唯一需要产品判断的地方，其余都是机械实现。
# ============================================================
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.growth import EXP_MAX, GrowthEvent, GrowthState, SkillStat
from app.services.rules.domain_engine import js_round
from app.services.rules.skill_cats import SKILL_CAT_BY_ID, SKILL_CATS

logger = logging.getLogger("app.growth")

MAX_LEVEL = 30

# 四维数值的默认值与上下限（与 PetConfig 的默认保持一致）
STAT_DEFAULT = 60
STAT_MIN = 0
STAT_MAX = 100


# ============================================================
# 1. 等级递推
# ============================================================
def _build_level_table() -> tuple[int, ...]:
    """等级门槛表（累计经验）。

    公式沿用交付物 A：第 lv 级的升级所需 = round(80 + lv*20*1.12^lv)
    指数增长使得 LV30 累计约 10.7 万 —— 按轻度使用约 4 年、重度约 1 年，
    对 Personal OS 是合理的长线目标（不需要为了"快点升级"而调参）。

    注意 js_round：Python 的 round() 是银行家舍入（round(2.5)=2），
    而源实现用的是 JS Math.round（.5 向上）。此处必须对齐，
    否则每一级的门槛都会有 ±1 的静默偏差。
    """
    table = [0] * (MAX_LEVEL + 2)  # index 0 占位（源实现如此），31 存总经验
    total = 0
    for lv in range(1, MAX_LEVEL + 1):
        table[lv] = total
        total += js_round(80 + lv * 20 * (1.12 ** lv))
    table[MAX_LEVEL + 1] = total
    return tuple(table)


LEVEL_TABLE: tuple[int, ...] = _build_level_table()

# 到达满级（LV30）所需的累计经验 = 107,069
#
# 注意索引（实测核对过，勿随手改成 31）：
#   源实现的 LEVEL_TABLE 末尾多存了一个 table[31]（=125,125），那是
#   「LV30 之后再升一级」的门槛 —— 满级之后并无意义。
#   评估报告里的 107,069 指的是**到达 LV30 的门槛**，即 table[30]。
#   两者相差 18,056，取错索引会让「距离满级还差多少」的展示凭空多出这一段。
TOTAL_EXP_TO_MAX = LEVEL_TABLE[MAX_LEVEL]


def get_level(exp: int) -> int:
    """经验值 → 等级。"""
    for lv in range(MAX_LEVEL, 0, -1):
        if exp >= LEVEL_TABLE[lv]:
            return lv
    return 1


def get_exp_progress(exp: int) -> dict:
    """经验值 → 当前等级内的进度（供进度条使用）。"""
    lv = get_level(exp)
    if lv >= MAX_LEVEL:
        return {
            "level": lv,
            "current": exp - LEVEL_TABLE[MAX_LEVEL],
            "need": 0,
            "percent": 100,
            "is_max": True,
        }
    cur_base = LEVEL_TABLE[lv]
    next_base = LEVEL_TABLE[lv + 1]
    current = exp - cur_base
    need = next_base - cur_base
    percent = min(100, round(current / need * 100)) if need > 0 else 100
    return {"level": lv, "current": current, "need": need, "percent": percent, "is_max": False}


# ============================================================
# 2. 行为 → 经验值映射（见文件头的权重重标定说明）
# ============================================================
EXP_RULES: dict[str, int] = {
    # ---- 沉淀类：高认知成本、低频、产出可复用 ----
    "project.memory.created": 35,   # 沉淀项目记忆（最高价值）
    "diary.created": 30,            # 写日记
    "review.created": 25,           # 写复盘
    "review.generated": 10,         # 生成复盘（系统辅助，略低）
    "project.created": 15,          # 立项
    "document.created": 10,         # 新建文档（有内容产出）
    "sop.used": 8,                  # 复用 SOP
    "inbox.item.processed": 8,      # 把收集箱条目处理掉（真正的整理动作）
    # ---- 处理类：低认知成本、高频、机械 ----
    "task.completed": 5,            # 勾掉一个任务
    "prompt.used": 5,               # 用一次提示词
    "habit.checkin": 4,             # 习惯打卡
    "flashcard.reviewed": 3,        # 复习一张卡片
    "mood.logged": 3,               # 记录心情
    "project.updated": 3,           # 更新项目
    "document.saved": 2,            # 保存文档
    "inbox.item.created": 2,        # 丢进收集箱
    "task.created": 1,              # 建任务
    "conversation.message": 1,      # 与分身对话
}

# 学习时长：按分钟折算（每 10 分钟 1 点，向上取整，单次上限 6 点）
STUDY_MINUTES_PER_EXP = 10
STUDY_EXP_MAX_PER_LOG = 6

# 动态规则：文档越长、关联技能越多，沉淀价值越高（沿用交付物 A 的思路）
DOCUMENT_EXP_LONG = 10       # 内容 > 500 字，额外 +10
DOCUMENT_EXP_VERY_LONG = 10  # 内容 > 1500 字，再 +10
DOCUMENT_EXP_MANY_TAGS = 5   # 标签/关联 ≥ 3 个，额外 +5


def exp_for_study_minutes(minutes: int) -> int:
    """学习时长折算经验值。"""
    if minutes <= 0:
        return 0
    return min(STUDY_EXP_MAX_PER_LOG, max(1, -(-minutes // STUDY_MINUTES_PER_EXP)))


# ============================================================
# 3. 技能自动归类（技能树的数据来源）
# ============================================================
def auto_classify(text: str) -> list[str]:
    """从文本里自动识别技能分类 id（可命中多个）。

    规则与源实现一致：小写化后做子串包含判断（不是分词），
    每个分类只要命中任一关键词就记一次，同类不重复计。
    """
    if not text:
        return []
    lowered = text.lower()
    hits: list[str] = []
    for cat in SKILL_CATS:
        for kw in cat.kws:
            if kw.lower() in lowered:
                hits.append(cat.id)
                break
    return hits


def category_level(count: int) -> int:
    """技能分类等级：源实现为 count + 1（第 1 次完成即为 1 级）。"""
    return count + 1 if count > 0 else 0


# ============================================================
# 4. 成长服务
# ============================================================
class GrowthService:
    """成长体系业务逻辑层。

    所有写操作都经 `award()` —— 它带幂等键，重复投递不会重复计分。
    """

    def __init__(self, db: Session):
        self.db = db

    # ---------- 状态读取 ----------

    def get_or_create_state(self, user_id: str) -> GrowthState:
        state = self.db.scalar(
            select(GrowthState).where(
                GrowthState.user_id == user_id,
                GrowthState.deleted_at.is_(None),
            )
        )
        if state is None:
            state = GrowthState(user_id=user_id, exp=0, level=1)
            self.db.add(state)
            self.db.commit()
            self.db.refresh(state)
        return state

    def get_state(self, user_id: str) -> dict:
        state = self.get_or_create_state(user_id)
        progress = get_exp_progress(state.exp)
        return {
            "exp": state.exp,
            "level": progress["level"],
            "current": progress["current"],
            "need": progress["need"],
            "percent": progress["percent"],
            "is_max": progress["is_max"],
            "next_level_exp": (
                None if progress["is_max"] else LEVEL_TABLE[progress["level"] + 1]
            ),
            "total_exp_to_max": TOTAL_EXP_TO_MAX,
        }

    # ---------- 结算 ----------

    def award(
        self,
        user_id: str,
        source_key: str,
        event_type: str,
        exp: int,
        label: str | None = None,
        classified_text: str | None = None,
    ) -> dict:
        """结算一次经验值（**幂等**）。

        `source_key` 是幂等键，形如 "task:<id>:completed"。同一 user 下
        重复投递会撞 growth_events 的唯一索引 —— 由数据库而非调用方保证
        不重复计分（见 models/growth.py 的说明）。

        返回 {"granted": bool, "exp": int, "level_up": bool, "level": int,
              "skill_cat_ids": [...]}
        """
        if exp <= 0:
            return {"granted": False, "exp": 0, "level_up": False, "level": None,
                    "skill_cat_ids": []}

        # 幂等检查（先查再插，避免依赖异常做流程控制）
        existing = self.db.scalar(
            select(GrowthEvent).where(
                GrowthEvent.user_id == user_id,
                GrowthEvent.source_key == source_key,
            )
        )
        if existing is not None:
            logger.debug("EXP 已结算，跳过: %s", source_key)
            return {"granted": False, "exp": existing.exp, "level_up": False,
                    "level": None, "skill_cat_ids": existing.skill_cat_ids or []}

        skill_ids = auto_classify(classified_text) if classified_text else []

        self.db.add(GrowthEvent(
            user_id=user_id,
            source_key=source_key,
            event_type=event_type,
            exp=exp,
            label=label,
            skill_cat_ids=skill_ids or None,
        ))
        self._bump_skills(user_id, skill_ids)

        state = self.get_or_create_state(user_id)
        old_level = get_level(state.exp)
        state.exp = min(EXP_MAX, state.exp + exp)
        new_level = get_level(state.exp)
        state.level = new_level
        self.db.commit()

        if new_level > old_level:
            logger.info("用户 %s 升级: LV%d → LV%d", user_id, old_level, new_level)

        return {
            "granted": True,
            "exp": exp,
            "level_up": new_level > old_level,
            "level": new_level,
            "skill_cat_ids": skill_ids,
        }

    def _bump_skills(self, user_id: str, category_ids: list[str]) -> None:
        """技能计数 +1（同类只加一次）。"""
        for cat_id in category_ids:
            row = self.db.scalar(
                select(SkillStat).where(
                    SkillStat.user_id == user_id,
                    SkillStat.category_id == cat_id,
                )
            )
            if row is None:
                self.db.add(SkillStat(user_id=user_id, category_id=cat_id, count=1))
            else:
                row.count += 1

    # ---------- 流水与技能树 ----------

    def list_events(self, user_id: str, limit: int = 20) -> list[dict]:
        rows = self.db.scalars(
            select(GrowthEvent)
            .where(GrowthEvent.user_id == user_id)
            .order_by(GrowthEvent.created_at.desc())
            .limit(limit)
        ).all()
        return [
            {
                "id": r.id,
                "event_type": r.event_type,
                "exp": r.exp,
                "label": r.label,
                "skill_cat_ids": r.skill_cat_ids or [],
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]

    def get_skill_tree(self, user_id: str) -> list[dict]:
        """技能树：返回有计数的分类（按计数降序）。"""
        rows = self.db.scalars(
            select(SkillStat).where(
                SkillStat.user_id == user_id,
                SkillStat.count > 0,
            )
        ).all()
        items: list[dict] = []
        for r in rows:
            cat = SKILL_CAT_BY_ID.get(r.category_id)
            items.append({
                "id": r.category_id,
                # 分类可能在数据更新后被移除，此时退化为展示 id 本身，
                # 而不是丢弃这条历史计数
                "name": cat.name if cat else r.category_id,
                "count": r.count,
                "level": category_level(r.count),
            })
        items.sort(key=lambda x: x["count"], reverse=True)
        return items


# ============================================================
# 5. 四维数值衰减（惰性计算）
# ============================================================
# 衰减速率：每小时下降的点数（饱食度掉得最快，亲密度最慢 —— 亲密度更像
# 长期关系的度量，不应因为一天没开应用就大幅回落）
STAT_DECAY_PER_HOUR: dict[str, float] = {
    "satiety": 2.0,
    "energy": 1.5,
    "mood": 1.0,
    "intimacy": 0.2,
}
STAT_DECAY_MAX_HOURS = 72  # 超过 3 天未打开，按 3 天计 —— 避免"长期没开=清零"


def apply_stat_decay(
    stats: dict[str, int],
    updated_at: datetime | None,
    now: datetime | None = None,
) -> dict[str, int]:
    """按经过时间惰性衰减四维数值。

    为什么是"惰性"：定时任务改写数值会导致「应用没开就不衰减」；
    而后端在用户不知情时持续写库也不合适。读取时按时间差现算最自然。

    为什么封顶 72 小时：否则用户出差一周回来会看到归零的宠物，
    惩罚与体验都不合理。
    """
    if updated_at is None:
        return dict(stats)
    now = now or datetime.now(timezone.utc)
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    hours = max(0.0, (now - updated_at).total_seconds() / 3600)
    hours = min(hours, STAT_DECAY_MAX_HOURS)

    out: dict[str, int] = {}
    for key, value in stats.items():
        rate = STAT_DECAY_PER_HOUR.get(key, 0.0)
        decayed = value - rate * hours
        out[key] = int(max(STAT_MIN, min(STAT_MAX, round(decayed))))
    return out


__all__ = [
    "EXP_RULES",
    "LEVEL_TABLE",
    "MAX_LEVEL",
    "STAT_DECAY_PER_HOUR",
    "STAT_DEFAULT",
    "TOTAL_EXP_TO_MAX",
    "GrowthService",
    "apply_stat_decay",
    "auto_classify",
    "category_level",
    "exp_for_study_minutes",
    "get_exp_progress",
    "get_level",
]
