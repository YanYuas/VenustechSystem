# 贡献指南

感谢参与启明星系统（Venustech System）开发。请遵循以下约定，保证代码一致与可持续。

## 分层架构（严格单向依赖）

```
api → services → repositories → models
           ↘ core（统一响应/异常/日志/加密/事件总线）
```

- **api**：参数校验 + 响应封装，不碰 models、不直接建 Session
- **services**：业务逻辑，不依赖 FastAPI
- **repositories**：纯数据存取
- 架构守护测试强制（`backend/tests/test_architecture.py`）

## 代码规范

- **后端**：PEP8；分层纪律；统一 `AppException`；Schema 字段 snake_case 且与前端类型一致；Prompt 集中 `PromptBuilder`
- **前端**：Vue3 `<script setup lang="ts">` + Composition API；TS 严格模式禁 `any`；原生 fetch（禁 axios）；组件经 common/ 基础件，hex 色值仅 token 处
- **Windows**：源码 UTF-8；.bat 存 ASCII/GBK（cmd 按系统代码页解析）；脚本输出 utf-8

## 验证（提交前必须过）

```bash
# 一键跑齐三项（零第三方依赖，不需要 pytest）
python scripts/check_all.py
# 只想快速过后端两项：
python scripts/check_all.py --skip-frontend
```

等价的单项命令：

```bash
cd backend && python tests/test_architecture.py      # 架构守护（分层依赖）
cd backend && python scripts/smoke_backend.py        # 端到端 + 迁移 + 回归断言
cd frontend && npm run typecheck                     # vue-tsc 零错误
cd frontend && npm run build                         # 生产构建成功
```

> ⚠️ 本机 venv 未安装 pytest，`python -m pytest` 不可用。上面三个脚本是**免 pytest**
> 的等价验证路径 —— 请务必执行，不要假定"测试已通过"。
> （历史教训：`test_architecture.py` 曾因缺 pytest 而长期无人执行，
> 导致 7 处分层违规悄悄累积，见《调试与性能优化报告》B-2。）

## 数据库变更（重要）

改模型后生成 Alembic 迁移（`alembic revision --autogenerate`），启动自动 `upgrade head`，勿手改表。

### 铁律：新迁移必须幂等

`0001_initial.py` 用的是 `Base.metadata.create_all()`，它建的是**当前代码里注册的全部模型**
（不是 0001 当时的 schema）。所以后续迁移要建的表，在**全新库上很可能已经被建好了**。

凡是没写守卫的建表/建索引，都会在全新库上抛
`sqlite3.OperationalError: table xxx already exists`，**直接中断迁移链**
——表现为「新装用户完全起不来」。（0009/0010/0011 曾因此长期不可用，
因为仓库里那个已建表的历史 `app.db` 把问题掩盖了。）

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

`migrations/script.py.mako` 模板已默认引入 `migration_helpers`，新迁移天然带守卫说明。
**`alembic revision --autogenerate` 产出的 `create_table`/`create_index` 需手动包上守卫。**

## 提交规范（Conventional Commits）

```
feat(scope): 描述      # 新功能
fix(scope): 描述       # 修复
docs(scope): 描述      # 文档
refactor(scope): 描述  # 重构（不改行为）
chore(scope): 描述     # 杂项/清理
```

scope 用 backend / frontend / docs / scripts 等。提交前确认工作区仅含本次意图变更，勿夹带无关文件（如本地数据、构建产物、测试库）。

## 数据与产物（勿提交）

`backend/data/`、`backend/data_test/`、`backend/data_smoke/`、`data-*/`、`data_*/`、
`frontend/dist/`、`node_modules/`、`*.log`、`.workbuddy/` 等已在 `.gitignore`。

> `backend/data/app.db` 已于 2026-09-15 执行 `git rm --cached` 移出版本控制
> （此前切分支会连数据库一起切，有丢数据风险）。**请勿再把它加回仓库** ——
> 全新库靠「迁移 + 种子数据」自动重建，这也是 B-1 能被发现的路径。

## 设计令牌

硬约束：组件内颜色应全部走 `frontend/src/styles/variables.scss` 的令牌。
当前**尚未达标的存量债务**可用审计脚本查看：

```bash
python scripts/audit_hardcoded_colors.py           # 列出各文件违规数
python scripts/audit_hardcoded_colors.py --max 171 # 棘轮：超阈值退出 1
```

新写的组件请勿再引入字面量颜色；数据驱动的颜色（如用户自选项目色）请集中到常量文件。
