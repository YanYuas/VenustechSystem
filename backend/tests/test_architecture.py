# ============================================================
# 架构守护（Architecture as Code）— pytest 入口
#
# 为什么只留这一层薄壳：
#   规则本体在 scripts/audit_architecture.py（AST 解析真实 import 图 +
#   领域地图校验）。旧版本文件只有 5 条"文本包含"断言，实测抓不到
#   core 反向依赖 services 这类真实违规（见 2026-10 架构审计）。
#   现在断言唯一事实来源 = 那个脚本，避免两套规则各自漂移。
#
# 除"全量零违规"外，本文件还有一条**负向测试**：临时注入一条 R13 违规
# （service 直连 ORM），断言守护会变红并点名 R13，然后删除探针、恢复绿色。
# 负向测试是必要的 —— 否则规则写错（例如 AST 匹配不到）也会显示"通过"。
#
# 单独运行（不装 pytest 也能跑）：
#     cd backend && python tests/test_architecture.py
#     python scripts/audit_architecture.py
# ============================================================
from __future__ import annotations

import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GUARD = ROOT / "scripts" / "audit_architecture.py"

# R13 探针放在 shared 包（app/services/rules/）里：
#   · R7 命名规则只扫 services/ 顶层，不会误报；
#   · R8 领域归属把 rules/ 视为 shared 包，不会误报；
#   · R13 是 rglob 扫描，能命中 —— 正好隔离出唯一一条 R13 违规。
# 文件名带**进程唯一后缀**：多个 agent 并发跑全量时，固定文件名会让两个
# 进程互相写入/删除对方的探针，导致「注入后守护没红」或「清理后仍未绿」
# 的假失败（2026-10-30 实测过一次）。
R13_PROBE = (
    ROOT / "backend" / "app" / "services" / "rules"
    / f"_r13_probe_{uuid.uuid4().hex[:8]}.py"
)
R13_PROBE_SRC = '''# 临时探针（仅测试期间存在）：故意直连 ORM，验证 R13 会变红
def probe(db):
    return db.scalars("SELECT 1")
'''


