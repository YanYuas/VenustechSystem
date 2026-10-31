# 启明星系统 · 架构总纲

> **本文是全项目架构的唯一权威描述（Single Source of Truth）。**
> 代码与文档冲突时以本文 + `docs/architecture/domains.json` + `scripts/audit_architecture.py` 为准。
>
> - 版本：对应应用 `VERSION` = 0.7.0 ｜ 最后更新：2026-10-26
> - 维护规则：**改架构必须同时改本文**；结构规则由机器守护（§9），不是靠自觉。
> - 读者：接手这个项目的你 / 未来的你。建议按 §0 → §3 → §4 顺序读，15 分钟能建立完整心智模型。

---

## 0. 一页速览（先读这个）

**一句话**：启明星是一个**本地优先的模块化单体**（Modular Monolith）——一个 SQLite 数据库、一个 FastAPI 进程、一个 Node 边缘服务、一个 Vue 前端，跑在用户自己的电脑上。

**一条主线**（记住这一条，其余都是它的分支）：

```
浏览器 / 手机 WebView
   │  (1) HTTP + {code,message,data} 信封
   ▼
ops/server/server.js  ── 静态资源 + /api 反向代理 + 访问令牌（唯一对外入口）
   │  (2) /api/v1/*
   ▼
backend/app/api/<module>.py ── 路由与参数校验（不写业务）
   │  (3) 调用
   ▼
services/<module>_service.py ── 业务规则、状态机、事务编排
   │  (4) 调用
   ▼
repositories/<module>_repo.py ── 数据访问（Repository 模式）
   │  (5) ORM
   ▼
models/<module>.py ── SQLAlchemy 模型 → SQLite（WAL）
```

**反向主线（副作用）**：service 里 `event_bus.publish(...)` → `app/bootstrap/*_handlers.py` 订阅者 → AI 摘要 / 通知 / 成长经验值。订阅者注册在**组合根**，不在 `core/`。

**三条铁律**（违反即架构违规，CI 会红）：

1. **依赖单向**：`api → services → repositories → models`，`core/` 只能被依赖、不能向上依赖。
2. **领域归属**：每个业务文件必须属于 `domains.json` 登记的 8 个领域之一，新增模块先登记。
3. **组合根唯一**：只有 `app/main.py`、`app/bootstrap/`、`api/deps.py` 允许"知道所有层"。

**先说清楚它不是什么**：不是微服务、不是事件溯源（CQRS）、不是多租户 SaaS、不是要拆成 20 个包的项目。它是一个**单人/小团队长期维护的本地应用**，所以架构目标是「边界清晰 + 改一处不炸别处 + 新人 10 分钟看懂」，而不是"看起来像大厂"。

---

## 1. 系统上下文

```
                    ┌──────────────────────────────┐
   用户（PC 浏览器）  │                              │
   用户（Android）  │   ops/server/server.js       │   ← 唯一对外入口 :3000
   Tailscale/LAN   │   静态 dist + /api 代理 + 令牌  │
                    └──────────────┬───────────────┘
                                   │ 127.0.0.1:8765
                    ┌──────────────▼───────────────┐
                    │      FastAPI 应用             │
                    │  api → services → repo → db  │
                    └───┬───────────┬──────────┬───┘
                        │           │          │
                 ┌──────▼───┐ ┌─────▼────┐ ┌──▼──────────────┐
                 │ SQLite   │ │ 本地文件  │ │ 外部 LLM API     │
                 │ app.db   │ │ 文档/备份 │ │ DeepSeek/OpenAI  │
                 │ (WAL)    │ │ 插件     │ │ （可缺省→降级）   │
                 └──────────┘ └──────────┘ └─────────────────┘
```

- **无云端**：数据不上传；AI 未配 Key 时全部功能降级为本地规则引擎（`services/ai/`、`core/growth_handlers`）。
- **单用户假设**：`default_user` 自动创建，认证是「本地信任 + 外部令牌」，不是账号体系。任何"多租户/权限矩阵"的改造都属于架构变更，需先写 ADR。
- **可离线**：前端有离线队列（`stores/offlineQueue.ts` + `api/http.ts`），弱网写操作先入队、恢复后重放。

---

## 2. 运行时拓扑：三种启动方式，其实只有两套结构

| 模式 | 启动器 | 进程 | 端口 | 数据目录 | 适用 |
|---|---|---|---|---|---|
| 开发 | `start-dev.bat` / `scripts/dev.ps1` | Vite + uvicorn(`--reload`) | 5173 / 8765 | `var/data` | 写代码 |
| 演示 | `start-demo.bat` | 同上，`VENUSTECH_DATA_DIR=<repo>/var/demo` | 5173 / 8765 | `var/demo` | 给别人看，不污染真实库 |
| 统一/移动 | `start-mobile.bat` | server.js + uvicorn | **3000**（对外）/ 8765（回环） | `var/data` | 局域网/手机/Tailscale |

**关键边界**：后端永远只绑 `127.0.0.1`；对外只暴露 `server.js` 的 3000。`server.js` 做三件事：托管 `frontend/dist`、把 `/api/*` 代理到 8765、校验 `X-API-Token`（回环来源豁免，PC 前端零配置）。

> ⚠️ 已知安全问题（P0，待修）：`server.js` 当前对**回环来源无条件放行**。若用 cloudflared 等隧道暴露 3000，隧道会把公网请求伪装成回环，令牌形同虚设。修复方案见 §10 债务表 D-01。

---

## 3. 一条请求的完整生命周期

以「任务列表页加载」为例，逐跳对应到文件——这是理解本项目的**唯一推荐路径**：

| # | 发生什么 | 文件 |
|---|---|---|
| 1 | 应用装配：Pinia、Router、全局错误处理、离线队列接线 | `frontend/src/app/main.ts` |
| 2 | 路由匹配，**懒加载**页面 | `frontend/src/app/router/index.ts` |
| 3 | 页面组件（视图只管渲染与交互） | `frontend/src/features/task/views/TaskListView.vue` |
| 4 | 组合式函数承接视图逻辑（可复用、可测） | `frontend/src/features/task/composables/useTask.ts` |
| 5 | 领域 API 封装（路径/类型/参数） | `frontend/src/features/task/api.ts` |
| 6 | **唯一 HTTP 漏斗**：baseURL、token、超时、重试、离线入队、SSE、信封解包、错误提示 | `frontend/src/kernel/http/index.ts` |
| 7 | 生产环境经边缘服务（dev 环境 Vite 直连 8765） | `ops/server/server.js` |
| 8 | FastAPI 入口：CORS、统一异常、插件路由挂载 | `backend/app/main.py` |
| 9 | 路由聚合 `/api/v1` | `backend/app/api/__init__.py` |
| 10 | 该模块路由 + 依赖注入（Session / 当前用户） | `backend/app/api/task.py`、`api/deps.py` |
| 11 | 业务逻辑（状态机、互斥、权限、事务） | `backend/app/services/task_service.py` |
| 12 | 数据访问 | `backend/app/repositories/task_repo.py` |
| 13 | ORM 模型 → SQLite | `backend/app/models/task.py` → `app.db` |
| 14 | 统一响应信封 `{code, message, data}` | `backend/app/core/response.py` |
| 15 | 前端解包 `body.data`，非 0 code 抛 ApiError | `frontend/src/kernel/http/index.ts` |

