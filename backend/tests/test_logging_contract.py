# ============================================================
# 日志契约守护（2026-10-11 新增 · 真机端到端探针发现）
#
# 发现的缺陷：全项目 50 处日志用了 `%s` / `exc_info=True`，但后端日志后端
# 是 **loguru**（占位符是 `{}`，`exc_info` 也不是它认的 kwarg）。实测后果 ——
# 参数与堆栈静默丢失，日志文本里留下裸 `%s`。真机 uvicorn 启动日志留下了
# 直接证据：「插件路由已挂载: %s」（应为实际插件名）。
#
# 本文件做三件事：
#   1. 把 loguru 的实测行为**钉成契约**（将来若换回标准库 logging，这里会红，
#      提醒同步改回 %-style）；
#   2. 静态扫描 backend/app，确保 %-占位符 / exc_info 不再回归；
#   3. **D-26**：静态扫描 backend/app，确保日志后端不再混用 stdlib
#      `logging.getLogger`（stdlib logger 下 loguru 的 `{}`/`opt()` 全部失效，
#      实测会留下裸 `{}`、抛 AttributeError）。豁免必须显式白名单 + 理由。
# ============================================================
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # backend/
APP_DIR = ROOT / "app"


# D-45（2026-10-30）：旧扫描器逐行匹配，多行日志调用里的 %-占位符会漏检
# （实测 backup_service / ai.client 共 3 处真漏）。这里把「跨行检测」钉成回归。
def _load_log_format_auditor():
    import importlib.util

    script = Path(__file__).resolve().parent.parent.parent / "scripts" / "audit_log_format.py"
    spec = importlib.util.spec_from_file_location("audit_log_format_regression", script)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestMultilineLogCallDetection:
    def test_multiline_percent_style_is_detected(self) -> None:
        mod = _load_log_format_auditor()
        text = (
            "logger.warning(\n"
            '    "备份版本 %s 与当前版本 %s 主版本号不同",\n'
            "    a, b,\n"
            ")\n"
        )
        kinds = [kind for _, kind in mod.scan_source(text)]
        assert "PCT_STYLE" in kinds

    def test_multiline_loguru_placeholders_are_accepted(self) -> None:
        mod = _load_log_format_auditor()
        text = (
            "logger.warning(\n"
            '    "备份版本 {} 与当前版本 {} 主版本号不同",\n'
            "    a, b,\n"
            ")\n"
        )
        assert mod.scan_source(text) == []

    def test_exc_info_inside_multiline_call_is_detected(self) -> None:
        mod = _load_log_format_auditor()
        text = "logger.error(\n    \"boom\",\n    exc_info=True,\n)\n"
        kinds = [kind for _, kind in mod.scan_source(text)]
        assert "EXC_INFO" in kinds

# `logger.info(` / `self.logger.info(` / `logger.opt(exception=True).warning(` 都覆盖
LOGGER_CALL = re.compile(
    r"\b(?:self\.)?logger\.(?:opt\([^)]*\)\.)?"
    r"(?:debug|info|success|warning|error|critical|exception|trace)\("
)
PCT_STYLE = re.compile(r"%s|%d|%\.\d+f")
STDLIB_GETLOGGER = re.compile(r"\blogging\.getLogger\(")

# 允许保留 stdlib logging.getLogger 的**显式白名单**（D-26）。
# 规则：每条必须给出理由；文件不再需要豁免时测试会提醒删除（防白名单腐烂）。
STDLIB_LOGGING_ALLOWED: dict[str, str] = {
    "app/config.py": (
        "与 app/core/logger.py 存在导入环（logger.py 顶部 `from app.config import get_settings`），"
        "且数据目录回退告警必须在日志系统初始化之前可用 —— 此处保留 stdlib logging 是唯一安全选择"
    ),
    "app/services/ai/ai_service.py": (
        "task-31 范围（AI 服务日志后端迁移由该任务统一处理）；合并后应删除本条豁免"
    ),
    "app/services/ai/client.py": (
        "task-31 范围（同上）；合并后应删除本条豁免"
    ),
}
# 日志桥自身必须使用 stdlib logging（把 loguru 记录转发给 caplog/第三方）
STDLIB_LOGGING_SELF = "app/core/logger.py"


def _app_python_files() -> list[Path]:
    return [p for p in sorted(APP_DIR.rglob("*.py")) if "__pycache__" not in p.parts]


class TestLoguruContract:
    """把 loguru 的真实行为钉成契约（捕获真实输出，非凭空断言）。"""

    @staticmethod
    def _capture_messages(call) -> list[str]:
        from loguru import logger

        msgs: list[str] = []
        sink = logger.add(lambda m: msgs.append(m.record["message"]), format="{message}")
        try:
            call(logger)
        finally:
            logger.remove(sink)
        return msgs

    def test_percent_style_args_are_dropped(self):
        """契约：loguru 认 `{}` 不认 `%s` —— 参数被静默丢弃，文本里留下裸 %s。"""
        msgs = self._capture_messages(lambda lg: lg.info("探针 %s 应丢失", 123))
        assert "探针 %s 应丢失" in msgs
        assert not any("探针 123 应丢失" == m for m in msgs)

    def test_brace_style_formats_argument(self):
        msgs = self._capture_messages(lambda lg: lg.info("探针 {} 应保留", 123))
        assert "探针 123 应保留" in msgs

    def test_composite_placeholders_round_trip(self):
        """复合占位符（%s + %.0f%%）转换后仍能正确格式化。"""
        msgs = self._capture_messages(lambda lg: lg.warning("事件 {} 失败率 {:.0f}%", "evt", 12.5))
        assert "事件 evt 失败率 12%" in msgs

    def test_exc_info_not_effective_but_opt_exception_is(self):
        """契约：exc_info= 在 loguru 下不进堆栈；`opt(exception=True)` 才进。"""
        from loguru import logger

        records: list[dict] = []
        sink = logger.add(lambda m: records.append(m.record), format="{message}")
        try:
            try:
                raise ValueError("boom")
            except ValueError:
                logger.warning("标准库写法")
                logger.opt(exception=True).warning("loguru 写法")
        finally:
            logger.remove(sink)

        by_msg = {r["message"]: r for r in records}
        assert by_msg["loguru 写法"].get("exception") is not None, "opt(exception=True) 应带堆栈"


