# ============================================================
# 领域规则引擎（S6-1）
#
# 作用：把交付物 A《地球Online》的「领域知识库 + 计划生成」内核，
#       从原生 JS 重写为 Python，接入启明星的 AI 降级路径。
#
# 为什么要有它（这是 S6-1 的全部价值所在）：
#   未配 API Key 时，启明星的 AI 能力实际上是空的 ——
#     · 后端 MockLLMClient 只会复读用户输入
#     · 前端 useConversation 只有 7 条硬编码关键词分支
#     · LearningService.create_plan() 是纯空壳（只存不生成）
#   而绝大多数用户**首次打开应用时不会去配 Key**。本引擎让「没有 Key」
#   也能产出**一份专业、可执行、有验收标准的学习计划**。
#
# 铁律一「内核优先于功能」的落实：
#   源码不可直搬（3381 行原生 JS 进 TS 严格模式是灾难），故只提炼算法：
#     matchDomain / buildUnitDefs / genericUnits / aiGeneratePlan / expandTasks
#   全部重写为纯函数，数据结构改为 frozen dataclass，无副作用、无全局状态。
#
# 移植中必须显式处理的差异（否则结果会静默偏差）：
#   1. **Math.round vs round()** —— 见 js_round() 的说明。这是最容易踩的坑。
#   2. JS `String.replace(re, s)` 无 g 标志时**只替换第一处**，
#      Python `re.sub` 默认替换全部 —— 已用 count=1 对齐。
#   3. JS 正则 `/i` 标志由「先 toLowerCase() 再 test()」实现，
#      本模块统一改为编译时 re.IGNORECASE，语义等价且更清晰。
# ============================================================
from __future__ import annotations

import json
from pathlib import Path

import math
import re
from dataclasses import dataclass

from app.core.logger import get_logger

logger = get_logger("rules")
from app.services.rules.domain_lib import DOMAIN_LIB, DomainDef, TaskDef, UnitDef

# 验证任务的「达标标准」是固定的 —— 源实现里就是硬编码字符串
VERIFY_ACCEPTANCE = "完成并记录为一段真实经历（记录后技能正式点亮）"

# 日/周模式的分界：≤45 天按天排，>45 天按周排（每周 5 个任务）
DAILY_MODE_MAX_DAYS = 45
WEEKLY_TASKS_PER_WEEK = 5


# ============================================================
# 数据结构
# ============================================================
@dataclass(frozen=True)
class PlannedUnit:
    """计划中的能力单元（含阶段划分，用于技能树展示）。"""

    name: str
    tasks: tuple[TaskDef, ...]
    phase: int  # 1 打基础 / 2 核心练习 / 3 整合实战


@dataclass(frozen=True)
class PlanItem:
    """计划中的一条待办。`day` 在周模式下表示周序号。"""

    unit_id: str
    day: int
    title: str
    task: str
    duration: str
    acceptance: str
    is_verify: bool = False


@dataclass(frozen=True)
class PlanResult:
    """一次计划生成的完整结果。"""

    goal: str
    skill_name: str
    matched: bool  # 是否命中领域库；False 表示走了通用拆解兜底
    domain_key: str | None
    domain_name: str | None
    total_days: int
    minutes_per_day: int
    weekly_mode: bool
    units: tuple[PlannedUnit, ...]
    items: tuple[PlanItem, ...]
    verify_task: str


@dataclass(frozen=True)
class _ExpandedTask:
    """expand_tasks 的中间产物。"""

    task: str
    duration: str
    acceptance: str


# ============================================================
# 0. 舍入对齐（**移植正确性的关键**）
# ============================================================
def js_round(x: float) -> int:
    """等价于 JS `Math.round`，即「.5 一律向上」。

    必须显式实现，不能直接用 Python 的 round()：
        JS      Math.round(2.5) == 3
        Python  round(2.5)      == 2   ← 银行家舍入（取偶）

    本引擎的日/周分配大量使用 Math.round 计算每个单元的天数配额，
    用错会**静默**让分配整体偏移 —— 不会报错、不会崩溃，只是计划看起来
    「差不多」。这类偏差是最难在事后发现的移植错误，所以在此显式对齐。

    注：负数行为与 JS 在 .5 上的定义略有差别，但本引擎的入参恒为非负。
    """
    return math.floor(x + 0.5)


