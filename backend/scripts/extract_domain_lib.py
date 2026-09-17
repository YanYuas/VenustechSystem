# ============================================================
# DOMAIN_LIB 提取器（S6-1 · 可复现工具）
#
# 为什么必须是脚本而不是手工转录：
#   DOMAIN_LIB 含 13 领域 / 52 能力单元 / **90 条中文长文本任务**，
#   且 90/90 都带「达标标准」。手工转录 90 条描述极易出现错字、漏字
#   与整条遗漏，而且**没有任何办法验证转录是否完整**。
#
#   本脚本用「括号匹配切片 → Node 求值 → JSON → Python 源码」的路径，
#   保证输出 100% 忠实于源头，并用断言锁定完整性。
#
# 用法：
#   python scripts/extract_domain_lib.py [源 app.js 路径] [输出 .py 路径]
#
# 校验断言（与《地球Online内核融入效果评估》附录索引一致）：
#   领域 13 · 能力单元 52 · 任务 90 · 带达标标准 90/90 · 标记重复练习 25
#   任一不符即报错退出，防止"静默少搬了几个领域"。
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
    "app", "services", "rules", "domain_lib.py",
)

# 源头实测基线（来自评估报告，提取结果必须与之逐项吻合）
EXPECT_DOMAINS = 13
EXPECT_UNITS = 52
EXPECT_TASKS = 90
EXPECT_ACCEPTANCE = 90
EXPECT_REPEATABLE = 25

RUFF_LINE_LENGTH = 110  # backend/pyproject.toml [tool.ruff]


# ---------- 1. 从源文件切出 DOMAIN_LIB 字面量 ----------
def slice_domain_lib(src: str) -> str:
    """用括号匹配切出 `const DOMAIN_LIB = [...]` 的数组字面量。

    需要同时跳过字符串与正则字面量 —— 否则正则里的 `/.../` 或字符串里的
    方括号会破坏嵌套计数。
    """
    start = src.index("const DOMAIN_LIB = [")
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


