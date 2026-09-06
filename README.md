# Venustech System（启明星）

> AI 驱动的个人操作系统（Personal OS）· 产品 Slogan：**方向启明，人生推演**
> 当前版本 **v0.2.0**（2026-09-06）· 9 模块深度开发完成 · 四套 UI 主题

## 项目简介

整合**任务、项目、知识、复盘与 AI 第二分身**于统一入口的本地优先个人系统。构建「输入 → 处理 → 输出 → 沉淀 → 复用」的个人复利闭环，以二次元**桌宠分身**为情感连接点，实现数据主动整理、灵感主动触发、复盘自动沉淀。

**核心差异化**：第二分身——不是冰冷的工具，而是一个了解用户、会主动整理知识、以二次元形象陪伴的 AI 伙伴。支持桌宠/人形双形态切换，12 种动作，四维度状态系统。

## 技术栈（架构 v2.0）

| 层 | 技术 |
|----|------|
| 后端 | FastAPI + SQLAlchemy 2.0 + SQLite(WAL/StaticPool) + Alembic + loguru + pytest |
| 前端 | Vue 3 + TypeScript 严格模式 + Vite + Pinia + Vue Router(Hash) + Element Plus（按需） + SCSS |
| AI | DeepSeek（OpenAI 兼容，httpx 自研客户端）；多模型切换（GPT/Claude/Ollama）；未配 Key 时本地规则降级 |
| 基础设施 | 事件总线（18 种事件/异步/历史 500 条）、插件系统（发现/加载/热重载）、加密存储（AES-128-CBC + HMAC + PBKDF2）、日志查看 API |
| 部署 | 开发：8765 后端 + 5173 前端（一键脚本）；生产：Node 统一服务单端口 3000（API 代理 + 静态资源） |

## 目录结构

`
backend/                 FastAPI 后端（app 分层：api → services → repositories → models）
  ├── app/main.py        应用入口（lifespan：迁移/种子/事件订阅/维护）
  ├── app/core/          核心：event_bus / plugin_manager / encryption / config
  ├── app/api/           18 个路由模块（auth/task/folder/document/conversation/review/dashboard/backup/panel/notification/project/events/plugins/security/logs/health...）
  ├── migrations/        Alembic 迁移（0001-0004）
  └── scripts/           冒烟测试
frontend/                Vue3 前端
  ├── src/views/         8 视图（Dashboard/Task/Document/Conversation/Review/Project/Settings/NotFound）
  ├── src/api/           HTTP API 层（9 模块 + http 封装/SSE）
  ├── src/composables/   业务逻辑（14+ 个 useXxx）
  ├── src/components/    组件（common 基础 + layout 壳 + pet 桌宠 + document/task 业务组件）
  └── src/styles/        主题变量（4 套主题 × 明暗模式）
docs/                    文档
  ├── design/            PRD / 技术架构 / UI 组件画廊（4 套主题）/ 交互设计
  ├── prd/               9 模块深度开发 PRD（M01-M09）
  ├── frontend/          前端开发说明
  ├── backend/           后端开发说明
  └── management/        进度评估 / 决策日志 / 项目计划
scripts/                 开发脚本（dev.ps1 一键启动）
server.js / package.json 统一 Web 服务（生产：静态 + /api 代理）
启动开发.bat             一键启动（双击）
`

## 功能模块

### 一期核心（已完成）

- **首页 Dashboard**：三栏布局（左信息面板 + 顶导航 + 主内容），今日焦点/状态/执行/项目/最近沉淀一屏聚合；本周进度环（SVG）、连续打卡徽章、卡片拖拽排序
- **任务 Task**：列表/看板双视图、拖拽换状态、子任务、优先级状态机、今日最重要、任务模板（5 内置+自定义）、任务依赖关系、桌宠联动
- **知识 Document**：文件夹层级、文档编辑器（三模式/自动保存）、标签、全文搜索、双向链接、模板系统、版本 diff、文档关系图谱（SVG 力导向图）、AI 摘要/标签建议
- **第二分身 Conversation**：SSE 流式、8 提示词模板 + / 快捷触发、6 套预设人设、多模型切换、用户画像沉淀（4 类特质标签）、主动提醒系统、引用文档(≤3)、无 Key 本地降级
- **复盘 Review**：热力日历、情绪趋势（双折线 SVG）、复盘模板（日/周/月/项目）、复盘导出 Markdown、年度复盘报告、自动数据填充、心情/精力评分、AI 反思问题、明日计划转任务
- **项目 Project**：项目列表（8 色/进度/状态）、项目详情页（5 Tab）、里程碑 CRUD、归档/恢复、项目模板、项目时间线、项目导出（JSON + JSZip 打包）

### 桌宠 Pet（一期亮点）

- 12 种动作系统、桌宠/人形双形态切换（旋转动画）
- 右键菜单（8 动作 + 形态切换）、双击快速切换
- 四维度状态系统（亲密度/饱食度/心情/精力随时间衰减）
- 互动系统（喂食/抚摸/玩耍/休息）、状态条实时显示
- 自定义形象配置（5 套预设 + 主色/辅色/眼色可配置）

### 全局能力

- 通知（30s 轮询+未读红点）、全局搜索(⌘K)、命令面板、快捷键
- 四套主题（奶油糖果/国风雅集/深渊档案/史诗典藏）× 明暗模式
- 备份导入导出、API Key 加密、数据目录管理
- 插件系统基础架构、加密存储、事件总线

### 待开发（二期方向）

资源中心、学习与成长、生活与自我、长期资产库、Electron 桌面打包、云端同步、移动端适配

## UI 组件画廊

四套主题深度对齐，每套 52 组件：
- [奶油糖果](docs/design/UI组件画廊-奶油糖果.html) · [国风雅集](docs/design/UI组件画廊-国风雅集.html)
- [深渊档案](docs/design/UI组件画廊-深渊档案.html) · [史诗典藏](docs/design/UI组件画廊-史诗典藏.html)

## 快速开始

前置：Python 3.11+、Node 18+；前端依赖 cd frontend && npm install

`ash
# 一键启动（开发模式）：后端 8765 + 前端 5173 + 自动开浏览器
#   双击「启动开发.bat」，或：
powershell -ExecutionPolicy Bypass -File scripts\dev.ps1

# 手动启动
cd backend && python -m uvicorn app.main:app --reload --port 8765   # 后端
cd frontend && npm run dev                                           # 前端 http://localhost:5173

# 生产 / 局域网访问（单端口 3000）
cd frontend && npm run build && cd .. && node server.js
#   → http://<本机IP>:3000 （前端 + /api 代理到 8765）
`

验证：后端 python scripts/smoke_backend.py（12+ 项断言）；前端 
pm run typecheck / 
pm run build。

## 文档

- [PRD v1.0](docs/design/PRD-启明星系统-v1.0.md) · [需求分析](docs/design/01-需求分析.md)
- [技术架构 v2.0](docs/design/02-技术架构-v2.0.md) · [交互设计](docs/design/04-交互设计.md)
- [模块深度开发 PRD](docs/prd/00-模块深度开发PRD总览.md)（M01-M09）
- [前端开发说明](docs/frontend/前端开发说明.md) · [后端开发说明](docs/backend/后端开发说明.md)
- [一期进度评估](docs/management/一期工程进度评估-2026-09-04.md) · [决策日志](docs/management/决策日志.md) · [项目计划](docs/management/项目计划.md)
- [方法论](docs/methodology.md) · [变更日志](CHANGELOG.md) · [贡献指南](CONTRIBUTING.md)

## 许可证

个人项目，保留所有权利。