# ============================================================
# 1. 领域匹配
# ============================================================
_PATTERN_CACHE: dict[str, re.Pattern[str]] = {}


def _compiled(pattern: str) -> re.Pattern[str]:
    """编译并缓存正则。

    DOMAIN_LIB 共 13 个领域、32 条模式；计划生成会被频繁调用，
    缓存可避免重复编译（re 模块内部也有缓存，但显式缓存更省一层查找）。
    """
    cached = _PATTERN_CACHE.get(pattern)
    if cached is None:
        cached = re.compile(pattern, re.IGNORECASE)
        _PATTERN_CACHE[pattern] = cached
    return cached


def match_domain(text: str) -> DomainDef | None:
    """按顺序返回第一个命中的领域；无命中返回 None（调用方走通用兜底）。

    顺序即优先级 —— DOMAIN_LIB 的排列本身就是设计（如「英语口语」排在
    「英语考试」之后，因为「口语」这个词更宽泛，让更专用的先匹配）。
    """
    lowered = (text or "").lower()
    # 内置库优先（PRD F4.1：用户扩展不得覆盖内置语义）
    for domain in DOMAIN_LIB:
        if any(_compiled(p).search(lowered) for p in domain.patterns):
            return domain
    # 其次用户扩展层
    for domain in user_domains():
        if any(_compiled(p).search(lowered) for p in domain.patterns):
            return domain
    return None


def list_domains() -> tuple[DomainDef, ...]:
    """暴露领域清单（内置 + 用户扩展），供设置页/计划页做「选择领域」下拉。"""
    return DOMAIN_LIB + user_domains()


# ============================================================
# 用户扩展层（F4.1）：data_dir/rules/domains/*.json
# - 内置库只读，用户不可改
# - 非法 JSON 跳过并 warning（指出文件名与原因）
# - 与内置 key 冲突的用户领域被忽略并 warning（内置优先）
# - reload_user_domains() 支持热重载，无需重启
# ============================================================

_user_domains: tuple[DomainDef, ...] = ()
_user_domains_loaded = False


def user_domains() -> tuple[DomainDef, ...]:
    """当前生效的用户扩展领域（未加载过则先加载一次）。"""
    global _user_domains_loaded
    if not _user_domains_loaded:
        reload_user_domains()
    return _user_domains


def _parse_user_domain(raw: dict) -> DomainDef:
    units = []
    for u in raw.get("units", []) or []:
        tasks = tuple(
            TaskDef(
                task=str(t.get("task", "")),
                duration=str(t.get("duration", "25 分钟")),
                acceptance=str(t.get("acceptance", "")),
                repeatable=bool(t.get("repeatable", False)),
            )
            for t in (u.get("tasks") or [])
        )
        units.append(UnitDef(name=str(u.get("name", "")), tasks=tasks))
    return DomainDef(
        key=str(raw.get("key", "")),
        name=str(raw.get("name", raw.get("key", ""))),
        patterns=tuple(raw.get("patterns") or []),
        verify_task=str(raw.get("verify_task", "")),
        units=tuple(units),
        source="user",
    )


