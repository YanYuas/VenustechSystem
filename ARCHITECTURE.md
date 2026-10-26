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
| 开发 | `start-dev.bat` / `scripts/dev.ps1` | Vite + uvicorn(`--reload`) | 5173 / 8765 | `backend/data` | 写代码 |
| 演示 | `start-demo.bat` | 同上，`VENUSTECH_DATA_DIR=backend/data_demo` | 5173 / 8765 | `backend/data_demo` | 给别人看，不污染真实库 |
| 统一/移动 | `start-mobile.bat` | server.js + uvicorn | **3000**（对外）/ 8765（回环） | `backend/data` | 局域网/手机/Tailscale |

**关键边界**：后端永远只绑 `127.0.0.1`；对外只暴露 `server.js` 的 3000。`server.js` 做三件事：托管 `frontend/dist`、把 `/api/*` 代理到 8765、校验 `X-API-Token`（回环来源豁免，PC 前端零配置）。

> ⚠️ 已知安全问题（P0，待修）：`server.js` 当前对**回环来源无条件放行**。若用 cloudflared 等隧道暴露 3000，隧道会把公网请求伪装成回环，令牌形同虚设。修复方案见 §10 债务表 D-01。

---

## 3. 一条请求的完整生命周期

以「任务列表页加载」为例，逐跳对应到文件——这是理解本项目的**唯一推荐路径**：

| # | 发生什么 | 文件 |
|---|---|---|
| 1 | 应用装配：Pinia、Router、全局错误处理、离线队列接线 | `frontend/src/app/main.ts` |
| 2 | 路由匹配，**懒加载**页面 | `frontend/src/app/router/index.ts` |
| 3 | 页面组件（视图只管渲染与交互） | `frontend/src/views/Task/TaskListView.vue` |
| 4 | 组合式函数承接视图逻辑（可复用、可测） | `frontend/src/composables/useTask.ts` |
| 5 | 领域 API 封装（路径/类型/参数） | `frontend/src/api/task.ts` |
| 6 | **唯一 HTTP 漏斗**：baseURL、token、超时、重试、离线入队、SSE、信封解包、错误提示 | `frontend/src/api/http.ts` |
| 7 | 生产环境经边缘服务（dev 环境 Vite 直连 8765） | `ops/server/server.js` |
| 8 | FastAPI 入口：CORS、统一异常、插件路由挂载 | `backend/app/main.py` |
| 9 | 路由聚合 `/api/v1` | `backend/app/api/__init__.py` |
| 10 | 该模块路由 + 依赖注入（Session / 当前用户） | `backend/app/api/task.py`、`api/deps.py` |
| 11 | 业务逻辑（状态机、互斥、权限、事务） | `backend/app/services/task_service.py` |
| 12 | 数据访问 | `backend/app/repositories/task_repo.py` |
| 13 | ORM 模型 → SQLite | `backend/app/models/task.py` → `app.db` |
| 14 | 统一响应信封 `{code, message, data}` | `backend/app/core/response.py` |
| 15 | 前端解包 `body.data`，非 0 code 抛 ApiError | `frontend/src/api/http.ts` |

**写路径的额外一跳**：service 提交后 `event_bus.publish(EVENT_TASK_COMPLETED, ...)` → 订阅者（`app/bootstrap/event_handlers.py`、`app/bootstrap/growth_handlers.py`）异步处理通知、AI 摘要、成长经验值。**事件是解耦手段，不是业务事实来源**——数据库仍是唯一真相。

> 读代码顺序建议：`api/task.py`（薄）→ `services/task_service.py`（厚，业务都在这里）→ `repositories/task_repo.py`（薄）→ `models/task.py`。看一个模块就够，全部 33 个模块同构。

---

## 4. 依赖规则（唯一权威，机器强制）

### 4.1 后端五层