def eval_with_node(snippet: str) -> list[dict]:
    """交给 Node 求值（字面量含 JS 正则，Python 无法直接解析）。"""
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

    tmp = tempfile.mkdtemp(prefix="domainlib_")
    jsf, outf = os.path.join(tmp, "slice.js"), os.path.join(tmp, "out.json")
    js = (
        "const DOMAIN_LIB = " + snippet + ";\n"
        "require('fs').writeFileSync(" + json.dumps(outf) + ","
        " JSON.stringify(DOMAIN_LIB,"
        " (k,v)=> v instanceof RegExp ? ('__RE__'+v.source) : v));\n"
    )
    io.open(jsf, "w", encoding="utf-8").write(js)
    proc = subprocess.run([node, jsf], capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(
            "Node 求值失败：" + proc.stderr.decode("utf-8", "replace")[:600]
        )
    return json.loads(io.open(outf, encoding="utf-8").read())


# ---------- 2. Python 源码生成（遵守 ruff line-length=110）----------
def py_literal(s: str) -> str:
    """生成合法的 Python 字符串字面量（保留中文，不转义为 \\uXXXX）。"""
    return json.dumps(s, ensure_ascii=False)


def split_text(s: str, limit: int) -> list[str]:
    """把长文本切成若干片段，优先在中文标点处断开。

    切分点优先选 `；，、：。` 等，使每个片段读起来仍是完整的短句；
    无标点可切时才硬切（拼接后与原值完全一致，语义无损）。
    """
    out: list[str] = []
    rest = s
    marks = "；，、：。！？;,"
    while len(rest) > limit:
        cut = -1
        for m in marks:
            pos = rest.rfind(m, 0, limit + 1)
            if pos > cut:
                cut = pos
        if cut <= 0:
            cut = limit - 1
        out.append(rest[: cut + 1])
        rest = rest[cut + 1 :]
    out.append(rest)
    return out


def emit_kv(indent: str, key: str, value: str, trailing: str = ",") -> list[str]:
    """生成 `key="..."` 行；超长时在括号内跨行隐式拼接。"""
    lit = py_literal(value)
    if len(indent) + len(key) + 1 + len(lit) + len(trailing) <= RUFF_LINE_LENGTH:
        return [f"{indent}{key}={lit}{trailing}"]

    inner = indent + "    "
    budget = RUFF_LINE_LENGTH - len(inner) - 2  # 两侧引号
    pieces = split_text(value, max(budget, 20))
    lines = [f"{indent}{key}=("]
    for p in pieces:
        lines.append(f"{inner}{py_literal(p)}")
    lines.append(f"{indent}){trailing}")
    return lines


def generate(data: list[dict]) -> str:
    L: list[str] = []
    L.append("# ============================================================")
    L.append("# 领域知识库（S6-1 · 阶段六「外部交付物内核融合」）")
    L.append("#")
    L.append("# 来源：交付物 A《地球Online（大学版）》assets/js/app.js 的 DOMAIN_LIB")
    L.append("#       （源文件 3380 行中的 L1653–L1952）")
    L.append("#")
    L.append("# 生成方式：**脚本提取，非手工转录**")
    L.append("#   python scripts/extract_domain_lib.py")
    L.append("#   路径为「括号匹配切片 → Node 求值 → JSON → Python 源码」，")
    L.append("#   以保证 90 条中文长文本零错漏、且完整性可被断言锁定。")
    L.append("#   **如需扩充或修正领域库，请改本文件并同步更新上面的断言基线。**")
    L.append("#")
    L.append(f"# 规模：{len(data)} 领域 / {EXPECT_UNITS} 能力单元 / {EXPECT_TASKS} 条任务")
    L.append(f"#       其中带「达标标准」{EXPECT_ACCEPTANCE}/{EXPECT_TASKS}（100%）")
    L.append("#       标记「可重复练习」%d 条" % EXPECT_REPEATABLE)
    L.append("#")
    L.append("# 为什么这块值得整体迁入（而不是重写）：")
    L.append("#   每条任务都写了**做到什么程度算完成**（standard），且 90 条无一遗漏。")
    L.append("#   这不是「多练多听」式的泛泛建议，而是可直接执行、且有验收标准的")
    L.append("#   真实内容投入 —— 也是交付物 A 里最不可替代的资产。")
    L.append("#")
    L.append("# 字段命名规范化（括号内为源头字段，便于对照与更新）：")
    L.append("#   TaskDef.task        做什么        (do)")
    L.append("#   TaskDef.duration    预估时长      (time)")
    L.append("#   TaskDef.acceptance  达标标准      (standard)")
    L.append("#   TaskDef.repeatable  可重复练习    (repeat)")
    L.append("#   TaskDef.beginner_only 零基础专用  (beginnerOnly)")
    L.append("#")
    L.append("# 关于 beginner_only 的现状（已核对，**不是遗漏，请勿当 bug 修**）：")
    L.append("#   源数据把该标记标在**任务**层级，而源实现的 buildUnitDefs() 读取的是")
    L.append("#   **单元**层级 `u.beginnerOnly` —— 读到的恒为 undefined，即该过滤")
    L.append("#   **从未生效过**。本模块忠实保留数据，但**刻意不实现这个过滤**：")
    L.append("#   源作者的本意到底是「过滤整个单元」还是「过滤单条任务」，无法从")
    L.append("#   代码推断，贸然实现等于发明一种未经证实的行为。")
    L.append("#   待有明确产品输入后再决定是否启用（届时需同时补单元级字段）。")
    L.append("# ============================================================")
    L.append("from __future__ import annotations")
    L.append("")
    L.append("from dataclasses import dataclass")
    L.append("")
    L.append("")
    L.append("@dataclass(frozen=True)")
    L.append("class TaskDef:")
    L.append('    """单条学习任务（四要素见文件头字段对照）。"""')
    L.append("")
    L.append("    task: str")
    L.append("    duration: str")
    L.append("    acceptance: str")
    L.append("    repeatable: bool = False")
    L.append("    beginner_only: bool = False")
    L.append("")
    L.append("")
    L.append("@dataclass(frozen=True)")
    L.append("class UnitDef:")
    L.append('    """能力单元：围绕同一能力点的一组任务。"""')
    L.append("")
    L.append("    name: str")
    L.append("    tasks: tuple[TaskDef, ...]")
    L.append("")
    L.append("")
    L.append("@dataclass(frozen=True)")
    L.append("class DomainDef:")
    L.append('    """学习领域：含匹配模式（正则源码）与最终验证任务。"""')
    L.append("")
    L.append("    key: str")
    L.append("    name: str")
    L.append("    patterns: tuple[str, ...]")
    L.append("    verify_task: str")
    L.append("    units: tuple[UnitDef, ...]")
    L.append("")
    L.append("")
    L.append("# 匹配用正则在引擎侧统一以 re.IGNORECASE 编译，")
    L.append("# 对应源实现「先 toLowerCase() 再 test()」的语义。")
    L.append("DOMAIN_LIB: tuple[DomainDef, ...] = (")
    for d in data:
        L.append("    DomainDef(")
        L.append(f"        key={py_literal(d['key'])},")
        L.append(f"        name={py_literal(d['name'])},")
        # 源字段形如 "__RE__雅思|ielts"，去掉标记即为正则源码
        pats = [(p[6:] if p.startswith("__RE__") else p) for p in d["patterns"]]
        if len(pats) == 1:
            L.append(f"        patterns=({py_literal(pats[0])},),")
        else:
            L.append("        patterns=(")
            for p in pats:
                L.append(f"            {py_literal(p)},")
            L.append("        ),")
        L.extend(emit_kv("        ", "verify_task", d["verifyTask"]))
        L.append("        units=(")
        for u in d["units"]:
            L.append("            UnitDef(")
            L.extend(emit_kv("                ", "name", u["name"]))
            L.append("                tasks=(")
            for t in u["tasks"]:
                L.append("                    TaskDef(")
                L.extend(emit_kv("                        ", "task", t["do"]))
                L.extend(emit_kv("                        ", "duration", t.get("time", "")))
                L.extend(emit_kv("                        ", "acceptance", t.get("standard", "")))
                if t.get("repeat"):
                    L.append("                        repeatable=True,")
                if t.get("beginnerOnly"):
                    L.append("                        beginner_only=True,")
                L.append("                    ),")
            L.append("                ),")
            L.append("            ),")
        L.append("        ),")
        L.append("    ),")
    L.append(")")
    L.append("")
    L.append("")
    L.append("__all__ = [\"DOMAIN_LIB\", \"DomainDef\", \"TaskDef\", \"UnitDef\"]")
    L.append("")
    return "\n".join(L)


def main() -> int:
    src_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SRC
    out_path = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_OUT

    if not os.path.exists(src_path):
        print(f"源文件不存在：{src_path}", file=sys.stderr)
        return 2

    src = io.open(src_path, encoding="utf-8").read()
    data = eval_with_node(slice_domain_lib(src))

    domains = len(data)
    units = sum(len(d["units"]) for d in data)
    tasks = sum(len(u["tasks"]) for d in data for u in d["units"])
    acceptance = sum(
        1 for d in data for u in d["units"] for t in u["tasks"] if t.get("standard")
    )
    repeatable = sum(
        1 for d in data for u in d["units"] for t in u["tasks"] if t.get("repeat")
    )
    beginner_only = sum(
        1
        for d in data
        for u in d["units"]
        for t in u["tasks"]
        if t.get("beginnerOnly")
    )

    print("提取结果：领域 %d / 单元 %d / 任务 %d" % (domains, units, tasks))
    print("  带达标标准 %d · 标记重复练习 %d · 标记零基础专用 %d"
          % (acceptance, repeatable, beginner_only))
    print("  领域：%s" % ", ".join(d["name"] for d in data))

    checks = [
        ("领域数", domains, EXPECT_DOMAINS),
        ("能力单元数", units, EXPECT_UNITS),
        ("任务数", tasks, EXPECT_TASKS),
        ("带达标标准数", acceptance, EXPECT_ACCEPTANCE),
        ("可重复练习数", repeatable, EXPECT_REPEATABLE),
    ]
    bad = [(n, got, exp) for n, got, exp in checks if got != exp]
    if bad:
        print("\n!! 完整性校验失败（与评估报告基线不符）：", file=sys.stderr)
        for n, got, exp in bad:
            print("   %s：实得 %d，期望 %d" % (n, got, exp), file=sys.stderr)
        return 1
    print("\n✅ 完整性校验通过（与《地球Online内核融入效果评估》附录基线逐项一致）")

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    io.open(out_path, "w", encoding="utf-8", newline="\n").write(generate(data))
    print("已生成：%s" % out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
