# ============================================================
# 交付物守护（2026-09-19 新增；2026-10-27 D-11 起改为守护"单一启动实现"）
#
# 为什么需要它：
#   check_all 的前几项都不需要「真实启动一个服务」，于是出现过
#   **全绿、但用户双击脚本后后端根本起不来**的情况：
#     - 启动开发.bat 用 PATH 上的裸 python（无 fastapi）→ 后端秒退
#     - start-demo.bat 在仓库根执行 uvicorn app.main:app
#       → ModuleNotFoundError: No module named 'app'（uvicorn 以 CWD 为 import 根）
#   两条都写在长期记忆里，但**记忆拦不住复发**（同类错误换了脚本又犯一次）。
#   本脚本把这几条铁律变成退出码非 0 的检查。
#
# D-11（启动器单一实现）之后的模型：
#   - 唯一实现：ops/start.ps1（-Mode dev|demo|mobile [-DataDir] [-WhatIf]）
#   - 唯一安装实现：ops/setup.ps1
#   - 根目录 .bat 与 scripts/dev.ps1 只是 3-5 行转发壳，不得再写实现
#   因此本脚本的检查目标也随之迁移：
#
# 检查项：
#   A. 唯一启动实现 ops/start.ps1 的后端启动规范
#      A1 起了 uvicorn 就必须把 CWD 设到 backend（-WorkingDirectory $Backend）
#      A2 解释器必须来自项目 venv（$VenvPython -> Resolve-Python），禁止裸 python
#   B. 编码：根 *.bat 必须 ASCII-only（cmd.exe 按系统代码页解析，中文会乱码）
#      ops/*.ps1 必须带 UTF-8 BOM（Windows PowerShell 5.1 否则按 ANSI 读，中文乱码）
#   C. 任何启动/安装脚本不得出现无人值守的 `git add -A`
#      （历史上一键脚本擅自提交过）
#   D. 冒烟断言水分扫描（check(..., X or True, ...) 这类永真断言）
#   E. 根 *.bat 必须是薄转发壳：只调用 powershell + ops\*.ps1，
#      不得出现 uvicorn / npm / node / netstat / .venv 等实现细节
#   F. ops/start.ps1 必须声明 -Mode dev|demo|mobile，且 mobile 必须启动
#      ops\server\server.js（边缘服务路径不能悄悄漂移）
#
# 用法：python scripts/audit_delivery.py
# 退出码 0 = 通过；1 = 有问题。
# 注意：本脚本只读文本，**从不执行**任何启动器。
# ============================================================
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
START_PS1 = ROOT / "ops" / "start.ps1"
SETUP_PS1 = ROOT / "ops" / "setup.ps1"
DEV_PS1 = ROOT / "scripts" / "dev.ps1"
SMOKE = ROOT / "backend" / "scripts" / "smoke_backend.py"

# 根目录必须存在的用户启动器（薄转发壳）与它必须转发的唯一实现
SHELLS = {
    "setup.bat": "ops\\setup.ps1",
    "start-dev.bat": "ops\\start.ps1",
    "start-demo.bat": "ops\\start.ps1",
    "start-mobile.bat": "ops\\start.ps1",
}

# 转发壳里不允许出现的实现细节（出现即说明"薄壳"被写厚了）
SHELL_IMPL_MARKERS = (
    "uvicorn",
    "npm",
    "node ",
    "netstat",
    "seed_demo",
    ".venv",
    "pip install",
    "python -m venv",
    "git push",
)

UVICORN_LAUNCH = re.compile(r"-m['\"]?\s*,\s*['\"]?uvicorn|uvicorn\s+app\.main", re.I)
BARE_PYTHON_UVICORN = re.compile(r"(?<![\w$.\\/-])python(?:\.exe)?\s+-m\s+uvicorn", re.I)
GIT_ADD_ALL = re.compile(r"git\s+add\s+(-A|--all|\.)", re.I)

problems: list[str] = []
warns: list[str] = []


# ------------------------------------------------------------------
# 通用读取
# ------------------------------------------------------------------
def _read(path: Path) -> str:
    return path.read_bytes().decode("utf-8", errors="replace")


def _has_utf8_bom(path: Path) -> bool:
    return path.read_bytes()[:3] == b"\xef\xbb\xbf"


def _is_comment(line: str) -> bool:
    return line.lstrip().lower().startswith(("rem", "::"))


def _code_lines(lines: list[str]):
    """跳过 PowerShell 行注释 `#` 与块注释 `<# ... #>`，避免把说明文字当代码。"""
    in_block = False
    for i, line in enumerate(lines, 1):
        s = line.strip()
        if in_block:
            if "#>" in s:
                in_block = False
            continue
        if s.startswith("<#"):
            if "#>" not in s:
                in_block = True
            continue
        if s.startswith("#"):
            continue
        yield i, line


