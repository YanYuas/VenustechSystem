# Changelog

本项目所有重要变更都记录在此文件。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### 进行中
- 二期规划（Electron 打包 / 文档版本历史 UI / 周报 UI / 桌宠人形切换 / 云端同步 / 移动端适配）
- 资源中心 / 学习与成长 / 生活与自我 / 长期资产库 模块开发

## [0.2.0] - 2026-09-06

### Added — 9 模块深度开发完成（分支合并至 main）

- **M01 首页 Dashboard**：本周进度环（SVG 环形图）、连续打卡徽章（火焰+天数）、卡片拖拽排序（HTML5 拖拽 + localStorage 持久化）
- **M02 任务 Task**：任务模板系统（5 内置模板 + 自定义保存）、任务依赖关系（前置任务 ID 列表 + 阻塞状态计算）
- **M03 知识 Document**：双向链接、文档导出补全、模板系统、版本 diff、文档关系图谱（后端 /documents/graph/data API + 前端 SVG 力导向图）
- **M04 第二分身 Conversation**：8 内置提示词模板 + 搜索 + / 快捷触发、6 套预设人设切换、多模型切换（DeepSeek/GPT/Claude/Ollama）、用户画像沉淀（4 类特质标签 + 模拟文档分析）、主动提醒系统（定时检查即将到期任务 + 桌宠事件触发提醒气泡）
- **M05 复盘 Review**：热力日历（月度打卡心情着色）、情绪趋势（近 14 天心情/精力双折线 SVG）、复盘模板系统（日/周/月/项目 4 类型）、复盘导出 Markdown（单条/批量）、年度复盘报告（年度数据聚合 + 里程碑 + 高频标签 + Markdown 导出）
- **M06 项目 Project**：项目详情页（672 行 5 Tab）、进度统计、里程碑 CRUD、归档/恢复、项目模板、项目内快速添加、项目时间线（timeline() 聚合）、项目导出（export() 返回 JSON + 前端 JSZip 打包）
- **M07 桌宠 Pet**：动作系统从 6 扩展到 12 种、桌宠/人形双形态切换（带旋转动画）、右键菜单（8 动作 + 形态切换）、双击快速切换、二次元人形 SVG、配置持久化、四维度状态系统（亲密度/饱食度/心情/精力随时间衰减）、互动系统（喂食/抚摸/玩耍/休息）、状态条实时显示、自定义形象配置（5 套预设 + 主色/辅色/眼色可配置）
- **M08 设置 Settings**：史诗典藏主题（亮色传说 + 暗色暗夜双模式）、四套主题完整对齐、桌宠设置面板（开关/默认形态/互动/透明度）、通知设置（任务/复盘/系统/提示音）、数据目录显示与打开、高级设置（动画开关/字体缩放 80-130%/性能模式/自动保存）、快捷键参考面板（8 组）、数据清理（缓存/临时文件/旧备份）、关于页增强（可展开更新日志 v0.1.70-v0.2.0）
- **M09 基础设施 Infrastructure**：健康检查增强（系统信息/数据库状态/磁盘使用/路径）、事件总线增强（异步事件 / 18 种事件类型 / 历史 500 条 / 统计 API）、events API（统计/历史/类型/清空/测试）、system/info 端点、插件系统基础架构（PluginManager 发现/加载/启用禁用/热重载 + plugin.json 元数据规范 + PluginContext 注入 API）、加密存储模块（Fernet AES-128-CBC + HMAC + PBKDF2 密钥派生 + 文件加密解密 + 密钥轮换 + 缺库优雅降级）、plugins API、security API、日志查看 API（日志文件列表/内容读取支持 tail 行数和级别过滤/清空/路径遍历安全防护）

### Changed
- UI 组件画廊 V3.0：四套主题（奶油糖果/国风雅集/深渊档案/史诗典藏）深度对齐，每套 52 组件
- 史诗典藏主题改为明亮传说史诗感，暗色仅作为暗夜模式
- 首页布局严格对齐参考 UI：顶部水平导航 + 主页面板跳转子页面，主页面板固定不下拉

### Fixed
- 合并后 SCSS 嵌套语法错误（ConversationView/ReviewView/SettingsView/ProjectDetailView/DesktopPet 多处 &__ 选择器在顶层使用）
- HTML 重复 class 属性（SettingsView/DesktopPet）
- DocumentEditor 类型错误（wikiResults 缺少 project_id 字段）
- 首页模块跳转问题：收集箱 404、待开发模块跳转到不相关页面、项目卡片应跳详情页

## [0.1.0] - 2026-09-04

### Added — 一期工程 100%（评估见 docs/management/一期工程进度评估-2026-09-04.md）

- **设计沉淀**：PRD v1.0 / 需求分析 / 技术架构 v2.0（后端/前端各多轮优化）/ UI 设计规范 / 交互设计 / UI 组件画廊（95 组件，三套主题变体）
- **后端骨架**：FastAPI + SQLAlchemy 2.0 + SQLite(WAL/StaticPool) + Alembic（迁移 0001-0004）+ pydantic-settings + loguru + AES 加密
  - 分层 pi → services → repositories → models，统一响应/异常/日志；14 张表（用户/任务/子任务/文档/版本/反链/文件夹/对话/消息/复盘/待办/提醒/通知/设置/项目）
  - 事件总线 + 订阅者（文档保存→AI 摘要/标签，任务完成→通知）
  - AI 服务抽象（DeepSeek httpx 客户端，指数退避重试）+ Mock 降级
  - 全模块路由：auth/task/document/folder/conversation/review/dashboard/backup/panel/notification/project
  - 演示种子（大量：任务/文档/复盘/对话/待办/提醒/通知）
- **前端工程**：Vue 3 + TS 严格 + Vite + Pinia + Router(Hash) + Element Plus 按需
  - 三栏布局（左信息面板 + 顶导航 + 主内容）；16 基础组件 + 7 布局组件 + 桌宠组件
  - 9 API 模块 + 14 composables + 8 视图（Dashboard/Task/Document/Conversation/Review/Project/Settings）
  - 全局搜索(⌘K)/命令面板/快捷键/通知(30s 轮询)/主题(三套)/备份/API Key 配置
- **功能模块**：任务（列表/看板/子任务/状态机/今日最重要）、知识（文件夹/编辑器/自动保存/标签/搜索/AI 摘要）、第二分身（SSE/5 思维模式/引用文档/灵感/本地降级）、复盘（自动填充/评分/AI 反思/转任务）、项目管理（/projects）
- **桌宠**：SVG 二次元形象、6 动作、拖拽、气泡、任务完成庆祝联动
- **工程化**：后端 pytest（架构守护 + 冒烟，12 项通过）、前端 vue-tsc 零错误、生产构建成功、一键启动脚本（bat + ps1）

### Changed
- 项目迁移至 D:\YanYuas\PersonalDevelopmentPortfolio\VenustechSystem，对接 GitHub 远程 origin
- 补齐 README（项目简介/技术栈/目录/快速开始/文档索引）
- 清理仓库根目录散落的开发修复脚本与误生成文件

### Fixed
- Windows 日志中文乱码（stdout/stderr UTF-8 reconfigure）
- Alembic path_separator 警告
- 迁移后 README/CHANGELOG 骨架化（本次补全）