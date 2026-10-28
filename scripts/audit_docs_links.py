#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""文档链接与路径守护（零第三方依赖）

为什么需要：
  docs/ 有 65+ 文件、3.7MB，且会随架构调整搬迁目录。2026-10 审计发现：
  - 正文承诺的 10 个路径根本不存在（如 docs/onboarding.md）；
  - 同一批数字在 README / PROJECT_STRUCTURE / DEVELOPMENT 三处互相矛盾。
  人工靠肉眼守 72 个 md 的链接不现实，故落成 CI 守护。

检查内容：
  A. Markdown 相对链接 [text](path) —— 目标必须存在
  B. 正文内联路径（`docs/xxx.md`、`backend/app/...` 等反引号包裹、
     且以仓库已知顶层目录开头的路径）—— 目标必须存在
  C. 锚点链接（#xxx）只校验同文件内是否存在对应标题（可选，默认开）

用  法：
  python scripts/audit_docs_links.py           # 扫描 README + docs/**/*.md
  python scripts/audit_docs_links.py --all     # 额外扫描 CONTRIBUTING/CHANGELOG
退出码：0 通过；1 存在失效链接
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent

# 视为"仓库内路径"的顶层目录（用于识别正文内联路径，避免误报 npm 包名等）
TOP_DIRS = ("backend", "frontend", "docs", "scripts", "ops", "var", ".github")

# 冻结区：历史快照，只读归档。里面的相对链接/内联路径反映的是"当时"的仓库结构，
# 架构调整后必然失效，但**不应改写历史文档**（那是取证材料）。因此不参与门禁，
# 只在输出里提示"已跳过 N 个归档文件"。
# 规则：现行文档必须零失效；归档文档不校验。
FROZEN_PREFIXES = (
    "docs/architecture/legacy/",
    "docs/product/prd/v1-archived/",
    "docs/process/",
)

# 变更日志是"历史记录"，写的是当时的路径，和归档文档同理：不参与门禁。
FROZEN_FILES = {"CHANGELOG.md"}

MD_LINK = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
INLINE_PATH = re.compile(r"`([^`\n]+)`")
HEADING = re.compile(r"^(#{1,6})\s+(.*)$", re.MULTILINE)

SKIP_PREFIXES = ("http://", "https://", "mailto:", "tel:", "data:", "#", "//")

# 运行期数据在 var/（整目录 gitignore）。文档当然要写它（用户要知道库在哪），
# 但 CI 的干净克隆里必然不存在 —— 不能当成"失效路径"。
RUNTIME_PREFIXES = (
    "var/",                  # 运行期数据（gitignored）
    "frontend/dist/",        # 前端构建产物（gitignored）
    "frontend/node_modules/",  # 依赖（gitignored）
    "frontend/coverage/",    # 覆盖率报告（gitignored）
    "backend/.venv/",        # Python 虚拟环境（gitignored）
    "backend/.coverage",     # pytest-cov 产物（gitignored）
)


def normalize_path(p: str) -> str:
    r"""Windows 反斜杠写法在 Linux runner 上会被当成普通字符。

    文档里 ops\start.ps1 这类反斜杠写法很自然，统一归一为 / 后再做存在性判断，
    保证同一份文档在 Windows 与 Linux 上结论一致。
    """
    return p.replace("\\", "/")


def md_files(extra_all: bool) -> list[Path]:
    files = [ROOT / "README.md"]
    if extra_all:
        files += [ROOT / "CONTRIBUTING.md", ROOT / "CHANGELOG.md", ROOT / "ARCHITECTURE.md"]
    files += sorted((ROOT / "docs").rglob("*.md"))
    return [f for f in files if f.is_file()]


def is_frozen(path: Path) -> bool:
    rel = path.relative_to(ROOT).as_posix()
    return rel in FROZEN_FILES or any(rel.startswith(p) for p in FROZEN_PREFIXES)


def slugify(text: str) -> str:
    """GitHub 风格锚点：小写、去标点、空格转 -（中文保留）。"""
    text = re.sub(r"[`*_~\[\]()]", "", text).strip().lower()
    text = re.sub(r"[^\w\u4e00-\u9fff\- ]", "", text)
    return re.sub(r"\s+", "-", text)


def headings_of(path: Path) -> set[str]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return set()
    return {slugify(m.group(2)) for m in HEADING.finditer(text)}


def check_file(path: Path) -> list[str]:
    problems: list[str] = []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError as e:
        return [f"{path.relative_to(ROOT)}: 读取失败 {e}"]

    where = path.relative_to(ROOT).as_posix()

    def report(target: str, kind: str) -> None:
        problems.append(f"{where}: {kind}失效 → {target}")

    for target in MD_LINK.findall(text):
        if target.startswith(SKIP_PREFIXES):
            continue
        clean = normalize_path(unquote(target.split("#")[0]))
        if not clean:
            continue  # 纯锚点
        dest = (path.parent / clean).resolve()
        if not dest.exists():
            report(target, "链接")
        elif target.startswith("#"):
            continue

    for inline in INLINE_PATH.findall(text):
        s = normalize_path(inline.strip())
        if not s or " " in s or "|" in s:
            continue
        if not s.startswith(TOP_DIRS):
            continue
        if any(ch in s for ch in "*<>{}"):
            continue
        if not re.search(r"\.(md|py|ts|vue|js|json|ya?ml|toml|bat|ps1|txt|db|html|scss|css)$", s):
            continue
        # 允许前缀式引用（目录）：去掉末尾 `.`、`:`、`#...`
        probe = re.split(r"[:#]", s)[0].rstrip(".")
        if probe.startswith(RUNTIME_PREFIXES):
            continue  # 运行期路径（gitignored），允许在文档中出现而不存在于克隆
        if not (ROOT / probe).exists():
            report(inline, "内联路径")

    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description="文档链接守护")
    ap.add_argument("--all", action="store_true", help="额外检查 CONTRIBUTING/CHANGELOG/ARCHITECTURE")
    args = ap.parse_args()

    files = md_files(args.all)
    frozen = [f for f in files if is_frozen(f)]
    live = [f for f in files if not is_frozen(f)]
    all_problems: list[str] = []
    for f in live:
        all_problems.extend(check_file(f))

    print("=" * 62)
    print(f"文档链接守护 · 现行 {len(live)} 个 / 归档跳过 {len(frozen)} 个 Markdown")
    print("=" * 62)
    if all_problems:
        print(f"\n❌ 失效引用：{len(all_problems)}\n")
        for p in all_problems:
            print(f"  · {p}")
        print("\n修复：把路径改成文件实际位置（docs/ 结构见 docs/README.md）")
        return 1
    print("\n✅ 全部链接与内联路径有效")
    return 0


if __name__ == "__main__":
    sys.exit(main())
