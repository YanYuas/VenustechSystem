#!/usr/bin/env python
"""版本一致性校验（mod-platform F1.4）

版本号散落在多处（后端 config / 前端 package.json / capacitor 配置），
改一处忘一处会导致"应用显示 v0.7 而 APK 是 v0.6"这类幽灵问题。本脚本
把它们对齐检查，纳入 check_all。

用法：python scripts/check_versions.py
退出码：0 一致；1 不一致（打印各处取值）
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def backend_version() -> str | None:
    p = ROOT / "backend/app/config.py"
    if not p.is_file():
        return None
    m = re.search(r'version:\s*str\s*=\s*"([^"]+)"', p.read_text(encoding="utf-8"))
    return m.group(1) if m else None


def frontend_version() -> str | None:
    p = ROOT / "frontend/package.json"
    if not p.is_file():
        return None
    return json.loads(p.read_text(encoding="utf-8")).get("version")


def capacitor_version() -> str | None:
    p = ROOT / "frontend/capacitor.config.ts"
    if not p.is_file():
        return None
    m = re.search(r'version:\s*[\'"]([^\'"]+)[\'"]', p.read_text(encoding="utf-8"))
    return m.group(1) if m else None


def main() -> int:
    found = {
        "backend/app/config.py": backend_version(),
        "frontend/package.json": frontend_version(),
        "frontend/capacitor.config.ts": capacitor_version(),
    }
    print("版本一致性检查（mod-platform F1.4）")
    for k, v in found.items():
        print(f"  {k:<32} {v or '(未声明)'}")
    values = {v for v in found.values() if v}
    if len(values) <= 1:
        print("✅ 版本号一致" if values else "⚠️ 未找到任何版本声明")
        return 0
    print("❌ 版本号不一致：请统一为一处（建议以后端 config 为准）")
    return 1


if __name__ == "__main__":
    sys.exit(main())
