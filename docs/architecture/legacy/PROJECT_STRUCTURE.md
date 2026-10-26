# 启明星系统 · 板块结构

> 最后更新：2026-09-27
> 版本：v0.7.0

## 项目定位

**启明星（Venustech System）** —— AI 驱动的个人操作系统。整合任务、项目、文档、知识、资产、生活、成长等个人数据，通过 AI 助手提供智能分析、自动归档和决策辅助。支持 Web 端和移动端（Capacitor Android）。

---

## 一、根目录结构

```
VenustechSystem/
├── backend/              # FastAPI 后端（Python 3.11+）
├── frontend/             # Vue 3 + TypeScript 前端（含 Android 移动端）
├── docs/                 # 项目文档（设计/PRD/管理/方法论）
├── scripts/              # 审计与检查脚本
├── server.js             # 统一 Web 服务（静态文件 + API 代理）
├── package.json          # 根目录 Node 依赖（仅 http-proxy）
├── setup.bat             # 环境初始化（运行一次）
├── start-dev.bat         # 开发环境一键启动
├── start-demo.bat        # 演示环境（丰富示例数据）
├── start-mobile.bat      # 移动端服务
├── push-branches.bat     # 推送所有分支
├── CHANGELOG.md          # 变更日志（30.8KB，完整历史）
├── CONTRIBUTING.md       # 贡献指南
└── README.md             # 项目说明
```

**特殊说明**：
- `.git/` 是目录联接（Junction），指向 `C:\Users\21722\qimingxing-git-repo`（Git 数据存 C 盘，项目文件存 D 盘）
- `.git-broken-20260917/` 是 9 月 17 日 Git 损坏时的备份，待确认后清理
- `.qm-token` 是本地令牌文件，已被 `.gitignore` 排除，不入库
- `backend/data_*/` 是运行期数据库，已被 `.gitignore` 排除

---

## 二、九大业务板块

### 板块 1：核心基础（Core）

| 层 | 路径 | 说明 |
|----|------|------|
| API | `backend/app/api/auth.py`, `sync.py`, `events.py` | 认证、数据同步、事件 |
| 模型 | `backend/app/models/user.py`, `settings.py` | 用户、设置 |
| 服务 | `backend/app/services/security_service.py`, `settings_service.py` | 安全、设置 |
| 前端 | `frontend/src/views/Settings/` | 设置页面 |

**职责**：JWT 认证、用户管理、系统设置、多端数据同步、事件总线。

---

### 板块 2：个人知识（Knowledge）

| 层 | 路径 | 说明 |
|----|------|------|
| API | `document.py`, `learning.py`, `resource.py`, `experience.py`, `review.py`, `folder.py` | 文档/学习/资源/经验/复盘/文件夹 |
| 模型 | `document.py`, `learning.py`, `resource.py`, `review.py`, `folder.py` | 对应数据模型 |
| 服务 | `document_service.py`, `experience_service.py`, `review_service.py` | 业务逻辑 |
| 前端 | `views/Document/`, `views/Learning/`, `views/Resource/`, `views/Experience/`, `views/Review/` | 5 个页面 |
| 组件 | `components/document/` (2) | 文档专用组件 |

**职责**：个人知识库的全生命周期管理——文档编写、学习记录、资源收藏、经验沉淀、定期复盘。

---

### 板块 3：执行管理（Execution）

| 层 | 路径 | 说明 |
|----|------|------|
| API | `task.py`, `project.py`, `workflow.py`, `workspace.py` | 任务/项目/工作流/工作区 |
| 模型 | `task.py`, `project.py`, `workflow.py`, `workspace.py` | 对应数据模型 |
| 服务 | `task_service.py`, `project_service.py`, `workflow_service.py`, `workspace_service.py` | 业务逻辑 |
| 前端 | `views/Task/`, `views/Project/`, `views/Workflow/`, `views/Workspace/` | 4 个页面 |
| 组件 | `components/task/` (1) | 任务专用组件 |

**职责**：从待办到项目的完整执行链路——任务管理、项目跟踪、工作流自动化、多工作区隔离。

---

### 板块 4：个人成长（Growth）

| 层 | 路径 | 说明 |
|----|------|------|
| API | `identity.py`, `growth.py`, `life.py`, `health.py` | 身份/成长/生活/健康 |
| 模型 | `identity.py`, `growth.py`, `life.py` | 对应数据模型 |
| 服务 | `identity_service.py`, `growth_service.py`, `life_service.py` | 业务逻辑 |
| 前端 | `views/Identity/`, `views/Growth/`, `views/Life/` | 3 个页面 |

**职责**：个人成长数据化——多重身份管理、成长轨迹记录、生活日志、健康数据。

---

### 板块 5：AI 交互（AI）

| 层 | 路径 | 说明 |
|----|------|------|
| API | `conversation.py`, `assistant.py`, `panel.py`, `plugins.py` | 对话/助手/面板/插件 |
| 模型 | `conversation.py`, `panel.py` | 对话、面板模型 |
| 服务 | `conversation_service.py`, `assistant_service.py`, `panel_service.py` | 业务逻辑 |
| 前端 | `views/Conversation/`, `views/Assistant/`, `views/AiHot/` | 3 个页面 |
| 插件 | `backend/app/plugins_builtin/` (2) | 内置插件 |

**职责**：AI 原生交互——多轮对话、AI 助手、快捷指令面板、插件扩展。

---

### 板块 6：资产安全（Asset & Security）