**写路径的额外一跳**：service 提交后 `event_bus.publish(EVENT_TASK_COMPLETED, ...)` → 订阅者（`app/bootstrap/event_handlers.py`、`app/bootstrap/growth_handlers.py`）异步处理通知、AI 摘要、成长经验值。**事件是解耦手段，不是业务事实来源**——数据库仍是唯一真相。

> 读代码顺序建议：`api/task.py`（薄）→ `services/task_service.py`（厚，业务都在这里）→ `repositories/task_repo.py`（薄）→ `models/task.py`。看一个模块就够，全部 33 个模块同构。

---

## 4. 依赖规则（唯一权威，机器强制）

### 4.1 后端五层

| 层 | 目录 | 职责 | 允许依赖 | 禁止 |
|---|---|---|---|---|
| API | `app/api/` | HTTP 路由、参数校验、调用 service、返回信封 | services, schemas, core, root | **models**（运行时）、**repositories**、业务逻辑 |
| Schema | `app/schemas/` | Pydantic DTO（入参/出参/分页） | schemas, core | services, models |
| Service | `app/services/` | 业务规则、状态机、事务编排、事件发布 | repositories, models, schemas, core | **fastapi**、api、**直连 ORM（R13）** |
| Repository | `app/repositories/` | **唯一数据访问入口**：CRUD/查询/批量写 | models, core | services, api、**commit（R11）** |
| Model | `app/models/` | SQLAlchemy ORM、表结构 | models, core | 任何上层 |
| Core | `app/core/` | **无业务语义的基础设施**：事件总线、加密、缓存、插件、日志、异常、响应、同步适配 | core, models | **services / repositories / api / schemas** |
| 组合根 | `app/main.py`、`app/bootstrap/`、`api/deps.py` | 装配：lifespan、插件、订阅者、Session/User 依赖 | 任意 | 承载业务规则 |

> `TYPE_CHECKING` 块内的 import 是**类型注解**，零运行时开销，不算违规（API 层合法引用 `User` 类型）。

**Repository 收口（D-06，R13 机器强制）**：service 里不得出现 `select(...)`、`text(...)`、`db.execute/get/scalar(s)/add/add_all/delete/query`；查询与写入一律经 repository 的语义化方法（`identity_counts`、`clear_project`、`replace_source_links`…）。
聚合服务（dashboard/report/backup/security）允许跨域**读**，但同样必须经各域 repository，不得自建跨表 SQL。
唯一豁免：`app/services/sync/`（D-07 数据同步引擎，基础设施原语，按 `Base.metadata` 逐表搬运，不属领域 service；D-07 落地后重新评估）。
新增 repository 时：文件命名 `<module>_repo.py`、继承 `BaseRepository[T]`、在 `app/repositories/__init__.py` 导出；模块名必须在 `docs/architecture/domains.json` 已登记（通常与同域 service 同名）。

### 4.2 前端分层（ADR-0007：kernel / shared / features）

```
features/<domain>/views      页面（只渲染/交互）
  → features/<domain>/composables   领域视图逻辑
    → features/<domain>/api.ts      领域接口封装
      → kernel/http                 唯一 HTTP 漏斗（baseURL/token/超时/重试/离线/SSE）
```

| 区域 | 职责 | 允许依赖 | 禁止 |
|---|---|---|---|
| `kernel/` | 无业务语义技术底座：http、toast、modal、offline 队列 | 自身（types/utils 为过渡） | shared、features、api、views |
| `shared/` | 设计系统与壳：constants、directives、common 组件、styles | kernel、shared | features、api、views、composables、stores |
| `features/<domain>/` | **一个领域一个包 = 唯一所有权落点**：api / model / composables / components / views / `index.ts` | kernel、shared、**自身**；跨领域只走对方 `index.ts` | `@/api`、`@/views`、`@/composables`、`@/stores`（过渡期目录） |

- 跨领域调用**只能**经对方 `features/<domain>/index.ts`（禁止深链；页面用懒加载入口避免主包污染）。
- `views/` 不得 import 另一个 view 的实现（跨域页面跳转走 router）。
- `types/` 是前后端契约的前端侧；新增字段时**两边同时改**（当前已知 13 处漂移，见 §10）。
- 迁移采用 **strangler**：被搬走的公共模块在原路径保留**薄转发壳**（`export *`，壳内零实现），P4 统一删除。
  现状：kernel 4 个模块 + shared 2 个 + 8 个旧路径壳；其余按 P3 逐域迁移（见 `frontend/src/features/README.md`）。
- 该分层由守护 **R14** 强制（kernel 反向依赖 / shared→features / feature 深链跨域 = CI 红）。

### 4.3 违反会怎样

`python scripts/audit_architecture.py` 用 AST 解析真实 import 图，逐条报告 `规则号 + file:line`，退出码非 0。
已知但暂不修的历史违规登记在 `scripts/architecture_baseline.json`（棘轮机制：**只减不增**）。

---

## 5. 领域地图（Bounded Contexts）

8 个领域，**互斥且完整**覆盖全部业务模块（33 个 API 模块 + 15 个子能力）。
机器可读版本：`docs/architecture/domains.json`（新增模块必须先登记，否则守护失败）。

| 领域 | 职责 | 模块 | 前端目录 |
|---|---|---|---|
| **platform** 平台底座 | 认证、设置、安全、备份、同步、事件、健康、日志、通知、规则、插件 | auth, user, settings, security, backup, sync, events, health, logs, notification, rules, plugins, audit, settings_history | `features/settings/`, `features/auth/`, `features/notification/`, `features/sync/`, `features/system/` |
| **execution** 执行管理 | 任务、项目、工作流、工作区 | task, project, workflow, workspace | `features/task/`, `features/project/`, `features/workflow/`, `features/workspace/` |
| **knowledge** 个人知识 | 文档、文件夹、学习/间隔重复、资源、模板、经验、复盘 | document, folder, learning, flashcard, study_plan, study_time, domain, resource, template, experience, review | `features/document/`, `features/learning/`, `features/resource/`, `features/experience/`, `features/review/` |
| **growth** 个人成长 | 成长 EXP、身份、习惯、心情、日记 | growth, identity, life, habit, habit_checkin, mood, diary | `features/growth/`, `features/identity/`, `features/life/` |
| **assistant** AI 交互 | 对话、助手、快捷面板、LLM 客户端与提示词 | conversation, assistant, panel, ai | `features/conversation/`, `features/assistant/`, `features/aihot/`, `features/panel/` |
| **companion** 桌宠陪伴 | 桌宠状态/动作、形象、头像 | avatar, pet | `features/avatar/`, `features/pet/` |
| **asset** 资产沉淀 | SOP/Prompt/Skill/项目记忆、保险箱 | asset, vault, sop, sop_version, skill, project_memory, prompt | `features/asset/`, `features/vault/` |
| **insight** 数据洞察 | 首页聚合、报告（只读，不写别人的表） | dashboard, report | `features/dashboard/`, `features/report/` |

