#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""架构守护（Architecture as Code）

把《docs/architecture/ARCHITECTURE.md》里的分层规则变成可执行断言。
旧的 tests/test_architecture.py 只有 5 条"文本包含"规则，抓不到真实违规
（2026-10 审计：core 曾反向依赖 services，文本规则仍全绿）。本脚本改用
**AST 解析真实 import 图**，并按 docs/architecture/domains.json 校验领域归属。

检查项
  R1  分层依赖方向（只算运行时 import，TYPE_CHECKING 内的类型引用豁免）
  R2  core 隔离（不得依赖 services / repositories / api / schemas）
  R3  services 不得依赖 FastAPI（保持与框架解耦，可单测）
  R4  api 不得直接创建 Session（SessionLocal / create_engine）
  R5  每个 api 模块都必须在 api/__init__.py 注册到 /api/v1
  R6  每个 models 模块都必须在 models/__init__.py 导入（否则不建表）
  R7  命名规范：services/*_service.py、repositories/*_repo.py
  R8  领域归属完整：每个文件属于已登记模块；每个登记模块真实存在
  R9  根目录契约：根目录只允许 domains.json.root_contract 列出的条目
  R10 前端 views 不得横向 import 另一个 view 的具体实现
  R11 repository 只 flush，不得 commit（提交权在 service / get_db）
  R12 迁移基线 0001 必须冻结为显式 DDL（不得 create_all/drop_all）
  R13 service 零直连 ORM（查询/写入一律经 repository）
  R14 前端 kernel/shared/features 分层（ADR-0007）：kernel 不依赖上层、
      shared 只依赖 kernel、feature 只依赖 kernel/shared/自身，跨 feature 只走 index

已知技术债
  见 scripts/architecture_baseline.json。基线内的违规降级为 WARN（不失败），
  但**新增**同类违规立即失败；修掉后请从基线删除，防止债务只增不减。

用法
  python scripts/audit_architecture.py          # 人类可读
  python scripts/audit_architecture.py --strict # 基线违规也算失败（CI 收口用）
退出码：0 通过；1 有未登记违规
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
APP = BACKEND / "app"
FRONTEND_SRC = ROOT / "frontend" / "src"
DOMAINS_FILE = ROOT / "docs" / "architecture" / "domains.json"
BASELINE_FILE = ROOT / "scripts" / "architecture_baseline.json"

# ---------------------------------------------------------------- 规则表
# 每层的"允许依赖"集合。root/bootstrap 是组合根，拥有装配特权。
ALL_LAYERS = {"api", "schemas", "services", "repositories", "models", "core", "root", "bootstrap", "plugins_builtin"}
LAYER_RULES: dict[str, set[str]] = {
    "api": {"api", "schemas", "services", "core", "root"},
    "schemas": {"schemas", "core", "root"},
    "services": {"services", "repositories", "models", "schemas", "core", "root"},
    "repositories": {"repositories", "models", "core", "root"},
    "models": {"models", "core"},
    # core 是最底层基础设施：只允许依赖自身与 root 级基础设施（config/database/
    # migrate/migration_helpers）。**不得依赖 models** —— D-07 把同步领域逻辑
    # 下沉到 services/sync 后，core 已 0 依赖 models；保留这条禁令防止回潮。
    "core": {"core", "root"},
    "root": ALL_LAYERS,
    "bootstrap": ALL_LAYERS,
    "plugins_builtin": ALL_LAYERS,
}
# 组合根例外：这两个文件可以跨层（数据库会话、用户依赖装配）
COMPOSITION_ROOT_FILES = {"app/api/deps.py", "app/api/__init__.py", "app/main.py"}

errors: list[tuple[str, str, str]] = []   # (rule, detail, where)
warns: list[tuple[str, str, str]] = []
checked = 0


def err(rule: str, detail: str, where: str = "") -> None:
    errors.append((rule, detail, where))


def warn(rule: str, detail: str, where: str = "") -> None:
    warns.append((rule, detail, where))


def rel(p: Path) -> str:
    return p.relative_to(ROOT).as_posix()


# ---------------------------------------------------------------- AST 工具
def iter_runtime_imports(path: Path) -> list[tuple[str, int]]:
    """返回 [(import 的模块名, 行号)]，排除 `if TYPE_CHECKING:` 分支。

    为什么必须排除：api 层合法地用 TYPE_CHECKING 引用 User 类型注解，
    这是零运行时开销的好实践，不应被判为"直接依赖 models"。
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as e:  # 语法错误的文件不参与依赖分析，但必须报出
        err("PARSE", f"无法解析: {e}", rel(path))
        return []

    found: list[tuple[str, int]] = []

    def is_type_checking(test: ast.expr) -> bool:
        if isinstance(test, ast.Name):
            return test.id == "TYPE_CHECKING"
        if isinstance(test, ast.Attribute):
            return test.attr == "TYPE_CHECKING"
        return False

    def visit(node: ast.AST, in_guard: bool = False) -> None:
        if isinstance(node, ast.If):
            guard = is_type_checking(node.test)
            for child in node.body:
                visit(child, in_guard or guard)
            for child in node.orelse:  # `if not TYPE_CHECKING:` 的 else 是真运行时代码
                visit(child, in_guard)
            return
        # 关键：TYPE_CHECKING 块内是**类型注解**，零运行时开销，不算运行依赖。
        # 旧实现把 in_guard 一路传下去却从不使用，导致 api 层合法的
        # `if TYPE_CHECKING: from app.models.user import User`
        # 被误报成运行时依赖（R1 假红）。
        if not in_guard:
            if isinstance(node, ast.Import):
                for a in node.names:
                    if a.name.startswith("app"):
                        found.append(("app" + a.name[3:], node.lineno))
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                if node.level:
                    # 相对 import：按文件位置还原成 app.xxx
                    base = path.relative_to(BACKEND).with_suffix("").parts
                    anchor = list(base[: len(base) - node.level])
                    mod = ".".join(anchor + ([mod] if mod else []))
                if mod == "app" or mod.startswith("app."):
                    found.append((mod, node.lineno))
        for child in ast.iter_child_nodes(node):
            visit(child, in_guard)

    visit(tree)
    return found


def layer_of_module(mod: str) -> str:
    parts = mod.split(".")
    if len(parts) < 2:
        return "root"
    top = parts[1]
    # app/main.py 与 app/seed.py 是装配/种子入口 = 组合根，不是普通 root
    if top in ("main", "seed", "bootstrap"):
        return "bootstrap"
    if top in ("config", "database", "migrate", "migration_helpers"):
        return "root"
    return top if top in ALL_LAYERS else "root"


def layer_of_file(p: Path) -> str:
    # 统一成相对 backend 的路径（"app/..."）。
    #
    # 历史 bug（2026-10-27 由 D-07 成员发现并在本轮修复）：
    #   旧实现 `r = rel(p)` 得到的是「相对仓库根」的 "backend/app/..."，
    #   却拿 "app/..." 前缀去比较 → 永远不匹配 → 所有文件都被判成 root，
    #   于是 R1/R2 的分层检查整体空转，`--strict` 恒为 0 违规。
    #   现在改相对 BACKEND，并加负向测试锁死（tests/test_architecture.py）。
    r = p.relative_to(BACKEND).as_posix()
    if r in ("app/main.py", "app/seed.py"):
        return "bootstrap"
    if r.startswith("app/bootstrap/"):
        return "bootstrap"
    for lay in ("api", "schemas", "services", "repositories", "models", "core", "plugins_builtin"):
        if r.startswith(f"app/{lay}/"):
            return lay
    return "root"


# ---------------------------------------------------------------- R1/R2 分层依赖
def check_layer_rules() -> None:
    global checked
    for path in sorted(APP.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        checked += 1
        src = layer_of_file(path)
        relsrc = path.relative_to(BACKEND).as_posix()
        if relsrc in COMPOSITION_ROOT_FILES or src in ("root", "bootstrap", "plugins_builtin"):
            continue
        for mod, line in iter_runtime_imports(path):
            dst = layer_of_module(mod)
            if dst == src:
                continue
            if dst not in LAYER_RULES[src]:
                rule = "R2-core-isolation" if src == "core" else "R1-layer-direction"
                err(rule, f"{src} 不得依赖 {dst}: import {mod}", f"{relsrc}:{line}")
            elif src == "api" and dst == "repositories":
                err("R1-layer-direction",
                    f"api 不得绕过 services 直接用 repositories: import {mod}（组合根例外见 deps.py）",
                    f"{relsrc}:{line}")


# ---------------------------------------------------------------- R3/R4
def check_framework_coupling() -> None:
    for path in sorted((APP / "services").rglob("*.py")):
        if path.name == "__init__.py":
            continue
        text = path.read_text(encoding="utf-8")
        if "fastapi" in text:
            err("R3-services-no-fastapi", "services 层不得 import fastapi（与框架解耦）", rel(path))

    for path in sorted((APP / "api").glob("*.py")):
        if path.name == "__init__.py":
            continue
        if path.relative_to(BACKEND).as_posix() in COMPOSITION_ROOT_FILES:  # deps.py 是会话装配点，例外
            continue
        text = path.read_text(encoding="utf-8")
        if "SessionLocal(" in text or "create_engine(" in text:
            err("R4-api-no-session", "api 层不得直接创建数据库连接/会话", rel(path))


# ---------------------------------------------------------------- R5 路由注册
def check_router_registration() -> None:
    init = APP / "api" / "__init__.py"
    text = init.read_text(encoding="utf-8")
    for path in sorted((APP / "api").glob("*.py")):
        stem = path.stem
        if stem in ("__init__", "deps"):
            continue
        if not re.search(rf"include_router\(\s*{re.escape(stem)}\.", text):
            err("R5-router-unregistered",
                f"api/{stem}.py 未在 api/__init__.py 注册（接口将不存在）", rel(path))


# ---------------------------------------------------------------- R6 模型注册
def check_model_registration() -> None:
    init_text = (APP / "models" / "__init__.py").read_text(encoding="utf-8")
    for path in sorted((APP / "models").glob("*.py")):
        stem = path.stem
        if stem in ("__init__", "base", "types"):
            continue
        if f"from app.models.{stem} import" not in init_text:
            err("R6-model-unregistered",
                f"models/{stem}.py 未在 models/__init__.py 导入 → 不会注册到 metadata、不会建表",
                rel(path))


# ---------------------------------------------------------------- R7 命名
def check_naming() -> None:
    for path in sorted((APP / "services").glob("*.py")):
        if path.name != "__init__.py" and not path.stem.endswith("_service"):
            err("R7-naming", "services 层文件必须命名为 <module>_service.py", rel(path))
    for path in sorted((APP / "repositories").glob("*.py")):
        if path.name not in ("__init__.py", "base.py") and not path.stem.endswith("_repo"):
            err("R7-naming", "repositories 层文件必须命名为 <module>_repo.py", rel(path))


# ---------------------------------------------------------------- R8 领域归属
MODULE_RULES = [
    ("api", re.compile(r"^api/(?P<m>[a-z0-9_]+)\.py$")),
    ("services", re.compile(r"^services/(?P<m>[a-z0-9_]+)_service\.py$")),
    ("repositories", re.compile(r"^repositories/(?P<m>[a-z0-9_]+)_repo\.py$")),
    ("models", re.compile(r"^models/(?P<m>[a-z0-9_]+)\.py$")),
    ("schemas", re.compile(r"^schemas/(?P<m>[a-z0-9_]+)\.py$")),
]


def check_domain_map(domains: dict) -> None:
    module_domain: dict[str, str] = {}
    for name, meta in domains["domains"].items():
        for m in meta["modules"]:
            if m in module_domain:
                err("R8-domain-overlap", f"模块 {m} 同时登记在 {module_domain[m]} 与 {name}（领域必须互斥）")
            module_domain[m] = name

    # domains.json 里的路径以 app/ 开头；这里统一成「相对 backend/app」的路径
    def norm(s: str) -> str:
        return s[len("app/"):] if s.startswith("app/") else s

    shared_files = {norm(x) for x in domains["shared"]["files"]}
    shared_dirs = [norm(d).rstrip("/") for d in domains["shared"]["packages"]]
    overrides = {norm(k): v for k, v in domains.get("file_domain_overrides", {}).items()}

    seen_modules: set[str] = set()
    for path in sorted(APP.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        r = path.relative_to(APP).as_posix()
        if r in shared_files or any(r == d or r.startswith(d + "/") for d in shared_dirs):
            continue
        if path.name == "__init__.py":
            continue
        if r in overrides:
            continue
        matched = False
        for layer, pattern in MODULE_RULES:
            m = pattern.match(r)
            if m:
                matched = True
                module = m.group("m")
                if module not in module_domain:
                    err("R8-domain-unmapped",
                        f"模块 {module} 未在 domains.json 登记领域（新增模块必须先登记）", r)
                else:
                    seen_modules.add(module)
                break
        if not matched and layer_of_file(path) in ("api", "services", "repositories", "models", "schemas"):
            err("R8-domain-unmapped", "文件命名不符合模块约定，无法归属领域", r)

    # 反向：登记了但代码里不存在（防止 domains.json 变成僵尸文档）
    for module in module_domain:
        if module not in seen_modules:
            warn("R8-domain-stale", f"domains.json 登记的模块 {module} 找不到对应实现文件")


    # 前端 features 目录（ADR-0007：一个领域一个包）
    features = FRONTEND_SRC / "features"
    declared_feat = {k: v for k, v in domains.get("frontend_features", {}).items() if not k.startswith("$")}
    if features.is_dir():
        for d in sorted(p for p in features.iterdir() if p.is_dir()):
            if d.name not in declared_feat:
                err("R8-feature-unmapped",
                    f"features/{d.name}/ 未在 domains.json.frontend_features 登记", rel(d))


# ---------------------------------------------------------------- R14 前端分层


def _frontend_target_area(spec: str, src_file: Path) -> tuple[str, str]:
    """把 import spec 解析成 (顶层区域, 子名)。相对路径按文件位置解析。"""
    if spec.startswith("@/"):
        parts = spec[2:].split("/")
        return parts[0], (parts[1] if len(parts) > 1 else "")
    if spec.startswith("."):
        target = (src_file.parent / spec).resolve()
        try:
            parts = target.relative_to(FRONTEND_SRC).parts
            return parts[0], (parts[1] if len(parts) > 1 else "")
        except ValueError:
            return "external", ""
    return "external", ""


def check_frontend_layers() -> None:
    """R14: kernel / shared / features 依赖方向（ADR-0007）。

    kernel  → 只能依赖 kernel
    shared  → kernel / shared
    features→ kernel / shared / 自身；跨 feature 只允许 `@/features/<other>`（index 入口）
    P4 起旧过渡目录（types/utils/components/api/views/composables/stores/constants/
    directives）已全部删除：对这些路径的任何依赖都是 ERROR，没有 WARN 豁免。
    """
    rules = {
        "kernel": {"kernel"},
        "shared": {"kernel", "shared"},
        "features": {"kernel", "shared", "features"},
    }
    for area, allowed in rules.items():
        base = FRONTEND_SRC / area
        if not base.is_dir():
            continue
        for f in sorted(list(base.rglob("*.ts")) + list(base.rglob("*.vue"))):
            if "__tests__" in f.parts or f.name.endswith(".d.ts"):
                continue
            text = f.read_text(encoding="utf-8", errors="ignore")
            own_feature = ""
            if area == "features":
                try:
                    own_feature = f.relative_to(base).parts[0]
                except ValueError:
                    own_feature = ""
            for spec in IMPORT_RE.findall(text):
                target, sub = _frontend_target_area(spec, f)
                if target == "external":
                    continue  # 第三方包（vue/pinia/...）不是分层违规
                if target in allowed:
                    if area == "features" and target == "features" and sub and sub != own_feature:
                        # 跨 feature：只允许 index（@/features/<other>），禁止深链
                        if spec.rstrip("/").count("/") > 2:
                            err("R14-frontend-cross-feature",
                                f"跨 feature 必须经对方 index.ts（禁止深链）: {spec}", rel(f))
                    continue
                err("R14-frontend-layers",
                    f"{area} 不得依赖 {target}: import {spec}", rel(f))


# ---------------------------------------------------------------- R11/R12 事务与迁移基线
def check_transaction_and_migration() -> None:
    """R11: repository 只 flush，不得 commit（提交权在 service / 请求边界）。

    背景：2026-10 审计 D-04 —— 每个 repository 方法内部 commit，导致多步用例
    （如「写文档 + 重建双链」）第二步失败时第一步已落库、无法回滚。
    改造后由 service 在用例边界提交、`api/deps.get_db` 兜底；本规则防止回退。
    BaseRepository 自身保留一个显式 `commit()` 出口（方法体内不算违规）。
    """
    for path in sorted((APP / "repositories").glob("*.py")):
        if path.name == "__init__.py":
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        except SyntaxError as e:
            # 不能静默跳过：解析不了 = 规则失效（合规假象）。BOM/语法错都要报。
            err("R11-repository-no-commit",
                f"无法解析 repository（R11 事务规则无法校验）：{e}", rel(path))
            continue

        def visit(node: ast.AST, inside_commit_method: bool = False) -> None:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                inside_commit_method = node.name == "commit"
            if isinstance(node, ast.Call) and not inside_commit_method:
                fn = node.func
                if isinstance(fn, ast.Attribute) and fn.attr == "commit":
                    err("R11-repository-no-commit",
                        "repository 不得调用 commit()：只 flush，提交权在 service / get_db",
                        f"{rel(path)}:{node.lineno}")
            for child in ast.iter_child_nodes(node):
                visit(child, inside_commit_method)

        visit(tree)

    # R12: 0001 基线必须是冻结 DDL，不得再出现 create_all/drop_all。
    # 背景：create_all 建的是"当前代码注册的全部模型"，基线会随模型静默变化、
    # 历史不可复现（审计 D-05）。重建后由 tests/test_migration_integrity.py 三方对账。
    baseline = BACKEND / "migrations" / "versions" / "0001_initial.py"
    if not baseline.is_file():
        err("R12-migration-baseline", "缺少 0001_initial.py", "migrations/versions/")
        return
    text = baseline.read_text(encoding="utf-8")
    for banned in ("create_all", "drop_all"):
        if banned in text:
            err("R12-migration-baseline",
                f"0001 基线不得使用 {banned}（必须冻结为显式 DDL）",
                rel(baseline))


# ---------------------------------------------------------------- R13 service 零直连 ORM
# 审计 D-06：service 层只能通过 repository 访问数据（写入 + 查询）。
# 禁止出现：
#   1. SQLAlchemy 表达式构造：select(...) / text(...)（text 还意味着裸 SQL）
#   2. 会话级查询/写入：<x>.db.execute / get / scalar / scalars /
#      add / add_all / delete / query
# 允许：
#   · commit / flush / refresh（事务边界归 service，见 D-04 约定）；
#   · 修改 repository 返回实体的属性（result.status = ...）。
#
# 为什么用 AST 而不是文本正则：docstring/注释里出现 "select(" 太常见，
# 正则会产生假阳性（本脚本自身注释里就有很多）。AST 只看真实调用。
#
# 已知豁免：app/services/sync/ 是 D-07 的数据同步引擎 —— 它是**基础设施
# 原语**，刻意按 Base.metadata 逐表搬运，不属于任何领域 service；D-07 落地
# 后再评估是否拆出专用 Query/Writer 模块。豁免显式登记于此，避免"静默跳过"。
R13_EXEMPT_DIRS = ("services/sync/",)

# 会话对象上禁止 service 直接调用的方法（查询 + 写入；commit/flush/refresh 不在此列）
R13_SESSION_METHODS = {
    "execute", "get", "scalar", "scalars",
    "add", "add_all", "delete", "query",
}


def _is_db_receiver(node: ast.AST) -> bool:
    """调用接收者是否为数据库会话：`db` 或 `xxx.db`。"""
    if isinstance(node, ast.Name):
        return node.id == "db"
    if isinstance(node, ast.Attribute):
        return node.attr == "db"
    return False


def check_service_no_direct_orm() -> None:
    """R13：services/**/*.py 不得直连 ORM（查询与写入都必须经 repository）。"""
    for path in sorted((APP / "services").rglob("*.py")):
        r = path.relative_to(APP).as_posix()
        if any(r.startswith(d) for d in R13_EXEMPT_DIRS):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        except SyntaxError as e:
            # 解析失败 = 规则失效（合规假象），必须报出而不是跳过
            err("R13-service-no-direct-orm", f"无法解析 {r}: {e}", r)
            continue

        def visit(node: ast.AST) -> None:
            if isinstance(node, ast.Call):
                fn = node.func
                if isinstance(fn, ast.Name) and fn.id in {"select", "text"}:
                    err(
                        "R13-service-no-direct-orm",
                        f"service 不得直连 ORM：{fn.id}() —— 查询/裸 SQL 请下沉到 repository",
                        f"{r}:{node.lineno}",
                    )
                elif (
                    isinstance(fn, ast.Attribute)
                    and fn.attr in R13_SESSION_METHODS
                    and _is_db_receiver(fn.value)
                ):
                    err(
                        "R13-service-no-direct-orm",
                        f"service 不得直连 ORM：db.{fn.attr}() —— 请改走 repository 的语义化方法",
                        f"{r}:{node.lineno}",
                    )
            for child in ast.iter_child_nodes(node):
                visit(child)

        visit(tree)


# ---------------------------------------------------------------- R9 根目录契约
def check_root_contract(domains: dict) -> None:
    contract = domains["root_contract"]
    allowed_files = {x for x in contract["files"] if not x.startswith("$")}
    allowed_dirs = {x for x in contract["dirs"] if not x.startswith("$")}
    ignored = set(contract.get("ignored_dirs", []))
    for entry in sorted(ROOT.iterdir()):
        if entry.name in ignored:
            continue
        if entry.is_dir():
            if entry.name not in allowed_dirs:
                err("R9-root-contract", f"根目录不允许出现目录：{entry.name}/（归位见 ARCHITECTURE.md §7）")
        else:
            if entry.name not in allowed_files:
                err("R9-root-contract", f"根目录不允许出现文件：{entry.name}（归位见 ARCHITECTURE.md §7）")


# ---------------------------------------------------------------- R10 前端横向依赖
IMPORT_RE = re.compile(
    r"""(?:import\s+(?:[^'"]*?\s+from\s+)?|export\s+[^'"]*?\s+from\s+)['"]([^'"]+)['"]"""
)


def check_frontend_boundaries() -> None:
    views = FRONTEND_SRC / "views"
    if not views.is_dir():
        return
    for f in sorted(list(views.rglob("*.vue")) + list(views.rglob("*.ts"))):
        text = f.read_text(encoding="utf-8", errors="ignore")
        owner = f.relative_to(views).parts[0]
        for spec in IMPORT_RE.findall(text):
            target: Path | None = None
            if spec.startswith("@/views/"):
                target = FRONTEND_SRC / spec[2:]
            elif spec.startswith("."):
                target = (f.parent / spec).resolve()
            if target is None:
                continue
            try:
                target_rel = target.relative_to(views)
            except ValueError:
                continue
            other = target_rel.parts[0] if target_rel.parts else ""
            if other and other != owner:
                warn("R10-view-cross-import",
                     f"view 跨域直接 import：views/{owner} → views/{other}（应走 feature 入口或提升为 shared 组件）",
                     rel(f))


# ---------------------------------------------------------------- 基线
def load_baseline() -> dict[str, set[str]]:
    if not BASELINE_FILE.is_file():
        return {}
    data = json.loads(BASELINE_FILE.read_text(encoding="utf-8"))
    out: dict[str, set[str]] = defaultdict(set)
    for item in data.get("violations", []):
        out[item["rule"]].add(item["detail"])
    return out


def apply_baseline(strict: bool) -> int:
    baseline = load_baseline()
    new_errors = []
    known = 0
    for rule, detail, where in errors:
        if detail in baseline.get(rule, set()):
            known += 1
            if strict:
                new_errors.append((rule, detail, where))
        else:
            new_errors.append((rule, detail, where))

    print("=" * 70)
    print(f"架构守护 · 扫描 {checked} 个后端模块")
    print("=" * 70)
    if new_errors:
        print(f"\n❌ 未登记的架构违规：{len(new_errors)}\n")
        for rule, detail, where in new_errors:
            loc = f"  [{where}]" if where else ""
            print(f"  ✗ {rule}{loc}\n      {detail}")
    if known and not strict:
        print(f"\n⚠️  已登记技术债：{known} 条（基线内，不阻断；修掉后请从 baseline 删除）")
        for rule, detail, where in errors:
            if detail in baseline.get(rule, set()):
                print(f"     · {rule}: {detail}")
    if warns:
        print(f"\n⚠️  提示：{len(warns)} 条")
        for rule, detail, where in warns:
            print(f"     · {rule}: {detail}")

    if new_errors:
        print(f"\n{'=' * 70}\n❌ 架构守护失败（{len(new_errors)} 条），修复指引见 docs/architecture/ARCHITECTURE.md §4")
        return 1
    print(f"\n{'=' * 70}\n✅ 架构守护通过（{known} 条已知债务）")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="启明星架构守护（Architecture as Code）")
    ap.add_argument("--strict", action="store_true", help="基线内的技术债也视为失败（CI 收口）")
    args = ap.parse_args()

    if not DOMAINS_FILE.is_file():
        print(f"❌ 缺少领域地图：{rel(DOMAINS_FILE)}")
        return 1
    domains = json.loads(DOMAINS_FILE.read_text(encoding="utf-8"))

    check_layer_rules()
    check_framework_coupling()
    check_router_registration()
    check_model_registration()
    check_naming()
    check_domain_map(domains)
    check_root_contract(domains)
    check_frontend_boundaries()
    check_frontend_layers()
    check_transaction_and_migration()
    check_service_no_direct_orm()
    return apply_baseline(args.strict)


if __name__ == "__main__":
    sys.exit(main())
