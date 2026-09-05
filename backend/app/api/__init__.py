# ============================================================
# 路由聚合：所有模块挂载到 /api/v1
# ============================================================
from __future__ import annotations

from fastapi import APIRouter

from app.api import (
    auth,
    backup,
    conversation,
    dashboard,
    document,
    folder,
    health,
    notification,
    panel,
    project,
    review,
    task,
)

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(task.router)
api_router.include_router(folder.router)
api_router.include_router(document.router)
api_router.include_router(document.tags_router)
api_router.include_router(document.search_router)
api_router.include_router(conversation.router)
api_router.include_router(conversation.ai_router)
api_router.include_router(review.router)
api_router.include_router(dashboard.router)
api_router.include_router(backup.router)
api_router.include_router(backup.data_router)
api_router.include_router(panel.router)
api_router.include_router(panel.todo_router)
api_router.include_router(panel.reminder_router)
api_router.include_router(notification.router)
api_router.include_router(project.router)
