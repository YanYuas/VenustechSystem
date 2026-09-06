# Venustech System（启明星）

> AI 驱动的个人操作系统（Personal OS）· 源名 **BetterLife AI**
> 一期工程 **100% 完成**（2026-09-04）· 产品 Slogan：**方向启明，人生推演**

## 项目简介

整合**任务、项目、知识、复盘与 AI 第二分身**于统一入口的本地优先个人系统。构建「输入 → 处理 → 输出 → 沉淀 → 复用」的个人复利闭环，以二次元**桌宠分身**为情感连接点，实现数据主动整理、灵感主动触发、复盘自动沉淀。

**核心差异化**：第二分身——不是冰冷的工具，而是一个了解用户、会主动整理知识、以二次元形象陪伴的 AI 伙伴。

## 技术栈（架构 v2.0）

| 层 | 技术 |
|----|------|
| 后端 | FastAPI 子进程 + SQLAlchemy 2.0 + SQLite(WAL) + Alembic + loguru |
| 前端 | Vue 3 + TypeScript 严格模式 + Vite + Pinia + Vue Router(Hash) + Element Plus（按需） |
| AI | DeepSeek（OpenAI 兼容，httpx 自研客户端）；未配 Key 时本地规则降级 |
| 部署 | 开发：8765 后端 + 5173 前端（一键脚本）；生产：Node 统一服务单端口 3000（API 代理 + 静态资源） |

## 目录结构

```
backend/                 FastAPI 后端（app 分层：api → services → repositories → models）
  ├── app/main.py        应用入口（lifespan：迁移/种子/事件订阅/维护）
  ├── migrations/        Alembic 迁移（0001-0004：初始/面板/通知/项目）
  └── scripts/           冒烟测试
frontend/                Vue3 前端
  ├── src/views/         8 视图（Dashboard/Task/Document/Conversation/Review/Project/Settings/NotFound）
  ├── src/api/           HTTP API 层（9 模块 + http 封装/SSE）
  ├── src/composables/   业务逻辑（14 个 useXxx）
  └── src/components/    组件（common 基础 + layout 壳 + pet 桌宠）
docs/                    文档（design 设计 / frontend 前端说明 / backend 后端说明 / management 进度与决策）
scripts/                 开发脚本（dev.ps1 一键启动）
server.js / package.json 统一 Web 服务（生产：静态 + /api 代理）
启动开发.bat             一键启动（双击）
```

## 一期功能（100%，见 [进度评估](docs/management/一期工程进度评估-2026-09-04.md)）

- **首页**：三栏布局（左信息面板 + 顶导航 + 主内容），今日焦点/状态/执行/项目/最近沉淀一屏聚合
- **任务**：列表/看板双视图、拖拽换状态、子任务、优先级状态机、今日最重要、桌宠联动
- **知识**：文件夹层级、文档编辑器（自动保存）、标签、全文搜索、AI 摘要/标签建议
- **第二分身**：SSE 流式、5 种思维模式、引用文档(≤3)、灵感/摘要/标签、无 Key 本地降级
- **复盘**：自动数据填充、心情/精力评分、AI 反思问题、明日计划转任务
- **项目**：项目管理页（8 色、进度、状态）、任务归属项目
- **全局**：通知（30s 轮询+未读红点）、全局搜索(⌘K)、命令面板、三套主题、备份导入导出、API Key 加密


<img width="2544" height="1402" alt="6f87a993-8cef-4db6-bb1d-9756c7e07738" src="https://github.com/user-attachments/assets/bea0dc76-af11-4e7a-ae53-f4fe59fc83ec" />


## 快速开始

前置：Python 3.11+、Node 18+；前端依赖 `cd frontend && npm install`（本机策略：终端下载由你执行）

```bash
# 一键启动（开发模式）：后端 8765 + 前端 5173 + 自动开浏览器
#   双击「启动开发.bat」，或：
powershell -ExecutionPolicy Bypass -File scripts\dev.ps1

# 手动启动
cd backend && python -m uvicorn app.main:app --reload --port 8765   # 后端（首启自动灌演示数据）
cd frontend && npm run dev                                           # 前端 http://localhost:5173

# 生产 / 局域网访问（单端口 3000）
cd frontend && npm run build && cd .. && node server.js
#   → http://<本机IP>:3000 （前端 + /api 代理到 8765）
```

验证：后端 `python scripts/smoke_backend.py`（12+ 项断言）；前端 `npm run typecheck`。

## 文档

- [PRD v1.0](docs/design/PRD-启明星系统-v1.0.md) · [需求分析](docs/design/01-需求分析.md)
- [技术架构 v2.0](docs/design/02-技术架构-v2.0.md) · [UI 组件规范](docs/design/03-UI组件index.md) · [交互设计](docs/design/04-交互设计.md)
- [UI 组件画廊](docs/design/UI组件画廊.html)（95 组件可视化 · 三套主题变体）
- [前端开发说明](docs/frontend/前端开发说明.md) · [后端开发说明](docs/backend/后端开发说明.md)
- [一期进度评估](docs/management/一期工程进度评估-2026-09-04.md) · [决策日志](docs/management/决策日志.md) · [项目计划](docs/management/项目计划.md)
- [方法论](docs/methodology.md) · [变更日志](CHANGELOG.md) · [贡献指南](CONTRIBUTING.md)

## 二期方向

Electron 桌面打包（真桌宠窗口）、文档版本历史 UI、周报 UI、桌宠↔人形切换、云端同步、移动端适配。