**跨领域规则**：允许调用对方 **service 的公开方法**（如 dashboard 聚合各域）；**禁止**直接 import 对方的 repository/model 做写操作。当前 `identity_service` 删除时跨 10 张表写，属于待收口债务（D-06）。

---

## 6. 目录契约（每个目录的职责）

```
VenustechSystem/
├── backend/                    FastAPI 后端（详见 §4.1）
│   ├── app/
│   │   ├── main.py             应用入口/组合根（CORS、异常、插件挂载、lifespan）
│   │   ├── bootstrap/          ★ 组合根：启动期装配、事件订阅者（不得写业务规则）
│   │   ├── api/                HTTP 层（33 个模块 + deps.py 依赖注入）
│   │   ├── services/           业务层（25 个 service + ai/ + rules/）
│   │   ├── repositories/       数据访问层（29 个 repo + base.py）
│   │   ├── models/             ORM 模型（25 个模块，__init__ 负责注册）
│   │   ├── schemas/            Pydantic DTO（22 个模块）
│   │   ├── core/               基础设施（事件总线/加密/缓存/插件/日志/异常/响应/同步）
│   │   ├── plugins_builtin/    内置插件（唯一扩展点，可绕过分层但需自证隔离）
│   │   ├── config.py           配置（VENUSTECH_* 环境变量，唯一入口）
│   │   ├── database.py         引擎/Session/PRAGMA（WAL 在这里维护）
│   │   ├── migrate.py          启动迁移；seed.py 演示数据
│   │   └── migration_helpers.py
│   ├── migrations/             Alembic（0001 冻结基线 + 0002–0022；见 §10 D-05）
│   ├── tests/                  1284 条测试（api/production/repository_contract/sync/architecture）
│   ├── scripts/                后端专用：冒烟/探针/种子/演示数据
│   ├── requirements.txt        ★ 运行时依赖唯一来源
│   ├── requirements-dev.txt    测试/工具依赖
│   ├── pyproject.toml          仅工具配置（pytest/ruff），**不声明依赖**
│   └── data/                   默认运行期数据（gitignored；长期目标见 §7）
├── frontend/                   Vue3 + TS + Vite（详见 §4.2）
│   ├── src/
│   │   ├── app/                main.ts / App.vue / router / errorHandler / layout(业务壳) / views(404)
│   │   ├── kernel/             ★ 无业务语义底座：http(client·errors·request·sse·types) / ui / offline / device / async / electron
│   │   ├── shared/             ★ 设计系统与壳：components(common+layout) / theme / constants / directives / composables / types
│   │   ├── features/           ★ 27 个领域包（api·model·composables·components·views·index.ts）
│   │   └── shared/styles/      ★ 4 套主题 × 明暗（2026-10-27 由 src/styles 迁入）
│   │       shared/test/        vitest setup（2026-10-27 由 src/test 迁入）
│   ├── eslint.config.js        ESLint 9 flat（含 ADR-0007 分层边界规则）
│   ├── .prettierrc.json        Prettier（semi:false；多语句内联 handler 必须抽函数）
│   ├── public/                 manifest + sw.js（PWA）
│   ├── android/                Capacitor 原生工程（构建产物，勿手改）
│   └── scripts/                前端专用测试脚本（esbuild）
├── ops/                        ★ 运行时与运维（不是业务代码）
│   ├── start.ps1               ★ 唯一启动实现（dev/demo/mobile，-WhatIf 可预演）
│   ├── setup.ps1               唯一安装实现（venv + 依赖 + node_modules）
│   ├── backup-git.ps1          Git 全历史 bundle 备份（轮转 + 校验）
│   ├── rebuild-remote.ps1      远端泄漏仓库重建（删→建→推干净历史→验证旧 SHA 404）
│   ├── push-branches.bat       推送辅助
│   └── server/                 统一 Web 服务：server.js + package.json + node_modules
├── scripts/                    质量门禁与工程脚本（check_all / audit_* / check_versions）
├── docs/                       文档（IA 见 docs/README.md）
│   ├── architecture/           ★ 本文、domains.json、ADR/、legacy/
│   ├── product/                需求与 PRD（v1-archived / v2-current）
│   ├── guides/                 开发/后端/前端/分支/协作指南
│   ├── process/archive/        带日期的过程记录（只读历史）
│   ├── runbooks/               运维手册（启动/备份/恢复/发布）
│   ├── design/                 UI 画廊与参考图
│   └── assets/                 截图
├── var/                        运行期数据约定（gitignored，见 §7）
│   ├── data/ demo/ legacy/     真实库 / 演示库 / 历史副本（**禁止删除**）
│   ├── backups/                本地备份产物（**禁止删除**，另需复制到仓库外）
│   ├── logs/ tmp/              日志与临时文件（tmp 可清）
│   └── .gitkeep                唯一入库的占位文件（保持目录结构）
├── .github/workflows/          CI：backend / frontend / repo-guard / android-build
├── ARCHITECTURE.md             ★ 本文（架构唯一权威）
├── VERSION                     ★ 版本单一事实来源
└── *.bat                       仅保留 4 个用户启动器（setup/start-dev/start-demo/start-mobile）
```

**根目录契约**：根目录只允许上表列出的条目；新增根级文件前先想清楚它属于哪一层（源码→backend/frontend，运维→ops，脚本→scripts，文档→docs，数据→var）。由守护规则 R9 强制。

**工作区卫生契约**（`scripts/audit_workspace_hygiene.py`，check_all 第 16 项 / repo-guard CI）：
- **tracked 泄漏**：`git ls-files` 不得含数据库 / 密钥 / 令牌 / `node_modules` / `dist` / `var` 运行期文件（唯一例外 `var/.gitkeep`）。
- **ignore 契约**：关键路径必须真的被 `.gitignore` 忽略（用 `git check-ignore` 做语义校验，不是 grep 文本）；`var/.gitkeep` 必须未被忽略。
- **根目录**：除 `domains.json.root_contract`（含 `ignored_dirs`）外不得出现未登记条目（本地模式）。
- **var/ 顶层白名单**：只允许 `data/ demo/ legacy/ backups/ logs/ tmp/`；`pytest-*`、`.ruff-*`、`rebuild`、`tools`、`junk` 等属垃圾（本地模式）。`var/logs/` 是启动器/服务日志目录，保留且 `--fix-local` **不删**（需要时手动清旧日志）。
- **测试覆盖率产物**：`backend/.coverage*`（pytest-cov 并行数据）、`frontend/coverage/`、`coverage/`、`htmlcov/`、`coverage.xml` 必须被忽略；本地存在时提示，`--fix-local` 可清理（属测试产物，可安全删除）。
- **清理**：`python scripts/audit_workspace_hygiene.py --fix-local` 只删"明确废弃"的本地垃圾，**绝不**碰 `var/data`、`var/demo`、`var/legacy`、`var/backups`、`var/logs`、`backend/.legacy-data-*`（只提示）。CI 干净克隆只跑 tracked + ignore 两项（`--ci`）。

---

## 7. 运行期数据与配置

**唯一配置入口**：`backend/app/config.py` 的 `Settings`，前缀 `VENUSTECH_`，模板见 `backend/.env.example`。