def reload_user_domains() -> dict:
    """扫描用户领域目录并热重载。返回统计（供 /rules/reload 与调试）。"""
    global _user_domains, _user_domains_loaded
    from app.config import get_settings

    builtin_keys = {d.key for d in DOMAIN_LIB}
    loaded: list[DomainDef] = []
    skipped: list[dict] = []
    directory = Path(get_settings().data_dir) / "rules" / "domains"
    directory.mkdir(parents=True, exist_ok=True)

    for path in sorted(directory.glob("*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            domain = _parse_user_domain(raw)
            if not domain.key or not domain.patterns:
                raise ValueError("缺少 key 或 patterns")
            if domain.key in builtin_keys:
                logger.warning("用户领域 %s 与内置领域同名，已忽略（内置优先）: %s",
                               domain.key, path.name)
                skipped.append({"file": path.name, "reason": "与内置领域 key 冲突（内置优先）"})
                continue
            if any(d.key == domain.key for d in loaded):
                logger.warning("用户领域 %s 重复定义，已忽略: %s", domain.key, path.name)
                skipped.append({"file": path.name, "reason": "key 重复"})
                continue
            loaded.append(domain)
            logger.info("加载用户领域: %s (%s)", domain.name, path.name)
        except Exception as exc:  # noqa: BLE001 - 单个文件坏掉不影响其他领域
            logger.warning("用户领域文件解析失败，已跳过: %s（原因：%s）", path.name, exc)
            skipped.append({"file": path.name, "reason": str(exc)})

    _user_domains = tuple(loaded)
    _user_domains_loaded = True
    return {
        "builtin": len(DOMAIN_LIB),
        "user": len(_user_domains),
        "total": len(DOMAIN_LIB) + len(_user_domains),
        "skipped": skipped,
    }


# ============================================================
# 2. 技能名提取（未命中领域库时用）
# ============================================================
# 顺序敏感：更专用的规则必须排在更宽泛的规则之前
# （例如 `python` 必须先于 `编程|代码|开发`）
_SKILL_NAME_RULES: tuple[tuple[str, str], ...] = (
    (r"雅思|ielts", "雅思"),
    (r"托福|toefl|四六级|四级|六级|考研英语", "英语考试"),
    (r"premiere|剪映|剪辑|剪视频", "视频剪辑"),
    (r"摄影|相机", "摄影"),
    (r"做饭|烹饪|炒菜|家常菜", "做饭"),
    (r"presentation|汇报|演讲", "Presentation"),
    (r"python", "Python编程"),
    (r"编程|代码|开发", "编程"),
    (r"英语口语|口语", "英语口语"),
    (r"英语|英文", "英语"),
    (r"健身|跑步|减脂|增肌", "健身"),
    (r"吉他|尤克里里", "吉他弹唱"),
    (r"画画|素描|手绘|板绘", "画画"),
    (r"写作|写文章|文案", "写作"),
    (r"设计|figma|ui", "设计"),
    (r"数据分析", "数据分析"),
)

_COMPILED_NAME_RULES: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(p, re.IGNORECASE), n) for p, n in _SKILL_NAME_RULES
)

# 冒号后面往往就是技能名：「我想学点什么：手冲咖啡」
_COLON_RE = re.compile(r"[：:]([^，。,!?！？\s]{1,12})")

# 「学会XX / 学个XX / 学一下XX」
_LEARN_RE = re.compile(r"学[会习]?(?:个|一下)?([^，。,!?！？\s]{1,12}?)(?:[，。,\s]|$)")

# 清洗前缀：「我想/我要…」「用30天」「里/内/的…」
_PREFIX_WANT_RE = re.compile(r"^我[想要]+")
_DAY_PREFIX_RE = re.compile(r"用?\d+\s*[天日周月]*")
_PREFIX_PARTICLE_RE = re.compile(r"^[里内的]+")

# 注意 count=1：源实现是 `replace(/[...]/, '')` **无 g 标志**，只去第一个
_STRIP_ONE_PUNCT_RE = re.compile(r"[，。！？,.!?：:]")

SKILL_NAME_MAX_LEN = 12


def extract_skill_name(what: str) -> str:
    """从自然语言目标里提取技能名（仅用于未命中领域库时）。"""
    raw = what or ""
    lowered = raw.lower()

    for pattern, name in _COMPILED_NAME_RULES:
        if pattern.search(lowered):
            return name

    colon = _COLON_RE.search(raw)
    if colon:
        return colon.group(1).strip()

    learn = _LEARN_RE.search(raw)
    if learn and learn.group(1).strip():
        return learn.group(1).strip()

    stripped = _PREFIX_WANT_RE.sub("", raw)
    stripped = _DAY_PREFIX_RE.sub("", stripped)
    stripped = _PREFIX_PARTICLE_RE.sub("", stripped)
    base = stripped or raw
    return _STRIP_ONE_PUNCT_RE.sub("", base[:SKILL_NAME_MAX_LEN], count=1).strip()


