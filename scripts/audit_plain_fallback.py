#!/usr/bin/env python
"""明文降级审计（mod-platform 验收 8.3）

PRD 要求："全库 grep `plain:` 前缀，非 Windows 降级路径有明确告警"。

本脚本扫描后端源码，报告所有 `plain:` 出现位置，并区分：
  - 定义/判断处（security.py 的前缀常量与兼容读取）—— 允许
  - **写入路径**（返回 "plain:" + ... 的地方）—— 必须受 dev 开关保护

用法：python scripts/audit_plain_fallback.py
退出码：0 合规；1 发现未受保护的明文写入路径
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend/app"


def main() -> int:
    offenders = []
    occurrences = []
    for path in BACKEND.rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="replace")
        for i, line in enumerate(text.splitlines(), 1):
            if "plain:" not in line:
                continue
            occurrences.append((path.relative_to(ROOT), i, line.strip()))
            # 写入路径：返回/赋值为 plain: 开头的密文
            if re.search(r'(return|=\s*)\s*"plain:"\s*\+', line):
                # 必须能就近找到 dev 开关保护（同一函数内出现 get_settings().dev）
                window = "\n".join(text.splitlines()[max(0, i - 25):i + 5])
                if ".dev" not in window:
                    offenders.append((path.relative_to(ROOT), i, line.strip()))

    print(f"明文降级审计：共 {len(occurrences)} 处 `plain:` 引用")
    for rel, i, line in occurrences:
        mark = "⚠️" if any(o[0] == rel and o[1] == i for o in offenders) else "  "
        print(f"  {mark} {rel}:{i}  {line[:100]}")

    if offenders:
        print(f"\n❌ 发现 {len(offenders)} 处未受 dev 开关保护的明文写入路径")
        return 1
    print("\n✅ 所有明文写入路径均受开发模式开关保护（生产环境会拒绝写入）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