**数据目录（最重要的一个变量）**：
- 开发/源码运行默认 `<仓库根>/var/data`（**相对仓库根解析，与启动方式无关** —— 曾经用 `./data` 导致从仓库根启动时生成第二份数据库）。
- 由 `VENUSTECH_DATA_DIR` 覆盖（演示库 `var/demo`、分支隔离、测试都用它）；启动器的 `-DataDir` 相对路径也按**仓库根**解析。
- 目录内包含：`app.db`（SQLite，WAL）、`logs/`、`backups/`、`documents/`、`plugins/`、`.encryption_key`。
- 一次性兼容分支：若 `var/data` 不存在但旧的 `backend/data` 存在，`config._default_data_dir()` 会回退旧目录并告警（迁移完成后可删除，见源码注释）。

**约定**：仓库内的一切运行期数据都属于 `var/`（已整体 gitignore）。**不要把数据库、密钥、日志放进任何会被提交的位置。**

| 目录 | 用途 |
|---|---|
| `var/data` | 真实库（含 `app.db` / `.encryption_key` / `logs` / `plugins` 等） |
| `var/demo` | 演示库（`seed_demo.py` 生成，可重建） |
| `var/legacy/` | 历史数据副本（`data_hc` / `data_pet` / `data_smoke*` / `data_tpl*` / `data_tt`） |
| `var/backups/` | 备份产物（git bundle、迁移前快照），**必须再复制到仓库外** |

> 2026-10-27 已把旧的 `backend/data*` 物理迁移到 `var/`；旧目录改名保留在 `backend/.legacy-data-2026-10-27/`（gitignored，确认无误后可删）。

| 文件 | 位置 | 说明 |
|---|---|---|
| `app.db` | `$VENUSTECH_DATA_DIR/app.db` | 唯一业务真相 |
| `.encryption_key` | 同上 | AES 主密钥，丢失 = 已加密字段不可解（备份它！） |
| `.qm-token` | 仓库根 | 外部访问令牌（`server.js` 生成，手机端填一次）；gitignored |
| `dist/` | `frontend/dist` | 构建产物，gitignored |

> **备份契约**：备份必须同时包含 `app.db` 与 `.encryption_key`，否则加密字段（API Key、保险箱凭据）无法恢复。自动备份逻辑见 `services/backup_service.py`，人工步骤见 `docs/runbooks/backup.md`。

---

## 8. 如何新增一个模块（照做即可）

1. **登记领域**：在 `docs/architecture/domains.json` 对应领域 `modules` 里加模块名（不登记 → 守护 R8 失败）。
2. **模型**：`models/<module>.py` + 在 `models/__init__.py` import（不登记 → 不建表，R6 失败）。
3. **迁移**：`alembic revision -m "..."`，**不要**改已有 migration（见 D-05）。
4. **仓储**：`repositories/<module>_repo.py`，继承 `BaseRepository`。
5. **DTO**：`schemas/<module>.py`。
6. **服务**：`services/<module>_service.py`，不 import fastapi；需要跨域就调对方 service。
7. **路由**：`api/<module>.py`，并在 `api/__init__.py` 注册（R5 失败会提示）。
8. **前端**：`types/<module>.ts` → `api/<module>.ts` → `composables/use<Module>.ts` → `views/<Module>/` → 路由 + `domains.json.frontend_views`。
9. **测试**：至少 `tests/test_<module>_api.py`（API 形状）+ `test_<module>_production.py`（真实行为/边界）。
10. **验证**：`python scripts/check_all.py`（16 项全绿）。
11. **记账**：CHANGELOG + 需要时 `docs/architecture/ADR/`。
12. **收口**：`python scripts/audit_architecture.py` 必须 0 新增违规。

---

## 9. 质量门禁与验证

**唯一验证入口**：`python scripts/check_all.py`（16 项）；CI 必须 `--strict`（缺依赖=失败，不给假绿）。

| 守护 | 命令 | 守什么 |
|---|---|---|
| 架构 | `scripts/audit_architecture.py` | 分层方向、core 隔离、领域归属、路由/模型注册、根目录契约、**事务边界(R11)**、**迁移基线(R12)**、**service 零直连 ORM(R13)**、**前端 kernel/shared/features 分层(R14)**；R1/R2/R13/R14 均有负向测试证明会变红 |
| 后端测试 | `pytest backend/tests` | 1284 条：API 形状 + 生产行为 + 仓储契约 + 同步引擎 + 数据库基础设施 |
| 后端 lint | `cd backend && python -m ruff check app tests` | ruff 0.6.2 只启正确性规则 `E4,E7,E9,F`：未定义名 / 未使用导入与变量 / 重定义 / 语法错误；**不跑 `ruff format`**（避免纯风格 diff），口径见 `backend/pyproject.toml` |
| 后端冒烟 | `backend/scripts/smoke_backend.py` | 真实启动 + 迁移 + 端到端断言 |
| 版本一致 | `scripts/check_versions.py` | 5 处版本 == `VERSION` |
| 文档链接 | `scripts/audit_docs_links.py` | 全量 md 相对链接与内联路径 |
| 测试质量 | `scripts/audit_test_quality.py` | 永真断言/无断言/吞异常（"缺陷在也全绿"的写法） |
| 日志格式 | `scripts/audit_log_format.py` | loguru `{}` 占位符（`%s` 会静默丢参数） |
| 交付物 | `scripts/audit_delivery.py` | 一键脚本真能启动、冒烟不含水分 |
| 工作区结构 | `scripts/audit_workspace_hygiene.py` | tracked 泄漏 / `.gitignore` 契约 / 根目录与 `var/` 白名单（CI 只查前两项）；`--fix-local` 清本地垃圾，不碰数据兜底目录 |
| 设计令牌 | `frontend/scripts/audit-tokens.py` | 用了不存在的 CSS 变量 |
| 前端 lint | `npm run lint` | ESLint 9 flat：正确性 + **ADR-0007 分层边界**（kernel/shared/features 依赖方向） |
| 前端格式 | `npm run format:check` | Prettier 一致性（`semi:false`；多语句内联 handler 必须抽函数） |
| 前端类型 | `npm run typecheck` | TS 严格模式 |
| 前端单测 | `npm test` | vitest（纯逻辑） |
| 前端行为 | `frontend/scripts/test-*.ts` | 离线队列 / HTTP 连通性 |

CI：`.github/workflows/{backend,frontend,repo-guard}.yml` + `android-build.yml`。

> 项目的历史教训（写在 `check_all.py` 注释里）：**"写了却跑不了的测试等于没有测试"**。任何新守护必须同时进 `check_all.py` 与 CI，否则三个月后没人记得它存在。

---

## 10. 当前架构债务（不假装健康）

完整证据见 `.arch-audit/reports/{backend,frontend,ops-docs}.md`（2026-10-26 基线）。按风险排序：