# ============================================================
# 3. 通用兜底拆解（长尾技能：不建库也能出计划）
# ============================================================
def generic_units(what: str) -> tuple[UnitDef, ...]:
    """未命中领域库时的四阶段通用拆解。

    仍然坚持「具体、能做、有结果」—— 每条任务都带达标标准，
    不使用「多练习」「多看书」这类无法验收的表述。
    """
    name = extract_skill_name(what)
    return (
        UnitDef(
            name=f"{name} · 入门准备",
            tasks=(
                TaskDef(
                    task=f"找出学「{name}」最常用的 3 个工具 / APP / 资源，"
                    '各花 15 分钟试用，选一个当主力，写一句"为什么选它"',
                    duration="45分钟",
                    acceptance="定了主力工具 + 一句理由",
                ),
                TaskDef(
                    task=f'读 2 篇"如何入门{name}"的高赞经验帖，'
                    "各读完后用自己的话写出 3 条共同建议",
                    duration="40分钟",
                    acceptance="6 条建议，合并重复后至少 3 条",
                ),
            ),
        ),
        UnitDef(
            name=f"{name} · 基础操作",
            tasks=(
                TaskDef(
                    task="跟一个入门教程完整做一遍（边看边做、不跳步骤），"
                    "做的过程记下卡壳的 3 个地方",
                    duration="60分钟",
                    acceptance="做出教程的成品 + 卡壳清单",
                ),
                TaskDef(
                    task="隔天不看教程，把昨天的成品独立重做一遍，卡住才允许回看",
                    duration="60分钟",
                    acceptance="能独立重做 80%",
                ),
            ),
        ),
        UnitDef(
            name=f"{name} · 核心练习",
            tasks=(
                TaskDef(
                    task=f"找一件你生活里真实需要用「{name}」解决的小事，直接用它解决一次",
                    duration="45分钟",
                    acceptance="事情真的被解决了",
                    repeatable=True,
                ),
                TaskDef(
                    task=f"给「{name}」定一个 30 分钟内能做完的小练习，做完立刻检验产出",
                    duration="30分钟",
                    acceptance="有一个看得见的产出",
                    repeatable=True,
                ),
            ),
        ),
        UnitDef(
            name=f"{name} · 实战产出",
            tasks=(
                TaskDef(
                    task=f"独立完成一个属于你自己的「{name}」小作品，"
                    "做完拿给一个朋友看，请对方说一句最直观的感受",
                    duration="90分钟",
                    acceptance="一个作品 + 一条他人反馈",
                ),
            ),
        ),
    )


def generic_verify_task(what: str) -> str:
    """未命中领域库时的验证任务。"""
    return (
        f"独立完成一个「{extract_skill_name(what)}」的完整成品"
        "（不看教程、不找人代做），并把它记录为一段真实经历。"
    )


# ============================================================
# 4. 能力单元构建与阶段划分
# ============================================================
def build_unit_defs(domain: DomainDef | None, what: str = "") -> tuple[PlannedUnit, ...]:
    """得到能力单元列表，并按位置划分三阶段。

    阶段规则（源实现原样）：前 40% 打基础、中间到 85% 核心练习、其余整合实战。

    关于源实现的单元过滤：源码里有一个
        `(!u.adv || opts.wantsAdvanced) && (!u.beginnerOnly || opts.isZero)`
    但它读的是**单元层级**的 `u.beginnerOnly`，而数据实际标在**任务层级**
    （见 domain_lib.py 的说明）→ 条件恒为真，**该过滤从未生效过**。
    本模块因此不做过滤：实现一个源作者本意不明的行为，等于发明新逻辑。
    """
    base: tuple[UnitDef, ...]
    if domain is not None:
        base = domain.units
    else:
        base = generic_units(what)

    total = len(base)
    return tuple(
        PlannedUnit(
            name=unit.name,
            tasks=unit.tasks,
            phase=1 if i < total * 0.4 else (2 if i < total * 0.85 else 3),
        )
        for i, unit in enumerate(base)
    )


# ============================================================
# 4.5 时长归一化（落库前的必要转换）
# ============================================================
_DURATION_RE = re.compile(r"(\d+)\s*(分钟|小时|分|h|min)")


def parse_duration_minutes(text: str | None) -> int | None:
    """把领域库的时长文本归一为分钟数。

    领域库的 `duration` 是**给人看的文本**，形态并不统一，实测有：
        "40分钟" · "90分钟" · "45分钟"
        "约 3 小时（可拆两个半天）"   ← 带前缀与括号说明
    若要写入 `Task.estimated_minutes`（整数），必须先归一 —— 否则这一列
    存不进去，时长也就无法参与任何排期或统计。

    识别失败时返回 None，**不做猜测**：宁可让这一列为空，也不要写入
    一个编造的数字（那会污染后续所有基于时长的统计）。
    """
    if not text:
        return None
    matched = _DURATION_RE.search(text)
    if not matched:
        return None
    amount = int(matched.group(1))
    unit = matched.group(2)
    return amount * 60 if unit in ("小时", "h") else amount


