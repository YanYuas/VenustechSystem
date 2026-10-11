# ============================================================
# 测试质量审计（2026-10-11 新增，纳入 check_all.py 第 10 项）
#
# 为什么必须有这个脚本：
#   用例数量（694 条）本身不是质量指标。本项目历史上出现过
#   「永真断言 or True 回归后还在代码里」——考察报告称已删除，
#   实际仍在，谁都没发现，因为**没有东西会因此变红**。
#   一条铁律如果不能变成退出码非 0 的检查，它一定会被再犯。
#
# 审计 5 类「一定有问题」的写法（基线 0，命中即失败）：
#   1. NO_ASSERT    测试函数里既没有 assert 也没有 pytest.raises/warns
#                   （只是"调用了代码"，不构成测试）
#   2. TAUTOLOGY    永真断言：or True / assert True / assert 1 == 1 /
#                   assert len(x) >= 0
#   3. BROAD_RAISES pytest.raises(Exception|BaseException) —— 连
#                   "函数根本没跑通、抛了 TypeError"都会算通过
#   4. SWALLOW      except Exception: pass（把失败吞掉）
#   5. EMPTY_BODY   函数体只有 pass / 只有 docstring
#
# 另外输出「断言密度」表（asserts / test）作为参考信息 —— 它**不**判失败：
#   密度低不等于有问题（架构守护类用例天然 1:1），密度高也不等于有效。
#   仅当某文件比值 < 1.0 时打印提示，供人工复核。
#
# 用法：python scripts/audit_test_quality.py
# ============================================================
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = ROOT / "backend" / "tests"

TAUTOLOGY_PATTERNS = [
    (re.compile(r"\bor\s+True\b"), "or True 永真"),
    (re.compile(r"\bassert\s+True\b"), "assert True"),
    (re.compile(r"\bassert\s+1\s*==\s*1\b"), "assert 1 == 1"),
    (re.compile(r"\bassert\s+len\([^)]*\)\s*>=\s*0\b"), "assert len(...) >= 0 恒成立"),
    (re.compile(r"\bassert\s+0\s*==\s*0\b"), "assert 0 == 0"),
]

BROAD_RAISES = re.compile(r"pytest\.raises\(\s*(Exception|BaseException)\s*\)")
SWALLOW = re.compile(r"except\s+(Exception|BaseException)\s*:\s*\n\s*pass\b")


def _iter_test_functions(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
            yield node


def _is_empty_body(fn: ast.AST) -> bool:
    """函数体除 docstring / pass 外没有实质语句。"""
    body = [n for n in fn.body]
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
            and isinstance(body[0].value.value, str):
        body = body[1:]
    body = [n for n in body if not (isinstance(n, ast.Pass))]
    return len(body) == 0


def audit_file(path: Path) -> tuple[list[str], int, int]:
    """返回 (问题列表, 用例数, 断言数)。"""
    violations: list[str] = []
    try:
        src = path.read_text(encoding="utf-8")
        tree = ast.parse(src)
    except SyntaxError as exc:
        return [f"{path.name}: 语法错误，无法解析（{exc}）"], 0, 0

    n_tests = 0
    n_asserts = 0
    for fn in _iter_test_functions(tree):
        n_tests += 1
        asserts = [n for n in ast.walk(fn) if isinstance(n, ast.Assert)]
        n_asserts += len(asserts)
        segment = ast.get_source_segment(src, fn) or ""
        loc = f"{path.name}::{fn.name}"

        if _is_empty_body(fn):
            violations.append(f"[EMPTY_BODY] {loc}: 函数体为空（只有 pass/文档字符串）")
            continue

        has_raises = "pytest.raises" in segment or "pytest.warns" in segment
        if not asserts and not has_raises:
            violations.append(f"[NO_ASSERT] {loc}: 无断言、无 pytest.raises（只是执行了代码）")
        for pattern, label in TAUTOLOGY_PATTERNS:
            if pattern.search(segment):
                violations.append(f"[TAUTOLOGY] {loc}: {label}")
        if BROAD_RAISES.search(segment):
            violations.append(
                f"[BROAD_RAISES] {loc}: pytest.raises(Exception) 过宽，无法区分真实异常类型"
            )
        if SWALLOW.search(segment):
            violations.append(f"[SWALLOW] {loc}: except Exception: pass 把失败吞掉了")

    return violations, n_tests, n_asserts


def main() -> int:
    print("=" * 62)
    print("▶ 测试质量审计（低价值断言 / 永真断言 / 宽泛异常）")
    print("=" * 62)
    print(f"  扫描目录: {TESTS_DIR}")

    files = sorted(TESTS_DIR.glob("test_*.py"))
    if not files:
        print(f"❌ 未找到测试文件: {TESTS_DIR}")
        return 1

    all_violations: list[str] = []
    rows: list[tuple[str, int, int, float]] = []
    for path in files:
        violations, n_tests, n_asserts = audit_file(path)
        all_violations.extend(violations)
        ratio = (n_asserts / n_tests) if n_tests else 0.0
        rows.append((path.name, n_tests, n_asserts, ratio))

    total_tests = sum(r[1] for r in rows)
    total_asserts = sum(r[2] for r in rows)
    print(f"\n  文件 {len(files)} 个 / 用例 {total_tests} 条 / 断言 {total_asserts} 处"
          f"（平均 {total_asserts / total_tests:.2f} 处/条）")

    # 断言密度仅作信息输出（低密度≠有问题），< 1.0 才提示复核
    low = [r for r in rows if r[3] < 1.0]
    if low:
        print("\n  断言密度偏低（< 1.0，建议人工复核，不判失败）：")
        for name, t, a, ratio in low:
            print(f"    {name:44s} tests={t} asserts={a} ratio={ratio}")

    if all_violations:
        print(f"\n❌ 发现 {len(all_violations)} 处低价值/无效写法：")
        for v in all_violations:
            print(f"   {v}")
        print("\n（这些模式会让用例在缺陷存在时依然全绿 —— 必须修）")
        return 1

    print("\n✅ 未发现永真断言 / 无断言用例 / 宽泛异常 / 吞异常写法")
    return 0


if __name__ == "__main__":
    sys.exit(main())