| ID | 等级 | 债务 | 证据 | 处置阶段 |
|---|---|---|---|---|
| D-01 | **P0** | 令牌回环绕过：cloudflared 场景等于无鉴权 | `ops/server/server.js` `isAuthorized()` | ✅ 已修（2026-10-26）：代理头检测 + 常量时间比较 + 16 条单测 + CI |
| D-02 | **P0** | `origin/feature/phase2-development` 曾包含真实用户库 `app.db`（当时在 `backend` 的 `data/` 下，606KB，公开可拉） | 泄漏提交 `6b5c2dd`，仅该分支可达；**无 `.encryption_key`**（密文字段安全） | ✅ **已彻底处置（2026-10-28）**：历史清洗（filter-repo，44 commits、tree 逐字节不变）+ 远端 refs 清理 + **仓库删除重建**（`ops/rebuild-remote.ps1`）；新仓库只剩 `main`+3 tags，旧 commit → HTTP 422 / 旧 blob → HTTP 404 / git 协议层 `not our ref`，全新克隆历史扫描 DB 命中 0；`audit_repo_secrets --strict` 常开 |
| D-03 | **P0** | 备份导入 100% 失败：`FormData` 被 `JSON.stringify` 后发 JSON，后端要 multipart → 422 | `frontend/src/features/dashboard/api.ts` + `kernel/http/index.ts` ↔ `backend/app/api/backup.py` | ✅ 已修（2026-10-26）：`http.postForm` + 真实 multipart 运行时断言 11/11 |
| D-04 | P1 | **事务边界下沉**：`BaseRepository` 每个方法内部 commit，service 再 commit → 多步操作无原子性 | `repositories/base.py` | ✅ 已修（2026-10-26）：repo 只 flush、service 控 commit、get_db 兜底；8 条原子性测试 + 守护 R11 |
| D-05 | P1 | 迁移基线失效：`0001` 用 `create_all()`，11 张基线表无 DDL；升级库缺 11 个索引 | `migrations/versions/0001_initial.py` | ✅ 已修（2026-10-26）：0001 冻结显式 DDL（49 表/79 索引）+ 0021 对账 + 6 条完整性测试 + 守护 R12 |
| D-06 | P1 | Repository 层名存实亡：16/31 service 直连 ORM；service 9441 行 vs repo 1412 行 | 审计报告 §2 | ✅ 已修（2026-10-27）：16 service / 156 调用点 → **0**；新增 7 个 repo、约 60 个语义化方法；守护 R13 |
| D-07 | P1 | `core/sync.py` 藏 389 行领域逻辑；core 内共 815 行业务代码 | 审计报告 §2 | ✅ 已修（2026-10-27）：`core/sync.py` → `services/sync/`；core **0 依赖 models**；删除死代码 `core/cache.py`；R2 收紧 |
| D-08 | P1 | 前端 13 处前后端契约漂移（几乎都是"后端有、前端类型没有"） | `frontend/src/features/*/model.ts` vs `backend/app/schemas/*` | ✅ 已修（2026-10-27）：13/13 + TaskStatus/TaskPriority Literal + ADR-0008 `\| null` 语义落地 34 处 |
| D-09 | P1 | 前端 god 组件：`SettingsView` 1577 行；16 个 view >500 行；`http.ts` 378 行 9 类职责 | 审计报告 §4–§6 | ✅ 已修（2026-10-27）：SettingsView **1701 → 291 行**；14 分区组件 + 3 composable；DOM 405 节点零差异；`http.ts` 迁入 `kernel/http` |
| D-10 | P1 | 前端死代码约 1188 行（`AppHeader`/`AppSidebar`/`stores/app.ts` 等） | 审计报告 §7 | ✅ 已修（2026-10-26）：15 文件 / 1625 行，typecheck ×5 全绿 |
| D-11 | P2 | 5 个启动器重复实现 venv/端口/令牌逻辑（4 份 venv 解析、2 种令牌生成） | `*.bat` + `scripts/dev.ps1` | ✅ 已修（2026-10-27）：唯一实现 `ops/start.ps1`（`-Mode`/`-WhatIf`）+ 根 .bat 薄转发壳；审计守护点迁移 + 负向测试 |
| D-12 | P2 | `.git` 是 Junction 指向 `C:\Users\21722\qimingxing-git-repo`：备份项目目录 ≠ 备份历史 | 文件系统 | ✅ 已提供工具（2026-10-27）：`ops/backup-git.ps1`（bundle 创建/校验/轮转，实测 4.5MB 通过）+ runbook；结构性迁移待停机窗口 |
| D-13 | P2 | 无 lint：ESLint/Prettier/ruff 全缺 | — | ✅ 已修（2026-10-27）：backend ruff E4/E7/E9/F（245→0，进 CI）；frontend ESLint 9 flat（含 ADR-0007 边界）+ Prettier（进 CI） |
| D-14 | P2 | `server.js` 是唯一鉴权点却零测试 | `ops/server/server.js` | ✅ 已修（2026-10-26）：`ops/server/test` 16 用例 + CI edge-server job |
| D-16 | P2 | `backend/scripts/**` 未纳入 ruff（实测 13 条，含 3 条 F821 疑似真 bug） | `backend/scripts/` | ✅ 已修（2026-10-27）：13 → 0（F541 4 / F401 3 / F821 3 / F841 3）。F821 逐条核实：`seed_demo.seed_tasks` 的 `utcnow()` 是**真 bug**（缺导入，补 `from app.models.base import utcnow`）；`smoke_backend` 两处 `pathlib.Path(...) if 'pathlib' in dir()` 是**死代码**（条件恒 False 且下一行覆盖），删除。门禁三处统一为 `ruff check app tests scripts`（backend.yml / check_all 第 15 项 / pyproject 口径注释） |
| D-15 | **P0（隐性）** | 架构守护 R1/R2 长期**空转**：`layer_of_file()` 拿仓库相对路径比 `app/` 前缀（永不匹配），且 `TYPE_CHECKING` 豁免标记传入未使用 → `--strict` 恒绿 | `scripts/audit_architecture.py` | ✅ 已修（2026-10-27）：路径基准改为 `backend/`、TYPE_CHECKING 真正豁免；新增 4 条负向 + 2 条回归测试 |
| D-17 | P1 | `PATCH /auth/me` 传 `pet_position` 必 500：`model_dump()` 后按对象取 `.x` | `api/auth.py` | ✅ 已修（2026-10-28）：改 dict 取值 + 嵌套部分坐标保留；strict xfail 转正 + 5 条边界测试 |
| D-18 | P1 | `api/logs.py` 对 stdlib logger 调 loguru `.opt()` → 清日志失败分支 AttributeError | `api/logs.py` | ✅ 已修（2026-10-28）：根因是混用后端，统一 `get_logger`（loguru），保留 `opt(exception=True)`；回归测试 + 负向验证 |
| D-19 | P2 | `api/logs.py` 错误分支返回裸 dict，绕过统一响应信封 | `api/logs.py` | ✅ 已修（2026-10-28）：400/404/500 改 `error()`，补信封契约测试 |
| D-20 | P1 | `avatar_service` memory/inspiration 写操作无 `user_id` 归属校验（IDOR） | `avatar_service.py` | ✅ 已修（2026-10-28）：7 个写方法加 `user_id` + 归属校验（NotFound，不泄漏存在性）；13 条 IDOR 用例 + 独立 Session 复核 |
| D-21 | P2 | SSE 请求未带 `X-API-Token` → 启用令牌后流式对话 401 | `frontend/src/kernel/http/sse.ts` | ✅ 已修（2026-10-28）：与普通请求对齐；+2 条头断言测试 |
| D-22 | P2 | `assistant_service._TIME_HINTS` 顺序使 "大后天" 先命中 "后天" → 解析成 +2 天 | `assistant_service.py:41-48` | ✅ 已修（2026-10-30）：长词前置（大后天+3、今晚优先）；同日发现 D-30/D-31 两个新分支 bug |
| D-23 | P2 | `ai/client.chat()` 200 缺字段抛裸 KeyError，未映射 `AIRequestFailedException` | `ai/client.py` | ✅ 已修（2026-10-30）：解析整体 try + 6 种坏结构/非法 JSON → `AIRequestFailedException`（保留 cause 链） |
| D-24 | P1 | `aihot` 双重响应信封 + `daily()` 对信封取 `ok` 恒 None → 404 回退成功分支运行期不可达 | `aihot/main.py` | ✅ 已修（2026-10-30）：`_fetch` 返回裸结果、端点单层信封；真实 HTTP 路径测试证明 `source=live/fallback-*` 可达 |
| D-25 | P3 | `AssistantService._encryption()` 每次 new `EncryptionManager` | `assistant_service.py` | ✅ 已修（2026-10-30）：`core/encryption.ensure_encryption()` 双检锁单例；7 条测试含 4 线程并发 |
| D-26 | P2 | 多个 app 模块用 stdlib `logging.getLogger` 却按 loguru 风格 `{}` 传参（参数被丢弃），且 `logger.opt()` 在 stdlib 上会 AttributeError | health/event_bus/plugin_manager/9 个 service 等 | ✅ 已修（2026-10-30）：12 文件统一 `get_logger` + 21 处 f-string→`{}` 惰性占位；`config.py` 因导入环保留 stdlib 并进白名单；契约新增"禁止 logging.getLogger"+ caplog 按需桥；顺带修掉 health/dashboard/pet 的 latent AttributeError |
| D-27 | P3 | `useSettingsDiagnostics` 的 400ms `ruleTimer` 未在 scope dispose 清理 | `useSettingsDiagnostics.ts` | ✅ 已修（2026-10-30）：`onScopeDispose` 清理 + 卸载后不触发预览回归测试 |
| D-28 | P3 | `offlineQueue` store `init()` 重复调用会重复注册网络监听 | `offlineQueue.ts` | ✅ 已修（2026-10-30）：`listenersBound` 幂等 + dispose 复位；2 条回归测试 |
| D-29 | P3 | `GlobalSearch` 的空态"没有找到相关内容"不可达：恒定操作项使 `hasAny` 恒 true（UX 决策） | `app/layout/GlobalSearch.vue` | ✅ 已修（2026-10-30）：新增 `realResults` 排除 action 项，空态条件改 `!realResults.length`+引导文案，操作项仍常驻 |
| D-30 | P2 | `_NUM_TIME` 的 `周X` 分支 base 已前进又叠加 offset → "周三" 解析成 +14 天 | `assistant_service.py` | ✅ 已修（2026-10-30）：`base=today`+只算一次 offset（未来最近周X），周 7 天矩阵 + numeric 矩阵 |
| D-31 | P2 | "下周X" 分支 `delta += delta`（+ `if False` 死代码）→ +14 天 | `assistant_service.py` | ✅ 已修（2026-10-30）：`delta=(7-today.weekday())+WEEKDAY[day]`，跨周边界矩阵（周一"下周三"+9 等） |
| D-32 | P2 | `domain_engine` 阶段公式使 4 单元通用兜底计划永不出现 phase 3 | `services/rules/domain_engine.py` | ✅ 已修（2026-10-30）：`phase=min(3,(i*3)//total+1)`，total≥3 恒三段齐全；内置 13 领域分布同步修正 |
| D-33 | P3 | `app/seed.py` 用 `datetime.utcnow()`（DeprecationWarning） | `app/seed.py` | ✅ 已修（2026-10-30）：改 `utcnow()`（aware UTC），移除多余 import |
| D-34 | P3 | `WorkspaceService.delete_root` 不清理 `_SCAN_PROGRESS` 僵尸条目 | `workspace_service.py` | ✅ 已修（2026-10-30）：commit 后 `_progress_clear(root_id)`；404 语义不变 |
| D-35 | P3 | `app/main.py` 3 处 f-string 日志（非惰性） | `app/main.py` | ✅ 已修（2026-10-30）：改 loguru `{}` 惰性占位，渲染文本不变 |
| D-36 | P2 | `useSettingsSync.loadDataDir` 硬编码 `127.0.0.1:8765` 健康检查（未走 `getApiBase()`）→ 移动端/局域网误报后端未连接 | `useSettingsSync.ts` | ✅ 已修（2026-10-30）：改 `` `${getApiBase()}/health` ``；baseURL 覆盖回归测试 |
| D-37 | P3 | `useSettingsSync` 导出/导入/包列表 catch 为空（非 http 错误静默） | 同上 | ✅ 已修（2026-10-30）：`reportUnexpected()` 区分 `ApiError`（http 层已提示）与意外错误（补 toast）；4 条测试 |
| D-38 | P3 | `useReminderWatcher` 模块级 `notifiedIds` 无上限（长会话缓慢增长） | `useReminderWatcher.ts` | ✅ 已修（2026-10-30）：`NOTIFIED_MAX=500` 按插入顺序淘汰最旧；容量回归测试 |
| D-39 | P3 | `notifiedIds` 淘汰存在"级联再通知"理论风险 | `useReminderWatcher.ts` | ✅ 已修（2026-10-30）：改 `Map<id,ts>` + 24h TTL + 容量清理（先清过期再淘汰最早） |
| D-40 | P3 | `BaseSelect` 外部改 `modelValue` 不重置搜索词 | `BaseSelect.vue` | ✅ 已修（2026-10-30）：watch 内同时 `query=''`；外部改值恢复全量选项测试 |
| D-41 | P3 | `BaseModal` 关闭动画期被卸载时 `closed` 不触发 | `BaseModal.vue` | ✅ 已修（2026-10-30）：保存 timer + `closedEmitted`，`onBeforeUnmount` 补发且恰好一次 |
| D-42 | P2 | `main.py` demo_seed 无 try/except（seed 失败阻断启动） | `app/main.py` | ✅ 已修（2026-10-30）：fail-open + exception 日志 + rollback；测试从 fatal 改 fail-open |
| D-43 | P2 | `main.py` 订阅注册无 try/except（异常中断启动） | `app/main.py` | ✅ 已修（2026-10-30）：event/growth 各自独立 fail-open；一个失败不影响另一个 |
| D-44 | P3 | 自动备份只对第一个用户执行 | `app/main.py` | ✅ 已修（2026-10-30）：遍历全部用户 + per-user 独立 Session/try；聚合计数 |
| D-45 | P2 | 多行日志调用里的 `%s` 被日志格式扫描器漏检（D-26 迁移遗留：`backup_service` 版本告警、`ai/client` 两处）→ loguru 下参数被丢弃 | 已修 | ✅ 已修（2026-10-30）：3 处改 `{}`；扫描器改**跨行调用**检测并加 3 条回归测试（`scan_source()` 可测） |

