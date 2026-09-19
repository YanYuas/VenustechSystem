#!/usr/bin/env python
"""设计引用存在性审计（可执行断言）：CSS 令牌 + 图标名。

背景：组件里写 `var(--text-tertiary)` 这类**不存在的令牌**时，CSS 变量解析
失败 → 该属性静默失效（不报错、不提示，只是样式没生效）。本轮就踩到了
（--text-tertiary / --surface / --text-1 等）。设计令牌体系已有"组件文件内
`#` 零命中"的审计，但**没有**"令牌必须存在"的审计 —— 本脚本补上这一环。

判定：
  used     = 源码里 var(--x) 的 x
  defined  = src/styles/*.scss 的 `--x:` 声明
             ∪ 内联注入（:style="{ '--x': ... }" / style.setProperty('--x')）
  missing  = used - defined

基线：存量未定义令牌（历史遗留，分布在各模块）记入 BASELINE。
**新增**未定义令牌会让审计失败；存量只允许减少，修一个就把基线下调一个。

用法：
  python scripts/audit_tokens.py           # 审计（超过基线即失败）
  python scripts/audit_tokens.py --list    # 列出全部缺失明细
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# 自适应定位前端根：脚本可能放在 <repo>/scripts 或 <repo>/frontend/scripts
_here = Path(__file__).resolve().parent
_candidates = [_here.parent, _here.parent.parent / "frontend", _here.parent.parent]
FRONTEND = next(
    (c for c in _candidates if (c / "src" / "styles" / "variables.scss").exists()),
    _here.parent,
)
SRC = FRONTEND / "src"

# 存量未定义令牌基线（历史遗留）。只能降，不能升。
# 新增功能引入了新的未定义令牌 → 审计失败，必须改成已存在的令牌或补定义。
BASELINE = 0

# 允许豁免的令牌：运行期由 JS 计算或第三方注入，静态扫描无法看到定义。
# 每一条都必须写明豁免理由。
ALLOWLIST: dict[str, str] = {
    "--el-*": "Element Plus 自注入（如 --el-color-primary），由 element-plus.scss 反向消费",
}

USED_RE = re.compile(r"var\(\s*(--[a-zA-Z0-9][a-zA-Z0-9-]*)")
# 图标：只统计静态 name="x"／name='x'；:name="expr" 是动态绑定（运行时才知道），不计
ICON_USED_RE = re.compile(r"""<AppIcon\b[^>]*?(?<![:\w])name=(["'])([a-z][a-z0-9-]*)\1""")
ICON_DEF_RE = re.compile(r"^\s+'?([a-z][a-z0-9-]*)'?\s*:", re.MULTILINE)
DEF_RE = re.compile(r"^\s*(--[a-zA-Z0-9][a-zA-Z0-9-]*)\s*:", re.MULTILINE)
# 内联注入：:style="{ '--x': v }" / .setProperty('--x', v) / style['--x']
INLINE_RE = re.compile(
    r"""['"](--[a-zA-Z0-9][a-zA-Z0-9-]*)['"]\s*:"""
    r"""|setProperty\(\s*['"](--[a-zA-Z0-9][a-zA-Z0-9-]*)['"]"""
    r"""|style\[\s*['"](--[a-zA-Z0-9][a-zA-Z0-9-]*)['"]"""
)

SCAN_EXT = {".vue", ".scss", ".css", ".ts", ".js"}


def _walk(d: Path):
    for entry in sorted(d.iterdir()):
        if entry.name in {"node_modules", "dist", ".git"}:
            continue
        if entry.is_dir():
            yield from _walk(entry)
        elif entry.suffix in SCAN_EXT:
            yield entry


def _is_allowlisted(name: str) -> bool:
    if name in ALLOWLIST:
        return True
    return any(
        pat.endswith("*") and name.startswith(pat[:-1]) for pat in ALLOWLIST if pat.endswith("*")
    )


def collect() -> tuple[dict[str, set[str]], set[str]]:
    used: dict[str, set[str]] = {}
    defined: set[str] = set()

    for f in _walk(SRC):
        text = f.read_text(encoding="utf-8", errors="replace")
        rel = f.relative_to(FRONTEND).as_posix()
        for m in USED_RE.finditer(text):
            used.setdefault(m.group(1), set()).add(rel)
        # 定义：任何 scss/css 里的 --x: 声明
        if f.suffix in {".scss", ".css"}:
            defined.update(m.group(1) for m in DEF_RE.finditer(text))
        # 内联注入（仅 JS/TS/Vue 里有意义）
        if f.suffix in {".vue", ".ts", ".js"}:
            for m in INLINE_RE.finditer(text):
                name = m.group(1) or m.group(2) or m.group(3)
                if name:
                    defined.add(name)

    return used, defined


def collect_icons() -> tuple[dict[str, set[str]], set[str]]:
    """图标名：定义来自 AppIcon.vue 的 paths 映射，使用来自静态 name="x"。"""
    used: dict[str, set[str]] = {}
    defined: set[str] = set()
    icon_file = FRONTEND / "src" / "components" / "common" / "AppIcon.vue"
    if icon_file.exists():
        text = icon_file.read_text(encoding="utf-8")
        block = text[text.index("paths") : text.index("}", text.index("paths"))]
        defined = set(m.group(1) for m in ICON_DEF_RE.finditer(block))
    for f in _walk(SRC):
        if f.suffix != ".vue":
            continue
        rel = f.relative_to(FRONTEND).as_posix()
        for m in ICON_USED_RE.finditer(f.read_text(encoding="utf-8", errors="replace")):
            used.setdefault(m.group(2), set()).add(rel)
    return used, defined


def main() -> int:
    show_list = "--list" in sys.argv
    used, defined = collect()
    missing = {
        name: files
        for name, files in used.items()
        if name not in defined and not _is_allowlisted(name)
    }

    print(f"[令牌审计] 使用中 {len(used)} 个 · 已定义 {len(defined)} 个 · 未定义 {len(missing)} 个")

    if show_list or len(missing) > BASELINE:
        for name in sorted(missing):
            files = sorted(missing[name])
            head = ", ".join(files[:3])
            more = f" 等 {len(files)} 文件" if len(files) > 3 else ""
            print(f"    {name} -> {head}{more}")

    # ---------- 图标存在性（同一类失败：名字不存在 → 静默渲染为空） ----------
    ic_used, ic_defined = collect_icons()
    ic_missing = {n: f for n, f in ic_used.items() if n not in ic_defined}

    print(f"[图标审计] 使用中 {len(ic_used)} 个 · 已定义 {len(ic_defined)} 个 · 未定义 {len(ic_missing)} 个")
    if show_list or ic_missing:
        for name in sorted(ic_missing):
            print(f"    {name} -> {', '.join(sorted(ic_missing[name])[:3])}")

    failed = False
    if len(missing) > BASELINE:
        print(f"\n[引用审计] ❌ 未定义令牌 {len(missing)} 个 > 基线 {BASELINE}")
        print("      → 请改用 src/styles/variables.scss 里已存在的令牌，或先在 variables.scss 补定义")
        failed = True
    if ic_missing:
        print(f"\n[引用审计] ❌ 未定义图标 {len(ic_missing)} 个")
        print("      → 请在 src/components/common/AppIcon.vue 的 paths 里补上，或改用已存在的图标名")
        failed = True

    if failed:
        return 1

    print(f"[引用审计] ✅ 未定义令牌 {len(missing)} 个（基线 {BASELINE}）· 未定义图标 0 个")
    return 0


if __name__ == "__main__":
    sys.exit(main())
