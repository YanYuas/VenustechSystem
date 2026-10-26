# M06 Project 项目管理深度开发PRD

> 分支：`feature/project-deep` | 优先级：P0 | 预计工时：3天

## 一、模块定位

项目管理是启明星系统的"多任务聚合器"，将分散的任务、文档、对话按项目维度组织。用户可为每个生活/学习/工作项目建立独立空间，追踪进度，管理资源。

**核心目标**：让多项目并行时井然有序，进度一目了然

## 二、当前实现状态

### 已实现
- 项目列表视图（K02）：项目卡片网格展示
- 项目卡（K01）：名称、状态、进度、任务数
- 项目创建表单（K04）：名称、描述、颜色、截止日期
- 项目基础CRUD
- 项目与任务关联（tasks.project_id）

### 未实现/待完善
- 项目详情页（K03）：项目内任务/文档/对话聚合
- 项目进度统计（K05）：环形图+趋势
- 项目归档/恢复
- 项目内文件管理
- 项目里程碑
- 项目时间线
- 项目模板
- 项目导出
- 项目成员（单机版可省略，但预留）

## 三、深度开发功能清单

### P0 必须完成

#### F01 项目详情页
- **需求**：点击项目卡进入项目详情，展示项目内所有关联内容
- **实现**：
  - 顶部：项目名称、描述、进度、状态、操作按钮
  - Tab切换：任务、文档、对话、复盘、文件
  - 任务Tab：显示该项目下所有任务，支持快速添加
  - 文档Tab：显示该项目关联的文档
  - 对话Tab：显示该项目相关的AI对话
  - 复盘Tab：显示该项目相关的复盘记录
- **组件**：`ProjectDetailView.vue`
- **路由**：`/projects/:id`
- **验收**：项目详情页正确显示各Tab内容

#### F02 项目进度统计
- **需求**：可视化展示项目进度和任务分布
- **实现**：
  - 环形进度图：整体完成率
  - 任务分布：待办/进行中/已完成数量
  - 本周趋势：任务完成柱状图
  - 逾期任务提醒
  - 项目健康度评估
- **组件**：`ProjectStats.vue`（K05）
- **验收**：统计数据与实际任务状态一致

#### F03 项目里程碑
- **需求**：项目可设置里程碑，追踪关键节点
- **实现**：
  - 里程碑列表：名称、目标日期、完成状态
  - 里程碑进度条
  - 新增/编辑/删除里程碑
  - 里程碑关联任务
  - 到期提醒
- **数据模型**：`project_milestones`表

#### F04 项目归档/恢复
- **需求**：完成的项目可归档，不占用主视图；可恢复
- **实现**：
  - 项目列表筛选：全部/进行中/已归档
  - 归档项目显示灰色
  - 归档后任务不可编辑（只读）
  - 一键恢复
- **数据模型**：projects表已有status字段（active/archived/completed）

### P1 高质量打磨

#### F05 项目时间线
- **需求**：时间线视图展示项目动态
- **实现**：
  - 按时间倒序展示项目事件
  - 事件类型：任务完成、文档创建、对话、复盘、里程碑
  - 时间线滚动加载
  - 可筛选事件类型

#### F06 项目模板
- **需求**：内置项目模板，快速创建标准项目
- **实现**：
  - 内置模板：学习计划、写作项目、开发项目、健身计划
  - 模板包含：预设任务结构、文档结构
  - 自定义模板：将项目保存为模板
  - 创建项目时选择模板

#### F07 项目导出
- **需求**：导出项目全部内容为压缩包
- **实现**：
  - 导出内容：任务(JSON)、文档(MD)、对话(JSON)、复盘(MD)
  - 导出为ZIP压缩包
  - 导出包含项目元数据
  - 支持导入项目（从备份恢复）

#### F08 项目内快速添加
- **需求**：项目详情页可快速添加任务/文档
- **实现**：
  - 任务Tab内联添加任务（自动关联项目）
  - 文档Tab内联创建文档
  - 对话Tab快速发起项目相关对话
  - 全局新建时可选择项目

