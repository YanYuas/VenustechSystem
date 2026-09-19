# ============================================================
# 交付物守护（2026-09-19 新增）
#
# 为什么需要它：
#   check_all 的前 7 项全都不需要「真实启动一个服务」，于是出现过
#   **7 项全绿、但用户双击脚本后后端根本起不来**的情况：
#     - 启动开发.bat 用 PATH 上的裸 python（无 fastapi）→ 后端秒退
#     - start-demo.bat 在仓库根执行 uvicorn app.main:app
#       → ModuleNotFoundError: No module named 'app'（uvicorn 以 CWD 为 import 根）
#   两条都写在长期记忆里，但**记忆拦不住复发**（同类错误换了脚本又犯一次）。
#   本脚本把这几条铁律变成退出码非 0 的检查。
#
# 检查项：
#   A. 一键脚本（*.bat）后端启动规范
#      A1 起了 uvicorn 就必须把 CWD 设到 backend（/D 或 cd / pushd）
#      A2 解释器必须是项目 venv，禁止裸 python
#   B. *.bat 必须 ASCII-only（cmd.exe 按系统代码页解析，中文会乱码）
#   C. *.bat 不得出现无人值守的 `git add -A`（历史上一键脚本擅自提交过）
#   D. 冒烟断言水分扫描（check(..., X or True, ...) 这类永真断言）
#
# 用法：python scripts/audit_delivery.py
# 退出码 0 = 通过；1 = 有问题。
# ============================================================
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BAT_FILES = sorted(ROOT.glob("*.bat"))
SMOKE = ROOT / "backend" / "scripts" / "smoke_backend.py"

problems: list[str] = []
warns: list[str] = []


def _check_bat(path: Path) -> None:
    raw = path.read_bytes()
    text = raw.decode("utf-8", errors="replace")
    name = path.name

    lines = text.splitlines()
    # rem / :: 是注释，不参与执行；但中文注释仍值得提醒（换机器易乱码）
    def is_comment(s: str) -> bool:
        return s.lstrip().lower().startswith(("rem", "::"))

    # --- B. ASCII-only（执行行阻断，注释行仅警告）---
    bad_exec: list[int] = []
    bad_comment: list[int] = []
    for i, line in enumerate(lines, 1):
        if any(ord(ch) > 127 for ch in line):
            (bad_comment if is_comment(line) else bad_exec).append(i)
    if bad_exec:
        problems.append(
            f"[B] {name}: 执行行含非 ASCII 字符（行 {bad_exec[:5]}）—— "
            f"cmd.exe 按系统代码页解析，中文会乱码甚至改变语义"
        )
    if bad_comment:
        warns.append(f"[B] {name}: 注释行含非 ASCII 字符（行 {bad_comment[:5]}）—— 建议改为 ASCII")

    # --- C. 无人值守的全量 add（只看执行行）---
    for i, line in enumerate(lines, 1):
        if is_comment(line):
            continue
        if re.search(r"git\s+add\s+(-A|--all|\.)", line, re.I):
            problems.append(
                f"[C] {name}:{i}: 一键脚本不得执行 git add -A（会擅自提交用户未确认的改动）"
            )

    # --- A. 后端启动规范 ---
    uv_lines = [(i, ln) for i, ln in enumerate(text.splitlines(), 1) if "uvicorn" in ln]
    # 只看真正「启动」的行（排除 echo / -c "import uvicorn" 之类的校验行）
    launch_lines = [
        (i, ln) for i, ln in uv_lines
        if "-m uvicorn" in ln or re.search(r"uvicorn\s+app\.main", ln)
    ]
    if not launch_lines:
        return

    for i, ln in launch_lines:
        # A1: CWD 必须是 backend
        has_d = bool(re.search(r"/D\s+\"?[^\"]*backend", ln, re.I))
        cwd_before = any(
            re.search(r"(cd\s+/d|pushd)\s+\"?[^\"]*backend", prev, re.I)
            for prev in text.splitlines()[: i - 1]
        )
        if not (has_d or cwd_before):
            problems.append(
                f"[A1] {name}:{i}: 启动 uvicorn 未把 CWD 设到 backend。"
                f"app 包只在 backend\\ 下，从仓库根启动必然 ModuleNotFoundError: No module named 'app'。"
                f'请改用 start "..." /D "%~dp0backend" 或先 cd /d "%~dp0backend"。'
            )

        # A2: 解释器必须是 venv，禁止裸 python
        if re.search(r"(?<![\w\\/])python(\.exe)?\s+-m\s+uvicorn", ln, re.I):
            problems.append(
                f"[A2] {name}:{i}: 用 PATH 上的裸 python 启动后端，依赖在 backend\\.venv，"
                f"会 ModuleNotFoundError: No module named 'fastapi'。请改用 .venv\\Scripts\\python.exe。"
            )
        elif "%PY" in ln or "%PYRUN%" in ln or "%PYFULL%" in ln:
            # 用了变量：确认变量被赋成 venv 解释器（而不是回退成裸 python 之后再启动）
            if ".venv" not in text and "venv" not in text.lower():
                problems.append(f"[A2] {name}:{i}: 启动用的解释器变量未指向 .venv")
        elif ".venv" not in ln.lower():
            problems.append(f"[A2] {name}:{i}: 无法确认解释器来自 .venv —— 请显式使用 .venv\\Scripts\\python.exe")


def _check_smoke() -> None:
    if not SMOKE.exists():
        warns.append(f"[D] 未找到冒烟脚本：{SMOKE}")
        return
    for i, line in enumerate(SMOKE.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        s = line.strip()
        if s.startswith("#"):
            continue
        # check("desc", <expr> or True, "") —— 永真断言，永远通过但什么也没验证
        if re.search(r"\bor\s+True\b", s) or re.search(r"\bassert\s+(True|1)\s*$", s):
            if "check(" in s or "assert" in s:
                problems.append(f"[D] smoke_backend.py:{i}: 永真断言（充数，恒通过）：{s[:100]}")


def main() -> int:
    print("交付物守护（一键脚本 / 冒烟水分）")
    print(f"  仓库: {ROOT}")
    print(f"  .bat: {len(BAT_FILES)} 个")

    if not BAT_FILES:
        warns.append("仓库根目录没有 .bat 文件")

    for bat in BAT_FILES:
        _check_bat(bat)
    _check_smoke()

    print()
    for w in warns:
        print(f"  ⚠️  {w}")

    if problems:
        print(f"\n❌ 发现 {len(problems)} 个问题：\n")
        for p in problems:
            print(f"  {p}")
        return 1

    print("  ✅ 一键脚本与冒烟断言均符合铁律")
    return 0


if __name__ == "__main__":
    sys.exit(main())
