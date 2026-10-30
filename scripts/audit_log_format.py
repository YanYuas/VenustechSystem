# ============================================================
# 日志格式审计（2026-10-11 新增，纳入 check_all.py 第 11 项）
#
# 为什么必须有这个脚本：
#   本项目日志后端是 **loguru**（见 app/core/logger.py），loguru 用 `{}` 占位，
#   既不认 printf 风格的 `%s` / `%d` / `%.0f`，也不认标准库 logging 的
#   `exc_info=` kwarg。实测（2026-10-11，真机 uvicorn 启动日志为证）：
#       logger.info("A %s", 1)             -> 输出 "A %s"      参数被丢弃
#       logger.info("B {}", 1)             -> 输出 "B 1"
#       logger.warning("x", exc_info=True) -> 无堆栈（exc_info 未生效）
#   后果：**日志文本里留下裸 `%s`，参数与异常堆栈全部丢失** —— 排查线上
#   问题时看到的是「用户 %s 升级: LV%d → LV%d」，毫无信息量。
#   实测证据：真机启动日志确实打印出「插件路由已挂载: %s」。
#   这类失真不会让任何测试变红 —— 正是「没有东西会因此变红」的典型，
#   故落成基线 0 的守护。
#
# 扫描 2 类写法（基线 0，命中即失败）：
#   1. PCT_STYLE  logger.<level>("... %s|%d|%.Nf ...", ...) → 应改为 {}
#   2. EXC_INFO   logger.<level>(..., exc_info=...)         → 应改为
#                 logger.opt(exception=True).<level>(...)
#
# 用法：python scripts/audit_log_format.py
# ============================================================
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "backend" / "app"

# 只关心日志/异常类方法调用所在的行
LOGGER_CALL = re.compile(r"\b(?:self\.)?logger\.(?:debug|info|warning|error|critical|exception|trace)\(")
PCT_STYLE = re.compile(r"%s|%d|%\.\d+f")
EXC_INFO = re.compile(r"exc_info\s*=")


def _call_span(text: str, start: int, max_len: int = 4000) -> str:
    """从日志调用起点截到匹配的右括号（跳过字符串内的括号）。

    D-45（2026-10-30）：旧实现逐行匹配，多行调用
        logger.warning(
            "备份版本 %s ...", 版本,
        )
    的第二行不在 LOGGER_CALL 命中行上，%-占位符会漏检（实测真漏了）。
    """
    i, depth, quote = start, 0, ""
    while i < len(text) and i - start < max_len:
        ch = text[i]
        if quote:
            if ch == "\\":
                i += 2
                continue
            if ch == quote:
                quote = ""
        elif ch in "'\"":
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
        i += 1
    return text[start : start + 400]


def scan_source(text: str) -> list[tuple[int, str]]:
    """返回 (行号, 违规类型) 列表；供主扫描与单测复用。"""
    findings: list[tuple[int, str]] = []
    for m in LOGGER_CALL.finditer(text):
        lineno = text.count("\n", 0, m.start()) + 1
        line_start = text.rfind("\n", 0, m.start()) + 1
        line_end = text.find("\n", m.start())
        line = text[line_start : line_end if line_end != -1 else len(text)]
        if line.strip().startswith("#"):
            continue
        span = _call_span(text, m.start())
        if PCT_STYLE.search(span):
            findings.append((lineno, "PCT_STYLE"))
        if EXC_INFO.search(span):
            findings.append((lineno, "EXC_INFO"))
    return findings


def scan() -> tuple[list[str], int]:
    violations: list[str] = []
    n_files = 0
    for path in sorted(APP_DIR.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        n_files += 1
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(ROOT)
        for lineno, kind in scan_source(text):
            snippet = text.split("\n")[lineno - 1].strip()[:120]
            violations.append(f"[{kind}] {rel}:{lineno}: {snippet}")
    return violations, n_files


def main() -> int:
    print("=" * 62)
    print("▶ 日志格式审计（loguru 占位符 / exc_info 误用）")
    print("=" * 62)
    print(f"  扫描目录: {APP_DIR}")

    violations, n_files = scan()
    print(f"  扫描文件: {n_files} 个")

    if violations:
        print(f"\n❌ 发现 {len(violations)} 处 loguru 不生效的日志写法：")
        for v in violations:
            print(f"   {v}")
        print("\n  修法：`%s`/`%d`/`%.Nf` → `{}`/`{:.Nf}`；"
              "`exc_info=True` → `logger.opt(exception=True)` 前缀")
        print("  （这些写法会让日志参数与堆栈静默丢失，且不会有任何测试变红）")
        return 1

    print("\n✅ 未发现 %-占位符 / exc_info 误用（日志参数与堆栈可正常记录）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
