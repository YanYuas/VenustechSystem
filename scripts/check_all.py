# ============================================================
# 一键验证入口（2026-09-15 新增，2026-10-11 扩到 12 项）
#
# 为什么需要它：
#   《一期模块考校报告》记录过 E-01：本机 venv 未安装 pytest，导致
#   tests/test_architecture.py 写好却从未执行，分层违规悄悄累积到 7 处
#   （见《调试与性能优化报告》B-2）。**写了却跑不了的测试等于没有测试。**
#   本脚本把各道验证串成一条命令。除「后端 pytest 套件」与「前端单元测试」
#   两项需要第三方依赖（未安装则优雅跳过）外，其余各项零第三方依赖。
#
# 用法（在仓库根目录或任意位置均可）：
#   python scripts/check_all.py
#   python scripts/check_all.py --skip-frontend    # 跳过前端四项，更快
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
VITEST = FRONTEND / "node_modules" / ".bin" / ("vitest.cmd" if sys.platform == "win32" else "vitest")


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
        if any(k in s for k in (
            "✅", "❌", "结果:", "error", "Error", "错误", "warning: SAWarning",
            "passed", "failed", "FAILED", "ERROR", "no module named",
        )):
            print("   " + s[:160])
    ok = proc.returncode == 0
    print(f"{'✅ 通过' if ok else '❌ 失败'}（退出码 {proc.returncode}）")
    return ok, "pass" if ok else "fail"


