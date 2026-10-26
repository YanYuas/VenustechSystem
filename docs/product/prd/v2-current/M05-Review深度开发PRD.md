# M05 Review 复盘深度开发PRD

> 分支：`feature/review-deep` | 优先级：P1 | 预计工时：3天

## 一、模块定位

复盘是启明星系统的"成长引擎"，帮助用户每日/每周/每月回顾总结，沉淀经验教训，追踪个人成长。结合任务完成数据、文档记录、情绪状态，生成结构化复盘。

**核心目标**：让复盘成为习惯，让成长可见可追踪

## 二、当前实现状态

### 已实现
- 复盘编辑器（F01）：基础文本编辑
- 反思问题卡（F02）：引导性问题
- 情绪记录（F03）：心情/能量值记录
- 基础CRUD：创建/编辑/查看复盘
- 日期选择

### 未实现/待完善
- 复盘模板系统（每日/每周/每月）
- 复盘热力日历（J04）
- 情绪趋势图表
- 复盘与任务/文档关联
- 周复盘/月复盘自动生成
- 复盘导出
- 复盘搜索
- 成长时间线
- AI复盘助手（总结/建议）

## 三、深度开发功能清单

### P0 必须完成

#### F01 复盘模板系统
- **需求**：内置多种复盘模板，引导用户高效复盘
- **实现**：
  - 每日复盘模板：今日成就、不足、明日计划、感恩
  - 每周复盘模板：本周总结、数据回顾、下周目标
  - 每月复盘模板：月度总结、成长曲线、下月规划
  - KPT模板：Keep/Problem/Try
  - ORID模板：Objective/Reflective/Interpretive/Decisional
  - 自定义模板
- **数据模型**：`review_templates`表
- **验收**：选择模板后自动填充引导问题

#### F02 复盘热力日历
- **需求**：日历视图展示复盘记录，颜色深浅表示复盘质量
- **实现**：
  - 月历视图，每天一格
  - 有复盘的日期显示颜色（按字数/完成度）
  - 点击日期查看/创建当天复盘
  - 连续复盘天数统计
  - 月份切换
- **组件**：`ReviewHeatmapCalendar.vue`
- **验收**：有复盘的日期正确显示颜色，点击可查看

#### F03 情绪趋势图表
- **需求**：可视化展示情绪/能量变化趋势
- **实现**：
  - 折线图：最近30天心情/能量值
  - 情绪分布饼图
  - 能量值柱状图
  - 与任务完成率关联分析
  - 周/月/年维度切换
- **技术**：ECharts或SVG自绘
- **验收**：图表正确显示历史情绪数据

#### F04 复盘与任务/文档关联
- **需求**：复盘可关联当天完成的任务和文档
- **实现**：
  - 复盘编辑器中显示"今日完成任务"列表
  - 可勾选关联任务
  - 可引用文档片段
  - 关联内容自动插入复盘
  - 任务详情中可查看关联复盘
- **数据模型**：`review_relations`表

### P1 高质量打磨

#### F05 周/月复盘自动生成
- **需求**：基于每日复盘和任务数据，自动生成周/月复盘草稿
- **实现**：
  - 聚合本周/月任务完成数据
  - 提取每日复盘要点
  - 生成结构化总结草稿
  - 用户可编辑修改
  - 一键生成按钮
- **技术**：本地规则聚合（无AI也能用）+ AI增强（可选）

#### F06 复盘搜索
- **需求**：按关键词/日期/标签搜索历史复盘
- **实现**：
  - 搜索框即时搜索
  - 结果列表：日期 + 标题 + 摘要
  - 按月份筛选
  - 关键词高亮
- **技术**：SQLite LIKE查询

#### F07 成长时间线
- **需求**：时间线视图展示个人成长历程
- **实现**：
  - 按时间倒序展示重要复盘
  - 里程碑标记（连续30天、首次月复盘等）
  - 可筛选类型（成就/反思/计划）
  - 时间线滚动加载
- **组件**：`GrowthTimeline.vue`

#### F08 复盘导出
- **需求**：导出复盘为Markdown/PDF
- **实现**：
  - 单篇复盘导出
  - 按月/年批量导出
  - 导出包含情绪数据和关联任务
  - PDF排版优化

