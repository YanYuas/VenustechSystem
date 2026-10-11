# ============================================================
# 日志契约守护（2026-10-11 新增 · 真机端到端探针发现）
#
# 发现的缺陷：全项目 50 处日志用了 `%s` / `exc_info=True`，但后端日志后端
# 是 **loguru**（占位符是 `{}`，`exc_info` 也不是它认的 kwarg）。实测后果 ——
# 参数与堆栈静默丢失，日志文本里留下裸 `%s`。真机 uvicorn 启动日志留下了
# 直接证据：「插件路由已挂载: %s」（应为实际插件名）。
#
# 本文件做两件事：
#   1. 把 loguru 的实测行为**钉成契约**（将来若换回标准库 logging，这里会红，
#      提醒同步改回 %-style）；
#   2. 静态扫描 backend/app，确保 %-占位符 / exc_info 不再回归。
# ============================================================
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # backend/
APP_DIR = ROOT / "app"

LOGGER_CALL = re.compile(r"\b(?:self\.)?logger\.(?:debug|info|warning|error|critical|exception)\(")
PCT_STYLE = re.compile(r"%s|%d|%\.\d+f")


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