| D-46 | P2 | `import_` 在「改名旧库→写新库」间无自动回滚（写失败/崩溃会留缺失或半截 DB） | `backup_service.py` | ✅ 已修（2026-10-31）：临时文件 + `fsync` + `os.replace()` 原子替换；失败自动从 `.bak` copy2 恢复（保留回滚点）+ 诊断日志 |
| D-47 | P3 | `.bak` 秒级时间戳同秒冲突（Windows 抛错 / POSIX 覆盖回滚副本） | `backup_service.py` | ✅ 已修（2026-10-31）：`YYYYmmdd_HHMMSS_mmm_<uuid6>`；同秒双恢复测试 |
| D-48 | P2 | `event_bus` async handler 在无运行 loop 时 `get_event_loop()` 自动创建未运行 loop → `create_task` 排队永不执行，handler 静默丢失（`called` 仍 +1） | `app/core/event_bus.py` | ✅ 已修（2026-10-31）：改 `get_running_loop()`；无运行 loop 逐 handler `asyncio.run()` 兜底；排队 task 延迟失败/取消经 `add_done_callback` 写入 history/stats + 日志，不静默 |
| D-49 | P3 | `task_service` 批量失败只 `failed += 1`，无日志/原因（排障无信息） | `app/services/task_service.py` | ✅ 已修（2026-10-31）：缺失/越权/异常分支均 `logger.warning("批量操作失败: task_id={} action={} reason={}")`；`BatchTaskResult` 契约不变 |
| D-50 | P3 | `PATCH /auth/me` 的 nickname 无 `min_length` → 可置空昵称 | `schemas/auth.py` | ✅ 已修（2026-10-31）：nickname `min_length=1`；avatar/theme 按 DB 列长加 `max_length`（500/20，不做白名单并说明理由） |
| D-51 | P3 | `verify-api` 空 Key 真实请求 provider | `api/auth.py` | ✅ 已修（2026-10-31）：strip 后为空先 `ValidationException`（400/1001），不构造 AIService；spy 断言三种空白零调用 |
| D-52 | P3 | `DesktopPet` 初始 1s 定时器未保存句柄/未卸载清理 | `DesktopPet.vue` | ✅ 已修（2026-10-31）：`initialMessageTimer` + onUnmounted clearTimeout；卸载瞬间 `getTimerCount()===0` 测试 |
| D-53 | P3 | 低精力玩耍自定义提示被 `setAction` 随机气泡覆盖；petClass 未映射部分动作 | 同上 | ✅ 已修（2026-10-31）：先 setAction 再写提示（与 feed/rest 一致）；petClass 注释说明只映射有样式的动作，不补死类 |
| D-54 | P3 | `DocumentGraph` 力导向 tick 无 `document.hidden` 暂停/拖拽惯性 | `DocumentGraph.vue` | ✅ 已修（2026-10-31）：visibilitychange hidden 停/visible 重启 + 卸载移除；mouseup 清零 vx/vy；测试区分度 1.6px vs 96px |
| D-55 | P3 | `DesktopPet` feed/play/rest 的"2~3s 自动收气泡"用未保存句柄的匿名 setTimeout → 卸载会残留 | `DesktopPet.vue` | ✅ 已修（2026-10-31）：`showMessageFor(text, ms)` 统一句柄 + `clearAllTimers()` 集中清理（含 toggleForm 两级定时器）；+5 用例 |
| D-56 | P3 | SQLAlchemy 2.1 升级被迁移完整性门禁拦下：隐式 `float` 注解映射由 `Float` 变 `Double`，5 个未显式标注类型的列（`pet_configs.opacity/tts_rate/tts_pitch/tts_volume`、`workspace.mtime`）与冻结迁移 DDL 漂移 | `app/models/pet.py`、`app/models/workspace.py` | Phase 15（先给 5 列显式 `Float` 再升 2.1；短期已 `@dependabot ignore this minor version`，PR #6 已关） |
| D-57 | P3 | vite 5→8 是 major（Node 版本/插件兼容/构建产物需回归） | `frontend/` | Phase 15（已关闭 PR #9 + `@dependabot ignore this major version`；需专门迁移任务） |

