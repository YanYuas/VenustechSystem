# M02 Task 任务管理深度开发PRD

> 分支：`feature/task-deep` | 优先级：P0 | 预计工时：4天

## 一、模块定位

任务管理是启明星系统的核心生产力模块，承担个人任务的全生命周期管理：从创建、执行到完成归档。支持列表/看板双视图，子任务拆解，优先级与标签体系。

**核心目标**：让用户清晰掌握待办，高效推进任务

## 二、当前实现状态

### 已实现
- 任务列表视图（C02）：显示任务标题、状态、截止日期
- 任务卡（C01）：标题、摘要、状态、优先级、标签
- 任务筛选器栏（C07）：按状态/优先级筛选
- 基础CRUD：创建、编辑、删除任务
- 任务状态：todo/in_progress/done
- 优先级：low/medium/high

### 未实现/待完善
- 子任务完整CRUD（C05）
- 看板视图（C03）：按状态分列展示
- 任务拖拽排序与状态切换
- 任务详情抽屉
- 重复任务（每日/每周/每月）
- 任务提醒与到期通知
- 任务与项目关联
- 任务时间追踪（番茄钟）
- 任务模板
- 批量操作（批量完成/删除/移动）

## 三、深度开发功能清单

### P0 必须完成

#### F01 子任务完整CRUD
- **需求**：任务可拆解为多个子任务，独立管理完成状态
- **实现**：
  - 任务详情中显示子任务列表
  - 支持添加/编辑/删除子任务
  - 子任务勾选完成，父任务进度自动计算
  - 子任务支持拖拽排序
- **数据模型**：`sub_tasks`表（id, task_id, title, completed, sort_order, created_at）
- **验收**：父任务进度 = 已完成子任务数/总子任务数

#### F02 看板视图
- **需求**：按任务状态分列展示（待办/进行中/已完成），支持拖拽切换状态
- **实现**：
  - 三列布局：待办、进行中、已完成
  - 每列显示任务卡，可纵向滚动
  - 拖拽任务卡到其他列切换状态
  - 列头显示该列任务数量
  - 列表/看板视图切换按钮
- **技术**：HTML5 Drag & Drop API 或 vuedraggable
- **验收**：拖拽后状态即时更新，刷新后保持

#### F03 任务详情抽屉
- **需求**：点击任务卡打开右侧抽屉，查看/编辑完整任务信息
- **实现**：
  - 抽屉从右侧滑入，宽度480px
  - 包含：标题、描述、状态、优先级、截止日期、标签、子任务、关联项目、创建时间
  - 支持编辑所有字段
  - 删除按钮（二次确认）
- **组件**：`TaskDetailDrawer.vue`（基于BaseDrawer）

#### F04 任务与项目关联
- **需求**：任务可归属到某个项目，项目页可查看关联任务
- **实现**：
  - 任务创建/编辑时可选择所属项目
  - 任务卡显示项目颜色标识
  - 项目详情页显示关联任务列表
  - 按项目筛选任务
- **数据模型**：tasks表已有project_id字段，需完善前端选择器

### P1 高质量打磨

#### F05 重复任务
- **需求**：支持设置任务重复规则（每日/每周/每月/自定义）
- **实现**：
  - 任务编辑时设置重复规则
  - 到期自动生成新任务实例
  - 重复任务显示循环图标
  - 支持暂停/停止重复
- **数据模型**：tasks表新增`recurrence`字段（JSON：{type, interval, days}）

#### F06 任务提醒
- **需求**：任务到期前推送通知提醒
- **实现**：
  - 任务设置提醒时间（到期前15分钟/1小时/1天）
  - 系统通知 + 桌面通知（桌宠气泡）
  - 提醒中心查看所有待提醒
  - 已提醒任务标记
- **依赖**：M09 Infrastructure通知系统

#### F07 批量操作
- **需求**：多选任务后批量操作
- **实现**：
  - 列表视图支持多选（复选框）
  - 批量操作：完成、删除、移动到项目、修改优先级
  - 底部出现操作栏
  - 全选/反选