# ============================================================
# 5. 任务展开
# ============================================================
def expand_tasks(
    pool: tuple[TaskDef, ...],
    count: int,
    default_duration: str,
    offset: int = 0,
    counts: dict[int, int] | None = None,
) -> list[_ExpandedTask]:
    """从任务池展开 count 条任务。

    规则（源实现原样）：
      · 先按顺序消耗一遍整个任务池；
      · 池子耗尽后循环整个池子，其中**标记 repeatable 的任务权重 ×2**；
      · 同一任务被重复使用时追加「（第N次）」。

    `counts` 由调用方持有并在多次调用间共享 —— 周模式下需要跨周累计
    使用次数，才能正确标出「第 2 次」。
    """
    if not pool or count <= 0:
        return []

    first_len = len(pool)
    cycle: list[int] = []
    for i, task in enumerate(pool):
        cycle.append(i)
        if task.repeatable:
            cycle.append(i)  # 可重复练习的任务在循环池里占两个槽位

    counter = counts if counts is not None else {}
    out: list[_ExpandedTask] = []
    for j in range(count):
        slot = offset + j
        idx = slot if slot < first_len else cycle[(slot - first_len) % len(cycle)]
        counter[idx] = counter.get(idx, 0) + 1
        task = pool[idx]
        suffix = f"（第{counter[idx]}次）" if counter[idx] > 1 else ""
        out.append(
            _ExpandedTask(
                task=task.task + suffix,
                duration=task.duration or default_duration,
                acceptance=task.acceptance,
            )
        )
    return out


# ============================================================
# 6. 计划生成
# ============================================================
def generate_plan(
    units: tuple[PlannedUnit, ...],
    total_days: int,
    minutes_per_day: int,
    verify_task: str,
) -> tuple[PlanItem, ...]:
    """把能力单元排成逐日 / 逐周的日程。

    ≤45 天 → 按天（Day N）；>45 天 → 按周（Week N，每周 5 个任务）。
    两种情况都在末尾追加一个**验证任务** —— 这是整套体系里最关键的一环：
    它要求用户真实地做一次完整成品并记录下来，作为「技能点亮」的凭证。
    """
    plan: list[PlanItem] = []
    default_duration = f"{minutes_per_day}分钟"
    verify_duration = f"{max(minutes_per_day * 2, 120)}分钟"

    if not units:
        # 防御：理论上不会发生（generic_units 至少返回 4 个单元）
        plan.append(
            PlanItem("verify", 1, "Day 1｜🏆 验证任务", verify_task,
                     verify_duration, VERIFY_ACCEPTANCE, is_verify=True)
        )
        return tuple(plan)

    total_weight = sum(len(u.tasks) for u in units) or 1

    if total_days <= DAILY_MODE_MAX_DAYS:
        plan.extend(
            _plan_daily(units, total_days, default_duration, verify_task,
                        verify_duration, total_weight)
        )
    else:
        plan.extend(
            _plan_weekly(units, total_days, default_duration, verify_task,
                         verify_duration, total_weight)
        )
    return tuple(plan)


def _plan_daily(
    units: tuple[PlannedUnit, ...],
    total_days: int,
    default_duration: str,
    verify_task: str,
    verify_duration: str,
    total_weight: int,
) -> list[PlanItem]:
    """按天排期：先给每个单元分配天数配额，再逐日展开任务。"""
    # 最后一天留给验证任务，所以学习日是 total_days - 1
    learning_days = max(len(units), total_days - 1)

    alloc: list[int] = []
    allocated = 0
    for unit in units:
        # 不重复的任务数决定该单元「值得排几天」的上限
        unique = sum(1 for t in unit.tasks if not t.repeatable) or len(unit.tasks)
        raw = max(1, js_round(learning_days * len(unit.tasks) / total_weight))
        # 上限 unique + 2：避免同一个练习机械重复太多次
        quota = min(raw, unique + 2)
        alloc.append(quota)
        allocated += quota

    if allocated != learning_days:
        if allocated > learning_days:
            scale = learning_days / allocated
            rescaled = 0
            for i in range(len(units)):
                alloc[i] = max(1, js_round(alloc[i] * scale))
                rescaled += alloc[i]
            allocated = rescaled

        # 补齐或继续削减：轮流在单元间增减，保证总数精确等于 learning_days
        rest = learning_days - allocated
        i = 0
        guard = 0
        while rest != 0 and guard < 2000:
            k = i % len(units)
            if rest > 0:
                alloc[k] += 1
                rest -= 1
            elif alloc[k] > 1:
                alloc[k] -= 1
                rest += 1
            i += 1
            guard += 1

    out: list[PlanItem] = []
    day = 1
    for idx, unit in enumerate(units):
        counts: dict[int, int] = {}
        expanded = expand_tasks(unit.tasks, alloc[idx], default_duration, 0, counts)
        for item in expanded:
            out.append(
                PlanItem(
                    unit_id=f"u{idx}",
                    day=day,
                    title=f"Day {day}｜{unit.name}",
                    task=item.task,
                    duration=item.duration,
                    acceptance=item.acceptance,
                )
            )
            day += 1

    out.append(
        PlanItem(
            unit_id="verify",
            day=day,
            title=f"Day {day}｜🏆 验证任务",
            task=verify_task,
            duration=verify_duration,
            acceptance=VERIFY_ACCEPTANCE,
            is_verify=True,
        )
    )
    return out