class TestAppLogFormat:
    """静态扫描 backend/app：不允许再出现 loguru 不生效的日志写法。"""

    def _scan(self, predicate) -> list[str]:
        offenders: list[str] = []
        for p in _app_python_files():
            for i, line in enumerate(p.read_text(encoding="utf-8").split("\n"), 1):
                s = line.strip()
                if s.startswith("#") or not LOGGER_CALL.search(line):
                    continue
                if predicate(line):
                    offenders.append(f"{p.relative_to(ROOT)}:{i}: {s[:100]}")
        return offenders

    def test_no_percent_style_in_logger_calls(self):
        offenders = self._scan(lambda line: bool(PCT_STYLE.search(line)))
        assert not offenders, (
            "发现 loguru 不生效的 %-占位符（应用 {}）：\n" + "\n".join(offenders)
        )

    def test_no_exc_info_kwarg_in_logger_calls(self):
        offenders = self._scan(lambda line: "exc_info" in line)
        assert not offenders, (
            "发现 loguru 不生效的 exc_info（应用 logger.opt(exception=True)）：\n"
            + "\n".join(offenders)
        )


class TestAppLogBackend:
    """D-26：app/** 的日志后端必须统一为 loguru（get_logger）。

    为什么必须静态守住：stdlib `logging.Logger` 没有 `.opt()`，也不认 `{}` 占位 ——
    混用时不是「日志不好看」，而是**参数丢失 + 错误分支 AttributeError**：
      · `logger.warning("x {}", v)`  → stdlib 下打出字面 `x {}`，v 被丢弃；
      · `logger.opt(exception=True)` → stdlib Logger 无此方法 → AttributeError；
      · `logger.info(f"...")`        → 能跑（f-string 提前求值），但失去惰性格式化。
    实测这正是 `app/api/health.py`、`app/services/dashboard_service.py`、
    `app/services/pet_service.py` 的降级分支此前会二次抛错的原因（2026-10-30 审计）。
    """

    @staticmethod
    def _stdlib_getlogger_lines() -> list[tuple[str, int, str]]:
        hits: list[tuple[str, int, str]] = []
        for p in _app_python_files():
            rel = p.relative_to(ROOT).as_posix()
            if rel == STDLIB_LOGGING_SELF or rel in STDLIB_LOGGING_ALLOWED:
                continue
            for i, line in enumerate(p.read_text(encoding="utf-8").split("\n"), 1):
                s = line.strip()
                if s.startswith("#"):     # 注释里引用该 API 不算违规
                    continue
                if STDLIB_GETLOGGER.search(line):
                    hits.append((rel, i, s[:100]))
        return hits

    def test_no_stdlib_logging_getlogger_in_app(self):
        """app/**（除白名单）不得再出现 logging.getLogger —— 后端必须统一 loguru。"""
        offenders = self._stdlib_getlogger_lines()
        assert not offenders, (
            "app/** 仍混用 stdlib logging.getLogger（loguru 的 {} 占位与 opt() 会全部失效）：\n"
            + "\n".join(f"  {rel}:{line}: {src}" for rel, line, src in offenders)
            + "\n修法：`from app.core.logger import get_logger` + "
              "`logger = get_logger(\"<module>\")`；确需保留请加入 "
              "test_logging_contract.STDLIB_LOGGING_ALLOWED 并写明理由。"
        )

    def test_allowlist_entries_are_justified(self):
        """白名单必须：文件存在 + 理由非空 —— 不允许「静默豁免」。"""
        for rel, reason in STDLIB_LOGGING_ALLOWED.items():
            assert (ROOT / rel).is_file(), f"白名单文件不存在：{rel}"
            assert len(reason.strip()) >= 10, f"白名单缺少理由：{rel}"

    def test_caplog_can_capture_loguru_records(self, caplog):
        """D-26 桥接契约：loguru 记录经 stdlib 桥后，pytest `caplog` 能捕获。

        为什么值得单独钉住：D-18 排查时 `caplog` 捕不到 loguru 日志，测试只能
        改用 spy 打桩（见 tests/test_api_error_paths.py::TestLogsApi）。桥接失效
        不会让业务失败，只会让「调试工具静默失灵」—— 那类问题只能靠断言守住。
        """
        import logging

        from app.core.logger import get_logger

        log = get_logger("contract.caplog")
        with caplog.at_level(logging.WARNING):
            log.warning("caplog 桥接探针: {}", 42)
        assert "caplog 桥接探针: 42" in caplog.text, "caplog 未能捕获 loguru 记录（桥接失效）"

    def test_migrated_modules_expose_loguru_api(self):
        """功能断言：已迁移模块的 logger 必须是 loguru logger（有 .opt/.bind）。"""
        import importlib

        for module_name in ("app.core.event_bus", "app.services.growth_service", "app.api.health"):
            module = importlib.import_module(module_name)
            module_logger = getattr(module, "logger", None)
            assert module_logger is not None, f"{module_name} 缺少模块级 logger"
            assert hasattr(module_logger, "opt") and hasattr(module_logger, "bind"), (
                f"{module_name}.logger 不是 loguru logger（可能是 stdlib logging.Logger）"
            )