# ------------------------------------------------------------------
# B + C + E：根目录 *.bat 薄转发壳
# ------------------------------------------------------------------
def _check_shell(path: Path, target: str) -> None:
    name = path.name
    text = _read(path)
    lines = text.splitlines()

    # --- B. ASCII-only（执行行阻断，注释行仅警告）---
    bad_exec: list[int] = []
    bad_comment: list[int] = []
    for i, line in enumerate(lines, 1):
        if any(ord(ch) > 127 for ch in line):
            (bad_comment if _is_comment(line) else bad_exec).append(i)
    if bad_exec:
        problems.append(
            f"[B] {name}: 执行行含非 ASCII 字符（行 {bad_exec[:5]}）—— "
            f"cmd.exe 按系统代码页解析，中文会乱码甚至改变语义"
        )
    if bad_comment:
        warns.append(f"[B] {name}: 注释行含非 ASCII 字符（行 {bad_comment[:5]}）—— 建议改为 ASCII")

    # --- C. 无人值守的全量 add（只看执行行）---
    for i, line in enumerate(lines, 1):
        if _is_comment(line):
            continue
        if GIT_ADD_ALL.search(line):
            problems.append(
                f"[C] {name}:{i}: 一键脚本不得执行 git add -A（会擅自提交用户未确认的改动）"
            )

    # --- E. 必须转发给唯一实现 ---
    if "powershell" not in text.lower():
        problems.append(
            f"[E] {name}: 转发壳必须用 powershell 调用唯一实现（找不到 powershell 调用）"
        )
    if target.lower() not in text.lower():
        problems.append(
            f"[E] {name}: 必须转发给 {target}（D-11 单一实现）；"
            f"启动逻辑不允许再写回 .bat"
        )

    # --- E. 不得含实现细节 ---
    for i, line in enumerate(lines, 1):
        if _is_comment(line):
            continue
        low = line.lower()
        for marker in SHELL_IMPL_MARKERS:
            if marker in low:
                problems.append(
                    f"[E] {name}:{i}: 转发壳里不允许出现实现细节 `{marker.strip()}`"
                    f"（应移入 {target}）"
                )
                break


# ------------------------------------------------------------------
# A + B + C + F：唯一启动实现 ops/start.ps1
# ------------------------------------------------------------------
def _check_start_ps1() -> None:
    if not START_PS1.exists():
        problems.append(
            f"[E] 缺少唯一启动实现：{START_PS1.relative_to(ROOT)} —— "
            f"D-11 要求全部启动逻辑集中在此文件"
        )
        return

    name = "ops/start.ps1"
    text = _read(START_PS1)
    lines = text.splitlines()

    # --- B. UTF-8 BOM（PowerShell 5.1 兼容）---
    if not _has_utf8_bom(START_PS1):
        problems.append(
            f"[B] {name}: 缺少 UTF-8 BOM —— Windows PowerShell 5.1 会把无 BOM 的 UTF-8 "
            f"按 ANSI 读取，中文提示与注释会乱码"
        )

    # --- C. 不得 git add -A ---
    for i, line in _code_lines(lines):
        if GIT_ADD_ALL.search(line):
            problems.append(f"[C] {name}:{i}: 启动器不得执行 git add -A")

    # --- A2 全局：解释器必须来自项目 venv ---
    if not re.search(r"\$[\w:]*VenvPython\s*=.*\.venv", text):
        problems.append(
            f"[A2] {name}: 未声明 `$VenvPython = ...\\.venv\\Scripts\\python.exe` —— "
            f"无法证明后端用项目 venv 的解释器启动"
        )

    # --- A1/A2：逐条 uvicorn 启动 ---
    launch_idx = [i for i, ln in enumerate(lines) if UVICORN_LAUNCH.search(ln)]
    if not launch_idx:
        problems.append(
            f"[A1] {name}: 找不到任何 uvicorn 启动（启动器缺少后端启动路径？）"
        )
    for i in launch_idx:
        line = lines[i]

        # A2：裸 python 启动后端（历史 bug 的直接形态）
        if BARE_PYTHON_UVICORN.search(line):
            problems.append(
                f"[A2] {name}:{i + 1}: 用 PATH 上的裸 python 启动后端，依赖在 backend\\.venv，"
                f"会 ModuleNotFoundError: No module named 'fastapi'。"
                f"请改用 Resolve-Python 得到的 $py.Path"
            )
            continue

        # 找到 8 行内真正发起进程的调用
        call_lineno: int | None = None
        call_line = ""
        for j in range(i + 1, min(i + 9, len(lines))):
            if re.search(r"Start-ServiceProcess|Start-Process", lines[j]):
                call_lineno, call_line = j + 1, lines[j]
                break
        if call_lineno is None:
            problems.append(
                f"[A1] {name}:{i + 1}: uvicorn 启动行后 8 行内没有统一启动调用，"
                f"无法确认 CWD=backend"
            )
            continue

        # A1：CWD 必须是 backend
        if "$Backend" not in call_line and "backend" not in call_line.lower():
            problems.append(
                f"[A1] {name}:{call_lineno}: 启动 uvicorn 未把 CWD 设为 backend。"
                f"app 包只在 backend\\ 下，从仓库根启动必然 "
                f"ModuleNotFoundError: No module named 'app'。"
                f"请传 -WorkingDirectory $Backend"
            )

        # A2：解释器来自 Resolve-Python / venv
        if ("$py.Path" not in call_line
                and "$VenvPython" not in call_line
                and "$pythonExe" not in call_line):
            problems.append(
                f"[A2] {name}:{call_lineno}: 无法确认解释器来自项目 venv "
                f"（应传 $py.Path / $VenvPython）"
            )

    # --- F. 模式契约 ---
    if not re.search(r"ValidateSet\(\s*'dev'\s*,\s*'demo'\s*,\s*'mobile'\s*\)", text):
        problems.append(
            f"[F] {name}: 必须声明 [ValidateSet('dev','demo','mobile')]$Mode —— "
            f"模式参数是启动器的对外契约"
        )
    if not re.search(r"ops\\server\\server\.js", text, re.I):
        problems.append(
            f"[F] {name}: mobile 模式必须启动 ops\\server\\server.js（边缘服务路径不得漂移）"
        )
    if not re.search(r"\[switch\]\$WhatIf", text):
        problems.append(
            f"[F] {name}: 必须提供 -WhatIf（只打印计划、不启动进程），否则无法被 CI 验证"
        )


