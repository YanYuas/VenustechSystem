# ============================================================
# 事件总线订阅者（应用启动时注册）
# - document.saved → AI 自动摘要 + 标签建议（异步后台执行，并发受控）
# - task.completed → 创建完成通知（异步，不阻塞请求）
# ============================================================
from __future__ import annotations

import asyncio

from app.core.event_bus import (
    EVENT_DOCUMENT_SAVED,
    EVENT_TASK_COMPLETED,
    event_bus,
)
from app.core.logger import get_logger
from app.database import SessionLocal
from app.repositories import (
    DocumentRepository,
    NotificationRepository,
    TaskRepository,
    UserRepository,
)
from app.services.ai import AIService

logger = get_logger("event_handlers")

# 全局事件循环引用（由 lifespan 设置）
_loop: asyncio.AbstractEventLoop | None = None

# AI 并发控制：最多 2 个并发 AI 调用，避免 API 限流
_ai_semaphore = asyncio.Semaphore(2)


def set_event_loop(loop: asyncio.AbstractEventLoop) -> None:
    """由 lifespan 调用，注入事件循环供同步事件处理器使用。"""
    global _loop
    _loop = loop


def _run_async(coro) -> None:
    """在后台事件循环中执行协程（fire-and-forget，异常自动记录）。

    事件可能从 FastAPI 线程池线程发布（同步路由内），loop.create_task
    非线程安全，必须用 run_coroutine_threadsafe 提交。
    """
    if _loop is None:
        logger.warning("事件循环未初始化，跳过异步事件处理")
        return
    try:
        future = asyncio.run_coroutine_threadsafe(coro, _loop)
        future.add_done_callback(_on_future_done)
    except RuntimeError:
        # 事件循环已关闭，丢弃事件（不再 asyncio.run 阻塞线程池线程）
        logger.warning("事件循环已关闭，丢弃事件")


def _on_future_done(future: "concurrent.futures.Future") -> None:
    """后台任务完成回调：记录未捕获的异常。"""
    try:
        exc = future.exception()
        if exc:
            logger.error("后台事件任务异常: %s", exc, exc_info=exc)
    except Exception:
        pass


# ---------- 文档保存：AI 自动摘要 + 标签建议 ----------
async def _handle_document_saved(document_id: str) -> None:
    """文档保存后异步生成摘要和标签建议（仅当用户配置了 API Key）。"""
    async with _ai_semaphore:
        db = SessionLocal()
        try:
            user = UserRepository(db).get_by_username("default_user")
            if not user or not user.api_key_encrypted or not user.ai_enabled:
                logger.debug("AI 未启用，跳过文档自动摘要: %s", document_id)
                return

            doc = DocumentRepository(db).get(document_id)
            if not doc or not doc.content or len(doc.content) < 50:
                return  # 内容太短，跳过

            ai = AIService(db, user)
            # 自动摘要
            try:
                summary = await ai.summarize(document_id)
                if summary and hasattr(summary, "summary") and summary.summary:
                    doc.summary = summary.summary[:500]
                    db.commit()
                    logger.info("文档自动摘要完成: %s", document_id)
            except Exception:
                logger.exception("文档自动摘要失败: %s", document_id)

            # 标签建议
            try:
                tags = await ai.suggest_tags(document_id)
                if tags and hasattr(tags, "tags") and tags.tags:
                    doc.ai_suggested_tags = tags.tags[:10]
                    db.commit()
                    logger.info("文档标签建议完成: %s", document_id)
            except Exception:
                logger.exception("文档标签建议失败: %s", document_id)
        finally:
            db.close()


def on_document_saved(document_id: str, **kwargs) -> None:
    _run_async(_handle_document_saved(document_id))


# ---------- 任务完成：创建通知 ----------
async def _handle_task_completed(task_id: str) -> None:
    """任务完成时异步创建系统通知（不阻塞请求线程）。"""
    db = SessionLocal()
    try:
        task = TaskRepository(db).get(task_id)
        if not task:
            return
        NotificationRepository(db).create(
            user_id=task.user_id,
            type="success",
            title="任务已完成",
            content=f"「{task.title[:50]}」已标记为完成",
            source_type="task",
            source_id=task_id,
        )
        logger.info("任务完成通知已创建: %s", task_id)
    except Exception:
        logger.exception("创建任务完成通知失败")
    finally:
        db.close()


def on_task_completed(task_id: str, **kwargs) -> None:
    _run_async(_handle_task_completed(task_id))


def register_event_handlers() -> None:
    """注册所有事件订阅者（由 lifespan 调用一次）。"""
    event_bus.subscribe(EVENT_DOCUMENT_SAVED, on_document_saved)
    event_bus.subscribe(EVENT_TASK_COMPLETED, on_task_completed)
    logger.info("事件总线订阅者已注册（AI并发上限: 2）")