> 原则：**先修 P0/P1 的"正确性"，再谈结构搬迁**。在事务边界、迁移基线、备份导入还有问题时做领域分包，只是把混乱打包进更漂亮的新目录。

---

## 11. 演进路线

| 阶段 | 目标 | 内容 | 状态 |
|---|---|---|---|
| **Phase 0** | 架构可见、可守、可查 | 本文 + `domains.json` + AST 守护 + 债务基线 + CI 三件套 + 文档 IA + 版本/依赖/配置单一来源 + `core` 去业务化 + 根目录契约 | ✅ 本轮完成 |
| **Phase 1** | 修正确性 P0/P1 | D-01/03/04/05/08/10/14 ✅ 完成；D-02 ✅ 已评估（runbook + 守护，**远端处置待你执行**）；D-06/07/09 转入 Phase 2 | ✅ 本轮完成（2026-10-26，1229 测试全绿） |
| **Phase 2** | 收口领域边界 | D-06 仓储收口（156→0，R13）、D-07 sync 下沉（core 0 models 依赖）、D-09 SettingsView 拆分（1701→291）、前端 `kernel/shared/features` + pet 试点（R14）、D-15 守护空转修复 | ✅ 本轮完成（2026-10-27，1282 测试 + 86 前端测试全绿） |
| **Phase 3** | 可持续交付 | P3 全量迁移（27 域 → features，旧路径 392→0）、P4（8 壳删除 + kernel 依赖归位 + `kernel/http` 拆分）、D-11 启动器单一实现、D-12 备份工具、D-13 前后端 lint 进 CI、ADR-0008 | ✅ 本轮完成（2026-10-27，1284 后端 + 86 前端测试，lint/format/构建全绿） |
| **Phase 4** | 收尾与交付 | P0-2 泄漏处置（已重建仓库彻底消除）、CI 四 workflow 首跑全绿（修正 runner 上下文 / 文档审计跨平台 / Node 24）、`styles/`+`test/setup` 归位（sass 输出逐字节一致）、D-16 `backend/scripts` 纳入 ruff（13→0，含 1 个真潜伏 bug）、`var/` 数据物理迁移（SHA256+行数校验）、敏感文件守护 `--strict` | ✅ 本轮完成（2026-10-27，1284 后端 + 86 前端测试；**仅剩仓库重建需 delete_repo 权限**） |
| **Phase 5** | 结构治理 + 测试质量 + 启动可靠性 | 工作区卫生守护（`audit_workspace_hygiene.py`，check_all 16 项，清理 193MB）；后端 pytest-cov 85.18%→88.48%（+166 测试，1450 全绿）；前端 coverage-v8 +49 测试（135 全绿，kernel/http 92.23%）；启动脚本真修：根治 `Start-Process` 新窗口死锁 + `-Verify` 自检 + `var/logs`；登记 D-17~D-21 | ✅ 本轮完成（2026-10-28） |
| **Phase 6** | 修测试发现的真 bug + 补测试缺口 | D-17/18/19（auth 500、logs loguru/envelope）、D-20（avatar IDOR）、D-21（SSE token）全部修复 + 回归测试；后端 +118 测试（1598 收集 / 1588 passed），覆盖率 89.04%→92.02%；前端 +59 测试（196 passed），lines 12.76%→20.95%、阈值棘轮 20/72/52/20 进 CI；新登记 D-22~D-28 | ✅ 本轮完成（2026-10-28） |
| **Phase 7** | 修 P1/P2 缺陷 + 日志统一 + 覆盖率棘轮 | D-22~D-28 全部修复（aihot 双信封/死分支、大后天解析、AI 响应错误映射、加密单例、日志后端统一、前端定时器/监听幂等）；后端 1706 passed、覆盖率 92.02%→**96%**（CI 阈值 91→95）；前端 239 passed、lines 20.95%→32.24%（阈值 {31,76,59,31} 进 CI）；架构负向探针改 uuid 防并发假红；新登记 D-29~D-35 | ✅ 本轮完成（2026-10-30） |
| **Phase 8** | 修剩余 P2/P3 缺陷 + 测试补缺 + 启动脚本进 CI | D-29~D-35 全部修复（GlobalSearch 空态、日期 +14 天×2、阶段划分、seed utcnow、扫描僵尸、main f-string）；后端 1743 passed、覆盖率 95.92%（CI 阈值 95）；前端 291 passed、lines 37.44%（阈值 {36,78,63,36}）；新增 windows-startup workflow（Windows runner 真跑 `ops/start.ps1 -Mode dev -Verify`）；新登记 D-36~D-38 | ✅ 本轮完成（2026-10-30） |
| **Phase 9** | 修剩余 P2/P3 + 生命周期测试 + CI 增强 | D-36~D-38 修复（健康检查 baseURL、同步错误兜底、提醒去重上限）；后端 1823 passed、覆盖率 96.63%（main.py/bootstrap 100%）；前端 344 passed、lines 41.54%（阈值 {40,79,64,40}）；windows-startup 支持 PR 触发 + 前后端覆盖率 artifact；backend 覆盖率阈值对齐 95→96；新登记 D-39~D-44 | ✅ 本轮完成（2026-10-30） |
| **Phase 10** | 修剩余 P2/P3 + 组件测试 + 备份恢复安全测试 | D-39~D-45 修复（提醒 TTL/容量、BaseSelect/BaseModal、main.py fail-open 一致性+多用户备份、多行 %-style 扫描）；后端 1841 passed、覆盖率 96.68%（main.py 100%）；前端 403 passed、lines 44.01%（阈值 {43,81,67,43}）；新增 `test_backup_import_subprocess.py`（10 条，子进程隔离真实恢复/拒绝坏包）；新登记 D-46/D-47 | ✅ 本轮完成（2026-10-30） |
| **Phase 11** | 数据安全修复 + 路由/壳层测试 + 覆盖率审计 | D-46/D-47 修复（备份恢复原子替换+自动回滚、.bak 命名冲突）；后端 1897 passed、覆盖率 **96.68%→97.9%**（CI 阈值 96→97）；前端 457 passed、lines **44.01%→82.42%**（阈值改 {81,88,45,81}，新增「统计面变化」的棘轮规则）；app/router 懒加载路径全部真实 import 防失效；新登记 D-48/D-49 | ✅ 本轮完成（2026-10-31） |
| **Phase 12** | 事件总线修复 + API 端点补测 + 大型组件测试 | D-48/D-49 修复（异步 handler 静默丢失、批量失败可观测性）；后端 1927 passed、覆盖率 **97.98%→98.33%**（CI 阈值保持 97）；前端 504 passed / 34 files、lines 82.09%（阈值 {81,88,48,81}）；A 类 API 端点（auth/avatar/conversation/asset/pet）未覆盖行清零；新登记 D-50~D-54 | ✅ 本轮完成（2026-10-31） |
| **Phase 13** | 输入校验/前端行为收尾 + 仓库治理 | D-50~D-54 修复（昵称/verify-api 校验、桌宠定时器与文案顺序、文档图后台暂停/惯性）；后端 1965 passed、覆盖率 **98.33%→98.95%**（CI 阈值 97→98）；前端 510 passed、lines 82.18%（阈值 {81,88,48,81} 保持）；GitHub 治理落地（Dependabot 4 生态分组 / PR 模板 / Issue 模板 / CODEOWNERS / development.md §2.1）；新登记 D-55 | ✅ 本轮完成（2026-10-31） |
| **Phase 14** | 依赖治理 + 定时器收尾 | D-55 修复（桌宠气泡定时器统一句柄/集中清理）；**7 个 Dependabot PR 合并**（pytest/coverage、sass、Actions×5、jsdom、FastAPI 栈、前端运行时、ruff+cryptography），#9 vite major + #6 SQLAlchemy 2.1 经评估后关闭并 ignore（登记 D-56/D-57）；main 5 workflow 全绿；本地依赖对齐（ruff 0.17.3 / pytest 9.2.0 / npm ci）；后端 1965 passed / 98.94%、前端 515 passed / 82.2% | ✅ 本轮完成（2026-10-31） |

