# ============================================================
# 成长体系事件订阅者（S6-2）
#
# 核心设计：**不改任何现有模块的代码**。
# 启明星已有 28 种事件的 event_bus，这里只是"多了一个订阅者"。
# Task / Learning / Life / Resource / Asset 等模块一行未动，
# 用户勾任务、复习卡片、打卡时，EXP 由本模块自动结算。
#
# 这是架构给的红利 —— 交付物 A 的单页站做不到这一点：
# 它必须把 addExp() 手工插进每一处交互代码里。
#
# 幂等保证
#   每次结算都带 source_key（形如 "task:<id>:completed"），由
#   growth_events 的 (user_id, source_key) 唯一索引兜底。
#   事件重复投递（任务反复标记完成、异常后重放）不会刷分。
#
# 为什么多数事件不带 user_id
#   现有 publish 调用只传业务 id（task_id / card_id …）。本模块不改这些
#   调用点，而是在 handler 内用 repository 反查实体拿 user_id ——
#   "零侵入"的代价是一次额外查询，这个交换是值得的。
# ============================================================
from __future__ import annotations

from typing import Callable

from sqlalchemy.orm import Session

from app.core.event_bus import (
    EVENT_DIARY_CREATED,
    EVENT_DOCUMENT_SAVED,
    EVENT_FLASHCARD_REVIEWED,
    EVENT_HABIT_CHECKIN,
    EVENT_INBOX_ITEM_CREATED,
    EVENT_INBOX_ITEM_PROCESSED,
    EVENT_MOOD_LOGGED,
    EVENT_PROJECT_MEMORY_CREATED,
    EVENT_PROMPT_USED,
    EVENT_SOP_USED,
    EVENT_STUDY_TIME_LOGGED,
    EVENT_TASK_COMPLETED,
    EVENT_TASK_CREATED,
    EVENT_WORKFLOW_APPLIED,
    event_bus,
)
from app.core.event_handlers import submit_background
from app.core.logger import get_logger
from app.database import SessionLocal
from app.repositories import (
    DiaryRepository,
    DocumentRepository,
    FlashcardRepository,
    HabitRepository,
    InboxItemRepository,
    MoodRepository,
    ProjectMemoryRepository,
    PromptRepository,
    SOPRepository,
    StudyTimeRepository,
    TaskRepository,
    WorkflowRepository,
)
from app.services.growth_service import EXP_RULES, GrowthService, exp_for_study_minutes

logger = get_logger("growth_handlers")

# loader 返回 (user_id, 用于技能归类的文本) 或 None
Loader = Callable[[Session], "tuple[str, str | None] | None"]


async def _grant(event_type: str, source_key: str, label: str, loader: Loader,
                 exp: int | None = None) -> None:
    """通用结算：查实体 → 取 user_id → 幂等加 EXP。

    exp 为 None 时取 EXP_RULES[event_type]（见 growth_service 的权重重标定）。
    """
    db = SessionLocal()
    try:
        loaded = loader(db)
        if not loaded:
            return
        user_id, text = loaded
        amount = EXP_RULES.get(event_type, 0) if exp is None else exp
        if amount <= 0:
            return
        GrowthService(db).award(
            user_id=user_id,
            source_key=source_key,
            event_type=event_type,
            exp=amount,
            label=label,
            classified_text=text,
        )
    except Exception:
        # 结算失败绝不能影响主流程（用户的任务已经完成、卡片已经复习）
        logger.exception("EXP 结算失败: %s", source_key)
    finally:
        db.close()


def _submit(event_type: str, source_key: str, label: str, loader: Loader,
            exp: int | None = None) -> None:
    submit_background(_grant(event_type, source_key, label, loader, exp))


# ============================================================
# 订阅者入口（同步函数 → 提交后台任务，与现有约定一致）
# ============================================================
def on_task_completed_growth(task_id: str, **kwargs) -> None:
    def loader(db: Session):
        task = TaskRepository(db).get(task_id)
        if not task:
            return None
        return task.user_id, f"{task.title} {task.description or ''}"

    _submit("task.completed", f"task:{task_id}:completed", "完成任务", loader)


def on_task_created_growth(task_id: str, **kwargs) -> None:
    def loader(db: Session):
        task = TaskRepository(db).get(task_id)
        return (task.user_id, task.title) if task else None

    _submit("task.created", f"task:{task_id}:created", "创建任务", loader)


def on_document_saved_growth(document_id: str, **kwargs) -> None:
    def loader(db: Session):
        doc = DocumentRepository(db).get(document_id)
        if not doc:
            return None
        return doc.user_id, f"{doc.title or ''} {doc.content or ''}"

    _submit("document.saved", f"document:{document_id}:saved", "保存文档", loader)


def on_flashcard_reviewed_growth(card_id: str, **kwargs) -> None:
    # 同一张卡片的每次复习都应计分（学习行为本身就有价值），
    # 因此 source_key 带上复习时间戳而不是只用 card_id
    def loader(db: Session):
        card = FlashcardRepository(db).get(card_id)
        return (card.user_id, card.front) if card else None

    _submit("flashcard.reviewed", f"flashcard:{card_id}:{_stamp()}", "复习卡片", loader)