### P2 二期预研

#### F09 项目甘特图
- 按时间线展示项目任务
- 拖拽调整时间
- 依赖关系展示

#### F10 项目协作（预留）
- 多用户协作（云端版）
- 任务分配
- 评论系统

#### F11 项目AI助手
- AI分析项目进度，给出建议
- AI生成项目报告
- AI识别风险任务

## 四、技术实现要点

### 前端
- 新增视图：`ProjectDetailView.vue`
- 新增组件：`ProjectStats.vue`、`ProjectMilestoneList.vue`、`ProjectTimeline.vue`、`ProjectTabNav.vue`
- 路由配置：`/projects`（列表）、`/projects/:id`（详情）
- `useProject` composable扩展：详情、统计、里程碑、导出

### 后端
- `project_service.py`扩展：
  - 项目详情聚合（任务+文档+对话+复盘）
  - 进度统计计算
  - 里程碑管理
  - 项目导出
- `project_repo.py`扩展：关联查询
- 新增模型：`ProjectMilestone`
- 新增迁移：0015_project_milestones.py

### 性能
- 项目详情数据聚合查询，避免N+1
- 任务列表分页
- 统计数据缓存

## 五、数据模型扩展

### project_milestones表
```sql
CREATE TABLE project_milestones (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  description TEXT,
  target_date DATE,
  completed BOOLEAN DEFAULT 0,
  completed_at DATETIME,
  sort_order INTEGER DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_milestones_project ON project_milestones(project_id);
```

### projects表扩展
```sql
ALTER TABLE projects ADD COLUMN template_id TEXT;
ALTER TABLE projects ADD COLUMN is_template BOOLEAN DEFAULT 0;
```

## 六、API接口设计

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/projects` | 项目列表（支持筛选） |
| POST | `/api/v1/projects` | 创建项目 |
| GET | `/api/v1/projects/{id}` | 项目详情（含统计） |
| PUT | `/api/v1/projects/{id}` | 更新项目 |
| DELETE | `/api/v1/projects/{id}` | 删除项目 |
| POST | `/api/v1/projects/{id}/archive` | 归档项目 |
| POST | `/api/v1/projects/{id}/restore` | 恢复项目 |
| GET | `/api/v1/projects/{id}/tasks` | 项目任务列表 |
| GET | `/api/v1/projects/{id}/documents` | 项目文档列表 |
| GET | `/api/v1/projects/{id}/conversations` | 项目对话列表 |
| GET | `/api/v1/projects/{id}/reviews` | 项目复盘列表 |
| GET | `/api/v1/projects/{id}/stats` | 项目统计数据 |
| GET | `/api/v1/projects/{id}/milestones` | 里程碑列表 |
| POST | `/api/v1/projects/{id}/milestones` | 创建里程碑 |
| PUT | `/api/v1/projects/milestones/{mid}` | 更新里程碑 |
| DELETE | `/api/v1/projects/milestones/{mid}` | 删除里程碑 |
| GET | `/api/v1/projects/{id}/export` | 导出项目 |
| GET | `/api/v1/projects/templates` | 项目模板列表 |

## 七、验收标准

1. 项目详情页正常显示，各Tab内容正确
2. 项目进度统计数据准确
3. 里程碑可正常增删改查
4. 项目可归档和恢复
5. 项目时间线正确展示动态
6. 项目模板可正常使用
7. 项目导出ZIP包含完整内容
8. 项目内可快速添加任务/文档
9. 项目与任务关联正确
10. 四套主题下项目页显示正常

## 八、风险与依赖

- **依赖**：M02 Task（任务关联）、M03 Document（文档关联）、M04 Conversation（对话关联）、M05 Review（复盘关联）
- **风险**：项目详情聚合查询可能较慢，需优化
- **兼容性**：归档项目的任务编辑需限制
- **数据迁移**：新增里程碑表