| 层 | 目录 | 职责 | 允许依赖 | 禁止 |
|---|---|---|---|---|
| API | `app/api/` | HTTP 路由、参数校验、调用 service、返回信封 | services, schemas, core, root | **models**（运行时）、**repositories**、业务逻辑 |
| Schema | `app/schemas/` | Pydantic DTO（入参/出参/分页） | schemas, core | services, models |
| Service | `app/services/` | 业务规则、状态机、事务编排、事件发布 | repositories, models, schemas, core | **fastapi**、api |
| Repository | `app/repositories/` | 数据访问（CRUD/查询） | models, core | services, api |
| Model | `app/models/` | SQLAlchemy ORM、表结构 | models, core | 任何上层 |
| Core | `app/core/` | **无业务语义的基础设施**：事件总线、加密、缓存、插件、日志、异常、响应、同步适配 | core, models | **services / repositories / api / schemas** |
| 组合根 | `app/main.py`、`app/bootstrap/`、`api/deps.py` | 装配：lifespan、插件、订阅者、Session/User 依赖 | 任意 | 承载业务规则 |

> `TYPE_CHECKING` 块内的 import 是**类型注解**，零运行时开销，不算违规（API 层合法引用 `User` 类型）。

### 4.2 前端分层

```
views（页面，只渲染/交互）
  → composables（视图逻辑，可测）
    → api/*.ts（领域接口封装）
      → api/http.ts（唯一 HTTP 漏斗）
```
- `views/` **不得** `import` 另一个 view 的实现（跨域页面跳转走 router）。
- `components/common|layout` 是**共享 UI**，不得 import 业务 `api/`。
- `types/` 是前后端契约的前端侧；新增字段时**两边同时改**（当前已知 13 处漂移，见 §10）。

### 4.3 违反会怎样

`python scripts/audit_architecture.py` 用 AST 解析真实 import 图，逐条报告 `规则号 + file:line`，退出码非 0。
已知但暂不修的历史违规登记在 `scripts/architecture_baseline.json`（棘轮机制：**只减不增**）。

---

## 5. 领域地图（Bounded Contexts）

8 个领域，**互斥且完整**覆盖全部业务模块（33 个 API 模块 + 15 个子能力）。
机器可读版本：`docs/architecture/domains.json`（新增模块必须先登记，否则守护失败）。

