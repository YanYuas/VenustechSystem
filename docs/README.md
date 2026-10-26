# 启明星系统 · 文档总索引

> `docs/` 的唯一入口。**先看「10 秒导航」，再进具体目录。**
> 本索引最后更新：2026-10-26（文档 IA 重组：架构 / 产品 / 指南 / 运维 / 过程 五类归档）

## 10 秒导航：我要做什么？

| 我要… | 去哪 | 备注 |
|---|---|---|
| 了解系统分层、模块边界、关键架构决策 | [1. 架构与决策](#1-架构与决策architecture) | 现行架构 + 旧架构存档（archived） |
| 知道产品现在做什么、验收标准是什么 | [2. 产品与需求](#2-产品与需求product) → `product/prd/v2-current/` | **现行**以 v2-current + M01–M09 为准 |
| 查 UI 规范、交互规则、主题效果 | [2 → UI 设计与交互](#ui-设计与交互) | 规范在 `product/ui/`，HTML 主题画廊在 `design/` |
| 本地跑起来 / 写代码前对齐规范 | [3. 开发指南](#3-开发指南guides) | 后端、前端、提交与分支、协作协议 |
| 部署、数据目录、演示数据、排障 | [4. 运维手册](#4-运维手册) | 备份 runbook 已建；部署 / 排障入口见该节 |
| 查某次交付 / 评估的结论、当时怎么决策 | [5. 历史过程记录](#5-历史过程记录archived) | 全部 **archived，只读，不代表现状** |
| 写复盘 / 交接 / 审计 | [5. 历史过程记录](#5-历史过程记录archived) | 按日期归档，附 2026-08～2026-10 全量清单 |

**现行 vs archived（重要）**

- ✅ **现行**：`architecture/`（除 legacy）、`product/requirements/`、`product/prd/v2-current/`、`product/ui/`、`guides/`。
- 🗄️ **archived 仅供参考**：`architecture/legacy/`、`product/prd/v1-archived/`、`process/archive/` 下**全部**文档。它们是历史快照，数字/结论/路径可能已过时，**不得作为开发依据**，只用于追溯与交接。

---

## 1. 架构与决策（architecture/）

**什么时候看**：接手系统、新增模块、做跨层改动、评审依赖方向、需要引用历史架构决策时。

| 文档 | 状态 | 用途 |
|---|---|---|
| [ARCHITECTURE.md](../ARCHITECTURE.md) | 现行 | **架构唯一入口**（位于仓库根）：分层、模块边界、依赖规则、§12 决策记录索引 |
| [domains.json](architecture/domains.json) | 现行 | 领域 / 模块划分的机器可读描述（脚本与 CI 消费） |
| `ADR/`（架构决策记录） | 现行 | [ADR 目录](architecture/ADR/)：0001 分层模块化单体 / 0002 core 最底层 / 0003 架构即代码 / 0004 运行期数据与密钥 / 0005 版本与依赖单一来源 / 0006 文档 IA（本索引的依据） |
| [legacy/02-技术架构.md](architecture/legacy/02-技术架构.md) | 🗄️ archived | v1.0 技术架构草案（Electron / asyncpg 等方案已推翻） |
| [legacy/02-技术架构-v2.0.md](architecture/legacy/02-技术架构-v2.0.md) | 🗄️ archived | 2026-08-27 技术架构 v2.0（已被 ARCHITECTURE.md 取代） |
| [legacy/PROJECT_STRUCTURE.md](architecture/legacy/PROJECT_STRUCTURE.md) | 🗄️ archived | 九大业务板块结构快照（数量数字已过时） |

> 2026-10-26 起：旧架构文档从 `docs/design/`、`docs/` 根迁入 `architecture/legacy/`，保留历史但不再维护。

---

## 2. 产品与需求（product/）

**什么时候看**：写需求、做功能设计、验收、拆分模块任务时。现行需求只看 `product/` 下的非 archived 目录。

### 需求分析

| 文档 | 状态 | 用途 |
|---|---|---|
| [01-需求分析.md](product/requirements/01-需求分析.md) | 现行 | 一期需求分析：业务背景、目标用户、功能范围 |

### PRD · 现行（v2-current）

| 文档 | 用途 |
|---|---|
| [00-模块深度开发PRD总览.md](product/prd/v2-current/00-模块深度开发PRD总览.md) | M01–M09 总览、模块边界与统一验收口径 |
| [M01-Dashboard深度开发PRD.md](product/prd/v2-current/M01-Dashboard深度开发PRD.md) | 首页总览（个人 OS 桌面） |
| [M02-Task深度开发PRD.md](product/prd/v2-current/M02-Task深度开发PRD.md) | 任务管理（列表 / 看板、子任务、优先级） |
| [M03-Document深度开发PRD.md](product/prd/v2-current/M03-Document深度开发PRD.md) | 知识文档（第二大脑、Markdown 编辑、检索） |
| [M04-Conversation深度开发PRD.md](product/prd/v2-current/M04-Conversation深度开发PRD.md) | 第二分身（本地 AI、隐私优先） |
| [M05-Review深度开发PRD.md](product/prd/v2-current/M05-Review深度开发PRD.md) | 复盘（日 / 周 / 月回顾与成长追踪） |
| [M06-Project深度开发PRD.md](product/prd/v2-current/M06-Project深度开发PRD.md) | 项目管理（多任务聚合空间） |
| [M07-Pet深度开发PRD.md](product/prd/v2-current/M07-Pet深度开发PRD.md) | 桌宠（情感化陪伴） |
| [M08-Settings深度开发PRD.md](product/prd/v2-current/M08-Settings深度开发PRD.md) | 设置（AI / 主题 / 数据 / 快捷键） |
| [M09-Infrastructure深度开发PRD.md](product/prd/v2-current/M09-Infrastructure深度开发PRD.md) | 基础设施（备份 / 通知 / 搜索 / 事件总线 / 认证） |
| [PRD-启明星系统-v2.0-二期.md](product/prd/v2-current/PRD-启明星系统-v2.0-二期.md) | 二期整体 PRD v2.0（状态：草稿） |

### PRD · 已归档（v1-archived）

| 文档 | 状态 | 说明 |
|---|---|---|
| [PRD-启明星系统-v1.0.md](product/prd/v1-archived/PRD-启明星系统-v1.0.md) | 🗄️ archived | 一期已交付版本，仅追溯用 |
| [PRD-模块-*.md](product/prd/v1-archived/PRD-模块-asset.md)（8 份） | 🗄️ archived | 2026-09-18 模块 PRD，已被 v2-current 的 M01–M09 取代：asset / companion / dashboard / execution / knowledge / life / platform / tools |

### UI 设计与交互

| 文档 / 资源 | 状态 | 用途 |
|---|---|---|
| [03-UI设计规范.md](product/ui/03-UI设计规范.md) | 现行 | 视觉规范、设计令牌、组件样式基线 |
| [03-UI组件index.md](product/ui/03-UI组件index.md) | 现行 | UI 组件索引与用法 |
| [04-交互设计.md](product/ui/04-交互设计.md) | 现行 | 交互流程与状态设计 |
| [UI组件画廊.html](design/UI组件画廊.html) | 现行参考 | 主题总览；另有 [奶油糖果](design/UI组件画廊-奶油糖果.html) / [国风雅集](design/UI组件画廊-国风雅集.html) / [深渊档案](design/UI组件画廊-深渊档案.html) / [史诗典藏](design/UI组件画廊-史诗典藏.html) 四套主题 |
| [ref-ui-2.png](design/ref-ui-2.png) · [screenshot-main.png](assets/screenshot-main.png) | 参考图 | UI 参考图与主界面截图 |

> `design/` 只放 UI 画廊 HTML 与参考图；**文档不放这里**。

---

## 3. 开发指南（guides/）

**什么时候看**：动手写代码前、提交前、开分支前。

| 文档 | 什么时候看 | 内容 |
|---|---|---|
| [development.md](guides/development.md) | 新环境第一次搭好之后必读 | 分支策略、提交规范、前后端代码规范、启动方式、质量检查 |
| [backend.md](guides/backend.md) | 改后端 / 查 API 契约 / 排查后端问题 | 后端架构、API 清单、SSE 规范、数据库、测试、常见问题（v1.12） |
| [frontend.md](guides/frontend.md) | 改前端 / 查前端模块与构建 | 前端架构、核心模块、开发规范、构建部署、与后端对接 |
| [branch-development.md](guides/branch-development.md) | 开分支、切分支、需要回退时 | 分支工作流、3 个必须先处理的坑、四种回退粒度 |
| [collaboration.md](guides/collaboration.md) | 多人 / 多智能体协作前 | 协作协议 6 条、本轮已落地事项、待拍板项 |
| [methodology.md](guides/methodology.md) | 理解工程约定从哪来 | 方法论、目录结构、版本控制、五大配置管理原则 |

> 根 `README.md` 只留「入口 + 快速开始」，`CONTRIBUTING.md` 只留「流程与纪律」，本目录存**代码规范细节**。三处验证命令若不一致，以 `guides/development.md` 为准。

---

## 4. 运维手册

**什么时候看**：部署、启动演示、准备演示数据、排查环境与数据目录问题时。

> 现状：**`docs/runbooks/` 已建立**（备份恢复 / 数据泄漏处置两份）；部署 / 发布 / 故障处置 runbook 待补。以下为当前可用的运维入口，均为现行。

| 场景 | 入口 |
|---|---|
| 备份与恢复（人工步骤 + 备份契约） | [runbooks/backup.md](runbooks/backup.md) |
| **真实数据库被提交进 Git 历史（P0）** | [runbooks/security-incident-db-leak.md](runbooks/security-incident-db-leak.md) |
| 访问令牌轮换（手机端配对） | `cd ops/server && npm run token:rotate` · 见 [README.md](../README.md) 部署章节 |
| 一键启动（开发 / 演示 / 移动端） | 仓库根 [start-dev.bat](../start-dev.bat) · [start-demo.bat](../start-demo.bat) · [start-mobile.bat](../start-mobile.bat) |
| 脚本化启动与守护检查 | [scripts/dev.ps1](../scripts/dev.ps1) · `scripts/check_all.py`（一键校验，项数以脚本输出为准） |
| 环境变量模板 | [backend/.env.example](../backend/.env.example)（照此配置，勿提交真实 `.env`） |
| 演示数据 / 种子数据 | [演示数据说明-2026-09-19.md](process/archive/2026-08-2026-10/演示数据说明-2026-09-19.md)（🗄️ archived，操作步骤仍可参照） |
| 后端环境搭建 / 排障 | [guides/backend.md](guides/backend.md) §三「开发环境搭建」、§十四「常见问题」 |
| 数据库与迁移纪律 | [CONTRIBUTING.md](../CONTRIBUTING.md)（数据库 / 迁移章节） |
| 生产托管与令牌鉴权 | `ops/server/`（静态托管 + `/api` 代理 + 令牌），说明见根 [README.md](../README.md) 部署章节 |
| 备份 / 数据目录 | 数据目录由 `VENUSTECH_DATA_DIR` 决定；备份契约与人工步骤见 [runbooks/backup.md](runbooks/backup.md) |

---

## 5. 历史过程记录（archived）

> 路径：`process/archive/2026-08-2026-10/`。**什么时候看**：写复盘、做交接、审计追溯「当时为什么这么做 / 当时结论是什么」时。
**全部 🗄️ archived：只读，结论可能已被后续迭代推翻。**

### 规划与路线

| 文档 | 内容 |
|---|---|
| [项目计划.md](process/archive/2026-08-2026-10/项目计划.md) | 项目分期与阶段目标（2026-08 快照） |
| [总路线-二三期融合-2026-09-16.md](process/archive/2026-08-2026-10/总路线-二三期融合-2026-09-16.md) | 二期 × 三期融合的唯一执行顺序 |
| [三期规划-身份层与档案库-2026-09-16.md](process/archive/2026-08-2026-10/三期规划-身份层与档案库-2026-09-16.md) | 身份层 / 工作区 / 保险箱 / 邮箱站规划 |
| [模块划分与分支开发方案-2026-09-18.md](process/archive/2026-08-2026-10/模块划分与分支开发方案-2026-09-18.md) | 模块拆分与分支策略 |
| [移动端与DeepSeek语音助理方案-2026-09-17.md](process/archive/2026-08-2026-10/移动端与DeepSeek语音助理方案-2026-09-17.md) | 移动端部署 + 语音行程助理方案 |

### 推进日志与交接

| 文档 | 内容 |
|---|---|
| [二期推进日志.md](process/archive/2026-08-2026-10/二期推进日志.md) | 二期逐阶段进度与踩坑 |
| [三期推进日志.md](process/archive/2026-08-2026-10/三期推进日志.md) | 三期进度看板 |
| [模块化开发交接日志-2026-09-18.md](process/archive/2026-08-2026-10/模块化开发交接日志-2026-09-18.md) | 模块化开发交接（各模块 PRD 索引） |
| [工作日志-工程与后端-2026-09-18-交接设计.md](process/archive/2026-08-2026-10/工作日志-工程与后端-2026-09-18-交接设计.md) | 工程与后端交接设计 |
| [移动端UI适配测试日志-2026-09-17.md](process/archive/2026-08-2026-10/移动端UI适配测试日志-2026-09-17.md) | 移动端 UI 适配测试记录 |

### 交付 / 完工报告

| 文档 | 内容 |
|---|---|
| [mod-platform完成报告-2026-09-18.md](process/archive/2026-08-2026-10/mod-platform完成报告-2026-09-18.md) | platform 模块完成报告 |
| [mod-platform完工报告-2026-09-19.md](process/archive/2026-08-2026-10/mod-platform完工报告-2026-09-19.md) | platform 模块完工报告 |
| [mod-platform考察报告-2026-09-19.md](process/archive/2026-08-2026-10/mod-platform考察报告-2026-09-19.md) | platform 开发情况考察 |
| [mod-tools交付报告-2026-09-19.md](process/archive/2026-08-2026-10/mod-tools交付报告-2026-09-19.md) | tools 模块交付报告 |
| [mod-tools离线队列交付报告-2026-09-19.md](process/archive/2026-08-2026-10/mod-tools离线队列交付报告-2026-09-19.md) | tools 离线队列子项交付 |
| [frontend-delivery-note.md](process/archive/2026-08-2026-10/frontend-delivery-note.md) | 前端骨架 v1.0 工程说明 |

### 评估、方案与契约

| 文档 | 内容 |
|---|---|
| [一期工程进度评估-2026-08-28.md](process/archive/2026-08-2026-10/一期工程进度评估-2026-08-28.md) | 一期进度评估（08-28） |
| [一期工程进度评估-2026-09-04.md](process/archive/2026-08-2026-10/一期工程进度评估-2026-09-04.md) | 一期进度评估（09-04） |
| [一期模块考校报告-2026-09-06.md](process/archive/2026-08-2026-10/一期模块考校报告-2026-09-06.md) | 一期模块考校（85/100） |
| [三交付物融合方案-2026-09-15.md](process/archive/2026-08-2026-10/三交付物融合方案-2026-09-15.md) | 外部交付物内核融合方案 |
| [地球Online内核融入效果评估-2026-09-15.md](process/archive/2026-08-2026-10/地球Online内核融入效果评估-2026-09-15.md) | 成长体系与领域知识库融入评估 |
| [调试与性能优化报告-2026-09-15.md](process/archive/2026-08-2026-10/调试与性能优化报告-2026-09-15.md) | 一期缺陷根因与性能优化 |
| [云适配器契约-2026-09-19.md](process/archive/2026-08-2026-10/云适配器契约-2026-09-19.md) | 云同步适配器契约（冻结版） |

### 决策记录与演示数据

| 文档 | 内容 |
|---|---|
| [决策日志.md](process/archive/2026-08-2026-10/决策日志.md) | 2026-08-26 ADR 快照。⚠️ 部分决策（Electron / axios / asyncpg 等）已被推翻，**勿作为现行依据**；现行决策以 `architecture/ADR/` 为准 |
| [演示数据说明-2026-09-19.md](process/archive/2026-08-2026-10/演示数据说明-2026-09-19.md) | 演示数据生成与使用说明 |

---

## 附录 A：目录结构

```
docs/
├── README.md                 # 本文件：唯一入口
├── architecture/             # 架构与决策（现行）
│   ├── domains.json          # 领域划分（机器可读）
│   ├── ADR/                  # 架构决策记录（0001–0006）
│   └── legacy/               # 🗄️ 旧架构文档（archived）
├── product/                  # 产品与需求
│   ├── requirements/         # 需求分析（现行）
│   ├── prd/v2-current/       # 现行 PRD：总览 + M01–M09 + 二期 PRD
│   ├── prd/v1-archived/      # 🗄️ 旧 PRD：v1.0 + 模块 PRD ×8
│   └── ui/                   # UI 规范 / 组件索引 / 交互设计（现行）
├── guides/                   # 开发指南（现行）
├── runbooks/                 # 运维手册（备份 / 恢复等可执行步骤）
├── process/archive/2026-08-2026-10/  # 🗄️ 历史过程记录（只读）
├── design/                   # UI 画廊 HTML ×5 + 参考图
└── assets/                   # 截图等静态资源

ARCHITECTURE.md               # 架构唯一入口（仓库根，与 docs/ 同级）
```

## 附录 B：文档维护约定

1. **新增文档**：长期有效 → 对应「现行」目录；一次性过程/报告 → `process/archive/<年月区间>/`，文件名带日期（`主题-YYYY-MM-DD.md`）。
2. **永不删除**：过期文档移入归档，不删内容；同一主题多版本用目录（`v1-archived` / `v2-current`）而非文件名后缀区分。
3. **链接**：站内引用一律用**相对当前文件的路径**；移动文档后必须跑链接校验（见下）。
4. **单一事实来源**：数字类事实（模块数、测试数、版本号）不在文档里手工复制，以代码 / CI 校验为准。

**链接校验命令**（只读，移动 / 改名文档后必跑）：

```powershell
python scripts/audit_docs_links.py        # 现行文档门禁（归档区不校验；已接入 check_all.py 与 CI）
python scripts/audit_docs_links.py --all  # 额外校验 README / CONTRIBUTING / CHANGELOG / ARCHITECTURE
backend\.venv\Scripts\python.exe .arch-audit\ops-docs\linkcheck.py  # 全量深检（含归档区）
```

判定标准：现行文档 `失效引用: 0`；归档区允许保留"当时"的旧路径（取证用，不改写）。注：`PRD-模块-knowledge.md` 中 3 条图片链接占位语法（url 为占位符）是需求正文的语法示例，不是真实链接，属校验器误报。

## 变更记录

| 日期 | 变更 |
|---|---|
| 2026-10-26 | 文档 IA 重组：58 个文档迁入 architecture / product / guides / process，建立本总索引，修正因移动失效的引用 |
