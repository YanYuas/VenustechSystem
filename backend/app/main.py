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
from app.core.growth_handlers import register_growth_handlers
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
    # 加密管理器初始化（mod-platform P1）：此前从未初始化，导致
    # get_encryption() 恒为 None —— API Key 加密被迫降级、vault/
    # assistant 每次自己 new 一个实例。统一在此初始化一次。
    try:
        from pathlib import Path

        from app.core.encryption import init_encryption

        init_encryption(Path(settings.data_dir))
        logger.info("加密管理器已初始化")
    except Exception:
        logger.exception("加密管理器初始化失败（敏感信息加密将不可用）")
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
    # 成长体系（S6-2）：订阅既有事件结算 EXP / 技能归类。
    # 之所以放在这里而不是并入 register_event_handlers()，是为了让
    # "业务事件订阅者"与"成长体系订阅者"职责分离，各自独立注册。
    register_growth_handlers()
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

    # 插件系统（S6-6）：第一次真实检验 —— AI HOT 信息源插件。
    # 内置插件随仓库分发（app/plugins_builtin/），用户插件放
    # {data_dir}/plugins/（同名 id 用户插件覆盖内置）。任何插件
    # 失败都不影响主应用启动。
    try:
        from pathlib import Path

        from app.core.plugin_manager import plugin_manager
        from app.core.event_bus import event_bus

        builtin_dir = Path(__file__).resolve().parent / "plugins_builtin"
        plugin_manager.initialize(event_bus=event_bus, data_dir=settings.data_dir)
        plugin_manager.discover(builtin_dir)
        plugin_manager.discover()  # 用户插件目录
        plugin_manager.load_all()
        for pid, router in plugin_manager.get_routers().items():
            app.include_router(router, prefix=f"/api/v1/plugins/{pid}")
            logger.info("插件路由已挂载: %s", pid)
    except Exception:
        logger.exception("插件系统初始化失败（不影响主应用）")

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