def _plan_weekly(
    units: tuple[PlannedUnit, ...],
    total_days: int,
    default_duration: str,
    verify_task: str,
    verify_duration: str,
    total_weight: int,
) -> list[PlanItem]:
    """按周排期：每周 5 个任务，最后一个单元吃掉剩余周数。"""
    weeks = max(len(units) + 1, js_round(total_days / 7))

    out: list[PlanItem] = []
    week = 1
    for idx, unit in enumerate(units):
        unit_weeks = max(1, js_round((weeks - 1) * len(unit.tasks) / total_weight))
        # 最后一个单元直接吃掉剩余周，避免配额凑不齐导致尾部长短不一
        if idx == len(units) - 1:
            unit_weeks = max(1, (weeks - 1) - (week - 1))

        offset = 0
        counts: dict[int, int] = {}  # 跨周累计，用于「（第N次）」
        for _ in range(unit_weeks):
            expanded = expand_tasks(
                unit.tasks, WEEKLY_TASKS_PER_WEEK, default_duration, offset, counts
            )
            for item in expanded:
                out.append(
                    PlanItem(
                        unit_id=f"u{idx}",
                        day=week,
                        title=f"Week {week}｜{unit.name}",
                        task=item.task,
                        duration=item.duration,
                        acceptance=item.acceptance,
                    )
                )
            offset += WEEKLY_TASKS_PER_WEEK
            week += 1

    out.append(
        PlanItem(
            unit_id="verify",
            day=week,
            title=f"Week {week}｜🏆 验证任务",
            task=verify_task,
            duration=verify_duration,
            acceptance=VERIFY_ACCEPTANCE,
            is_verify=True,
        )
    )
    return out


# ============================================================
# 7. 顶层入口
# ============================================================
def generate_study_plan(
    goal: str,
    total_days: int = 30,
    minutes_per_day: int = 45,
) -> PlanResult:
    """从一句自然语言目标生成完整学习计划（离线可用，不依赖任何模型）。

    这是 S6-1 对外的主入口：
        generate_study_plan("我想学雅思，30天，每天1小时")
    """
    goal = (goal or "").strip()
    total_days = max(1, int(total_days or 30))
    minutes_per_day = max(10, int(minutes_per_day or 45))

    domain = match_domain(goal)
    units = build_unit_defs(domain, goal)
    verify = domain.verify_task if domain else generic_verify_task(goal)
    items = generate_plan(units, total_days, minutes_per_day, verify)

    return PlanResult(
        goal=goal,
        skill_name=domain.name if domain else extract_skill_name(goal),
        matched=domain is not None,
        domain_key=domain.key if domain else None,
        domain_name=domain.name if domain else None,
        total_days=total_days,
        minutes_per_day=minutes_per_day,
        weekly_mode=total_days > DAILY_MODE_MAX_DAYS,
        units=units,
        items=items,
        verify_task=verify,
    )


__all__ = [
    "DAILY_MODE_MAX_DAYS",
    "VERIFY_ACCEPTANCE",
    "WEEKLY_TASKS_PER_WEEK",
    "PlanItem",
    "PlanResult",
    "PlannedUnit",
    "build_unit_defs",
    "expand_tasks",
    "extract_skill_name",
    "generate_plan",
    "generate_study_plan",
    "generic_units",
    "generic_verify_task",
    "js_round",
    "list_domains",
    "match_domain",
    "parse_duration_minutes",
]
