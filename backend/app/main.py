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
from app.bootstrap.event_handlers import register_event_handlers, set_event_loop
from app.bootstrap.growth_handlers import register_growth_handlers
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
            # D-42：与其它启动步骤（加密/重复任务/自动备份/插件）保持 fail-open
            # 一致 —— 演示数据失败（磁盘满/约束冲突等）不应阻断真实服务启动。
            # 失败后 rollback，避免半成品事务影响后续「重复任务」步骤。
            try:
                seed_if_empty(db)
            except Exception:
                logger.exception("演示数据初始化失败（不影响启动）")
                db.rollback()
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
                logger.info("重复任务生成 {} 个实例", total)
        except Exception:
            logger.exception("重复任务生成失败（不影响启动）")
    # 自动备份（PRD F7.1）：默认关闭；开启后按配置间隔判断是否到期。
    # D-44：遍历**全部用户**（原先只备份第一个用户）；每个用户独立 Session +
    # 独立 try/except —— 某个用户失败不影响其他用户，也不阻断启动。
    try:
        from sqlalchemy import select as _select

        from app.models.user import User as _User
        from app.services.backup_service import BackupService

        # 先取用户 id 快照（单独短 Session），再逐用户开独立 Session
        with SessionLocal() as _sdb:
            _user_ids = [row[0] for row in _sdb.execute(_select(_User.id)).all()]
        _ran = 0
        for _uid in _user_ids:
            try:
                with SessionLocal() as _bdb:
                    _info = BackupService(_bdb, _uid).auto_backup_if_due()
            except Exception:
                logger.exception("自动备份失败（用户 {}，不影响其他用户/启动）", _uid)
                continue
            if _info.get("ran"):
                _ran += 1
                logger.info("自动备份完成: {}", _info.get("path"))
        if _ran:
            logger.info("自动备份完成: {} 个用户", _ran)
    except Exception:
        logger.exception("自动备份检查失败（不影响启动）")

    # 注册事件总线订阅者（文档保存→AI摘要/标签，任务完成→通知）
    import asyncio
    set_event_loop(asyncio.get_running_loop())
    # D-43：业务订阅者与成长订阅者**各自独立 fail-open** —— 一个注册失败不影响
    # 另一个，也不阻断启动（与插件失败不影响主应用一致）。
    # set_event_loop 不包 try：它只是保存 loop 引用；若此处失败说明 lifespan
    # 不在事件循环中运行（运行环境异常），应暴露问题而不是静默吞掉。
    try:
        register_event_handlers()
    except Exception:
        logger.exception("业务事件订阅者注册失败（不影响启动）")
    # 成长体系（S6-2）：订阅既有事件结算 EXP / 技能归类。
    # 之所以放在这里而不是并入 register_event_handlers()，是为了让
    # "业务事件订阅者"与"成长体系订阅者"职责分离，各自独立注册。
    try:
        register_growth_handlers()
    except Exception:
        logger.exception("成长体系订阅者注册失败（不影响启动）")
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
            logger.info("插件路由已挂载: {}", pid)
    except Exception:
        logger.exception("插件系统初始化失败（不影响主应用）")

    @app.exception_handler(AppException)
    async def app_exception_handler(_request: Request, exc: AppException):
        logger.warning("业务异常 {}: {}", exc.code, exc.message)
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
