# Changelog

本项目所有重要变更都记录在此文件。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### 进行中
- 二期规划（Electron 打包 / 文档版本历史 UI / 周报 UI / 桌宠人形切换 / 云端同步）

## [0.1.0] - 2026-09-04

### Added — 一期工程 100%（评估见 `docs/management/一期工程进度评估-2026-09-04.md`）

- **设计沉淀**：PRD v1.0 / 需求分析 / 技术架构 v2.0（后端/前端各多轮优化）/ UI 设计规范 / 交互设计 / UI 组件画廊（95 组件，三套主题变体）
- **后端骨架**：FastAPI + SQLAlchemy 2.0 + SQLite(WAL/StaticPool) + Alembic（迁移 0001-0004）+ pydantic-settings + loguru + AES 加密
  - 分层 `api → services → repositories → models`，统一响应/异常/日志；14 张表（用户/任务/子任务/文档/版本/反链/文件夹/对话/消息/复盘/待办/提醒/通知/设置/项目）
  - 事件总线 + 订阅者（文档保存→AI 摘要/标签，任务完成→通知）
  - AI 服务抽象（DeepSeek httpx 客户端，指数退避重试）+ Mock 降级
  - 全模块路由：auth/task/document/folder/conversation(review/dashboard/backup/panel/notification/project
  - 演示种子（大量：任务/文档/复盘/对话/待办/提醒/通知）
- **前端工程**：Vue 3 + TS 严格 + Vite + Pinia + Router(Hash) + Element Plus 按需
  - 三栏布局（左信息面板 + 顶导航 + 主内容）；16 基础组件 + 7 布局组件 + 桌宠组件
  - 9 API 模块 + 14 composables + 8 视图（Dashboard/Task/Document/Conversation/Review/Project/Settings）
  - 全局搜索(⌘K)/命令面板/快捷键/通知(30s 轮询)/主题(三套)/备份/API Key 配置
- **功能模块**：任务（列表/看板/子任务/状态机/今日最重要）、知识（文件夹/编辑器/自动保存/标签/搜索/AI 摘要）、第二分身（SSE/5 思维模式/引用文档/灵感/本地降级）、复盘（自动填充/评分/AI 反思/转任务）、项目管理（/projects）
- **桌宠**：SVG 二次元形象、6 动作、拖拽、气泡、任务完成庆祝联动
- **工程化**：后端 pytest（架构守护 + 冒烟，12 项通过）、前端 vue-tsc 零错误、生产构建成功、一键启动脚本（bat + ps1）

### Changed
- 项目迁移至 `D:\YanYuas\PersonalDevelopmentPortfolio\VenustechSystem`，对接 GitHub 远程 `origin`
- 补齐 README（项目简介/技术栈/目录/快速开始/文档索引）
- 清理仓库根目录散落的开发修复脚本与误生成文件

### Fixed
- Windows 日志中文乱码（stdout/stderr UTF-8 reconfigure）
- Alembic path_separator 警告
- 迁移后 README/CHANGELOG 骨架化（本次补全）
