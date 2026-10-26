#!/usr/bin/env python
"""版本一致性校验 + 同步（单一事实来源：仓库根 VERSION）

为什么需要：版本号曾散落在 6 处（后端 config、前后端 package.json、
pyproject、Android versionName），实际出现 0.1.0 / 0.7.0 / 1.0 三个
互不相同的值 —— "应用显示 v0.7 而 APK 是 v0.6" 这类问题无法靠人眼守住。

规则：
  - 唯一事实来源 = 仓库根 `VERSION`（语义化版本，如 0.7.0）
  - 以下位置必须与它一致：
      backend/app/config.py             -> Settings.version
      backend/pyproject.toml            -> [project].version
      frontend/package.json             -> version
      package.json（仓库根，统一服务）   -> version
      frontend/android/app/build.gradle -> versionName
        （Android versionCode 是整数发布序号，独立维护，不参与校验）
  - Capacitor 配置不声明版本（跟随 App），无需检查。

用法：
  python scripts/check_versions.py          # 校验，退出码 0/1
  python scripts/check_versions.py --sync   # 把全部位置改写成 VERSION 的值
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = ROOT / "VERSION"

CONFIG = ROOT / "backend/app/config.py"
PYPROJECT = ROOT / "backend/pyproject.toml"
FE_PKG = ROOT / "frontend/package.json"
# 统一服务（静态托管 + /api 代理）已迁到 ops/server/，版本号仍需与 App 一致
ROOT_PKG = ROOT / "ops/server/package.json"
GRADLE = ROOT / "frontend/android/app/build.gradle"


def read_truth() -> str:
    if not VERSION_FILE.is_file():
        raise SystemExit("❌ 缺少版本事实来源文件：VERSION（仓库根）")
    v = VERSION_FILE.read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", v):
        raise SystemExit(f"❌ VERSION 不是语义化版本：{v!r}（应形如 0.7.0）")
    return v


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.is_file() else ""


def get_config() -> str | None:
    m = re.search(r'version:\s*str\s*=\s*"([^"]+)"', _read(CONFIG))
    return m.group(1) if m else None


def get_pyproject() -> str | None:
    m = re.search(r'^version\s*=\s*"([^"]+)"', _read(PYPROJECT), flags=re.MULTILINE)
    return m.group(1) if m else None


def _json_version(p: Path) -> str | None:
    try:
        return json.loads(_read(p)).get("version") if p.is_file() else None
    except json.JSONDecodeError:
        return None


def get_gradle() -> str | None:
    m = re.search(r'versionName\s+"([^"]+)"', _read(GRADLE))
    return m.group(1) if m else None


def get_android_code() -> str | None:
    m = re.search(r'versionCode\s+(\d+)', _read(GRADLE))
    return m.group(1) if m else None


SOURCES = [
    ("backend/app/config.py", get_config),
    ("backend/pyproject.toml", get_pyproject),
    ("frontend/package.json", lambda: _json_version(FE_PKG)),
    ("ops/server/package.json", lambda: _json_version(ROOT_PKG)),
    ("frontend/android/app/build.gradle", get_gradle),
]


def _write(p: Path, text: str) -> None:
    p.write_text(text, encoding="utf-8")


def set_config(v: str) -> None:
    _write(CONFIG, re.sub(r'(version:\s*str\s*=\s*)"[^"]+"', rf'\1"{v}"', _read(CONFIG)))


def set_pyproject(v: str) -> None:
    _write(PYPROJECT, re.sub(r'^version\s*=\s*"[^"]+"', f'version = "{v}"',
                              _read(PYPROJECT), count=1, flags=re.MULTILINE))


def set_gradle(v: str) -> None:
    _write(GRADLE, re.sub(r'versionName\s+"[^"]+"', f'versionName "{v}"', _read(GRADLE)))


def set_json(p: Path, v: str) -> None:
    data = json.loads(_read(p))
    data["version"] = v
    _write(p, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


SYNCERS = [
    set_config,
    set_pyproject,
    lambda v: set_json(FE_PKG, v),
    lambda v: set_json(ROOT_PKG, v),
    set_gradle,
]


def main() -> int:
    ap = argparse.ArgumentParser(description="版本一致性校验（以 VERSION 为唯一事实来源）")
    ap.add_argument("--sync", action="store_true", help="把不一致的位置改写成 VERSION 的值")
    args = ap.parse_args()

    truth = read_truth()
    print(f"版本事实来源 VERSION = {truth}\n")

    if args.sync:
        for fn in SYNCERS:
            fn(truth)
        print("✅ 已同步全部版本位置\n")

    bad = []
    for name, fn in SOURCES:
        cur = fn()
        ok = cur == truth
        print(f"  {'✅' if ok else '❌'} {name:<40} {cur if cur else '(未声明)'}")
        if not ok:
            bad.append(name)

    code = get_android_code()
    if code:
        print(f"  ℹ️  {'frontend/android/app/build.gradle':<40} versionCode {code}"
              f"（整数发布序号，人工递增，不参与语义版本校验）")

    if bad:
        print(f"\n❌ 有 {len(bad)} 处版本号与 VERSION 不一致：{', '.join(bad)}")
        print("   修复：python scripts/check_versions.py --sync")
        return 1
    print("\n✅ 版本号一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())
