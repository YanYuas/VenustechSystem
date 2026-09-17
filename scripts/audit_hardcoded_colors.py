# ============================================================
# 硬编码颜色审计（设计令牌合规）
#
# 项目硬约束（frontend/src/styles/variables.scss 头部）：
#   「全库组件只出现以下 token，组件文件内 grep '#' 零命中」
#
# 实测（2026-09-15）：约束**大范围未落实** —— 16 个组件里共 171 处颜色字面量。
# 本脚本把它变成可测量的债务台账，便于逐文件递减，而不是靠人眼记忆。
#
# 用法（在仓库根目录）：
#   python scripts/audit_hardcoded_colors.py            # 列出明细
#   python scripts/audit_hardcoded_colors.py --max 171  # 超过阈值则退出码 1（可接 CI 棘轮）
#
# 注意：会排除 SVG 引用（url(#id) / href="#id"），它们不是颜色 —— 不排除会把
# DesktopPet.vue 的 47 处误报成颜色违规（实际多为渐变 id）。
# ============================================================
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "frontend" / "src"

# 颜色字面量的两种上下文：CSS 属性值 / SVG 属性
CSS_RE = re.compile(r"[: ](#[0-9a-fA-F]{3,8})\b")
ATTR_RE = re.compile(r'="(#[0-9a-fA-F]{3,8})"')
# 需要排除的 SVG 引用（非颜色）
REF_RE = re.compile(r'url\(#[^)]*\)|href="#[^"]*"')


def scan() -> tuple[Counter, Counter, list[str]]:
    per_file: Counter = Counter()
    palette: Counter = Counter()
    details: list[str] = []

    for f in sorted(SRC.rglob("*.vue")):
        text = f.read_text(encoding="utf-8", errors="replace")
        hits: list[str] = []
        for raw_line in text.splitlines():
            line = REF_RE.sub("", raw_line)  # 先剔除 SVG 引用
            found = CSS_RE.findall(line) + ATTR_RE.findall(line)
            if found:
                hits.extend(found)
                for h in found:
                    palette[h.lower()] += 1
        if hits:
            rel = str(f.relative_to(SRC)).replace("\\", "/")
            per_file[rel] = len(hits)
            details.extend(f"{rel}:{h}" for h in hits)

    return per_file, palette, details


def main() -> int:
    ap = argparse.ArgumentParser(description="硬编码颜色审计")
    ap.add_argument("--max", type=int, default=None,
                    help="允许的最大硬编码数；超过则退出码 1")
    args = ap.parse_args()

    per_file, palette, _ = scan()
    total = sum(per_file.values())

    print("=" * 66)
    print("硬编码颜色审计（约束：组件内颜色应全部走 variables.scss 令牌）")
    print("=" * 66)
    print(f"命中文件 {len(per_file)} 个，合计 {total} 处")
    print("-" * 66)
    for name, n in per_file.most_common():
        bar = "█" * min(40, n)
        print(f"  {n:>4}  {name:<44}{bar}")

    print("-" * 66)
    print(f"出现最多的颜色（TOP 12，共 {len(palette)} 种不同色值）：")
    for color, n in palette.most_common(12):
        print(f"  {color:<12}{n:>4} 次")

    print()
    print("处理建议：")
    print("  1) 能对应现有令牌的，直接替换为 var(--xxx) —— 收益最大、零风险。")
    print("  2) 令牌里没有的色值，先判断是否该进 variables.scss 成为新令牌；")
    print("     若只是局部装饰，考虑用 color-mix() 从现有令牌派生。")
    print("  3) 数据驱动的颜色（如用户自选项目色）属合理例外，")
    print("     建议集中到 constants 里作为调色板常量，组件内不写字面量。")
    print("  逐文件递减，可用 --max N 设棘轮阈值防止反弹。")

    if args.max is not None and total > args.max:
        print(f"\n❌ 超过阈值 {args.max}（当前 {total}）")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