#### F08 番茄钟时间追踪
- **需求**：任务可启动番茄钟，记录专注时间
- **实现**：
  - 任务卡显示"开始专注"按钮
  - 25分钟倒计时 + 5分钟休息
  - 记录每次专注时长
  - 任务详情显示总专注时间
- **数据模型**：`focus_sessions`表（id, task_id, start_time, end_time, duration）

### P2 二期预研

#### F09 任务模板
- 保存常用任务为模板，一键创建
- 支持模板分类

#### F10 任务依赖关系
- 任务A完成后才能开始任务B
- 依赖关系可视化

#### F11 甘特图视图
- 按时间线展示任务
- 支持拖拽调整时间

## 四、技术实现要点

### 前端
- `TaskListView.vue`重构：列表/看板双视图切换
- 新增组件：`TaskDetailDrawer.vue`、`SubTaskList.vue`、`KanbanColumn.vue`、`TaskCard.vue`、`FocusTimer.vue`
- `useTask` composable扩展：子任务CRUD、重复任务、批量操作
- 拖拽：使用`vuedraggable`或原生Drag API

### 后端
- `task_service.py`扩展：
  - 子任务CRUD方法
  - 看板数据聚合
  - 重复任务生成逻辑（定时任务）
  - 专注时间记录
- `task_repo.py`扩展：子任务查询、批量更新
- 新增模型：`SubTask`、`FocusSession`
- 新增迁移：0006_subtasks.py、0007_focus_sessions.py

### 性能
- 任务列表虚拟滚动（超过100条时）
- 看板列懒加载
- 子任务展开时才查询

## 五、数据模型扩展

### sub_tasks表
```sql
CREATE TABLE sub_tasks (
  id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  completed BOOLEAN DEFAULT 0,
  sort_order INTEGER DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_subtasks_task ON sub_tasks(task_id);
```

### focus_sessions表
```sql
CREATE TABLE focus_sessions (
  id TEXT PRIMARY KEY,
  task_id TEXT REFERENCES tasks(id) ON DELETE SET NULL,
  start_time DATETIME NOT NULL,
  end_time DATETIME,
  duration INTEGER, -- 秒
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_focus_task ON focus_sessions(task_id);
```

### tasks表扩展
```sql
ALTER TABLE tasks ADD COLUMN recurrence TEXT; -- JSON重复规则
ALTER TABLE tasks ADD COLUMN reminder_time DATETIME;
ALTER TABLE tasks ADD COLUMN focus_duration INTEGER DEFAULT 0; -- 总专注秒数
```

## 六、API接口设计

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/tasks` | 任务列表（支持筛选/排序/分页） |
| POST | `/api/v1/tasks` | 创建任务 |
| GET | `/api/v1/tasks/{id}` | 任务详情（含子任务） |
| PUT | `/api/v1/tasks/{id}` | 更新任务 |
| DELETE | `/api/v1/tasks/{id}` | 删除任务 |
| POST | `/api/v1/tasks/{id}/subtasks` | 添加子任务 |
| PUT | `/api/v1/tasks/{id}/subtasks/{sid}` | 更新子任务 |
| DELETE | `/api/v1/tasks/{id}/subtasks/{sid}` | 删除子任务 |
| POST | `/api/v1/tasks/batch` | 批量操作 |
| POST | `/api/v1/tasks/{id}/focus/start` | 开始专注 |
| POST | `/api/v1/tasks/{id}/focus/stop` | 结束专注 |
| GET | `/api/v1/tasks/kanban` | 看板数据（按状态分组） |

## 七、验收标准

1. 子任务CRUD完整，父任务进度自动计算
2. 看板视图正常显示，拖拽切换状态生效
3. 任务详情抽屉可编辑所有字段
4. 任务可关联项目，项目页显示关联任务
5. 重复任务到期自动生成
6. 任务到期提醒正常推送
7. 批量操作正常工作
8. 番茄钟计时准确，专注时间记录正确
9. 列表/看板切换无数据丢失
10. 四套主题下显示正常

## 八、风险与依赖

- **依赖**：M06 Project模块（任务-项目关联）、M09 Infrastructure（通知系统）
- **风险**：拖拽在低性能设备上可能卡顿，需做性能优化
- **兼容性**：重复任务的时区处理需注意
- **数据迁移**：新增表和字段需向后兼容
