# ============================================================
# SKILL_CATS 提取器（S6-2 · 可复现工具）
#
# 与 extract_domain_lib.py 同一套路：源数据是 JS 字面量。
# 22 个分类 × 约 164 个关键词，手工转录极易错漏，且**无法验证完整性**；
# 脚本化后可从源头重放，并用断言锁定规模。
#
# 用法：
#   python scripts/extract_skill_cats.py [源 app.js 路径] [输出 .py 路径]
#
# 校验：分类数与关键词总数（后者只打印，源注释声称"30个"但实测为 22，
#       故以实测为准并在此说明，避免后来者被注释误导）
# ============================================================
from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

DEFAULT_SRC = (
    r"C:/Users/21722/WorkBuddy/2026-09-15-20-56-14/"
    r"earth-online-university/assets/js/app.js"
)
DEFAULT_OUT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "app", "services", "rules", "skill_cats.py",
)

# 实测基线：源注释写的是"（30个，自动识别 + 等级累计）"，但实际只有 22 条。
# 以实测为准 —— 注释与数据不一致时，数据才是事实。
EXPECT_CATS = 22

RUFF_LINE_LENGTH = 110


def slice_array(src: str, marker: str) -> str:
    """切出 `const <marker> = [...]` 的数组字面量（跳过字符串与正则）。"""
    start = src.index(f"const {marker} = [")
    i = src.index("[", start)
    depth, j, quote, esc, in_re = 0, i, "", False, False
    while j < len(src):
        ch = src[j]
        if quote:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == quote:
                quote = ""
        elif in_re:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == "/":
                in_re = False
        else:
            if ch in "'\"`":
                quote = ch
            elif ch == "/" and j > 0 and src[j - 1] in "(,=[ \n":
                in_re = True
            elif ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    break
        j += 1
    return src[i : j + 1]


def eval_with_node(snippet: str, var: str) -> list[dict]:
    node = shutil.which("node")
    for cand in (
        r"C:/Users/21722/.workbuddy/binaries/node/versions/22.22.2-3/node.exe",
        node,
    ):
        if cand and os.path.exists(cand):
            node = cand
            break
    if not node:
        raise RuntimeError("找不到 node，无法求值 JS 字面量")

    tmp = tempfile.mkdtemp(prefix="skillcats_")
    jsf = os.path.join(tmp, "slice.js")
    outf = os.path.join(tmp, "out.json")
    js = (
        f"const {var} = " + snippet + ";\n"
        "require('fs').writeFileSync(" + json.dumps(outf) + ","
        f" JSON.stringify({var}, (k,v)=> v instanceof RegExp ? ('__RE__'+v.source) : v));\n"
    )
    io.open(jsf, "w", encoding="utf-8").write(js)
    proc = subprocess.run([node, jsf], capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError("Node 求值失败：" + proc.stderr.decode("utf-8", "replace")[:600])
    return json.loads(io.open(outf, encoding="utf-8").read())


def py_literal(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def generate(cats: list[dict]) -> str:
    total_kw = sum(len(c["kws"]) for c in cats)
    L: list[str] = []
    L.append("# ============================================================")
    L.append("# 技能分类表（S6-2 · 成长体系之技能树）")
    L.append("#")
    L.append("# 来源：交付物 A《地球Online（大学版）》assets/js/app.js 的 SKILL_CATS")
    L.append("#       （源文件 L1094–L1117）")
    L.append("#")
    L.append("# 生成方式：**脚本提取，非手工转录**")
    L.append(f"#   python scripts/extract_skill_cats.py")
    L.append("#   如需增删分类或关键词，改本文件即可（引擎侧无需改动）。")
    L.append("#")
    L.append(f"# 规模：{len(cats)} 个分类 / {total_kw} 个关键词（实测）")
    L.append("#")
    L.append("# 与源注释的差异（以实测为准）")
    L.append('#   源注释写的是「技能分类（30个，自动识别 + 等级累计）」，')
    L.append(f"#   但实际只有 {len(cats)} 条。注释与数据不一致时以数据为准 ——")
    L.append("#   本文件由提取器生成并带规模断言，不会被注释误导。")
    L.append("#")
    L.append("# 已知局限（需后续处理，勿当 bug 修）")
    L.append("#   分类偏建筑/校园场景（含「建筑建造」及 sketchup / rhino / 评图 等关键词），")
    L.append("#   与启明星「自由职业者 / 创业者 / 开发者」画像不完全匹配。")
    L.append("#   本表是纯数据，**扩容不需要改任何代码**，故先原样迁入不缩水。")
    L.append("# ============================================================")
    L.append("from __future__ import annotations")
    L.append("")
    L.append("from dataclasses import dataclass")
    L.append("")
    L.append("")
    L.append("@dataclass(frozen=True)")
    L.append("class SkillCat:")
    L.append('    """技能分类：id 稳定标识、name 展示名、kws 关键词（用于自动归类）。"""')
    L.append("")
    L.append("    id: str")
    L.append("    name: str")
    L.append("    kws: tuple[str, ...]")
    L.append("")
    L.append("")
    L.append("SKILL_CATS: tuple[SkillCat, ...] = (")
    for c in cats:
        L.append("    SkillCat(")
        L.append(f"        id={py_literal(c['id'])},")
        L.append(f"        name={py_literal(c['name'])},")
        kws = [py_literal(k) for k in c["kws"]]
        one = "        kws=(" + ", ".join(kws) + ",),"
        if len(one) <= RUFF_LINE_LENGTH:
            L.append(one)
        else:
            L.append("        kws=(")
            line = "            "
            for kw in kws:
                if len(line) + len(kw) + 3 > RUFF_LINE_LENGTH:
                    L.append(line.rstrip())
                    line = "            "
                line += kw + ", "
            if line.strip():
                L.append(line.rstrip())
            L.append("        ),")
        L.append("    ),")
    L.append(")")
    L.append("")
    L.append("")
    L.append("SKILL_CAT_BY_ID: dict[str, SkillCat] = {c.id: c for c in SKILL_CATS}")
    L.append("")
    L.append("")
    L.append('__all__ = ["SKILL_CATS", "SKILL_CAT_BY_ID", "SkillCat"]')
    L.append("")
    return "\n".join(L)


def main() -> int:
    src_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SRC
    out_path = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_OUT

    if not os.path.exists(src_path):
        print(f"源文件不存在：{src_path}", file=sys.stderr)
        return 2

    src = io.open(src_path, encoding="utf-8").read()
    cats = eval_with_node(slice_array(src, "SKILL_CATS"), "SKILL_CATS")

    total_kw = sum(len(c["kws"]) for c in cats)
    ids = [c["id"] for c in cats]
    print(f"提取结果：{len(cats)} 个分类 / {total_kw} 个关键词")
    print("  分类：%s" % "、".join(c["name"] for c in cats))

    if len(cats) != EXPECT_CATS:
        print(f"\n!! 校验失败：期望 {EXPECT_CATS} 个分类，实得 {len(cats)}", file=sys.stderr)
        return 1
    if len(set(ids)) != len(ids):
        dup = [i for i in ids if ids.count(i) > 1]
        print(f"\n!! 分类 id 重复：{sorted(set(dup))}", file=sys.stderr)
        return 1
    print("\n✅ 校验通过（分类数与 id 唯一性）")

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    io.open(out_path, "w", encoding="utf-8", newline="\n").write(generate(cats))
    print(f"已生成：{out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
