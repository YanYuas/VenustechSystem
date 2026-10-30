# ============================================================
# 日志（loguru：控制台 + 按天轮转文件，保留 30 天）
#
# D-26：全仓日志后端统一为 loguru（`get_logger`），不再混用 stdlib logging。
# stdlib logger 下 loguru 的 `{}` 占位与 `opt(exception=True)` 全部失效
# （参数静默丢失 / AttributeError），详见 tests/test_logging_contract.py。
# ============================================================
from __future__ import annotations

import logging
import sys

from loguru import logger

from app.config import get_settings


# ---------- loguru → stdlib logging 单向桥（按需安装，给 caplog / 第三方工具） ----------
# 背景：本仓日志后端是 loguru，而通用调试设施（pytest 的 `caplog`、第三方库的
# 日志钩子）只认 stdlib `logging.Handler`。不桥接时 caplog 永远捕不到应用日志
# （D-18 排查时因此只能改用 spy 打桩）。
#
# **为什么默认不安装**（这是实测结论，不是保守）：
#   1) 全局桥会让每条日志再走一遍 stdlib logging —— 生产环境若 stdlib 侧有
#      handler，同一行日志会被打印两次；
#   2) 本机（Windows + pytest 默认 fd 级捕获）实测：桥接后 stdlib handler 输出的
#      captured stderr 出现非 UTF-8 字节，pytest 读捕获文件时
#      `UnicodeDecodeError: invalid start byte` → 一次解码失败让整场测试级联
#      报错（2987 errors）。关掉桥后同一份代码全绿，因此桥不能常驻。
#
# 结论：桥做成**显式工具**，只在真正需要 caplog 的场景临时安装
# （见 tests/conftest.py 的 `_loguru_stdlib_bridge_for_caplog` fixture）。


def _forward_to_stdlib(message) -> None:  # loguru sink
    """把一条 loguru 记录转发成 stdlib LogRecord（供 caplog / 第三方捕获）。

    `record["message"]` 已是 loguru 格式化后的最终文本（`{}` 参数已填充），
    因此 stdlib 侧看到的是可读日志，不会出现裸 `{}`。
    仅在 stdlib 侧确实有 handler 时转发，避免 lastResort 把 WARNING+ 再打一遍。
    """
    if not logging.getLogger().handlers:
        return
    record = message.record
    # loguru 的 level.no 与 stdlib logging 数值一致（INFO=20 / WARNING=30 / ...）
    logging.getLogger(record["name"] or "app").log(record["level"].no, record["message"])


def add_stdlib_bridge() -> int:
    """安装 loguru→stdlib 桥，返回 loguru sink id（调用方负责用 remove 移除）。"""
    return logger.add(_forward_to_stdlib, level=0, catch=True)


def remove_stdlib_bridge(sink_id: int | None) -> None:
    """移除 `add_stdlib_bridge()` 安装的 sink（幂等：已被清掉时静默忽略）。"""
    if sink_id is None:
        return
    try:
        logger.remove(sink_id)
    except ValueError:
        pass


def setup_logger() -> None:
    settings = get_settings()
    logger.remove()
    logger.add(
        sys.stderr,
        level=settings.log_level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level:<7}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    )
    logger.add(
        settings.logs_dir / "{time:YYYY-MM-DD}.log",
        rotation="00:00",
        retention="30 days",
        level=settings.log_level,
        encoding="utf-8",
    )


def get_logger(name: str = "app"):
    return logger.bind(name=name)