# ------------------------------------------------------------------
# B + E：其它 PowerShell 脚本
# ------------------------------------------------------------------
def _check_aux_ps1(path: Path, must_forward_to: str | None = None) -> None:
    if not path.exists():
        return
    name = str(path.relative_to(ROOT)).replace("\\", "/")
    if not _has_utf8_bom(path):
        problems.append(f"[B] {name}: 缺少 UTF-8 BOM（PowerShell 5.1 中文会乱码）")
    text = _read(path)
    for i, line in _code_lines(text.splitlines()):
        if GIT_ADD_ALL.search(line):
            problems.append(f"[C] {name}:{i}: 不得执行 git add -A")
    if must_forward_to is not None:
        if must_forward_to.lower() not in text.lower():
            problems.append(
                f"[E] {name}: 兼容壳必须转发给 {must_forward_to}（D-11 单一实现）"
            )
        # 兼容壳同样不许藏实现（只查真正的启动动作，避免误伤说明文字）
        for i, line in enumerate(text.splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            if UVICORN_LAUNCH.search(line) or re.search(r"-WorkingDirectory", line):
                problems.append(
                    f"[E] {name}:{i}: 兼容壳里不允许出现启动实现（应转发给 {must_forward_to}）"
                )


# ------------------------------------------------------------------
# D：冒烟断言水分
# ------------------------------------------------------------------
def _check_smoke() -> None:
    if not SMOKE.exists():
        warns.append(f"[D] 未找到冒烟脚本：{SMOKE}")
        return
    for i, line in enumerate(_read(SMOKE).splitlines(), 1):
        s = line.strip()
        if s.startswith("#"):
            continue
        # check("desc", <expr> or True, "") —— 永真断言，永远通过但什么也没验证
        if re.search(r"\bor\s+True\b", s) or re.search(r"\bassert\s+(True|1)\s*$", s):
            if "check(" in s or "assert" in s:
                problems.append(f"[D] smoke_backend.py:{i}: 永真断言（充数，恒通过）：{s[:100]}")


# ------------------------------------------------------------------
def main() -> int:
    print("交付物守护（D-11 启动器单一实现 / 薄转发壳 / 冒烟水分）")
    print(f"  仓库: {ROOT}")
    print(f"  唯一实现: ops/start.ps1 + ops/setup.ps1；根 *.bat 只转发")

    # 根目录启动器缺失（比"没有 bat"更严格：四个入口都必须存在）
    for shell_name, target in SHELLS.items():
        shell = ROOT / shell_name
        if not shell.exists():
            problems.append(f"[E] 缺少根目录启动器：{shell_name}（应转发给 {target}）")

    extra = sorted(p.name for p in ROOT.glob("*.bat") if p.name not in SHELLS)
    for name in extra:
        warns.append(f"[E] 根目录出现计划外的 .bat：{name}（确认它是否也应改为转发壳）")

    for shell_name, target in SHELLS.items():
        shell = ROOT / shell_name
        if shell.exists():
            _check_shell(shell, target)

    _check_start_ps1()

    if SETUP_PS1.exists():
        _check_aux_ps1(SETUP_PS1)
    else:
        warns.append("[E] 未找到 ops/setup.ps1（setup.bat 的转发目标）")

    _check_aux_ps1(DEV_PS1, must_forward_to="ops\\start.ps1")
    if not DEV_PS1.exists():
        warns.append("[E] 未找到 scripts/dev.ps1（旧入口兼容壳；文档仍引用它）")

    _check_smoke()

    print()
    for w in warns:
        print(f"  ⚠️  {w}")

    if problems:
        print(f"\n❌ 发现 {len(problems)} 个问题：\n")
        for p in problems:
            print(f"  {p}")
        return 1

    print("  ✅ 单一启动实现 + 薄转发壳 + 冒烟断言均符合铁律")
    return 0


if __name__ == "__main__":
    sys.exit(main())
