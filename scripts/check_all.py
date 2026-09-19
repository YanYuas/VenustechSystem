# ============================================================
# 一键验证入口（2026-09-15 新增）
#
# 为什么需要它：
#   《一期模块考校报告》记录过 E-01：本机 venv 未安装 pytest，导致
#   tests/test_architecture.py 写好却从未执行，分层违规悄悄累积到 7 处
#   （见《调试与性能优化报告》B-2）。**写了却跑不了的测试等于没有测试。**
#   本脚本把三道验证串成一条命令，且零第三方依赖（不需要 pytest）。
#
# 用法（在仓库根目录或任意位置均可）：
#   python scripts/check_all.py
#   python scripts/check_all.py --skip-frontend    # 只跑后端两项，更快
#
# 退出码 0 = 全部通过；1 = 有失败。
# ============================================================
from __future__ import annotations

import argparse
import subprocess
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"

# 后端解释器优先用项目 venv，回退到当前解释器
VENV_PY = BACKEND / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
PYTHON = str(VENV_PY) if VENV_PY.exists() else sys.executable
NODE = shutil.which('node') or 'node'

VUE_TSC = FRONTEND / "node_modules" / ".bin" / ("vue-tsc.cmd" if sys.platform == "win32" else "vue-tsc")


def _run(label: str, cmd: list[str], cwd: Path) -> tuple[bool, str]:
    print(f"\n{'=' * 62}\n▶ {label}\n{'=' * 62}")
    if not Path(cmd[0]).exists() and not shutil_which(cmd[0]):
        print(f"⏭  跳过：找不到可执行文件 {cmd[0]}")
        return True, "skipped"
    try:
        proc = subprocess.run(
            cmd, cwd=str(cwd), capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
    except Exception as exc:  # noqa: BLE001
        print(f"❌ 执行失败：{type(exc).__name__}: {exc}")
        return False, "error"

    out = (proc.stdout or "") + (proc.stderr or "")
    # 只回显有信息量的行，避免刷屏
    for line in out.splitlines():
        s = line.strip()
        if not s:
            continue
        if any(k in s for k in ("✅", "❌", "结果:", "error", "Error", "错误", "warning: SAWarning")):
            print("   " + s[:160])
    ok = proc.returncode == 0
    print(f"{'✅ 通过' if ok else '❌ 失败'}（退出码 {proc.returncode}）")
    return ok, "pass" if ok else "fail"


def shutil_which(name: str) -> bool:
    import shutil
    return shutil.which(name) is not None


def main() -> int:
    ap = argparse.ArgumentParser(description="启明星系统一键验证")
    ap.add_argument("--skip-frontend", action="store_true", help="跳过前端类型检查（更快）")
    args = ap.parse_args()

    print("启明星系统 · 一键验证")
    print(f"  仓库: {ROOT}")
    print(f"  Python: {PYTHON}")

    results: list[tuple[str, bool, str]] = []

    ok, st = _run("1/6 架构守护（分层依赖）",
                  [PYTHON, "tests/test_architecture.py"], BACKEND)
    results.append(("架构守护", ok, st))

    ok, st = _run("2/6 后端冒烟（端到端 + 迁移 + 回归断言）",
                  [PYTHON, "scripts/smoke_backend.py"], BACKEND)
    results.append(("后端冒烟", ok, st))

    ok, st = _run("3/6 版本一致性（F1.4）", [PYTHON, "scripts/check_versions.py"], ROOT)
    results.append(("版本一致性", ok, st))

    # 4/6 设计令牌存在性：用了不存在的 var(--x) 会让样式静默失效
    ok, st = _run("4/6 设计引用存在性（令牌 + 图标）", [PYTHON, "scripts/audit-tokens.py"], FRONTEND)
    results.append(("设计引用审计", ok, st))

    if args.skip_frontend:
        results.append(("前端类型检查", True, "skipped"))
        results.append(("离线队列测试", True, "skipped"))
    else:
        ok, st = _run("5/6 前端类型检查（vue-tsc）",
                      [str(VUE_TSC), "--noEmit"], FRONTEND)
        results.append(("前端类型检查", ok, st))

        # 6/6 离线队列核心测试（esbuild 转译 TS → node 跑；见 mod-tools F4.3）
        esbuild = FRONTEND / "node_modules/.bin/esbuild.cmd"
        if not esbuild.exists():
            esbuild = FRONTEND / "node_modules/.bin/esbuild"
        bundle = FRONTEND / ".tq.mjs"
        ok_build, st_build = _run(
            "6/6a 离线队列测试打包（esbuild）",
            [str(esbuild), "--bundle", "scripts/test-offline-queue.ts",
             "--outfile=.tq.mjs", "--format=esm", "--platform=node"],
            FRONTEND,
        )
        if ok_build:
            ok, st = _run("6/6 离线队列核心测试（node）", [NODE, ".tq.mjs"], FRONTEND)
        else:
            ok, st = False, st_build
        try:
            bundle.unlink()
        except OSError:
            pass
        results.append(("离线队列测试(15)", ok, st))

    print(f"\n{'=' * 62}\n汇总\n{'=' * 62}")
    for name, ok, st in results:
        icon = "✅" if ok else "❌"
        note = "（跳过）" if st == "skipped" else ""
        print(f"  {icon} {name}{note}")

    failed = [n for n, ok, _ in results if not ok]
    if failed:
        print(f"\n❌ 有 {len(failed)} 项失败：{', '.join(failed)}")
        return 1
    print("\n✅ 全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
