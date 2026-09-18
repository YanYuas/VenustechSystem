# 启明星系统 · 模块深度开发PRD总览

> 版本：v1.0 | 日期：2026-09-05 | 基于：PRD-启明星系统-v1.0 + 一期实际实现

## 一、一期模块全景

| 编号 | 模块 | Git分支 | 核心定位 | 一期完成度 |
|------|------|---------|----------|-----------|
| M01 | Dashboard 首页 | `feature/dashboard-deep` | 个人OS入口，信息聚合与快速操作 | 75% |
| M02 | Task 任务管理 | `feature/task-deep` | 任务全生命周期管理 | 70% |
| M03 | Document 知识文档 | `feature/document-deep` | 本地知识库与文档编辑器 | 65% |
| M04 | Conversation 第二分身 | `feature/conversation-deep` | AI对话与个人知识沉淀 | 60% |
| M05 | Review 复盘 | `feature/review-deep` | 每日复盘与成长追踪 | 55% |
| M06 | Project 项目管理 | `feature/project-deep` | 多项目聚合与进度管理 | 40% |
| M07 | Pet 桌宠 | `feature/pet-deep` | 二次元互动桌宠与情感陪伴 | 50% |
| M08 | Settings 设置 | `feature/settings-deep` | 系统配置与个性化 | 60% |
| M09 | Infrastructure 基础设施 | `feature/infrastructure-deep` | 备份/通知/搜索/事件总线 | 70% |

## 二、分支管理规范

### 分支策略
- `main`：稳定基线，仅接受经过验证的合并
- `feature/<module>-deep`：各模块深度开发分支
- 开发流程：分支开发 → 自测 → PR合并 → main验证

### 合并规则
1. 每个模块独立开发，互不阻塞
2. 合并前必须通过：后端pytest + 前端tsc + 生产构建
3. 涉及共享组件（common/）修改时，需通知其他模块
4. 数据库迁移必须向后兼容

### 版本号规则
- 模块级功能完成 → 修订号+1（v0.1.x）
- 多模块合并 → 次版本号+1（v0.x.0）
- 一期全部完成 → v1.0.0

## 三、深度开发优先级

### P0（一期必须完成）
- M01 Dashboard：首页卡片自适应、项目模块入口、灰度待开发模块
- M02 Task：子任务完整CRUD、看板视图、任务拖拽
- M03 Document：文件夹跳转、Markdown编辑器增强、全文搜索
- M06 Project：项目详情页、项目内任务/文档关联

### P1（一期高质量打磨）
- M04 Conversation：对话历史、引用文档、提示词模板
- M05 Review：复盘模板、情绪趋势、周/月复盘
- M07 Pet：动作系统、互动反馈、桌宠与人形切换
- M08 Settings：四主题切换、AI模型配置、数据加密

### P2（二期预研）
- M09 Infrastructure：云端同步、多设备、插件市场
- 全部模块：性能优化、无障碍、国际化

## 四、共享技术约束

### 前端
- Vue3 + TypeScript严格模式
- 组件分层：common/（基础）→ layout/（布局）→ 模块组件
- Composables：useXxx模式，API调用与状态分离
- 主题：四套CSS变量，通过data-theme切换
- 构建：vite build必须0错误0警告

### 后端
- FastAPI + SQLAlchemy 2.0 + Alembic
- 分层：api → service → repository → model
- 事件总线：模块间解耦通信
- 测试：pytest覆盖率≥80%
- 数据库：SQLite，迁移必须可回滚

### 数据安全
- 用户数据本地加密存储（AES-256）
- 支持导出为加密包
- 备份自动定时 + 手动触发
- 删除操作软删除，30天可恢复

## 五、文档索引

各模块详细PRD：
- [M01 Dashboard首页深度开发PRD](./M01-Dashboard深度开发PRD.md)
- [M02 Task任务管理深度开发PRD](./M02-Task深度开发PRD.md)
- [M03 Document知识文档深度开发PRD](./M03-Document深度开发PRD.md)
- [M04 Conversation第二分身深度开发PRD](./M04-Conversation深度开发PRD.md)
- [M05 Review复盘深度开发PRD](./M05-Review深度开发PRD.md)
- [M06 Project项目管理深度开发PRD](./M06-Project深度开发PRD.md)
- [M07 Pet桌宠深度开发PRD](./M07-Pet深度开发PRD.md)
- [M08 Settings设置深度开发PRD](./M08-Settings深度开发PRD.md)
- [M09 Infrastructure基础设施深度开发PRD](./M09-Infrastructure深度开发PRD.md)