def _run_guard() -> subprocess.CompletedProcess:
    assert GUARD.is_file(), f"缺少架构守护脚本: {GUARD}"
    return subprocess.run(
        [sys.executable, str(GUARD)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def test_architecture_guard_passes() -> None:
    """架构分层 / 领域归属 / 根目录契约 / 事务 / 迁移基线 / service 零直连 全部零违规。"""
    proc = _run_guard()
    assert proc.returncode == 0, (
        "架构守护失败（scripts/audit_architecture.py 退出码非 0）：\n"
        + (proc.stdout or "")
        + (proc.stderr or "")
    )


def test_r13_negative_probe_turns_guard_red() -> None:
    """负向测试：注入 service 直连 ORM → 守护必须变红并报 R13；删掉后恢复绿色。

    防什么：R13 的实现如果坏了（AST 没遍历到、豁免范围写错、规则没接进
    main），全量测试仍会显示"架构守护通过" —— 护栏变成装饰。这条用例让
    "规则真的会失败"成为可执行断言。
    """
    proc = _run_with_probe(R13_PROBE, R13_PROBE_SRC)
    output = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode != 0, (
        "注入 service 直连 ORM 后守护仍然通过 → R13 规则失效：\n" + output
    )
    assert "R13-service-no-direct-orm" in output, (
        "守护失败了，但不是 R13 报的（说明探针触发了别的规则，需调整探针）：\n" + output
    )

    # 清理后必须恢复绿色，证明红/绿差异确实来自探针
    proc_after = _run_guard()
    after_output = (proc_after.stdout or "") + (proc_after.stderr or "")
    assert proc_after.returncode == 0, (
        "删除 R13 探针后守护仍未通过"
        "（若本机有其它 agent 正在并发跑架构负向测试，其临时探针可能瞬时存在；"
        "串行复跑即可确认）：\n" + after_output
    )


def _load_guard_module():
    """把守护脚本当模块导入（不执行 main），用于直接断言其内部函数。"""
    import importlib.util

    spec = importlib.util.spec_from_file_location("audit_architecture_under_test", GUARD)
    assert spec and spec.loader, f"无法加载守护脚本: {GUARD}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# R1 探针：service 依赖 api（反向依赖）。放 rules/ shared 包只触发 R1。
# 文件名带 uuid：同一工作树上并行跑多个 pytest（人 + 子智能体）时，
# 固定文件名会互相写/删探针造成假红（2026-10-30 实测）。
R1_PROBE = ROOT / "backend" / "app" / "services" / "rules" / f"_r1_probe_{uuid.uuid4().hex[:8]}.py"
R1_PROBE_SRC = '''# 临时探针（仅测试期间存在）：service 反依赖 api，验证 R1 会变红
from app.api.task import router  # noqa: F401
'''

# R2 探针：core 依赖 services。放 app/core/（shared 包）只触发 R2。
# 同 R1：uuid 文件名防并发互踩。
R2_PROBE = ROOT / "backend" / "app" / "core" / f"_r2_probe_{uuid.uuid4().hex[:8]}.py"
R2_PROBE_SRC = '''# 临时探针（仅测试期间存在）：core 反依赖 service，验证 R2 会变红
from app.services.task_service import TaskService  # noqa: F401
'''


def _run_with_probe(probe: Path, src: str) -> subprocess.CompletedProcess:
    """注入探针 → 跑守护 → **无论成败都清理**，返回守护进程结果。

    刻意不在 helper 里做断言：断言必须出现在测试函数体内，
    否则静态质量审计（audit_test_quality.py）会把用例判成 NO_ASSERT。
    """
    assert not probe.exists(), f"探针文件已存在，先清理: {probe}"
    try:
        probe.write_text(src, encoding="utf-8")
        return _run_guard()
    finally:
        probe.unlink(missing_ok=True)


def test_r1_layer_direction_negative_probe_turns_guard_red() -> None:
    """负向：service 反依赖 api → 必须报 R1。"""
    proc = _run_with_probe(R1_PROBE, R1_PROBE_SRC)
    output = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode != 0, "注入 service→api 依赖后守护仍然通过 → R1 规则失效：\n" + output
    assert "R1-layer-direction" in output, f"守护失败了但不是 R1 报的：\n{output}"
    after = _run_guard()
    assert after.returncode == 0, "删除 R1 探针后守护仍未通过：\n" + (after.stdout or "")


def test_r2_core_isolation_negative_probe_turns_guard_red() -> None:
    """负向：core 反依赖 service → 必须报 R2。

    防的是 2026-10-27 发现的真实缺陷：layer_of_file() 的空转让 R1/R2 长期
    不生效（所有文件被当 root 跳过），`--strict` 恒绿。
    """
    proc = _run_with_probe(R2_PROBE, R2_PROBE_SRC)
    output = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode != 0, "注入 core→service 依赖后守护仍然通过 → R2 规则失效：\n" + output
    assert "R2-core-isolation" in output, f"守护失败了但不是 R2 报的：\n{output}"
    after = _run_guard()
    assert after.returncode == 0, "删除 R2 探针后守护仍未通过：\n" + (after.stdout or "")


def test_layer_classification_is_not_blind() -> None:
    """回归：分层判定必须按真实目录返回层名，而不是一律 root。"""
    guard = _load_guard_module()
    backend = guard.BACKEND
    expected = {
        "app/api/task.py": "api",
        "app/schemas/task.py": "schemas",
        "app/services/task_service.py": "services",
        "app/services/sync/engine.py": "services",
        "app/repositories/base.py": "repositories",
        "app/models/task.py": "models",
        "app/core/logger.py": "core",
        "app/bootstrap/event_handlers.py": "bootstrap",
        "app/main.py": "bootstrap",
        "app/config.py": "root",
        "app/database.py": "root",
    }
    for rel_path, layer in expected.items():
        actual = guard.layer_of_file(backend / rel_path)
        assert actual == layer, f"{rel_path} 被判为 {actual}，期望 {layer}（R1/R2 会空转）"
    assert guard.layer_of_module("app.services.task_service") == "services"
    assert guard.layer_of_module("app.core.logger") == "core"
    assert guard.layer_of_module("app.main") == "bootstrap"


def test_type_checking_imports_are_exempt() -> None:
    """回归：`if TYPE_CHECKING:` 内的类型引用不算运行依赖。

    api 层普遍这样引用 User 类型注解；旧实现把 in_guard 传来传去却不用，
    导致 28 条 api→models 假违规（2026-10-27 实测）。
    """
    guard = _load_guard_module()
    api_file = guard.APP / "api" / "task.py"
    source = api_file.read_text(encoding="utf-8")
    assert "if TYPE_CHECKING:" in source, "回归前提变化：task.py 不再用 TYPE_CHECKING，请调整用例"
    runtime_mods = [mod for mod, _ in guard.iter_runtime_imports(api_file)]
    assert not any(m.startswith("app.models") for m in runtime_mods), (
        "TYPE_CHECKING 内的 models 引用被误判为运行依赖: "
        + ", ".join(m for m in runtime_mods if m.startswith("app.models"))
    )


def test_r14_frontend_layer_negative_probe_turns_guard_red() -> None:
    """负向：kernel 反向依赖 feature → 必须报 R14。

    防的是 R14（ADP-0007 前端分层）写错或没接进 main —— 前端目录搬迁后
    "规则在但没生效"同样属于护栏装饰。
    """
    # uuid 文件名：防并行 pytest 互踩探针（同 R1/R2）
    probe = ROOT / "frontend" / "src" / "kernel" / f"_r14_probe_{uuid.uuid4().hex[:8]}.ts"
    src = "// 临时探针（仅测试期间存在）：kernel 反依赖 feature\nexport const probe = 1\n"
    import_line = "import '@/features/pet'\n"
    assert not probe.exists(), f"探针文件已存在，先清理: {probe}"
    try:
        probe.write_text(import_line + src, encoding="utf-8")
        proc = _run_guard()
        output = (proc.stdout or "") + (proc.stderr or "")
        assert proc.returncode != 0, "注入 kernel→feature 依赖后守护仍然通过 → R14 规则失效：\n" + output
        assert "R14-frontend-layers" in output, f"守护失败了但不是 R14 报的：\n{output}"
    finally:
        probe.unlink(missing_ok=True)
    proc_after = _run_guard()
    assert proc_after.returncode == 0, "删除 R14 探针后守护仍未通过：\n" + (proc_after.stdout or "")


def test_frontend_feature_registry_matches_disk() -> None:
    """回归：features/ 下每个领域包都必须在 domains.json.frontend_features 登记。"""
    import json

    guard = _load_guard_module()
    domains = json.loads(guard.DOMAINS_FILE.read_text(encoding="utf-8"))
    declared = {k for k in domains.get("frontend_features", {}) if not k.startswith("$")}
    features_dir = guard.FRONTEND_SRC / "features"
    on_disk = {p.name for p in features_dir.iterdir() if p.is_dir()} if features_dir.is_dir() else set()
    assert on_disk <= declared, f"未登记领域包: {sorted(on_disk - declared)}（新增 feature 必须先登记 domains.json）"


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        test_architecture_guard_passes()
        test_r13_negative_probe_turns_guard_red()
        test_r1_layer_direction_negative_probe_turns_guard_red()
        test_r2_core_isolation_negative_probe_turns_guard_red()
        test_layer_classification_is_not_blind()
        test_type_checking_imports_are_exempt()
        test_r14_frontend_layer_negative_probe_turns_guard_red()
        test_frontend_feature_registry_matches_disk()
        print("✅ 架构守护通过（含 R1/R2/R13/R14 负向测试 + 分层判定回归）")
        sys.exit(0)
    except AssertionError as e:
        print(f"❌ {e}")
        sys.exit(1)