def _has_module(python: str, module: str) -> bool:
    """判断解释器是否可导入指定模块（用于优雅跳过可选步骤）。"""
    try:
        proc = subprocess.run(
            [python, "-c", f"import {module}"],
            capture_output=True, text=True, timeout=60,
        )
    except Exception:  # noqa: BLE001
        return False
    return proc.returncode == 0


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

    ok, st = _run("1/12 架构守护（分层依赖）",
                  [PYTHON, "tests/test_architecture.py"], BACKEND)
    results.append(("架构守护", ok, st))

    # 2/12 后端 pytest 套件（Service 单元 + API 集成 + 数据库基础设施守护）
    # 为什么必须有这一项：这批用例（2026-10-11 实测 1126 条）此前**从未进入本入口**，
    # 「写了却跑不了/没人跑」正是 E-01 的翻版。这里用 venv 解释器跑全量
    # pytest；若环境未装 pytest，则优雅跳过（不误报失败）。
    if _has_module(PYTHON, "pytest"):
        ok, st = _run("2/12 后端 pytest 套件（单元 + 集成）",
                      [PYTHON, "-m", "pytest", "tests/",
                       "-p", "no:cacheprovider", "-p", "no:warnings",
                       "--tb=line", "-rf"], BACKEND)
        results.append(("后端 pytest 套件", ok, st))
    else:
        print("\n⏭  跳过 2/12：当前解释器未安装 pytest（pip install pytest 后可启用）")
        results.append(("后端 pytest 套件", True, "skipped"))

    ok, st = _run("3/12 后端冒烟（端到端 + 迁移 + 回归断言）",
                  [PYTHON, "scripts/smoke_backend.py"], BACKEND)
    results.append(("后端冒烟", ok, st))

    ok, st = _run("4/12 版本一致性（F1.4）", [PYTHON, "scripts/check_versions.py"], ROOT)
    results.append(("版本一致性", ok, st))

    # 5/12 设计令牌存在性：用了不存在的 var(--x) 会让样式静默失效
    ok, st = _run("5/12 设计引用存在性（令牌 + 图标）", [PYTHON, "scripts/audit-tokens.py"], FRONTEND)
    results.append(("设计引用审计", ok, st))

    if args.skip_frontend:
        results.append(("前端类型检查", True, "skipped"))
        results.append(("离线队列测试", True, "skipped"))
        results.append(("连通性测试", True, "skipped"))
        results.append(("前端单元测试(vitest)", True, "skipped"))
    else:
        ok, st = _run("6/12 前端类型检查（vue-tsc）",
                      [str(VUE_TSC), "--noEmit"], FRONTEND)
        results.append(("前端类型检查", ok, st))

        # 7/12 离线队列核心测试（esbuild 转译 TS → node 跑；见 mod-tools F4.3）
        esbuild = FRONTEND / "node_modules/.bin/esbuild.cmd"
        if not esbuild.exists():
            esbuild = FRONTEND / "node_modules/.bin/esbuild"
        bundle = FRONTEND / ".tq.mjs"
        ok_build, st_build = _run(
            "7/12a 离线队列测试打包（esbuild）",
            [str(esbuild), "--bundle", "scripts/test-offline-queue.ts",
             "--outfile=.tq.mjs", "--format=esm", "--platform=node"],
            FRONTEND,
        )
        if ok_build:
            ok, st = _run("7/12 离线队列核心测试（node）", [NODE, ".tq.mjs"], FRONTEND)
        else:
            ok, st = False, st_build
        try:
            bundle.unlink()
        except OSError:
            pass
        results.append(("离线队列测试(15)", ok, st))

        # 8/12 HTTP 连通性行为测试（mod-tools：不可达识别 / 入队 / 重试 / 提示收敛）
        ok_build, st_build = _run(
            "8/12a 连通性测试打包（esbuild）",
            [str(esbuild), "--bundle", "scripts/test-http-connectivity.ts",
             "--outfile=.tc.mjs", "--format=esm", "--platform=node",
             "--banner:js=import.meta.env={VITE_API_BASE:'http://127.0.0.1:9/api/v1'};"],
            FRONTEND,
        )
        if ok_build:
            ok, st = _run("8/12 连通性行为测试（node）", [NODE, ".tc.mjs"], FRONTEND)
        else:
            ok, st = False, st_build
        try:
            (FRONTEND / ".tc.mjs").unlink()
        except OSError:
            pass
        results.append(("连通性测试(16)", ok, st))

        # 12/12 前端单元测试（vitest + jsdom）
        # 为什么新增：此前前端**零单元测试**，只有两个 esbuild 脚本覆盖
        # 离线队列与连通性 —— 报告导出、主题解析、路由参数消费这些纯逻辑
        # 全靠手点页面验证。本项把 src/**/__tests__/ 下的用例纳入一键入口，
        # 同样守「写了却跑不了 = 等于没有测试」。
        # 未装 vitest 时优雅跳过（不误报失败）。
        ok, st = _run("12/12 前端单元测试（vitest + jsdom）",
                      [str(VITEST), "run"], FRONTEND)
        results.append(("前端单元测试(vitest)", ok, st))

    # 9/12 交付物守护：一键脚本能不能真的把服务起起来 + 冒烟有没有水分断言
    # 为什么必须有这一项：其余项都不需要「真实启动服务」，出现过
    # 全绿但用户双击脚本后后端起不来的情况（裸 python / 错误 CWD）。
    # 这一项守的是「用户路径」，不是「代码路径」。
    ok, st = _run("9/12 交付物守护（一键脚本 + 冒烟水分）",
                  [PYTHON, "scripts/audit_delivery.py"], ROOT)
    results.append(("交付物守护", ok, st))

    # 10/12 测试质量审计：用例数不是质量指标。
    # 守着 5 类「缺陷存在时依然全绿」的写法：永真断言 / 无断言用例 /
    # 宽泛 pytest.raises(Exception) / 吞异常 / 空函数体。
    # 本项目历史教训：考察报告称"已删除"的 `or True` 永真断言实际还在代码里，
    # 没有任何东西会因此变红 —— 于是它活到了下一轮。
    ok, st = _run("10/12 测试质量审计（永真断言 / 无断言 / 宽泛异常）",
                  [PYTHON, "scripts/audit_test_quality.py"], ROOT)
    results.append(("测试质量审计", ok, st))

    # 11/12 日志格式审计：后端日志后端是 **loguru**（占位符 `{}`），但项目里有
    # 50 处写成 printf 风格 `%s` / 标准库 `exc_info=`。实测（2026-10-11 真机
    # 启动日志为证）参数与异常堆栈**静默丢失**，日志里留下裸 `%s`
    # （如「插件路由已挂载: %s」）。这类失真不会让任何测试变红 —— 正是
    # 「没有东西会因此变红」的典型，故落成基线 0 的守护。
    ok, st = _run("11/12 日志格式审计（loguru 占位符 / exc_info）",
                  [PYTHON, "scripts/audit_log_format.py"], ROOT)
    results.append(("日志格式审计", ok, st))

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
