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
    events,
    folder,
    health,
    notification,
    panel,
    plugins,
    security,
    logs,
    project,
    review,
    task,
    resource,
    learning,
    life,
    asset,
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
api_router.include_router(events.router)
api_router.include_router(plugins.router)
api_router.include_router(security.router)
api_router.include_router(logs.router)
api_router.include_router(resource.router)
api_router.include_router(learning.router)
api_router.include_router(life.router)
api_router.include_router(asset.router)