| 层 | 路径 | 说明 |
|----|------|------|
| API | `asset.py`, `vault.py`, `backup.py`, `security.py` | 资产/保险箱/备份/安全 |
| 模型 | `asset.py`, `vault.py`, `audit.py` | 资产、保险箱、审计 |
| 服务 | `asset_service.py`, `vault_service.py`, `backup_service.py`, `security_service.py` | 业务逻辑 |
| 前端 | `views/Asset/`, `views/Vault/` | 2 个页面 |

**职责**：个人资产与敏感数据保护——资产管理、密码保险箱、数据备份、安全审计。

---

### 板块 7：数据可视化（Dashboard）

| 层 | 路径 | 说明 |
|----|------|------|
| API | `dashboard.py`, `report.py` | 仪表盘、报告 |
| 服务 | `dashboard_service.py`, `report_service.py` | 聚合统计、报告生成 |
| 前端 | `views/Dashboard/`, `views/Report/` | 2 个页面 |

**职责**：个人数据全景——多维度仪表盘、自动生成分析报告。

---

### 板块 8：系统管理（System）

| 层 | 路径 | 说明 |
|----|------|------|
| API | `settings.py`, `notification.py`, `logs.py`, `avatar.py`, `pet.py`, `rules.py` | 设置/通知/日志/头像/宠物/规则 |
| 模型 | `settings.py`, `notification.py`, `pet.py`, `avatar.py`, `settings_history.py` | 对应模型 |
| 服务 | `settings_service.py`, `notification_service.py`, `pet_service.py`, `avatar_service.py` | 业务逻辑 |
| 前端 | `views/Settings/`, `views/Pet/`, `views/Avatar/` | 3 个页面 |
| 组件 | `components/pet/` (1) | 宠物组件 |

**职责**：系统运维与个性化——全局设置、通知中心、操作日志、虚拟宠物、头像管理。

---

### 板块 9：移动端（Mobile）

| 路径 | 说明 |
|------|------|
| `frontend/android/` (170 文件) | Capacitor Android 原生工程 |
| `frontend/capacitor.config.ts` | Capacitor 配置 |
| `start-mobile.bat` | 移动端一键启动 |
| `.github/workflows/android-build.yml` | Android CI 构建 |

**职责**：将 Web 应用打包为 Android APK，支持离线队列（弱网不丢数据）、移动端交互适配（ActionSheet 等）。

---

## 三、技术架构

### 后端（FastAPI）

```
backend/app/
├── api/              # 34 个路由模块（HTTP 端点）
├── core/             # 14 个核心模块（配置/数据库/中间件）
├── models/           # 26 个 SQLAlchemy 模型
├── repositories/     # 31 个仓储层（数据访问）
├── schemas/          # 23 个 Pydantic 模式
├── services/         # 34 个业务服务
├── plugins_builtin/  # 2 个内置插件
├── config.py         # 配置管理
├── database.py       # 数据库连接
├── main.py           # 应用入口
├── migrate.py        # 迁移工具
└── seed.py           # 种子数据
```

**分层原则**：api → services → repositories → models，单向依赖。

### 前端（Vue 3 + TypeScript）

```
frontend/src/
├── api/              # 30 个 API 模块（类型化请求）
├── app/              # 4 个应用级模块
├── components/       # 39 个组件（common 20 + layout 15 + 业务 4）
├── composables/      # 24 个组合式函数
├── constants/        # 2 个常量
├── directives/       # 1 个自定义指令
├── stores/           # 2 个 Pinia 状态
├── styles/           # 4 套主题样式
├── types/            # 22 个类型定义
├── utils/            # 4 个工具函数
└── views/            # 23 个页面目录
```

**三套主题**：奶油糖果（默认）、国风雅集、深空档案，通过 CSS 变量 + data-theme 切换。

### 统一 Web 服务（server.js）

- 提供前端静态文件（`frontend/dist/`）
- 代理 `/api/*` 到 FastAPI 后端（`http://127.0.0.1:8765`）
- 单端口对外暴露，cloudflared 只需隧道一个端口
- 默认端口 3000，可通过 `PORT` 环境变量修改

---

## 四、文档体系

```
docs/
├── README.md                 # 文档总索引（待建）
├── PROJECT_STRUCTURE.md      # 本文件（板块结构）
├── DEVELOPMENT.md            # 开发规范（待建）
├── methodology.md            # 开发方法论
├── design/                   # 23 个设计文档
├── prd/                      # 10 个产品需求文档
├── management/               # 25 个管理文档
├── backend/                  # 后端文档
├── frontend/                 # 前端文档（含 frontend-delivery-note.md）
└── assets/                   # 文档资源
```

---

## 五、脚本工具

| 脚本 | 用途 |
|------|------|
| `scripts/check_all.py` | 全量检查（6.7KB） |
| `scripts/audit_delivery.py` | 交付物审计（6.1KB） |
| `scripts/audit_hardcoded_colors.py` | 硬编码颜色审计（3.9KB） |
| `scripts/check_versions.py` | 版本检查（1.9KB） |
| `scripts/audit_plain_fallback.py` | 纯文本回退审计（2KB） |
| `scripts/dev.ps1` | 开发辅助脚本（4.3KB） |

---

## 六、Git 分支策略

| 分支 | 状态 | 说明 |
|------|------|------|
| `main` | ✅ 活跃 | 主分支，始终可运行 |
| `mod-tools` | ✅ 已合并 | 工具模块开发（已合并到 main） |
| `mod-asset` 等 7 个 | ⚠️ 已合并停滞 | 指向同一提交，待清理 |
| `feature-mobile-deepseek-assistant` | ⚠️ 已合并停滞 | 移动端功能，待清理 |

**当前状态**：9 个分支已完全合并到 main（领先 0 提交），待用户确认后删除。
