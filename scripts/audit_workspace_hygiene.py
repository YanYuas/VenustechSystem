#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""工作区结构守护（零第三方依赖）—— 把「哪里放什么」变成可执行规则

为什么需要：
  2026-10-28 盘点发现仓库根/var/backend 下长期累积本地垃圾：
  24 个 pytest basetemp（约 160MB）、var/.ruff-install（32MB）、var/rebuild、
  var/tools、var/junk、backend/.ruff_cache、backend/.pytest_cache、
  backend/.pytest-tmp*、backend/venustech_smoke ……
  这些目录都被 .gitignore 忽略，所以 `git status` 永远干净 —— 没人会发现它们，
  直到某天磁盘满了，或者换机器时把 200MB 垃圾一起拷走。
  更危险的是反向情况：某个运行期文件**没被忽略**却也没人注意（`backend/.arch-audit-x`
  当时就不在忽略规则里），一次 `git add -A` 就会入库。

检查项：
  A. tracked 泄漏（所有模式都查）
     `git ls-files` 里不得出现数据库、密钥、令牌、node_modules、dist、
     var/ 运行期文件、测试覆盖率产物（`var/.gitkeep` 是唯一例外）。
  B. .gitignore 契约（所有模式都查）
     关键路径必须**确实被忽略**（用 `git check-ignore` 逐条验证语义，
     而不是只 grep 文本）；`var/.gitkeep` 必须**不被**忽略。
  C. 根目录契约增强（仅本地模式）
     根下除 `docs/architecture/domains.json` 的 `root_contract` 允许项
     （含 `ignored_dirs`）外，不得出现新的未登记目录/文件。
  D. var/ 顶层白名单（仅本地模式）
     只允许 `data/ demo/ legacy/ backups/ logs/ tmp/`（+ `.gitkeep`）。
     其余视为垃圾：`pytest-*`、`.ruff-*`、`rebuild`、`tools`、`junk` 等。
     `var/logs/` 是启动器/服务日志目录：保留、**不自动删**（只提示可手动清旧日志）。
  E. 测试覆盖率产物（仅本地模式）
     `backend/.coverage*`（pytest-cov 并行数据）、`frontend/coverage/`、
     `coverage/`、`htmlcov/`、`coverage.xml`：被忽略则提示可清；未被忽略直接失败。

动作：
  --check      （默认）只检查，退出码 0 通过 / 1 有违规
  --fix-local 清理**明确废弃**的本地垃圾（含测试覆盖率产物），然后重新检查
              绝不触碰：var/data、var/demo、var/legacy、var/backups、var/logs、
              backend/.legacy-data-*（只提示"确认后可删"）

CI 兼容：
  CI 的干净克隆里没有 var/ 本地数据，根/var 白名单不适用。
  检测到 `CI=true` / `GITHUB_ACTIONS` 时自动只跑 A+B；也可显式 `--ci` / `--local`。

用法：
  python scripts/audit_workspace_hygiene.py
  python scripts/audit_workspace_hygiene.py --ci
  python scripts/audit_workspace_hygiene.py --fix-local
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GITIGNORE = ROOT / ".gitignore"
DOMAINS_JSON = ROOT / "docs" / "architecture" / "domains.json"

# ---------- A. tracked 泄漏规则 ----------
# 顺序即报告顺序；每条 (正则, 说明, 修复提示)
TRACKED_RULES: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(r"(^|/)\.encryption_key(\..*)?$"),
     "加密主密钥", "git rm --cached 并从历史清除；密钥只应存在于 $VENUSTECH_DATA_DIR"),
    (re.compile(r"(^|/)\.qm-token(\.prev)?$"),
     "访问令牌", "git rm --cached；令牌由 ops/server 在本地生成"),
    (re.compile(r"\.(db|db-wal|db-shm|sqlite|sqlite3)$", re.I),
     "数据库文件", "git rm --cached；运行期库只应存在于 var/"),
    (re.compile(r"(^|/)node_modules/"),
     "node_modules", "git rm -r --cached；依赖由 npm ci 重建"),
    (re.compile(r"(^|/)dist/"),
     "构建产物 dist/", "git rm -r --cached；构建产物由 npm run build 重建"),
    (re.compile(r"^var/"),
     "var/ 运行期文件", "git rm --cached；var/ 整体 gitignore（唯一例外 var/.gitkeep）"),
    (re.compile(r"(^|/)\.coverage(\.|$)"),
     "测试覆盖率数据", "git rm --cached；覆盖率是测试产物，只应留在本地"),
    (re.compile(r"(^|/)(coverage|htmlcov)/"),
     "测试覆盖率报告目录", "git rm -r --cached；覆盖率报告是测试产物，只应留在本地"),
]

