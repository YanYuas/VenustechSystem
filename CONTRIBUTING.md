# 贡献指南

> 本文只讲**流程与纪律**。架构原理看 [ARCHITECTURE.md](ARCHITECTURE.md)，
> 代码规范看 [docs/guides/development.md](docs/guides/development.md)，文档索引看 [docs/README.md](docs/README.md)。

## 1. 改动前先建立心智模型

读 [ARCHITECTURE.md §3「一条请求的完整生命周期」](ARCHITECTURE.md)。
一个模块永远按同一顺序读：`api/<m>.py`（薄）→ `services/<m>_service.py`（厚）→
`repositories/<m>_repo.py`（薄）→ `models/<m>.py`。33 个模块同构，看懂一个就够。

## 2. 分层纪律（CI 强制）

```
api  →  services  →  repositories  →  models
              ↘  core（事件总线/加密/缓存/日志/异常/响应）
```

| 层 | 可以 | 不可以 |
|---|---|---|
| `api/` | 校验参数、调 service、返回信封 | 碰 models、直接建 Session、写业务 |
| `services/` | 业务规则、状态机、事务、发事件 | import fastapi |
| `repositories/` | 数据访问，只 `flush()` | **`commit()`**（提交权在 service / `get_db`，守护 R11 强制） |
| `core/` | 基础设施 | 反向依赖 services / repositories |

组合根（`main.py`、`bootstrap/`、`api/deps.py`）是唯一装配特权区。
**违反会被 `scripts/audit_architecture.py` 拦截**，新增模块还要先在
[docs/architecture/domains.json](docs/architecture/domains.json) 登记领域。

## 3. 提交前必须过

```bash
python scripts/check_all.py --strict     # 13 项全绿（CI 同款）
```

单项速查：

```bash
python scripts/audit_architecture.py     # 架构守护
cd backend && python -m pytest tests -q  # 后端测试（pytest 在 requirements-dev.txt）
cd frontend && npm run typecheck && npm test
```

> 历史教训：项目曾出现"测试写了却没人跑"（长期未装 pytest，7 处分层违规悄悄累积）。
> 所以新守护**必须同时进 `check_all.py` 与 CI**，否则三个月后没人记得它存在。

## 4. 数据库变更（重要）

改模型后生成迁移，启动时自动 `upgrade head`，**勿手改表**。

> 基线已冻结：`0001_initial.py` 是**显式 DDL**（49 表 / 79 索引），不得再出现 `create_all`（守护 R12）。
> 新模型变更一律新增迁移（下一个版本号），`0021_schema_reconcile` 负责把老库补齐到 ORM 一致。
> 完整性由 `backend/tests/test_migration_integrity.py` 三方对账（全新库 / ORM metadata / 真实 DB）。

### 铁律：新迁移必须幂等

`0001_initial.py` 用的是 `Base.metadata.create_all()`，它建的是**当前代码里注册的全部模型**，
不是 0001 当时的 schema。所以后续迁移要建的表，在全新库上很可能已经被建好了。
没写守卫的建表/建索引会在全新库上抛 `table xxx already exists`，**直接中断迁移链**
（表现为"新装用户完全起不来"；历史上被仓库里那个已存在的 `app.db` 掩盖过）。

```python
from app.migration_helpers import table_exists, index_exists, column_exists

def upgrade() -> None:
    conn = op.get_bind()
    if not table_exists(conn, "my_table"):
        op.create_table("my_table", ...)
        op.create_index("idx_a", "my_table", ["a"])
    elif not index_exists(conn, "idx_a"):
        op.create_index("idx_a", "my_table", ["a"])   # 表在但索引缺，补上
```

`alembic revision --autogenerate` 产出的 `create_table`/`create_index` 需**手动包守卫**。
背景与待修债务见 [ARCHITECTURE.md §10 D-05](ARCHITECTURE.md)。

## 5. 提交规范（Conventional Commits）

```
feat(scope): 描述        # 新功能
fix(scope): 描述         # 修复
docs(scope): 描述        # 文档
refactor(scope): 描述    # 重构（不改行为）
test(scope): 描述        # 测试
chore(scope): 描述       # 杂项/清理
```

- `scope` 用 `backend` / `frontend` / `docs` / `scripts` / `ops`。
- 一次提交只做一件事；勿夹带本地数据、构建产物、测试库。
- 重构与功能不要混在同一个 commit（否则无法回滚）。

## 6. 数据与产物（勿提交）

`var/`、`backend/data*`、`frontend/dist/`、`node_modules/`、`*.log`、`.qm-token`、
`*.db`、`.env`、`.arch-audit/` 均已在 `.gitignore`。

> `backend/data/app.db` 曾于 2026-09-15 移出版本控制（此前切分支会连数据库一起切）。
> **请勿再把它加回仓库**；全新库靠「迁移 + 种子数据」重建。
> ⚠️ 已知历史问题：旧分支 `origin/feature/phase2-development` 里仍残留该库，
> 处置方案见 [ARCHITECTURE.md §10 D-02](ARCHITECTURE.md)。

## 7. 设计令牌

组件内颜色应走 `frontend/src/styles/variables.scss` 的 CSS 变量；存量债务用审计脚本查看：

```bash
python scripts/audit_hardcoded_colors.py            # 列出违规
python scripts/audit_hardcoded_colors.py --max 171  # 棘轮：超阈值退出 1
```

新组件请勿再引入字面量颜色；数据驱动的颜色（如用户自选项目色）集中到常量文件。

## 8. 文档与决策

- 改架构 → **必须同步改 [ARCHITECTURE.md](ARCHITECTURE.md) 与 `docs/architecture/domains.json`**。
- 做非显然的技术取舍 → 写 [ADR](docs/architecture/ADR/)（照现有模板：背景/决策/理由/后果/替代方案）。
- 文档放对分区（架构/产品/指南/过程归档/设计），并确认 `python scripts/audit_docs_links.py` 通过。