def on_study_time_logged_growth(log_id: str, duration: int = 0, **kwargs) -> None:
    """学习时长按分钟折算（每 10 分钟 1 点，单次上限 6 点）。"""

    def loader(db: Session):
        log = StudyTimeRepository(db).get(log_id)
        if not log:
            return None
        return log.user_id, log.subject

    _submit(
        "study.time.logged",
        f"study:{log_id}",
        f"学习 {duration} 分钟",
        loader,
        exp=exp_for_study_minutes(duration),
    )


def on_habit_checkin_growth(habit_id: str, date: str = "", **kwargs) -> None:
    def loader(db: Session):
        habit = HabitRepository(db).get(habit_id)
        return (habit.user_id, habit.name) if habit else None

    _submit("habit.checkin", f"habit:{habit_id}:{date}", "习惯打卡", loader)


def on_mood_logged_growth(mood_id: str, **kwargs) -> None:
    def loader(db: Session):
        mood = MoodRepository(db).get(mood_id)
        return (mood.user_id, None) if mood else None

    _submit("mood.logged", f"mood:{mood_id}", "记录心情", loader)


def on_diary_created_growth(diary_id: str, **kwargs) -> None:
    def loader(db: Session):
        diary = DiaryRepository(db).get(diary_id)
        if not diary:
            return None
        return diary.user_id, f"{getattr(diary, 'title', '') or ''}"

    _submit("diary.created", f"diary:{diary_id}", "写日记", loader)


def on_sop_used_growth(sop_id: str, **kwargs) -> None:
    def loader(db: Session):
        sop = SOPRepository(db).get(sop_id)
        return (sop.user_id, sop.title) if sop else None

    _submit("sop.used", f"sop:{sop_id}:{_stamp()}", "复用 SOP", loader)


def on_prompt_used_growth(prompt_id: str, **kwargs) -> None:
    def loader(db: Session):
        prompt = PromptRepository(db).get(prompt_id)
        return (prompt.user_id, prompt.title) if prompt else None

    _submit("prompt.used", f"prompt:{prompt_id}:{_stamp()}", "使用提示词", loader)


def on_project_memory_created_growth(memory_id: str, **kwargs) -> None:
    def loader(db: Session):
        memory = ProjectMemoryRepository(db).get(memory_id)
        if not memory:
            return None
        return memory.user_id, f"{getattr(memory, 'title', '') or ''} {getattr(memory, 'content', '') or ''}"

    _submit("project.memory.created", f"memory:{memory_id}", "沉淀项目记忆", loader)


def on_inbox_item_created_growth(item_id: str, **kwargs) -> None:
    def loader(db: Session):
        item = InboxItemRepository(db).get(item_id)
        return (item.user_id, getattr(item, "content", None)) if item else None

    _submit("inbox.item.created", f"inbox:{item_id}:created", "收集想法", loader)


def on_inbox_item_processed_growth(item_id: str, action: str = "", **kwargs) -> None:
    def loader(db: Session):
        item = InboxItemRepository(db).get(item_id)
        return (item.user_id, getattr(item, "content", None)) if item else None

    _submit("inbox.item.processed", f"inbox:{item_id}:processed", f"整理收集箱({action})", loader)


def on_workflow_applied_growth(workflow_id: str, user_id: str = "", **kwargs) -> None:
    """工作流应用：这是唯一直接带 user_id 的事件。"""
    def loader(db: Session):
        if user_id:
            return user_id, None
        workflow = WorkflowRepository(db).get(workflow_id)
        return (workflow.user_id, None) if workflow else None

    _submit("project.updated", f"workflow:{workflow_id}:{_stamp()}", "应用工作流", loader)


# ---------- 工具 ----------
def _stamp() -> str:
    """秒级时间戳，用于"同一实体可以被多次计分"的场景做幂等键。"""
    from datetime import datetime, timezone

    return str(int(datetime.now(timezone.utc).timestamp()))


# 订阅表：事件 → 订阅者
_SUBSCRIPTIONS: tuple[tuple[str, Callable], ...] = (
    (EVENT_TASK_COMPLETED, on_task_completed_growth),
    (EVENT_TASK_CREATED, on_task_created_growth),
    (EVENT_DOCUMENT_SAVED, on_document_saved_growth),
    (EVENT_FLASHCARD_REVIEWED, on_flashcard_reviewed_growth),
    (EVENT_STUDY_TIME_LOGGED, on_study_time_logged_growth),
    (EVENT_HABIT_CHECKIN, on_habit_checkin_growth),
    (EVENT_MOOD_LOGGED, on_mood_logged_growth),
    (EVENT_DIARY_CREATED, on_diary_created_growth),
    (EVENT_SOP_USED, on_sop_used_growth),
    (EVENT_PROMPT_USED, on_prompt_used_growth),
    (EVENT_PROJECT_MEMORY_CREATED, on_project_memory_created_growth),
    (EVENT_INBOX_ITEM_CREATED, on_inbox_item_created_growth),
    (EVENT_INBOX_ITEM_PROCESSED, on_inbox_item_processed_growth),
    (EVENT_WORKFLOW_APPLIED, on_workflow_applied_growth),
)


def register_growth_handlers() -> None:
    """注册成长体系订阅者（由 lifespan 调用一次）。"""
    for event, handler in _SUBSCRIPTIONS:
        event_bus.subscribe(event, handler)
    logger.info("成长体系订阅者已注册（%d 个事件）", len(_SUBSCRIPTIONS))