TRACKED_EXCEPTIONS = {"var/.gitkeep"}

# ---------- B. .gitignore 契约（用 git check-ignore 验证语义） ----------
# (示例路径, 说明)：示例路径必须被忽略。选路径时覆盖"任意层级"与"仅仓库根"两类语义。
REQUIRED_IGNORED: list[tuple[str, str]] = [
    ("var/data/app.db", "真实运行期库"),
    ("var/demo/app.db", "演示库"),
    ("var/legacy/x.db", "历史数据副本"),
    ("var/backups/x.bundle", "本地备份产物"),
    ("var/pytest-bt-123/x", "pytest basetemp"),
    ("var/.ruff-install/python.exe", "本地工具安装目录"),
    (".arch-audit/reports/ops-docs.md", "本地审计报告"),
    (".claude/handoff.md", "智能体会话状态"),
    (".workbuddy/memory/MEMORY.md", "智能体长期记忆"),
    ("backend/venustech_smoke/app.db", "冒烟临时库"),
    ("backend/.pytest_cache/v/cache", "pytest 缓存"),
    ("backend/.ruff_cache/content", "ruff 缓存"),
    ("backend/.pytest-tmp-run/x", "pytest 临时/基线目录"),
    ("backend/.arch-audit-x/x", "旧审计临时目录（曾未被忽略）"),
    ("backend/.legacy-data-2026-10-27/app.db", "迁移前旧数据兜底"),
    ("frontend/node_modules/x", "前端依赖"),
    ("frontend/dist/index.html", "前端构建产物"),
    (".env", "真实环境变量文件"),
    ("foo/app.db", "任意层级的数据库"),
    ("frontend/foo.log", "日志文件"),
    # 测试覆盖率产物（pytest-cov / vitest；2026-10-28 实测 backend/.coverage.<machine>.<pid>.<rand>）
    ("backend/.coverage", "pytest-cov 覆盖率数据文件"),
    ("backend/.coverage.长空.pid1.x", ".coverage.* 并行覆盖率数据文件"),
    ("frontend/coverage/index.html", "前端 vitest 覆盖率报告目录"),
    ("coverage/index.html", "任意层级的 coverage/ 目录"),
    ("backend/htmlcov/index.html", "pytest-cov HTML 报告"),
    ("coverage.xml", "覆盖率 XML 报告"),
]
# 必须**不被**忽略的路径（目录结构锚点）
REQUIRED_TRACKED = [("var/.gitkeep", "var/ 目录结构锚点必须入库")]

# 测试覆盖率产物：本地模式若存在就提示（可 --fix-local 清理）；其中"未被忽略"直接判失败。
COVERAGE_PATHS = (
    "backend/.coverage",
    "frontend/coverage",
    "coverage",
    "backend/htmlcov",
    "coverage.xml",
)

# ---------- C/D. 本地目录契约 ----------
VAR_ALLOWED_DIRS = ("data", "demo", "legacy", "backups", "logs", "tmp")
VAR_ALLOWED_FILES = (".gitkeep",)
VAR_PROTECTED_DIRS = ("data", "demo", "legacy", "backups")  # 数据兜底：只提示，绝不删除
BACKEND_PROTECTED_PREFIX = ".legacy-data-"

# --fix-local 的清理白名单（"明确废弃"的本地垃圾）
VAR_JUNK_DIR_EXACT = {"rebuild", "tools", "junk", "probe-ps", "sandbox_patch"}
VAR_JUNK_DIR_GLOB = ("pytest-*", ".ruff-*", ".deleting-*")
BACKEND_JUNK_DIR_EXACT = {".ruff_cache", ".pytest_cache", ".arch-audit-x", "venustech_smoke"}
BACKEND_JUNK_DIR_GLOB = (".pytest-tmp*",)