**明确不做（以及为什么）**：

- ❌ 微服务化：单机单用户，拆服务只增加运维成本。
- ❌ 一次性大搬家：644 个文件同时挪目录，回归风险远大于收益；领域的收益来自**边界收口**，不是目录名。
- ❌ 直接上 frontend `features/` 全量迁移：先修 D-03/D-08/D-10，否则只是把 bug 换个文件夹。
- ❌ 用新框架重写：现有分层（api→service→repo→model）是**健康的**（审计实测： repositories 无上行依赖、无真实循环、服务层零 FastAPI 依赖），问题在边界收口与工程底座，不在框架。

---

## 12. 决策记录（ADR）

| ADR | 结论 |
|---|---|
| [0001](docs/architecture/ADR/0001-layered-modular-monolith.md) | 采用分层模块化单体，不做微服务/一次性垂直切片 |
| [0002](docs/architecture/ADR/0002-core-is-lowest-layer.md) | `core` 是最底层，业务订阅者上移 `bootstrap` |
| [0003](docs/architecture/ADR/0003-architecture-as-code.md) | 架构即代码：领域地图 + AST 守护 + 债务棘轮 |
| [0004](docs/architecture/ADR/0004-runtime-data-and-secrets.md) | 运行期数据收敛 `var/`，配置单一入口 |
| [0005](docs/architecture/ADR/0005-version-and-dependency-single-source.md) | `VERSION` 为版本真相；`requirements.txt` 为依赖真相 |
| [0006](docs/architecture/ADR/0006-docs-information-architecture.md) | 文档 IA：架构/产品/指南/过程/设计 五分区 |
| [0007](docs/architecture/ADR/0007-frontend-feature-architecture.md) | 前端 kernel / shared / features 分层 + strangler 迁移 |
| [0008](docs/architecture/ADR/0008-null-semantics-in-requests.md) | 请求体 `null` = 清空，省略 = 不改 |