### P2 二期预研

#### F09 AI复盘助手
- AI总结一周复盘，给出成长建议
- AI识别重复问题，提醒改进
- AI生成月度成长报告

#### F10 复盘提醒
- 每日固定时间提醒复盘
- 桌宠气泡提醒
- 连续未复盘时激励提醒

#### F11 复盘分享
- 生成精美的复盘分享图
- 支持导出为图片

## 四、技术实现要点

### 前端
- `ReviewView.vue`重构：左侧日历/列表 + 右侧编辑器
- 新增组件：`ReviewHeatmapCalendar.vue`、`MoodTrendChart.vue`、`ReviewTemplateSelector.vue`、`GrowthTimeline.vue`、`ReviewRelationPanel.vue`
- `useReview` composable扩展：模板、搜索、统计、导出
- 图表：ECharts（轻量引入）或SVG自绘

### 后端
- `review_service.py`扩展：
  - 模板管理
  - 热力图数据聚合
  - 情绪趋势统计
  - 周/月复盘生成
  - 复盘搜索
- 新增模型：`ReviewTemplate`、`ReviewRelation`
- 新增迁移：0013_review_templates.py、0014_review_relations.py

### 性能
- 热力图数据按月加载
- 图表数据缓存
- 复盘列表分页

## 五、数据模型扩展

### review_templates表
```sql
CREATE TABLE review_templates (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  name TEXT NOT NULL,
  type TEXT NOT NULL, -- daily/weekly/monthly/custom
  content TEXT NOT NULL, -- JSON: [{question, placeholder}]
  is_builtin BOOLEAN DEFAULT 0,
  sort_order INTEGER DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### review_relations表
```sql
CREATE TABLE review_relations (
  id TEXT PRIMARY KEY,
  review_id TEXT NOT NULL REFERENCES reviews(id) ON DELETE CASCADE,
  related_type TEXT NOT NULL, -- task/document
  related_id TEXT NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(review_id, related_type, related_id)
);
```

### reviews表扩展
```sql
ALTER TABLE reviews ADD COLUMN template_id TEXT;
ALTER TABLE reviews ADD COLUMN mood_score INTEGER; -- 1-5心情
ALTER TABLE reviews ADD COLUMN energy_score INTEGER; -- 1-5能量
ALTER TABLE reviews ADD COLUMN tags TEXT; -- JSON数组
```

## 六、API接口设计

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/reviews` | 复盘列表（按日期/筛选） |
| POST | `/api/v1/reviews` | 创建复盘 |
| GET | `/api/v1/reviews/{date}` | 获取指定日期复盘 |
| PUT | `/api/v1/reviews/{id}` | 更新复盘 |
| DELETE | `/api/v1/reviews/{id}` | 删除复盘 |
| GET | `/api/v1/reviews/heatmap?year=&month=` | 热力图数据 |
| GET | `/api/v1/reviews/trend?days=30` | 情绪趋势数据 |
| GET | `/api/v1/reviews/templates` | 模板列表 |
| POST | `/api/v1/reviews/templates` | 创建模板 |
| POST | `/api/v1/reviews/generate?type=weekly` | 生成周/月复盘 |
| GET | `/api/v1/reviews/search?q=` | 搜索复盘 |
| GET | `/api/v1/reviews/{id}/export?format=` | 导出复盘 |

## 七、验收标准

1. 复盘模板可正常选择和使用
2. 热力日历正确显示复盘记录，颜色区分质量
3. 情绪趋势图表数据准确
4. 复盘可关联任务和文档
5. 周/月复盘可自动生成草稿
6. 复盘搜索功能正常
7. 成长时间线正确展示
8. 复盘导出格式正确
9. 四套主题下图表显示正常
10. 无AI时本地规则模式可正常生成周/月复盘

## 八、风险与依赖

- **依赖**：M02 Task（任务关联）、M03 Document（文档关联）
- **风险**：图表库可能增加包体积，需按需引入
- **兼容性**：情绪数据历史缺失时图表需处理空状态
- **数据迁移**：reviews表新增字段需处理旧数据