# 删除被 Windows 文件权限挡住时（典型：别的工作区/沙箱创建的 0700 目录）的隔离区：
# 移到 var/tmp/ 下（var/tmp 在白名单内），等有权限的会话彻底删除。
QUARANTINE_DIRNAME = "acl-blocked"

# 空目录也占位；var/tmp 只清内容，保留目录
VAR_TMP_DIR = "tmp"


# ==================================================================
# 基础工具
# ==================================================================
def _run_git(args: list[str]) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            ["git", *args], cwd=str(ROOT), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=120,
        )
    except (OSError, subprocess.SubprocessError):
        return None


def _size(path: Path) -> int:
    if path.is_file():
        try:
            return path.stat().st_size
        except OSError:
            return 0
    total = 0
    try:
        for p in path.rglob("*"):
            try:
                if p.is_file():
                    total += p.stat().st_size
            except OSError:
                continue
    except OSError:
        return total
    return total


def _mb(n: int) -> str:
    return f"{n / 1024 / 1024:.1f}MB"


def _rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def _is_ci() -> bool:
    for key in ("CI", "GITHUB_ACTIONS", "CONTINUOUS_INTEGRATION"):
        if os.environ.get(key, "").strip().lower() in ("1", "true", "yes", "on"):
            return True
    return False


# ==================================================================
# A. tracked 泄漏
# ==================================================================
def get_tracked_files() -> list[str] | None:
    proc = _run_git(["ls-files", "-z"])
    if proc is None or proc.returncode != 0:
        return None
    return [p for p in proc.stdout.split("\0") if p]


def check_tracked(files: list[str]) -> list[str]:
    problems: list[str] = []
    for path in files:
        if path in TRACKED_EXCEPTIONS:
            continue
        for pattern, label, hint in TRACKED_RULES:
            if pattern.search(path):
                problems.append(f"[A] tracked 泄漏：{path}（{label}）—— {hint}")
                break
    return problems