| 领域 | 职责 | 模块 | 前端目录 |
|---|---|---|---|
| **platform** 平台底座 | 认证、设置、安全、备份、同步、事件、健康、日志、通知、规则、插件 | auth, user, settings, security, backup, sync, events, health, logs, notification, rules, plugins, audit, settings_history | `Settings/`, `NotFound/` |
| **execution** 执行管理 | 任务、项目、工作流、工作区 | task, project, workflow, workspace | `Task/`, `Project/`, `Workflow/`, `Workspace/` |
| **knowledge** 个人知识 | 文档、文件夹、学习/间隔重复、资源、模板、经验、复盘 | document, folder, learning, flashcard, study_plan, study_time, domain, resource, template, experience, review | `Document/`, `Learning/`, `Resource/`, `Experience/`, `Review/` |
| **growth** 个人成长 | 成长 EXP、身份、习惯、心情、日记 | growth, identity, life, habit, habit_checkin, mood, diary | `Growth/`, `Identity/`, `Life/` |
| **assistant** AI 交互 | 对话、助手、快捷面板、LLM 客户端与提示词 | conversation, assistant, panel, ai | `Conversation/`, `Assistant/`, `AiHot/` |
| **companion** 桌宠陪伴 | 桌宠状态/动作、形象、头像 | avatar, pet | `Avatar/`, `Pet/` |
| **asset** 资产沉淀 | SOP/Prompt/Skill/项目记忆、保险箱 | asset, vault, sop, sop_version, skill, project_memory, prompt | `Asset/`, `Vault/` |
| **insight** 数据洞察 | 首页聚合、报告（只读，不写别人的表） | dashboard, report | `Dashboard/`, `Report/` |

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
│   ├── migrations/             Alembic（0001–0020，见 §10 D-05）
│   ├── tests/                  1165 条测试（api/production/architecture/logging_contract）
│   ├── scripts/                后端专用：冒烟/探针/种子/演示数据
│   ├── requirements.txt        ★ 运行时依赖唯一来源
│   ├── requirements-dev.txt    测试/工具依赖
│   ├── pyproject.toml          仅工具配置（pytest/ruff），**不声明依赖**
│   └── data/                   默认运行期数据（gitignored；长期目标见 §7）
├── frontend/                   Vue3 + TS + Vite（详见 §4.2）
│   ├── src/
│   │   ├── app/                main.ts / App.vue / router / errorHandler
│   │   ├── views/              23 个页面目录（一域一目录）
│   │   ├── composables/        视图逻辑（useXxx）
│   │   ├── api/                30 个领域 API + http.ts（唯一漏斗）
│   │   ├── components/         common(共享) / layout(壳) / 业务组件
│   │   ├── stores/             Pinia（offlineQueue 是唯一活 store）
│   │   ├── types/              与后端 schemas 对应的前端类型
│   │   ├── styles/             4 套主题 × 明暗（CSS 变量）
│   │   ├── constants/ directives/ utils/
│   │   └── test/               vitest setup
│   ├── public/                 manifest + sw.js（PWA）
│   ├── android/                Capacitor 原生工程（构建产物，勿手改）
│   └── scripts/                前端专用测试脚本（esbuild）
├── ops/                        ★ 运行时与运维（不是业务代码）
│   ├── server/                 统一 Web 服务：server.js + package.json + node_modules
│   ├── push-branches.bat       推送辅助
│   └── （规划）scripts/ 唯一启动实现、ci/ 门禁脚本、runbooks/
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
├── .github/workflows/          CI：backend / frontend / repo-guard / android-build
├── ARCHITECTURE.md             ★ 本文（架构唯一权威）
├── VERSION                     ★ 版本单一事实来源
└── *.bat                       仅保留 4 个用户启动器（setup/start-dev/start-demo/start-mobile）
```

**根目录契约**：根目录只允许上表列出的条目；新增根级文件前先想清楚它属于哪一层（源码→backend/frontend，运维→ops，脚本→scripts，文档→docs，数据→var）。由守护规则 R9 强制。

---

## 7. 运行期数据与配置

**唯一配置入口**：`backend/app/config.py` 的 `Settings`，前缀 `VENUSTECH_`，模板见 `backend/.env.example`。

**数据目录（最重要的一个变量）**：
- 开发默认 `backend/data`（**相对 `backend/` 解析，与启动方式无关** —— 曾经用 `./data` 导致从仓库根启动时生成第二份数据库）。
- 由 `VENUSTECH_DATA_DIR` 覆盖（演示库、分支隔离、测试都用它）。
- 目录内包含：`app.db`（SQLite，WAL）、`logs/`、`backups/`、`documents/`、`plugins/`、`.encryption_key`。

**约定**：仓库内的一切运行期数据都属于 `var/`（已整体 gitignore）。**不要把数据库、密钥、日志放进任何会被提交的位置。**

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
10. **验证**：`python scripts/check_all.py`（13 项全绿）。
11. **记账**：CHANGELOG + 需要时 `docs/architecture/ADR/`。
12. **收口**：`python scripts/audit_architecture.py` 必须 0 新增违规。

---

## 9. 质量门禁与验证

**唯一验证入口**：`python scripts/check_all.py`（13 项）；CI 必须 `--strict`（缺依赖=失败，不给假绿）。

| 守护 | 命令 | 守什么 |
|---|---|---|
| 架构 | `scripts/audit_architecture.py` | 分层方向、core 隔离、领域归属、路由/模型注册、根目录契约、**事务边界(R11)**、**迁移基线(R12)**、前端边界 |
| 后端测试 | `pytest backend/tests` | 1165 条：API 形状 + 生产行为 + 数据库基础设施 |
| 后端冒烟 | `backend/scripts/smoke_backend.py` | 真实启动 + 迁移 + 端到端断言 |
| 版本一致 | `scripts/check_versions.py` | 5 处版本 == `VERSION` |
| 文档链接 | `scripts/audit_docs_links.py` | 全量 md 相对链接与内联路径 |
| 测试质量 | `scripts/audit_test_quality.py` | 永真断言/无断言/吞异常（"缺陷在也全绿"的写法） |
| 日志格式 | `scripts/audit_log_format.py` | loguru `{}` 占位符（`%s` 会静默丢参数） |
| 交付物 | `scripts/audit_delivery.py` | 一键脚本真能启动、冒烟不含水分 |
| 设计令牌 | `frontend/scripts/audit-tokens.py` | 用了不存在的 CSS 变量 |
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
| D-02 | **P0** | `origin/feature/phase2-development` 包含真实用户库 `backend/data/app.db`（606KB，公开可拉） | 泄漏提交 `6b5c2dd`，仅该分支可达；**无 `.encryption_key`**（密文字段安全） | ⚠️ 已评估 + 检测守护 + runbook；**待你执行删分支/重建远端**（不可逆） |
| D-03 | **P0** | 备份导入 100% 失败：`FormData` 被 `JSON.stringify` 后发 JSON，后端要 multipart → 422 | `frontend/src/api/dashboard.ts` + `api/http.ts` ↔ `backend/app/api/backup.py` | ✅ 已修（2026-10-26）：`http.postForm` + 真实 multipart 运行时断言 11/11 |
| D-04 | P1 | **事务边界下沉**：`BaseRepository` 每个方法内部 commit，service 再 commit → 多步操作无原子性 | `repositories/base.py` | ✅ 已修（2026-10-26）：repo 只 flush、service 控 commit、get_db 兜底；8 条原子性测试 + 守护 R11 |
| D-05 | P1 | 迁移基线失效：`0001` 用 `create_all()`，11 张基线表无 DDL；升级库缺 11 个索引 | `migrations/versions/0001_initial.py` | ✅ 已修（2026-10-26）：0001 冻结显式 DDL（49 表/79 索引）+ 0021 对账 + 6 条完整性测试 + 守护 R12 |
| D-06 | P1 | Repository 层名存实亡：16/31 service 直连 ORM；service 9441 行 vs repo 1412 行 | 审计报告 §2 | Phase 2（事务边界已修，下一轮收口 repo 覆盖） |
| D-07 | P1 | `core/sync.py` 藏 389 行领域逻辑；core 内共 815 行业务代码 | 审计报告 §2 | Phase 2 |
| D-08 | P1 | 前端 13 处前后端契约漂移（几乎都是"后端有、前端类型没有"） | `frontend/src/types/*` vs `backend/app/schemas/*` | ✅ 已修 13/13（2026-10-26）；剩余：TaskStatus 需后端补 Literal、24 处 `| null` 语义待定 |
| D-09 | P1 | 前端 god 组件：`SettingsView` 1577 行；16 个 view >500 行；`http.ts` 378 行 9 类职责 | 审计报告 §4–§6 | Phase 2 |
| D-10 | P1 | 前端死代码约 1188 行（`AppHeader`/`AppSidebar`/`stores/app.ts` 等） | 审计报告 §7 | ✅ 已修（2026-10-26）：15 文件 / 1625 行，typecheck ×5 全绿 |
| D-11 | P2 | 5 个启动器重复实现 venv/端口/令牌逻辑（4 份 venv 解析、2 种令牌生成） | `*.bat` + `scripts/dev.ps1` | Phase 2 |
| D-12 | P2 | `.git` 是 Junction 指向 `C:\Users\21722\qimingxing-git-repo`：备份项目目录 ≠ 备份历史 | 文件系统 | Phase 1（写备份 runbook） |
| D-13 | P2 | 无 lint：ESLint/Prettier/ruff 全缺 | — | Phase 2 |
| D-14 | P2 | `server.js` 是唯一鉴权点却零测试 | `ops/server/server.js` | ✅ 已修（2026-10-26）：`ops/server/test` 16 用例 + CI edge-server job |

> 原则：**先修 P0/P1 的"正确性"，再谈结构搬迁**。在事务边界、迁移基线、备份导入还有问题时做领域分包，只是把混乱打包进更漂亮的新目录。

---

## 11. 演进路线

| 阶段 | 目标 | 内容 | 状态 |
|---|---|---|---|
| **Phase 0** | 架构可见、可守、可查 | 本文 + `domains.json` + AST 守护 + 债务基线 + CI 三件套 + 文档 IA + 版本/依赖/配置单一来源 + `core` 去业务化 + 根目录契约 | ✅ 本轮完成 |
| **Phase 1** | 修正确性 P0/P1 | D-01/03/04/05/08/10/14 ✅ 完成；D-02 ✅ 已评估（runbook + 守护，**远端处置待你执行**）；D-06/07/09 转入 Phase 2 | ✅ 本轮完成（2026-10-26，1229 测试全绿） |
| **Phase 2** | 收口领域边界 | Repository 收口（D-06）、`core/sync` 领域逻辑下沉（D-07）、前端 `kernel/shared/features` 分层试点（单领域先迁） | 待批 |
| **Phase 3** | 可持续交付 | lint、`server.js` 测试、启动器单一实现、发布/备份 runbook、`.git` 位置治理 | 待批 |

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
