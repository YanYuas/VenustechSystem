# ============================================================
# 架构守护（Architecture as Code）— pytest 入口
#
# 为什么只留这一层薄壳：
#   规则本体在 scripts/audit_architecture.py（AST 解析真实 import 图 +
#   领域地图校验）。旧版本文件只有 5 条"文本包含"断言，实测抓不到
#   core 反向依赖 services 这类真实违规（见 2026-10 架构审计）。
#   现在断言唯一事实来源 = 那个脚本，避免两套规则各自漂移。
#
# 单独运行（不装 pytest 也能跑）：
#     cd backend && python tests/test_architecture.py
#     python scripts/audit_architecture.py
# ============================================================
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GUARD = ROOT / "scripts" / "audit_architecture.py"


def test_architecture_guard_passes() -> None:
    """架构分层 / 领域归属 / 根目录契约 全部零违规。"""
    assert GUARD.is_file(), f"缺少架构守护脚本: {GUARD}"
    proc = subprocess.run(
        [sys.executable, str(GUARD)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        raise AssertionError(
            "架构守护失败（scripts/audit_architecture.py 退出码非 0）：\n"
            + (proc.stdout or "")
            + (proc.stderr or "")
        )


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        test_architecture_guard_passes()
        print("✅ 架构守护通过")
        sys.exit(0)
    except AssertionError as e:
        print(f"❌ {e}")
        sys.exit(1)
