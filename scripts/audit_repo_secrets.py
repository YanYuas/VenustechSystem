#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""仓库敏感文件守护（零第三方依赖）

为什么需要：
  2026-10 审计确认 `backend/data/app.db`（606KB 真实用户库）曾被提交，
  至今仍存在于远端分支 `origin/feature/phase2-development` 的树里，
  任何能访问该仓库的人都能 `git show <branch>:backend/data/app.db`。
  只靠 `.gitignore` 挡不住"历史上已经提交过"的文件，必须有主动检查。

检查三件事：
  A. 当前索引（git ls-files）里不得出现数据库/密钥/令牌/环境文件；
  B. 全部 refs 的历史新增文件里，不得再出现数据库（默认 WARN，--strict 时 ERROR）；
  C. `.gitignore` 对运行期数据的覆盖是否生效（抽样断言）。

用法：
  python scripts/audit_repo_secrets.py            # 本地：历史泄漏只提示
  python scripts/audit_repo_secrets.py --strict   # CI：历史泄漏也算失败
退出码：0 通过；1 有当前索引违规（或 --strict 下的历史泄漏）
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 当前索引中禁止出现的文件（正则，匹配相对路径的 posix 形式）
FORBIDDEN_INDEX = [
    (r"(^|/)\.env$", "环境变量文件（含密钥）"),
    (r"(^|/)\.qm-token$", "访问令牌"),
    (r"(^|/)\.encryption_key$", "AES 主密钥"),
    (r"\.db$", "SQLite 数据库"),
    (r"\.db-wal$", "SQLite WAL"),
    (r"\.db-shm$", "SQLite 共享内存"),
    (r"\.sqlite3?$", "SQLite 数据库"),
    (r"\.pem$", "私钥/证书"),
    (r"\.key$", "密钥文件"),
    (r"^backend/data[\w.\-]*/", "运行期数据目录"),
]

# 允许的模板文件（不是真密钥）
ALLOW = {
    "backend/.env.example",
    "frontend/.env.development",
    "frontend/.env.production",
    "frontend/android/app/debug.keystore",  # Android 调试签名，公开且非敏感
}

# 历史新增文件里只追究"数据/密钥"，不追究 .env 模板
HISTORY_FORBIDDEN = re.compile(r"(\.db|\.db-wal|\.db-shm|\.sqlite3?|\.encryption_key|\.qm-token|\.pem)$")


def git(*args: str) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=str(ROOT), capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    return proc.stdout if proc.returncode == 0 else ""


def check_index() -> list[str]:
    problems = []
    for rel in (git("ls-files", "-z").split("\0")):
        if not rel or rel in ALLOW:
            continue
        for pattern, desc in FORBIDDEN_INDEX:
            if re.search(pattern, rel):
                problems.append(f"索引包含 {desc}: {rel}")
                break
    return problems


def check_history() -> list[tuple[str, str]]:
    """返回 [(commit, path)] —— 历史中曾被新增的敏感文件。"""
    out = git("log", "--all", "--diff-filter=A", "--name-only", "--pretty=format:__COMMIT__%H")
    leaks: list[tuple[str, str]] = []
    commit = "?"
    for line in out.splitlines():
        if line.startswith("__COMMIT__"):
            commit = line[len("__COMMIT__"):]
        elif line.strip() and HISTORY_FORBIDDEN.search(line.strip()):
            leaks.append((commit, line.strip()))
    return sorted(set(leaks))


def check_ignore_rules() -> list[str]:
    """抽样确认运行期数据不会被再次提交。"""
    problems = []
    for sample in ("var/data/app.db", "backend/data/app.db", ".qm-token", "backend/data/x.db"):
        proc = subprocess.run(
            ["git", "check-ignore", "-q", sample], cwd=str(ROOT),
            capture_output=True, text=True,
        )
        if proc.returncode != 0:
            problems.append(f".gitignore 未覆盖运行期路径: {sample}")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description="仓库敏感文件守护")
    ap.add_argument("--strict", action="store_true", help="历史泄漏也视为失败（CI 收口）")
    args = ap.parse_args()

    print("=" * 62)
    print("仓库敏感文件守护")
    print("=" * 62)

    index_problems = check_index()
    ignore_problems = check_ignore_rules()
    leaks = check_history()

    if index_problems:
        print(f"\n❌ 当前索引违规：{len(index_problems)}")
        for p in index_problems:
            print(f"  · {p}")
    else:
        print("\n✅ 当前索引无数据库/密钥/令牌/环境文件")

    if ignore_problems:
        print(f"\n❌ .gitignore 覆盖不足：{len(ignore_problems)}")
        for p in ignore_problems:
            print(f"  · {p}")

    if leaks:
        print(f"\n⚠️  历史中曾新增敏感文件：{len(leaks)} 处（已删除的仍需处置，见 runbook）")
        for commit, path in leaks[:20]:
            print(f"  · {commit[:10]}  {path}")
        if len(leaks) > 20:
            print(f"  … 另有 {len(leaks) - 20} 处")
        print("  处置：docs/runbooks/security-incident-db-leak.md")
    else:
        print("\n✅ 历史中未发现敏感文件")

    failed = bool(index_problems or ignore_problems or (args.strict and leaks))
    print("\n" + "=" * 62)
    if failed:
        print("❌ 仓库敏感文件守护失败")
        return 1
    print("✅ 仓库敏感文件守护通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
