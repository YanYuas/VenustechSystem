# ============================================================
# FastAPI 应用入口
# - app factory + lifespan（迁移/维护/种子/日志）
# - 统一异常处理器（不泄堆栈）
# - CORS 允许前端 dev server
# ============================================================
from __future__ import annotations

import sys

# Windows 控制台 UTF-8 保障（防止日志中文乱码）
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import api_router
from app.config import get_settings
from app.core.event_handlers import register_event_handlers, set_event_loop
from app.core.exceptions import AppException
from app.core.logger import get_logger, setup_logger
from app.core.response import error
from app.database import SessionLocal, run_maintenance
from app.migrate import run_migrations
from app.seed import seed_if_empty

settings = get_settings()
logger = get_logger("main")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    setup_logger()
    run_migrations()
    run_maintenance()
    with SessionLocal() as db:
        if settings.demo_seed:
            seed_if_empty(db)
        # 重复任务（M02 F05）：启动时惰性生成到期实例（幂等）
        try:
            from sqlalchemy import select
            from app.models.user import User
            from app.services.task_service import TaskService
            svc = TaskService(db)
            total = sum(
                svc.generate_recurring_instances(uid)
                for (uid,) in db.execute(select(User.id)).all()
            )
            if total:
                logger.info(f"重复任务生成 {total} 个实例")
        except Exception:
            logger.exception("重复任务生成失败（不影响启动）")
    # 注册事件总线订阅者（文档保存→AI摘要/标签，任务完成→通知）
    import asyncio
    set_event_loop(asyncio.get_running_loop())
    register_event_handlers()
    logger.info("后端启动完成")
    yield


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version=settings.version, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)

    @app.exception_handler(AppException)
    async def app_exception_handler(_request: Request, exc: AppException):
        logger.warning(f"业务异常 {exc.code}: {exc.message}")
        return JSONResponse(
            status_code=exc.http_status, content=error(exc.code, exc.message)
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_request: Request, exc: RequestValidationError):
        msgs = []
        for e in exc.errors():
            loc = ".".join(str(x) for x in e.get("loc", []))
            msgs.append(f"{loc}: {e.get('msg', '')}")
        return JSONResponse(
            status_code=400,
            content=error(1001, "参数错误: " + "; ".join(msgs)),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_request: Request, exc: Exception):
        logger.exception("未捕获异常")
        return JSONResponse(status_code=500, content=error(5000, "服务器内部错误"))

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=settings.dev)