# ==================================================================
# B. .gitignore 契约（语义验证，不 grep 文本）
# ==================================================================
def _check_ignored(samples: list[str]) -> set[str] | None:
    """返回被忽略的样本集合；git 不可用时返回 None。

    用 `-z`（NUL 分隔）而不是逐行：Windows 上 text 模式会把 `\n` 写成 `\r\n`，
    git 会把尾随 `\r` 当成路径的一部分，导致"明明被忽略却判为未忽略"。
    """
    if not samples:
        return set()
    payload = ("\0".join(samples) + "\0").encode("utf-8")
    try:
        proc = subprocess.run(
            ["git", "check-ignore", "--stdin", "-z"], cwd=str(ROOT),
            input=payload, capture_output=True, timeout=120,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode not in (0, 1):
        return None
    out = proc.stdout.decode("utf-8", errors="replace")
    return {p for p in out.split("\0") if p}


def check_ignore_contract() -> list[str]:
    problems: list[str] = []
    if not GITIGNORE.is_file():
        return ["[B] 缺少 .gitignore —— 忽略契约无从谈起"]
    samples = [p for p, _ in REQUIRED_IGNORED]
    ignored = _check_ignored(samples)
    if ignored is None:
        return ["[B] git 不可用，无法验证 .gitignore 契约（不可静默通过）"]
    for sample, label in REQUIRED_IGNORED:
        if sample not in ignored:
            problems.append(
                f"[B] .gitignore 未覆盖：{sample}（{label}）—— "
                f"在 .gitignore 补上对应模式后重跑"
            )
    # 锚点文件必须能入库
    tracked_anchor = [p for p, _ in REQUIRED_TRACKED]
    anchor_ignored = _check_ignored(tracked_anchor)
    if anchor_ignored is None:
        problems.append("[B] git 不可用，无法验证 var/.gitkeep 未被忽略")
    else:
        for sample, label in REQUIRED_TRACKED:
            if sample in anchor_ignored:
                problems.append(
                    f"[B] {sample} 被 .gitignore 忽略了（{label}）—— 需要 `!var/.gitkeep` 例外"
                )
    return problems


# ==================================================================
# C. 根目录契约（本地模式）
# ==================================================================
def _load_root_contract() -> tuple[set[str], set[str], set[str]] | None:
    try:
        data = json.loads(DOMAINS_JSON.read_text(encoding="utf-8"))
        contract = data["root_contract"]
    except (OSError, KeyError, json.JSONDecodeError):
        return None
    allowed_files = {x for x in contract.get("files", []) if not x.startswith("$")}
    allowed_dirs = {x for x in contract.get("dirs", []) if not x.startswith("$")}
    ignored_dirs = {x for x in contract.get("ignored_dirs", []) if not x.startswith("$")}
    return allowed_files, allowed_dirs, ignored_dirs


def check_root_contract() -> list[str]:
    problems: list[str] = []
    contract = _load_root_contract()
    if contract is None:
        return [f"[C] 无法读取根目录契约：{_rel(DOMAINS_JSON)}（root_contract）"]
    allowed_files, allowed_dirs, ignored_dirs = contract
    try:
        entries = sorted(ROOT.iterdir(), key=lambda p: p.name.lower())
    except OSError as exc:
        return [f"[C] 无法读取仓库根目录：{exc}"]
    for entry in entries:
        name = entry.name
        if name in ignored_dirs:
            continue
        if entry.is_dir():
            if name not in allowed_dirs:
                problems.append(
                    f"[C] 根目录出现未登记的目录：{name}/ —— "
                    f"移入对应层（源码→backend/frontend，运维→ops，脚本→scripts）"
                    f"或在 domains.json root_contract.dirs 登记"
                )
        else:
            if name not in allowed_files:
                problems.append(
                    f"[C] 根目录出现未登记的文件：{name} —— "
                    f"移入对应层，或在 domains.json root_contract.files 登记"
                )
    return problems


# ==================================================================
# D. var/ 顶层白名单（本地模式）
# ==================================================================
def _classify_var_entry(entry: Path) -> str | None:
    """返回垃圾原因；None 表示不是已知垃圾。

    只用于 --check 的"可 --fix-local 清理"提示；
    白名单判定见 check_var_whitelist。
    """
    name = entry.name
    if entry.is_dir():
        if name in VAR_PROTECTED_DIRS or name == "logs":
            return None
        if name in VAR_JUNK_DIR_EXACT:
            return "本地工具/中间产物目录"
        for pat in VAR_JUNK_DIR_GLOB:
            if Path(name).match(pat):
                return "pytest/ruff 本地临时目录"
        return "未登记的 var/ 顶层目录"
    if name in VAR_ALLOWED_FILES:
        return None
    return "var/ 顶层散落的本地日志/脚本/临时文件"


def _is_acl_blocked(path: Path) -> bool:
    """目录是否被 Windows 文件权限挡住（本会话连列目录都做不到）。

    这是 DSH 沙箱边界：目录由**其他沙箱会话**创建（`mode0700` 的 AppContainer ACL），
    当前会话没有 READ_CONTROL/WRITE_DAC，`rd /s`、`takeown`、`icacls` 全部 Access denied。
    这种残留无法在本会话删除，只能提示用完全权限会话清理。
    """
    try:
        next(os.scandir(path), None)
        return False
    except PermissionError:
        return True
    except OSError:
        return False


def _matches_var_junk(name: str) -> bool:
    if name in VAR_JUNK_DIR_EXACT:
        return True
    return any(Path(name).match(pat) for pat in VAR_JUNK_DIR_GLOB)


def check_var_whitelist() -> tuple[list[str], list[str]]:
    """返回 (problems, warnings)。warnings 是数据兜底/ACL 残留提示，不参与判定。"""
    problems: list[str] = []
    warns: list[str] = []
    var_dir = ROOT / "var"
    if not var_dir.is_dir():
        return problems, warns
    for entry in sorted(var_dir.iterdir(), key=lambda p: p.name.lower()):
        name = entry.name
        if entry.is_dir():
            if name in VAR_ALLOWED_DIRS:
                continue
            if _matches_var_junk(name) and _is_acl_blocked(entry):
                warns.append(
                    f"var/{name}/ — Windows 文件权限拒绝访问（DSH 沙箱边界，本会话无法删除/验证）。"
                    f"请在完全权限会话执行：rd /s /q \"{entry}\""
                )
                continue
            reason = _classify_var_entry(entry) or "未登记的 var/ 顶层目录"
            problems.append(
                f"[D] var/{name}/ 不在白名单（{reason}，{_mb(_size(entry))}）"
                f" —— 删除或迁移；已知垃圾可 `--fix-local` 清理"
            )
        else:
            if name in VAR_ALLOWED_FILES:
                continue
            problems.append(
                f"[D] var/{name} 不在白名单（var/ 顶层散落文件，{_mb(_size(entry))}）"
                f" —— 移入 var/tmp 或删除"
            )
    # 数据兜底目录：只提示
    for name in VAR_PROTECTED_DIRS:
        p = var_dir / name
        if p.is_dir():
            warns.append(f"var/{name}/（{_mb(_size(p))}）— 数据兜底/真实库，保留（确认后可手动删）")
    # 启动器日志：白名单内，--fix-local 不删（只提示，旧日志由人自行判断）
    logs = var_dir / "logs"
    if logs.is_dir():
        n = sum(1 for _ in logs.rglob("*")) if _is_readable(logs) else 0
        warns.append(
            f"var/logs/（{_mb(_size(logs))}，{n} 个条目）— 启动器/服务日志目录（白名单内）；"
            f"--fix-local 不删，需要时手动清理旧日志（如 var/logs/*.log）"
        )
    return problems, warns


def _is_readable(path: Path) -> bool:
    try:
        next(os.scandir(path), None)
        return True
    except OSError:
        return False


def check_coverage_artifacts() -> tuple[list[str], list[str]]:
    """测试覆盖率产物（pytest-cov / vitest）。

    本地模式：存在即提示（可 `--fix-local` 清理）；**未被 .gitignore 覆盖**直接判失败
    —— 覆盖率数据一旦被 `git add -A` 带上就是几千行二进制/巨量 HTML。
    CI 干净 clone 不会有这些文件，故 CI 模式跳过存在性检查（ignore 契约仍在 B 检查）。
    """
    problems: list[str] = []
    warns: list[str] = []
    found: list[Path] = []
    for rel in COVERAGE_PATHS:
        p = ROOT / rel
        if p.exists():
            found.append(p)
    backend = ROOT / "backend"
    if backend.is_dir():
        for p in sorted(backend.glob(".coverage*")):
            if p not in found:
                found.append(p)
    for p in found:
        rel = _rel(p)
        ignored = _check_ignored([rel])
        if ignored is None:
            problems.append(f"[E] git 不可用，无法验证覆盖率产物是否被忽略：{rel}")
            continue
        if rel not in ignored:
            problems.append(
                f"[E] 测试覆盖率产物未被 .gitignore 忽略：{rel}（{_mb(_size(p))}）"
                f" —— 在 .gitignore 加 `.coverage*` / `coverage/` / `htmlcov/`"
            )
        else:
            warns.append(
                f"{rel}（{_mb(_size(p))}）— 本地测试覆盖率产物，可安全删除"
                f"（`--fix-local` 会清理）"
            )
    return problems, warns


def check_backend_protected_warnings() -> list[str]:
    warns: list[str] = []
    backend = ROOT / "backend"
    if not backend.is_dir():
        return warns
    for entry in sorted(backend.iterdir(), key=lambda p: p.name.lower()):
        if entry.is_dir() and entry.name.startswith(BACKEND_PROTECTED_PREFIX):
            warns.append(
                f"backend/{entry.name}/（{_mb(_size(entry))}）— 迁移前旧数据兜底，"
                f"确认无误后可手动删（守护不删）"
            )
    return warns


# ==================================================================
# --fix-local：清理明确废弃的本地垃圾
# ==================================================================
def check_quarantine_warnings() -> list[str]:
    """var/tmp/acl-blocked/：Windows 权限拒绝删除的残留（不参与判定，但必须提示）。"""
    warns: list[str] = []
    qroot = ROOT / "var" / "tmp" / QUARANTINE_DIRNAME
    if not qroot.is_dir():
        return warns
    for entry in sorted(qroot.iterdir(), key=lambda p: p.name.lower()):
        warns.append(
            f"{_rel(entry)}（{_mb(_size(entry))}）— Windows 文件权限拒绝删除（来自其他沙箱会话），"
            f"需在完全权限会话执行：rd /s /q \"{entry}\""
        )
    return warns


def collect_fix_targets() -> list[tuple[Path, str]]:
    """返回 [(路径, 说明)]。**绝不**包含数据兜底/受保护目录。"""
    targets: list[tuple[Path, str]] = []

    def _is_protected(p: Path) -> bool:
        rel = _rel(p)
        if rel in {f"var/{d}" for d in VAR_PROTECTED_DIRS}:
            return True
        if rel.startswith("var/logs"):
            return True
        if rel.startswith("backend/" + BACKEND_PROTECTED_PREFIX):
            return True
        return False

    var_dir = ROOT / "var"
    if var_dir.is_dir():
        for entry in sorted(var_dir.iterdir(), key=lambda p: p.name.lower()):
            if _is_protected(entry):
                continue
            name = entry.name
            if entry.is_dir():
                if name in VAR_JUNK_DIR_EXACT:
                    targets.append((entry, "var/ 本地工具/中间产物目录"))
                elif any(Path(name).match(pat) for pat in VAR_JUNK_DIR_GLOB):
                    targets.append((entry, "var/ pytest/ruff 临时目录"))
                elif name == VAR_TMP_DIR:
                    for child in sorted(entry.iterdir(), key=lambda p: p.name.lower()):
                        if child.name in (".gitkeep", QUARANTINE_DIRNAME):
                            continue
                        targets.append((child, "var/tmp 临时文件"))
            else:
                if name not in VAR_ALLOWED_FILES:
                    targets.append((entry, "var/ 顶层散落文件（日志/一次性脚本/临时产物）"))

    backend = ROOT / "backend"
    if backend.is_dir():
        for entry in sorted(backend.iterdir(), key=lambda p: p.name.lower()):
            if not entry.is_dir():
                continue
            name = entry.name
            if name.startswith(BACKEND_PROTECTED_PREFIX):
                continue
            if name in BACKEND_JUNK_DIR_EXACT:
                targets.append((entry, "backend/ 本地缓存/临时目录"))
            elif any(Path(name).match(pat) for pat in BACKEND_JUNK_DIR_GLOB):
                targets.append((entry, "backend/ pytest 临时目录"))

    # 测试覆盖率产物（pytest-cov / vitest）—— 测试产物，可安全删除
    for rel in COVERAGE_PATHS:
        p = ROOT / rel
        if p.exists():
            targets.append((p, "测试覆盖率产物"))
    if backend.is_dir():
        for p in sorted(backend.glob(".coverage*")):
            if p.exists() and not any(t[0] == p for t in targets):
                targets.append((p, "pytest-cov 并行覆盖率数据文件"))
    return targets


def safe_remove(path: Path) -> tuple[str, str]:
    """先重命名再删除；删不掉（权限/占用）时隔离到 var/tmp，绝不半删。

    返回 (status, message)：status ∈ {"removed", "quarantined", "blocked", "skipped"}。

    为什么先 rename：Windows 上目录里有文件被打开时无法删除；rename 失败即说明
    "可能正在使用"，跳过而不是原地 rmtree 造成半删。
    为什么隔离：本工作区曾被其他沙箱会话创建过 0700 目录（`.piptmp` / `.ruff_install`），
    当前会话没有 WRITE_DAC 权限，`rd /s` 也报 Access denied —— 这类残留移入
    `var/tmp/acl-blocked/`（白名单内），由有权限的会话用一条命令彻底删除。
    """
    quarantine_root = ROOT / "var" / "tmp" / QUARANTINE_DIRNAME

    def _quarantine(src: Path, msg: str) -> tuple[str, str]:
        try:
            quarantine_root.mkdir(parents=True, exist_ok=True)
            dest = quarantine_root / f"{src.name}-{os.getpid()}"
            src.rename(dest)
            return "quarantined", (
                f"{msg}；已隔离到 {_rel(dest)}（Windows 文件权限拒绝删除，"
                f"请在完全权限会话执行 rd /s /q \"{dest}\"）"
            )
        except OSError as exc:
            return "skipped", f"{msg}；隔离失败：{exc}"

    try:
        if path.is_file() or path.is_symlink():
            for attempt in range(3):
                try:
                    path.unlink()
                    return "removed", "removed"
                except PermissionError:
                    if attempt == 2:
                        return _quarantine(path, "删除失败（可能是正在运行的测试/进程）")
                    time.sleep(0.3)
            return _quarantine(path, "删除失败")
        if path.is_dir():
            trash = path.with_name(f".deleting-{os.getpid()}-{path.name}")
            try:
                path.rename(trash)
            except OSError:
                if _is_acl_blocked(path):
                    return "blocked", (
                        "Windows 文件权限拒绝访问（DSH 沙箱边界，本会话无法删除/验证）；"
                        f"请在完全权限会话执行：rd /s /q \"{path}\""
                    )
                return "skipped", "被占用（可能是正在运行的测试/进程），已跳过"
            last_err: str = ""
            for _attempt in range(4):
                try:
                    shutil.rmtree(trash)
                    return "removed", "removed"
                except OSError as exc:
                    last_err = str(exc)
                    time.sleep(0.4)
            # 删不干净：把 trash 移到隔离区（同一卷内的 rename，不需要读子目录权限）
            return _quarantine(trash, f"删除失败（{last_err or 'permission denied'}）")
    except OSError as exc:
        return "skipped", str(exc)
    return "skipped", "unknown"


def fix_local() -> int:
    """执行清理；返回删除失败的条数（用于退出提示）。"""
    if _is_ci():
        print("❌ 拒绝在 CI 环境执行 --fix-local（CI 不应删除文件）")
        return 1
    targets = collect_fix_targets()
    if not targets:
        print("\n[fix-local] 没有需要清理的本地垃圾。")
        return 0

    total = sum(_size(p) for p, _ in targets)
    print(f"\n{'=' * 62}")
    print(f"[fix-local] 计划清理 {len(targets)} 项，共 {_mb(total)}")
    print(f"{'=' * 62}")
    for path, reason in targets:
        print(f"  - {_rel(path):<52} {_mb(_size(path)):>9}  {reason}")
    print("\n  受保护（绝不删除）：var/data、var/demo、var/legacy、var/backups、backend/.legacy-data-*")

    failed = 0
    quarantined = 0
    blocked = 0
    freed = 0
    print(f"\n{'=' * 62}\n[fix-local] 执行清理\n{'=' * 62}")
    for path, _reason in targets:
        size = _size(path)
        status, msg = safe_remove(path)
        if status == "removed":
            freed += size
            print(f"  ✅ {_rel(path)}（{_mb(size)}）")
        elif status == "quarantined":
            quarantined += 1
            print(f"  ⚠️  {_rel(path)} 未能删除，已隔离：{msg}")
        elif status == "blocked":
            blocked += 1
            print(f"  🔒 {_rel(path)} 无法访问：{msg}")
        else:
            failed += 1
            print(f"  ⚠️  {_rel(path)} 跳过：{msg}")
    print(f"\n[fix-local] 完成：释放 {_mb(freed)}；隔离 {quarantined} 项；"
          f"跳过 {failed} 项（占用）；权限锁定 {blocked} 项（需完全权限会话）")
    return failed


# ==================================================================
# 入口
# ==================================================================
def run_checks(local_mode: bool) -> int:
    mode_label = "本地（A+B+C+D+E）" if local_mode else "CI（仅 A+B，干净克隆无本地数据）"
    print("=" * 62)
    print("工作区结构守护 · tracked 泄漏 / .gitignore 契约 / 根与 var 白名单")
    print("=" * 62)
    print(f"  仓库: {ROOT}")
    print(f"  模式: {mode_label}")

    problems: list[str] = []
    warns: list[str] = []

    # --- A ---
    print(f"\n▶ A. tracked 泄漏（git ls-files）")
    files = get_tracked_files()
    if files is None:
        problems.append("[A] git 不可用，无法读取 tracked 文件列表（不可静默通过）")
        print("  ❌ git 不可用")
    else:
        a_problems = check_tracked(files)
        problems += a_problems
        if a_problems:
            for p in a_problems:
                print(f"  ❌ {p}")
        else:
            print(f"  ✅ {len(files)} 个 tracked 文件中无数据库/密钥/令牌/node_modules/dist/var 运行期文件")

    # --- B ---
    print(f"\n▶ B. .gitignore 契约（{len(REQUIRED_IGNORED)} 条关键路径 + {len(REQUIRED_TRACKED)} 个锚点）")
    b_problems = check_ignore_contract()
    problems += b_problems
    if b_problems:
        for p in b_problems:
            print(f"  ❌ {p}")
    else:
        print("  ✅ 关键路径全部被忽略；var/.gitkeep 未被忽略")

    # --- C ---
    print(f"\n▶ C. 根目录契约（domains.json root_contract）")
    if not local_mode:
        print("  ⏭  跳过：CI 干净克隆不检查本地特有的根级目录")
    else:
        c_problems = check_root_contract()
        problems += c_problems
        if c_problems:
            for p in c_problems:
                print(f"  ❌ {p}")
        else:
            print("  ✅ 根目录条目均已在 root_contract 登记")

    # --- D ---
    print(f"\n▶ D. var/ 顶层白名单（{'/'.join(VAR_ALLOWED_DIRS)}）")
    if not local_mode:
        print("  ⏭  跳过：CI 干净克隆里 var/ 只有 .gitkeep")
    else:
        d_problems, d_warns = check_var_whitelist()
        problems += d_problems
        warns += d_warns
        if d_problems:
            for p in d_problems:
                print(f"  ❌ {p}")
        else:
            print("  ✅ var/ 顶层只有白名单目录（data/demo/legacy/backups/logs/tmp）")

    # --- E. 测试覆盖率产物（本地模式；CI 干净 clone 没有这些文件）---
    print(f"\n▶ E. 测试覆盖率产物（pytest-cov / vitest）")
    if not local_mode:
        print("  ⏭  跳过：CI 干净克隆不会带覆盖率产物（忽略契约仍在 B 校验）")
    else:
        e_problems, e_warns = check_coverage_artifacts()
        problems += e_problems
        warns += e_warns
        if e_problems:
            for p in e_problems:
                print(f"  ❌ {p}")
        else:
            print(f"  ✅ 覆盖率产物均已被 .gitignore 覆盖（{len(e_warns)} 个本地产物可 --fix-local 清理）")

    # --- W: 数据兜底 / 本地产物提示（不参与判定）---
    if local_mode:
        all_warns = warns + check_backend_protected_warnings() + check_quarantine_warnings()
        if all_warns:
            print("\n▶ W. 数据兜底 / 隔离区 / 本地产物提示（不参与判定，只提示）")
            for w in all_warns:
                print(f"  ℹ️  {w}")

    print(f"\n{'=' * 62}\n汇总\n{'=' * 62}")
    if problems:
        print(f"❌ 发现 {len(problems)} 个结构问题\n")
        print("修复：")
        print("  · 本地垃圾（含测试覆盖率产物）：python scripts/audit_workspace_hygiene.py --fix-local")
        print("  · tracked 泄漏：git rm --cached <file> 并从历史清除")
        print("  · 忽略缺失：在 .gitignore 补齐（契约清单见本脚本 REQUIRED_IGNORED）")
        print("  · 根目录/ var 白名单：移动到对应层，或在 domains.json 登记（根级）")
        return 1
    print("✅ 工作区结构符合契约")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="工作区结构守护（tracked 泄漏 / ignore 契约 / 根与 var 白名单）")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="只检查（默认）")
    mode.add_argument("--fix-local", action="store_true",
                      help="清理明确废弃的本地垃圾，然后重新检查（绝不删数据兜底目录）")
    scope = ap.add_mutually_exclusive_group()
    scope.add_argument("--ci", action="store_true", help="强制 CI 模式：只查 A+B")
    scope.add_argument("--local", action="store_true", help="强制本地模式：A+B+C+D+E")
    args = ap.parse_args()

    if args.local:
        local_mode = True
    elif args.ci:
        local_mode = False
    else:
        local_mode = not _is_ci()

    if args.fix_local:
        failed = fix_local()
        print()
        rc = run_checks(local_mode)
        if failed and rc == 0:
            print(f"\n⚠️  有 {failed} 项未能清理（可能被占用），请关闭相关进程后重跑 --fix-local")
            return 1
        return rc
    return run_checks(local_mode)


if __name__ == "__main__":
    sys.exit(main())
