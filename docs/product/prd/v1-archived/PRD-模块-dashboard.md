# PRD · 首页总览模块（mod-dashboard）

> 模块编号：mod-dashboard
> 所属维度：首页（dashboard）
> 文档版本：v1.0（模块化深度优化版）
> 日期：2026-09-18
> 状态：现状盘点完成，深度优化方向待排期
> 读者：前端开发、后端开发、产品经理、测试
> 代码基线：
> - 前端视图 `frontend/src/views/Dashboard/DashboardView.vue`
> - 前端数据层 `frontend/src/composables/useDashboard.ts`
> - 后端路由 `backend/app/api/dashboard.py`
> - 后端服务 `backend/app/services/dashboard_service.py`
> - 数据契约 `backend/app/schemas/dashboard.py`

---

## 目录

1. 模块定位与目标
2. 现状盘点（基于代码逐行确认）
3. 深度优化方向（P0 / P1 / P2）
4. 功能需求详细拆解（F1 ~ F15）
5. 移动端适配需求（375px 宽度）
6. 数据模型与 API 补充
7. 用户故事
8. 验收标准（模块级）
9. 风险与依赖

---

## 1. 模块定位与目标

### 1.1 一句话定位

首页总览（Dashboard）是用户打开启明星应用的**第一屏**，承担「状态感知 → 任务聚焦 → 跨模块导航」三重职责。用户在 3 秒内应当回答三个问题：

1. 我现在最该做什么？（今日最重要任务）
2. 今天还有多少事要处理？（今日执行概览）
3. 我人生的几条线各自推到哪了？（身份进度）

### 1.2 在六维导航中的位置

根据 `frontend/src/constants/dimensions.ts`，启明星系统采用六维导航：首页 / 执行 / 知识 / 人生 / 资产 / 伙伴。

| 维度 | 默认路由 | 首页是否聚合其数据 |
|------|----------|-------------------|
| 首页 dashboard | `/dashboard` | 本模块自身 |
| 执行 execution | `/tasks` | ✅ 今日执行、当前项目、今日最重要 |
| 知识 knowledge | `/documents` | ✅ 最近沉淀、资源中心计数 |
| 人生 life | `/identities` | ✅ 身份进度、经历时间线入口 |
| 资产 asset | `/learning` | ✅ 学习与成长、生活与自我、长期资产计数 |
| 伙伴 companion | `/conversation` | ✅ AI 助手状态、第二分身入口 |

首页是**唯一聚合全部六个维度数据的模块**，因此它的性能和加载体验直接决定用户对整个产品的第一印象。

### 1.3 本期深度优化目标

| 目标 | 量化指标 | 现状基线 |
|------|----------|----------|
| 首屏可交互时间 | P95 ≤ 800ms（本地 SQLite） | 当前全量拉任务，任务量 2000+ 时目测 > 2s |
| 卡片个性化编排 | 用户可拖拽排序、可隐藏卡片、排序持久化 | 拖拽排序已有，隐藏未实现 |
| AI 摘要落地 | 首页渲染 AI 助手状态卡 + 快捷提问入口 | API 已返回 `ai_assistant`，前端未渲染 |
| 数据契约收敛 | Schema 中存在但未渲染的字段必须落地或标注废弃 | `quick_actions` / `week_progress` / `streak` / `assets` 均未渲染 |
| 移动端可用 | 375px 宽度下无横向滚动、可单手操作 | 当前仅有 1024px 断点，手机端三列网格塌缩为单列但未做交互适配 |

### 1.4 非目标（本期不做）

- 不在首页做任务的编辑/删除操作（跳转任务模块完成）
- 不在首页做富文本/文档预览（跳转文档模块完成）
- 不做服务端推送/实时同步（一期本地优先，手动刷新即可）
- 不做首页自定义主题色（主题切换走全局四套主题）

---

## 2. 现状盘点（基于代码逐行确认）

### 2.1 已渲染卡片清单（DashboardView.vue 模板）

| 序号 | 卡片 ID | 标题 | 数据来源 | 开发状态 | 是否全宽 |
|------|---------|------|----------|----------|----------|
| 0 | hero | Banner 大标题区 | `data.user` | ready | ✅ 通栏 |
| 1 | focus | ⭐ 今日最重要 | `data.focus_task` | ready | ✅ 通栏 |
| 2 | execution | 📋 今日执行 | `data.today_execution` | ready | ✅ 通栏 |
| 3 | projects | 📁 当前项目 | `data.projects` | beta | 三列网格 |
| 4 | identities | 🧭 身份进度 | `data.identities` | ready | 三列网格 |
| 5 | resources | 🗂️ 资源中心 | `data.resource_center` | beta | 三列网格 |
| 6 | learning | 📚 学习与成长 | `data.learning` | beta | 三列网格 |
| 7 | recent | 📝 最近沉淀 | `data.recent_documents` | ready | 三列网格 |
| 8 | life | 💚 生活与自我 | `data.life` | beta | 三列网格 |

### 2.2 API 已返回但前端未渲染的字段（技术债清单）

以下字段在 `DashboardDataOut` schema 中已定义、后端已计算、前端 CSS 甚至预留了样式类（`.dash__quick` / `.dash__ai` / `.dash__assets`），但模板中**没有任何节点消费它们**：

| 字段 | Schema 定义位置 | 后端计算位置 | 前端预留样式 | 处置建议 |
|------|----------------|-------------|-------------|----------|
| `quick_actions` | `QuickActions` / `QuickAction` | `QUICK_ACTIONS` 常量（9 项） | `.dash__quick` / `.dash__quick-item` / `.dash__quick-icon` / `.dash__quick-name` | **P0 落地**：补齐快速入口卡 |
| `ai_assistant` | `AIAssistantStatus` | `get_settings()` + `user.api_key_encrypted` | `.dash__ai` / `.dash__ai-desc` / `.dash__ai-prompts` / `.dash__ai-prompt` | **P0 落地**：补齐 AI 摘要卡 |
| `week_progress` | `WeekProgress` | `_build_week_progress(all_tasks)` | 无 | **P1 落地**：本周进度环 |
| `streak` | `StreakData` | `_build_streak()` | 无 | **P1 落地**：连续打卡徽章 |
| `assets` | `AssetsSection` / `AssetCategory` | 4 个 repo.count() | `.dash__assets` / `.dash__asset` / `.dash__assets-enter` | **P2 落地**：长期资产库卡（与资源中心合并或独立） |
| `modules_status` | `list[ModuleStatusItem]` | `MODULES_STATUS` 常量（10 项） | 无 | **P2 落地**：用于灰度开关，前端可用于「待开发」标签的统一管理 |

> 结论：后端做了大量「预埋」工作，前端处于半完成状态。本期 PRD 的核心价值之一就是把这些预埋字段全部落地，消除技术债。

### 2.3 已实现交互盘点

| 交互 | 实现方式 | 代码位置 |
|------|----------|----------|
| 卡片拖拽排序 | HTML5 DragEvent，`localStorage` 持久化 | `onDragStart` / `onDragOver` / `onDrop`，key = `venustech_dashboard_card_order` |
| 默认卡片顺序 | `['focus','execution','projects','identities','resources','learning','recent','life']` | `defaultOrder` 常量 |
| 拖拽悬停态 | `dragOverCard` ref 控制 `.is-drag-over` class | `onDragOver` / `onDragLeave` |
| 待开发灰度 | `opacity: 0.55; filter: grayscale(0.3)` | `.is-planned` 样式 |
| 提交成果 | `updateTask(id, { status: 'completed' })` + toast | `submitFocusTask()` |
| 优先级圆点 | urgent=--strawberry / high=--butter / medium=--sky / low=--mint | `.dash__exec-dot.is-*` |
| 状态标签语义 | pending=default / in_progress=butter / waiting=lilac / completed=mint | `STATUS_SEMANTIC` 映射 |
| 骨架屏 | `BaseSkeleton variant="list" :rows="N"` | 每张卡片 loading 分支 |
| 空状态 | `BaseEmpty` + 引导按钮 | 每张卡片无数据分支 |
| Hero 入场动画 | `slide-in-up 0.5s var(--ease-soft)` + 星星 `sparkle 2s infinite` | `.dash__hero-title` / `.dash__hero-star` |
| 进度条动画 | `transition: width 0.5s var(--ease-soft)` | `.dash__bar-fill` |
| 项目/身份 hover | `background: var(--bg-inset)` 150ms | `.dash__project` / `.dash__identity` |

### 2.4 后端数据流盘点

```
GET /dashboard
  └── DashboardService.get()
        ├── list_user_tasks(user.id)          ← 【性能瓶颈】全量加载所有任务
        ├── doc_repo.recent(user.id, 5)      ← 最近文档
        ├── IdentityRepository.list_user()   ← 身份列表
        ├── ProjectService.list(user.id)     ← 项目（失败降级 project_tag 聚合）
        ├── inbox_repo.count()               ← 资源中心（3 个 COUNT）
        ├── learning_svc.list_plans()         ← 学习（含分页查询）
        ├── flashcard_repo.count()            ← 学习（2 个 COUNT）
        ├── habit_repo.count()                ← 生活
        ├── life_svc.get_mood_stats()         ← 生活
        ├── sop/prompt/skill/memory_repo.count()  ← 资产（4 个 COUNT）
        ├── Review 表查询近 30 天             ← 连续打卡
        └── get_settings()                   ← AI 模型名
```

**关键性能问题**：`list_user_tasks(user.id)` 返回该用户**全部**任务记录（含已完成、含所有分页外数据），然后在 Python 内存中做：
- `next(...)` 找 focus_task
- 4 次 `sum(1 for t in all_tasks if ...)` 算今日统计
- `_build_today_execution` 遍历全量过滤「今日可执行」
- `_build_identities` 遍历全量按 identity_id 分组
- `_build_projects` 遍历全量按 project_tag 聚合
- `_build_week_progress` 遍历全量按 due_date 过滤本周

这意味着用户任务量增长到 5000+ 时，首页每次打开都要：
1. 一次性 SELECT 5000+ 行任务（含 ORM hydrate）
2. 在 Python 里遍历 6 遍

**修复方向**：把「今日可执行」「本周到期」「focus_task」「各身份计数」下推到 SQL 层，首页只取需要的数据。详见 F13。

### 2.5 已知缺陷与不一致

| 编号 | 缺陷 | 代码位置 | 严重度 |
|------|------|----------|--------|
| B-01 | 三列网格在 ≤1024px 时塌缩为 `1fr`，但没有针对 375px 手机的单列交互适配（卡片间距、字号、触控热区） | `@media (max-width: 1024px)` | 中 |
| B-02 | `.is-planned` 设置了 `pointer-events: none` 但子元素 `pointer-events: auto`，导致灰度卡仍然可点，与「待开发」语义矛盾 | `.is-planned` 样式 | 低 |
| B-03 | `quick_actions` 中 `voice_record` 状态为 `planned`，但前端未渲染，用户看不到这个「即将上线」的提示 | `QUICK_ACTIONS` | 低 |
| B-04 | 拖拽排序仅在桌面端 HTML5 DnD 有效，手机端无长按拖拽 | `onDragStart` 等 | 中 |
| B-05 | `week_progress` 和 `streak` 数据已算好但前端不展示，属于「白算」 | `_build_week_progress` / `_build_streak` | 中 |
| B-06 | 身份进度卡点击跳转 `/tasks?identity_id=xxx`，但未确认任务列表页是否消费该 query 参数 | `router.push({ query: { identity_id } })` | 待验证 |
| B-07 | 学习与成长卡的「今日学习」进度条硬编码 `width: 0%`，未绑定真实数据 | `.dash__learning-item` 模板 | 低 |
| B-08 | 最近沉淀卡点击任意文档都跳 `/documents`（列表页），未跳转到具体文档编辑页 | `router.push('/documents')` | 中 |

---

## 3. 深度优化方向（P0 / P1 / P2）

### 3.1 优先级总览

| 优先级 | 方向 | 涉及功能点 | 预期收益 |
|--------|------|-----------|----------|
| **P0** | 首屏性能优化：任务查询下推 SQL | F13 | 首屏 P95 从 >2s 降到 <800ms |
| **P0** | 快速入口卡落地（`quick_actions`） | F10 | 用户高频操作 1 步直达 |
| **P0** | AI 摘要卡落地（`ai_assistant`） | F11 | 产品差异化卖点可见化 |
| **P0** | 移动端 375px 适配 | F14 | 手机端可用 |
| **P1** | 本周进度环落地（`week_progress`） | F12.1 | 周维度节奏感 |
| **P1** | 连续打卡徽章落地（`streak`） | F12.2 | 留存激励 |
| **P1** | 卡片隐藏/显示配置 | F12.3 | 个性化编排闭环 |
| **P1** | 修复已知缺陷 B-02 / B-06 / B-08 | — | 一致性 |
| **P2** | 长期资产库卡落地（`assets`） | F15.1 | 资产维度可见 |
| **P2** | 手机端长按拖拽排序 | F15.2 | 移动端个性化 |
| **P2** | 模块状态灰度统一管理（`modules_status`） | F15.3 | 前端可维护性 |

### 3.2 P0 详述：首屏性能优化

**问题根因**（`dashboard_service.py` 第 149 行）：

```python
all_tasks = self.task_repo.list_user_tasks(self.user.id)
```

这一行把用户所有任务拉进内存。后续 6 个 `_build_*` 方法各自遍历这个列表。当任务量到数千级，ORM hydrate 和 Python 遍历都成为瓶颈。

**优化策略**：

| 原做法 | 新做法 | 收益 |
|--------|--------|------|
| 全量 SELECT + 内存过滤今日可执行 | SQL `WHERE status IN (...) AND (due_date <= :today OR status IN ('in_progress','waiting'))` | 只取今日需要的 ~20 条 |
| 全量遍历找 focus_task | SQL `WHERE is_focus = 1 AND user_id = :uid` LIMIT 1 | 只取 1 条 |
| 全量遍历算本周到期 | SQL `WHERE due_date BETWEEN :monday AND :sunday` | 只取本周 ~50 条 |
| 全量遍历按身份分组计数 | SQL `GROUP BY identity_id, status` | 聚合下推数据库 |
| 全量遍历按 project_tag 聚合 | SQL `GROUP BY project_tag` | 聚合下推数据库 |

**验收标准**：
- [ ] 首屏 SQL 查询次数 ≤ 8 次（当前为 1 + 6 次内存遍历）
- [ ] 任务量 5000 时 P95 首屏可交互 ≤ 800ms
- [ ] 内存中 `all_tasks` 变量移除，不再全量加载
- [ ] 各 `_build_*` 方法改为接收 SQL 结果集而非全量列表

### 3.3 P0 详述：个性化卡片编排闭环

现状已有拖拽排序（P2 时代遗留），但缺少：
1. **隐藏卡片**：用户不需要的卡片（如「学习与成长」）应能暂时收起
2. **排序持久化跨设备**：当前存 localStorage，换设备/清缓存即丢失（本期接受 localStorage，但需预留服务端字段）
3. **重置默认排序**：提供「恢复默认」入口
4. **移动端拖拽**：手机端长按进入拖拽模式

---

## 4. 功能需求详细拆解

> 编号规则：F{模块}.{序号}。每个功能点包含：功能描述、验收标准（checkbox）、交互细节（含动画时长/偏移量数值）、状态全覆盖（默认/空/加载/错误）。

---

### F1. Hero 欢迎区

#### F1.1 标题与问候语

**功能描述**：
通栏横幅，左侧展示主标题「专注当下，持续创造真实成果」+ 问候语 + 用户昵称；右侧展示一颗闪烁的星星图标。

**数据来源**：`data.user.greeting`（后端按小时计算）+ `data.user.nickname`。

**验收标准**：
- [ ] 主标题字号使用 `--text-xl`（24px），字重 800，字体 `--font-cute`
- [ ] 问候语由后端 `greeting_by_hour()` 计算，分时段正确（6-12 早上好 / 12-18 下午好 / 18-24 晚上好 / 0-6 夜深了）
- [ ] 昵称为空时显示默认值「启明星用户」
- [ ] 副标题文案：`{greeting}，{nickname} · 你的人生与项目，由你主导；系统记住一切，帮你推进一步。`
- [ ] 横幅背景使用 `linear-gradient(135deg, var(--primary-soft), var(--lilac-soft))`，圆角 `--radius-lg`（24px）

**交互细节**：
- 标题入场动画：`slide-in-up 0.5s var(--ease-soft)`（opacity 0→1，translateY 10px→0）
- 星星图标：`sparkle 2s var(--ease-soft) infinite`（opacity 0.6，颜色 `--primary`）
- 横幅左右 padding：`--space-2 var(--space-4)`（8px 16px）
- 昵称超长时单行省略，最大宽度不超过横幅可用宽度的 60%

**状态全覆盖**：
- 默认态：正常显示标题 + 问候 + 昵称 + 星星
- 加载态：Hero 区骨架屏（标题 1 行 + 副标题 1 行，高度占位 80px）
- 错误态：问候语获取失败时显示「你好」，不影响昵称和标题
- 空态：昵称为空显示「启明星用户」，无其他异常

---

### F2. 今日最重要任务卡（focus）

#### F2.1 任务信息展示

**功能描述**：
通栏大卡，展示当前设为「今日最重要」的任务。字段：任务标题、项目标签 chip、下一步行动描述、进度条、进度百分比。

**数据来源**：`data.focus_task`（后端 `next(t for t in all_tasks if t.is_focus)`）。

**验收标准**：
- [ ] 卡片标题「⭐ 今日最重要」，右上角状态标签（完成时显示「已完成」mint 语义，否则显示当前 stage）
- [ ] 任务标题字号 `--text-lg`（18px），字重 700
- [ ] 项目标签 chip：圆角 `--radius-pill`，背景 `--primary-soft`，文字色 `--primary`，字号 `--text-xs`
- [ ] 下一步行动文案：`下一步：{next_step || '继续推进'}`，颜色 `--text-mid`，字号 `--text-xs`
- [ ] 进度条高度 6px，圆角 `--radius-pill`，背景 `--bg-inset`，填充色 `--primary`
- [ ] 进度百分比文字在进度条下方，字号 `--text-xs`，颜色 `--text-mid`

**交互细节**：
- 进度条入场动画：进入页面时 width 从 0% 过渡到实际值，`transition: width 0.5s var(--ease-soft)`
- 两个按钮间距 `--space-3`（12px）：「继续工作」primary variant → `/tasks`；「提交成果」secondary variant → 调用 `updateTask`
- 「提交成果」成功后 toast：`toast.success('提交成果', '任务已标记完成 🎉')`
- 「提交成果」失败后 toast：`toast.error('操作失败', '请稍后重试')`

**状态全覆盖**：
- 默认态：有 focus_task，正常展示
- 空状态：无 focus_task 时显示 `BaseEmpty`：标题「今天还没有设定最重要的任务」，描述「去任务模块选一个吧，让今天有焦点」，主按钮「去任务模块」→ `/tasks`
- 加载态：`BaseSkeleton variant="list" :rows="2"`
- 错误态：接口失败时显示「加载失败，点击重试」（需新增），重试按钮重新调用 `fetchDashboard()`
- 完成态：任务已完成时，进度条填充 100%，状态标签显示「已完成」mint 色，「提交成果」按钮置灰

---

### F3. 今日执行卡（execution）

#### F3.1 按状态分组展示

**功能描述**：
通栏卡片，按任务状态分三组展示今日可执行任务：必须完成（pending）/ 进行中（in_progress）/ 等待处理（waiting）。每组最多展示 5 条。

**数据来源**：`data.today_execution.groups`（后端 `_build_today_execution`）。

**业务规则**（来自 `_is_actionable_today`）：
- `in_progress` / `waiting`：无论截止日期，都计入今日执行
- `pending`：仅当 `due_date <= today`（今日到期或已逾期）才计入
- 无截止日期的 pending 任务不计入

**排序规则**（来自 `sort_key`）：
1. 已逾期（due_date < today）— urgency = 0
2. 今日到期（due_date == today）— urgency = 1
3. 无截止日期 — urgency = 2
4. 未来到期（due_date > today）— urgency = 3
- 同级按优先级排序：high(0) > medium(1) > low(2)

**验收标准**：
- [ ] 卡片标题「📋 今日执行」，右上角 mint 语义标签显示总项数 `{total} 项`
- [ ] 三组顺序固定：必须完成 → 进行中 → 等待处理
- [ ] 每组标题行：左侧图标（pending=target / in_progress=spin / waiting=dot）+ 组名 + 右侧「N 项」
- [ ] 每组最多展示 5 条任务，超出的不展示（后端已截断）
- [ ] 每条任务前有优先级圆点：urgent=--strawberry / high=--butter / medium=--sky / low=--mint
- [ ] 点击任意任务跳转到 `/tasks`（跳转后应自动定位到该任务，本期可接受跳到列表页）
- [ ] 组内无任务时显示「暂无任务」，缩进 `padding-left: var(--space-4)`

**交互细节**：
- 任务列表项 hover 时背景 `--bg-inset`，圆角 `--radius-sm`，padding `var(--space-1) var(--space-2)`
- 任务标题超长单行省略（`text-overflow: ellipsis; white-space: nowrap`）
- 组间距 `--space-3`（12px），组内列表间距 `--space-1`（4px）
- 卡片支持 `scroll` 属性（BaseCard 自带滚动），内容超高时卡片内部滚动而非撑破布局

**状态全覆盖**：
- 默认态：有今日可执行任务，正常分组展示
- 空状态：三组全空时，卡片整体显示「今天没有需要动手的任务，享受一下吧」（需新增）
- 加载态：`BaseSkeleton variant="list" :rows="3"`
- 错误态：接口失败显示「加载失败，点击重试」

---

### F4. 当前项目卡（projects）

#### F4.1 项目进度列表

**功能描述**：
三列网格卡片，展示用户当前进行中的项目，最多 5 个。每个项目显示名称、进度百分比、进度条、完成任务数/总任务数。

**数据来源**：`data.projects.items`（后端优先 `ProjectService.list`，失败降级 `project_tag` 聚合）。

**验收标准**：
- [ ] 卡片标题「📁 当前项目」，右上角根据 `status` 显示标签：ready 无标签 / beta 显示「内测」butter 色 / planned 显示「待开发」default 色
- [ ] 每个项目行：项目名（左，`--text-base` 13px 字重 600）+ 百分比（右，`--primary` 色字重 600）
- [ ] 项目进度条高度 4px（`--bar--sm`），填充色 `--primary`
- [ ] 项目元信息：`{completed_count}/{task_count} 任务完成`，字号 `--text-xs`，颜色 `--text-low`
- [ ] 点击项目行跳转到 `/projects/{p.id}`
- [ ] hover 时背景微亮，圆角 `--radius-sm`

**交互细节**：
- 项目间距 `--space-3`（12px）
- 进度条 width 过渡 0.5s `--ease-soft`
- 项目行 padding 4px，margin -4px（hover 背景不撑破边距）

**状态全覆盖**：
- 默认态：有项目，展示进度列表
- 空状态：`BaseEmpty`「还没有项目」+ 描述「去项目管理创建第一个项目」+ 主按钮「创建项目」→ `/projects`
- 加载态：`BaseSkeleton variant="list" :rows="3"`
- 降级态：ProjectService 失败时，后端返回 `status="planned"` 的 project_tag 聚合结果，前端显示「内测」标签但内容仍展示（需确认当前降级路径）

---

### F5. 身份进度卡（identities）

#### F5.1 人生线进度

**功能描述**：
三列网格卡片，按身份（人生线）聚合任务进度。每行显示：身份色点、身份图标、身份名、待办数、进行中数、今日完成数。底部显示未归类任务提示。

**数据来源**：`data.identities.items` + `data.identities.unassigned_open`。

**验收标准**：
- [ ] 卡片标题「🧭 身份进度」，右上角链接按钮「经历时间线 →」→ `/experience`
- [ ] 每个身份行：10px 色点（`colorVar(i.color_token)`）+ 14px 图标 + 身份名 + 右侧统计
- [ ] 统计格式：`{open_tasks} 待办 · {in_progress} 进行 · 今日 +{completed_today}`
- [ ] 待办数为 0 时数字变灰（`.is-zero` class，颜色 `--text-low`）
- [ ] 已归档身份（`is_archived=true`）行 opacity 0.5
- [ ] 未归类任务数 > 0 时，底部显示：`另有 {unassigned_open} 个未归类任务 —— 建立身份后给任务挂上，线才看得清`，「建立身份」链接 → `/identities`
- [ ] 点击身份行跳转到 `/tasks?identity_id={i.id}`

**交互细节**：
- 身份行 padding 7px `var(--space-2)`，圆角 `--radius-sm`
- hover 时背景 `--bg-inset`，过渡 150ms `--ease-soft`
- 身份名超长单行省略

**状态全覆盖**：
- 默认态：有身份，展示进度
- 空状态：无身份时 `BaseEmpty`「还没有身份」+ 描述「身份是人生的分类轴：AI 研究、音乐、交易……各是一条线」+ 主按钮「建立身份」→ `/identities`
- 加载态：`BaseSkeleton variant="list" :rows="3"`
- 归档态：已归档身份降透明度但仍可见

---

### F6. 资源中心卡（resources）

#### F6.1 资源计数网格

**功能描述**：
三列网格卡片，2 列布局展示资源中心各分类计数：收集箱 / 模板库 / 领域库。

**数据来源**：`data.resource_center.categories`（后端真实 COUNT 查询）。

**验收标准**：
- [ ] 卡片标题「🗂️ 资源中心」，右上角状态标签
- [ ] 2 列 grid 布局，gap `--space-2`（8px）
- [ ] 每个资源项：16px 图标（`--primary` 色）+ 名称（左）+ 计数（右，`--text-low` 字重 600）
- [ ] 点击资源项跳转到 `/resource-center`
- [ ] hover 时背景 `--bg-inset`，圆角 `--radius-sm`

**交互细节**：
- 资源项 padding `--space-2`，字号 `--text-sm`（12px）

**状态全覆盖**：
- 默认态：展示真实计数
- 降级态：后端聚合失败时 `status="planned"`，返回占位数据（7 个分类 count=0），前端灰度显示
- 加载态：整卡骨架屏
- 空态：所有分类计数为 0 时仍正常展示 0（不显示空状态，因为资源中心本身是入口）

---

### F7. 学习与成长卡（learning）

#### F7.1 学习概览

**功能描述**：
三列网格卡片，展示今日学习进度、进行中学习计划数、今日复习卡片数。

**数据来源**：`data.learning`（后端 `learning_svc.list_plans` + `flashcard_repo`）。

**验收标准**：
- [ ] 卡片标题「📚 学习与成长」，右上角状态标签
- [ ] 三行信息：今日学习（进度条 + 百分比）/ 学习计划（进行中 N 项）/ 知识卡片（今日复习 N 张）
- [ ] 底部链接「进入学习中心 →」→ `/learning`
- [ ] 修复 B-07：今日学习进度条必须绑定真实数据，不得硬编码 `width: 0%`

**交互细节**：
- 标签列宽度固定 `min-width: 60px`，值列右对齐
- 进度百分比用 `--primary` 色字重 600
- 底部链接居中，`--text-sm`，`--primary` 色

**状态全覆盖**：
- 默认态：展示真实学习数据
- 降级态：学习服务异常时 `status="planned"`，前端灰度
- 空态：无学习计划时显示「开始第一个学习计划吧」
- 加载态：骨架屏

---

### F8. 最近沉淀卡（recent）

#### F8.1 最近文档列表

**功能描述**：
三列网格卡片，展示最近修改的 5 篇文档。每项显示文档图标、标题、更新时间、最多 2 个标签。

**数据来源**：`data.recent_documents`（后端 `doc_repo.recent(limit=5)`）。

**验收标准**：
- [ ] 卡片标题「📝 最近沉淀」
- [ ] 每项：16px 文档图标 + 标题（左，`--text-base`）+ 时间（右，`--text-low`）+ 最多 2 个 lilac 语义标签
- [ ] 时间格式 `MM-DD HH:mm`（当前 `fmtTime`）
- [ ] 标签超过 2 个时只显示前 2 个
- [ ] 点击文档项跳转到 `/documents`（**P1 修复**：应跳转到具体文档 `/documents/{d.id}`）

**交互细节**：
- 文档项 padding `var(--space-2) var(--space-3)`，圆角 `--radius-md`（16px）
- hover 时背景 `--bg-inset`，过渡 150ms
- 标题超长单行省略

**状态全覆盖**：
- 默认态：展示 5 篇文档
- 空状态：`BaseEmpty`「还没有文档」+ 描述「创建第一篇笔记吧」
- 加载态：`BaseSkeleton variant="list" :rows="3"`

---

### F9. 生活与自我卡（life）

#### F9.1 生活指标

**功能描述**：
三列网格卡片，展示习惯数、心情均分、日记、成长四个生活指标项。

**数据来源**：`data.life.categories`（后端 `habit_repo.count` + `life_svc.get_mood_stats`）。

**验收标准**：
- [ ] 卡片标题「💚 生活与自我」，右上角状态标签
- [ ] 4 个生活项：习惯（N 项，「坚持打卡」）/ 心情（近 7 天均分 X.X）/ 日记 / 成长
- [ ] 每项：16px 图标（`--mint` 色）+ 名称（上）+ 值（下，`--text-xs`）
- [ ] 底部链接「记录生活，自我觉察 →」→ `/life`
- [ ] 心情无记录时显示「暂无记录」

**交互细节**：
- 生活项 padding `--space-2`，圆角 `--radius-sm`
- hover 时背景 `--bg-inset`

**状态全覆盖**：
- 默认态：展示真实数据
- 降级态：生活服务异常时 `status="planned"`，返回占位文案
- 空态：无习惯/无心情记录时正常展示「暂无记录」
- 加载态：骨架屏

---

### F10. 快速入口卡（quick_actions）【P0 新增落地】

#### F10.1 高频操作直达

**功能描述**：
通栏或三列网格卡片，展示 9 个快速操作入口。当前 API 已返回 `quick_actions.items` 但前端未渲染。本功能点要求补齐渲染。

**数据来源**：`data.quick_actions.items`（后端 `QUICK_ACTIONS` 常量，9 项）。

**入口清单**：

| ID | 名称 | 图标 | 跳转 | 状态 |
|----|------|------|------|------|
| new_task | 新建任务 | plus | `/tasks?action=new` | ready |
| new_doc | 新建笔记 | doc | `/documents?action=new` | ready |
| new_project | 新建项目 | folder | `/projects?action=new` | ready |
| inbox | 收集箱 | inbox | `/resource-center` | ready |
| workflow | 工作流 | workflow | `/workflows` | ready |
| avatar | 第二分身 | robot | `/avatar` | ready |
| aihot | AI 资讯 | spark | `/aihot` | ready |
| pet | 桌宠设置 | pet | `/pet` | ready |
| voice | 语音记录 | mic | `voice_record`（命令） | planned |

**验收标准**：
- [ ] 卡片标题「⚡ 快速入口」
- [ ] 3 列 grid 布局（桌面端），gap `--space-2`
- [ ] 每个入口项：图标（上，`--primary` 色）+ 名称（下，`--text-xs`），纵向排列
- [ ] 每项 padding `--space-3 var(--space-2)`，圆角 `--radius-md`，边框 `1px solid var(--line)`，背景 `--bg-panel`
- [ ] `planned` 状态的入口（voice）灰度显示，点击提示「即将上线」
- [ ] `action` 以 `/` 开头的走 `router.push(action)`；以 `voice_record` 等命令开头的走对应命令分发
- [ ] 特别注意：`?action=new` 参数由目标页面的 `useQueryAction` 消费后自动打开新建弹窗（已在后端注释中确认此修复 R-02）

**交互细节**：
- hover 时 `transform: translateY(-2px)` + 背景 `--bg-inset`，过渡 150ms
- 点击后按钮短暂 `--primary-soft` 背景反馈（100ms）再跳转
- planned 项降低 opacity 0.55，cursor 变为 not-allowed

**状态全覆盖**：
- 默认态：9 个入口正常展示
- 加载态：6 个骨架占位块
- 空态：无（入口是配置常量，始终有数据）
- 错误态：API 返回空数组时显示「暂无快速入口配置」

---

### F11. AI 摘要卡（ai_assistant）【P0 新增落地】

#### F11.1 AI 助手状态与快捷提问

**功能描述**：
展示 AI 助手是否已启用、当前模型、3 个快捷提问按钮。当前 API 已返回 `ai_assistant` 但前端未渲染。

**数据来源**：`data.ai_assistant`（后端：`enabled = bool(user.api_key_encrypted) and user.ai_enabled`，`model = settings.ai_model`）。

**验收标准**：
- [ ] 卡片标题「🤖 AI 助手」
- [ ] 状态行：启用时显示「已连接 · {model}」，mint 色圆点；未启用时显示「未配置 API Key」，`--text-low` 色
- [ ] 描述文案：根据 enabled 状态展示不同引导文案
- [ ] 3 个快捷提问按钮：「帮我总结今天」「生成明日计划」「头脑风暴」
- [ ] 快捷按钮样式：圆角 `--radius-pill`，背景 `--primary-soft`，文字 `--primary`，字号 `--text-sm`
- [ ] 点击快捷按钮跳转到 `/conversation`（第二分身对话页），并把提问文案作为初始消息传入
- [ ] 未启用 API Key 时，快捷按钮置灰，点击跳转到设置页引导配置

**交互细节**：
- 快捷按钮 flex-wrap 布局，gap `--space-2`
- hover 时背景 `--bg-inset`
- 启用状态圆点带呼吸动画（opacity 0.6→1→0.6，2s 循环）

**状态全覆盖**：
- 默认态（已启用）：显示模型名 + 3 个可点击快捷按钮
- 未启用态：显示「去配置 API Key」引导按钮 → `/settings`
- 加载态：骨架屏
- 错误态：API 异常时显示「AI 状态获取失败」

---

### F12. 本周进度环与连续打卡【P1 新增落地】

#### F12.1 本周进度环（week_progress）

**功能描述**：
以环形进度条展示本周（周一至周日）任务完成率。

**数据来源**：`data.week_progress`（后端 `_build_week_progress(all_tasks)`：本周 due_date 范围内，已完成数 / 总数）。

**验收标准**：
- [ ] 环形进度条直径 80px，stroke 宽度 8px
- [ ] 环背景色 `--line`，填充色 `--primary`，圆角端点
- [ ] 环中心显示百分比数字（`--text-md` 字重 700）
- [ ] 环下方显示「本周完成 {completed}/{total} 项」
- [ ] 本周无任务时（total=0），环显示 0%，下方文案「本周还没有安排任务」

**交互细节**：
- 环入场动画：stroke-dashoffset 从满环过渡到目标值，`0.8s var(--ease-soft)`
- hover 时环颜色微亮（opacity 0.8→1）

#### F12.2 连续打卡徽章（streak）

**功能描述**：
展示连续复盘天数 + 本周 7 天打卡情况（周一至周日 7 个圆点）。

**数据来源**：`data.streak`（后端 `_build_streak()`：查 Review 表近 30 天，从今天往前数连续天数）。

**验收标准**：
- [ ] 左侧大数字：连续打卡天数（`--text-2xl` 32px，字重 800，`--gold` 色）+ 「天」字
- [ ] 右侧 7 个小圆点（直径 12px），周一至周日排列
- [ ] 已打卡圆点填充 `--gold`，未打卡填充 `--line`
- [ ] 今天的圆点带脉冲动画（`box-shadow` 扩散，1.5s 循环）
- [ ] streak=0 时数字显示灰色，文案「还没有连续打卡，今天开始第一次复盘吧」

**交互细节**：
- 大数字入场：`count-up` 动画从 0 到实际天数，0.6s `--ease-soft`
- 7 个圆点间距 `--space-1`（4px），当前天圆点放大 1.2 倍

---

### F13. 首屏性能优化【P0】

#### F13.1 任务查询下推 SQL

**功能描述**：
将 `dashboard_service.py` 中的全量任务加载改为按需 SQL 查询，消除内存遍历瓶颈。

**改造点**：

| 原方法 | 原数据来源 | 新数据来源 |
|--------|-----------|-----------|
| focus_task | `next(t for t in all_tasks if t.is_focus)` | `task_repo.get_focus_task(user_id)` 新增方法 |
| today_stats | 4 次 `sum(1 for t in all_tasks if ...)` | `task_repo.count_today_stats(user_id, day_start, day_end)` 新增方法 |
| today_execution | 全量过滤 + 排序 + 截断 5 | `task_repo.list_actionable_today(user_id, today, limit=5)` 新增方法 |
| identities | 全量按 identity_id 分组计数 | `task_repo.count_by_identity(user_id, day_start, day_end)` 新增方法 |
| projects | 全量按 project_tag 聚合 | ProjectService 已有，保持不变 |
| week_progress | 全量按 due_date 过滤本周 | `task_repo.count_week_progress(user_id, monday, sunday)` 新增方法 |

**验收标准**：
- [ ] 移除 `all_tasks = self.task_repo.list_user_tasks(self.user.id)` 这一行
- [ ] 新增 Repository 方法，每个方法只查询首页需要的数据量
- [ ] 首屏 SQL 总查询次数 ≤ 8 次（当前为 1 次全量 + 6 次内存遍历）
- [ ] 任务量 5000 时，首屏 P95 可交互时间 ≤ 800ms（本地 SQLite）
- [ ] 各 `_build_*` 方法签名改为接收查询结果集而非 `all_tasks`
- [ ] 现有功能行为不变（今日执行口径、身份统计口径、周进度口径必须与改造前一致）
- [ ] 添加单元测试验证改造前后数据一致

**交互细节**：
- 前端 `useDashboard` 无需改动（API 契约不变）
- 加载态骨架屏时长从「全量加载」变为「按需加载」，骨架屏闪烁时间应明显缩短

---

### F14. 移动端适配（375px 宽度）【P0】

#### F14.1 布局塌缩与触控优化

**功能描述**：
当前仅有 `@media (max-width: 1024px)` 断点将三列网格塌缩为单列。手机端（375px 宽度）需要进一步优化交互。

**验收标准**：
- [ ] 375px 宽度下无横向滚动
- [ ] 三列网格（`dash__grid-3`）在 ≤ 640px 时塌缩为单列（当前 1024px 断点即可满足，但需验证 375px 下卡片间距合适）
- [ ] 卡片间距从 `--space-3`（12px）在手机端保持不变，卡片内 padding 从 `--space-3` 保持不变
- [ ] 所有可点击元素最小触控热区 44×44px（iOS HIG 标准）
- [ ] 「继续工作」「提交成果」按钮在手机端全宽排列（flex-direction: column），不挤压
- [ ] Hero 区星星图标在手机端缩小至 32px（当前 48px）
- [ ] 进度条高度在手机端保持 6px 不变（过细难以辨识）
- [ ] 身份进度行的统计文字在手机端允许换行（当前 flex 布局可能挤压）

**交互细节**：
- 手机端卡片进入动画改为 `slide-in-up 0.4s var(--ease-soft)`（比桌面端 0.5s 稍快）
- 手机端 hover 效果全部移除（无 hover 概念），改为 `:active` 状态：`transform: scale(0.98)` + 背景微暗
- 拖拽排序在手机端改为长按进入编辑模式（详见 F15.2）

**状态全覆盖**：
- 默认态：375px 单列布局，单手可滑动浏览
- 横屏态：375px 高度的横屏场景下，卡片不应过度拉伸（max-width 限制）
- 折叠屏态：≥ 768px 时保持双列布局（需新增 768px 断点：双列）

---

### F15. 长期资产库与其他【P2】

#### F15.1 长期资产库卡（assets）

**功能描述**：
三列网格卡片，展示 SOP / Prompt / Skill / 项目记忆 四个资产分类计数。

**数据来源**：`data.assets.categories`（后端 4 个 repo.count()）。

**验收标准**：
- [ ] 卡片标题「🏛️ 长期资产」
- [ ] 2 列 grid 布局，4 个资产项
- [ ] 每项：图标（`--gold` 色）+ 名称 + 计数
- [ ] 底部链接「进入资产库 →」→ `/assets`

#### F15.2 手机端长按拖拽排序

**功能描述**：
手机端不支持 HTML5 DragEvent，需实现长按进入拖拽模式。

**验收标准**：
- [ ] 长按卡片 500ms 进入拖拽模式，卡片放大 1.05 倍 + `--shadow-raise` 阴影
- [ ] 拖拽中其他卡片显示占位虚线框
- [ ] 松手后排序更新并持久化到 localStorage
- [ ] 点击「完成」按钮退出拖拽模式

#### F15.3 模块状态灰度统一管理

**功能描述**：
利用 `data.modules_status`（10 个模块的 ready/beta/planned 状态）统一管理前端灰度。

**验收标准**：
- [ ] 前端维护一个 `useModuleStatus()` composable，从 API 数据中读取
- [ ] 所有卡片的「待开发」标签统一通过 `useModuleStatus` 判断，不再硬编码
- [ ] planned 模块的卡片自动降低 opacity 0.55 + grayscale 0.3

---

## 5. 移动端适配需求（375px 宽度）

### 5.1 断点策略

| 断点 | 布局 | 适用设备 |
|------|------|----------|
| ≥ 1024px | 三列网格 + 全宽卡片 | 桌面端 |
| 768px ~ 1023px | 双列网格 | 平板横屏 |
| 375px ~ 767px | 单列网格 + 触控优化 | 手机端 |
| < 375px | 单列 + 字号缩放 | 小屏手机（iPhone SE 1/2 代） |

### 5.2 手机端交互细节

| 元素 | 桌面端交互 | 手机端交互 |
|------|-----------|-----------|
| 卡片排序 | HTML5 拖拽 | 长按 500ms 进入编辑模式，拖拽手柄排序 |
| 按钮点击 | hover + click | `:active` 缩放 0.98 |
| 任务列表项 | hover 背景 | `:active` 背景微暗 |
| Hero 星星 | 48px 闪烁动画 | 32px 闪烁动画（性能考虑降低帧率） |
| 快速入口 | 3 列 grid | 4 列 grid（每行 4 个，减少纵向滚动） |
| 进度条 | 6px 高 | 6px 高（保持不变） |
| 触控热区 | 无要求 | 最小 44×44px |
| 文字字号 | `--text-xs` 11px | 手机端提升至 `--text-sm` 12px（可读性） |

### 5.3 Capacitor 壳约束

- 移动端运行在 Capacitor 7 + Android 壳中
- 不支持浏览器的右键菜单（拖拽排序方案需适配）
- 不支持 hover 事件
- 需要考虑 WebView 的滚动惯性（-webkit-overflow-scrolling: touch）
- 状态栏高度需预留（Capacitor StatusBar 插件处理）

---

## 6. 数据模型与 API 补充

### 6.1 现有 API

```
GET /dashboard
响应：DashboardDataOut
```

### 6.2 本期新增 API

#### 6.2.1 卡片排序持久化（可选，P1）

当前排序存 localStorage，不跨设备。如需跨设备同步：

```
PUT /dashboard/card-order
Body: { "order": ["focus", "execution", "projects", ...] }
Response: { "success": true }
```

```
GET /dashboard/card-order
Response: { "order": ["focus", "execution", ...] }
```

> 本期接受 localStorage 方案，服务端 API 预留不实现。

#### 6.2.2 卡片可见性配置（P1）

```
GET /dashboard/card-settings
Response: {
  "cards": [
    { "id": "learning", "visible": true },
    { "id": "life", "visible": false }
  ]
}
```

### 6.3 新增 Schema 字段

在 `DashboardDataOut` 基础上，本期不新增字段（所有字段后端已返回），只做前端渲染补齐。

### 6.4 Repository 新增方法（P0 性能优化）

```python
# TaskRepository 新增方法
def get_focus_task(self, user_id: str) -> Task | None
def count_today_stats(self, user_id: str, day_start: datetime, day_end: datetime) -> dict
def list_actionable_today(self, user_id: str, today: date, limit: int = 5) -> list[Task]
def count_by_identity(self, user_id: str, day_start: datetime, day_end: datetime) -> dict[str, dict]
def count_week_progress(self, user_id: str, monday: date, sunday: date) -> dict
```

---

## 7. 用户故事

### 故事 1：早间启动——程序员小张

> **场景**：小张早上 9 点打开启明星，准备开始一天的编码工作。

小张打开应用，3 秒内看到：
1. Hero 区显示「早上好，小张 · 你的人生与项目，由你主导」
2. 今日最重要任务卡显示「完成 PRD 第 4 章」，进度 60%
3. 今日执行卡显示：必须完成 2 项（1 项逾期红色圆点）、进行中 1 项、等待处理 0 项
4. 身份进度卡显示：「AI 研究」3 待办、「音乐」0 待办

小张点击「继续工作」直接跳转任务编辑页，开始编码。

**验收**：首屏 < 800ms，focus_task 一眼可见，逾期任务红色圆点醒目。

---

### 故事 2：项目中期——自由职业者李姐

> **场景**：李姐同时在做 3 个客户项目，需要快速了解各项目进度。

李姐打开首页，当前项目卡显示：
- 项目 A：75%（6/8 任务完成）
- 项目 B：30%（3/10 任务完成）
- 项目 C：0%（0/5 任务完成）

她一眼看出项目 C 还没动，点击项目 C 跳转详情页安排任务。

**验收**：项目进度条动画流畅，点击跳转正确，项目数 > 5 时只显示前 5 个。

---

### 故事 3：晚间复盘——学生小陈

> **场景**：小陈晚上 10 点准备做今日复盘。

小陈打开首页：
1. 连续打卡徽章显示「连续 7 天」，本周 7 个金点全亮
2. 本周进度环显示 85%
3. 今日执行卡显示今日完成了 3 项

他点击身份进度卡的「经历时间线 →」跳转复盘模块，开始写今日复盘。

**验收**：streak 和 week_progress 正确显示，打卡数据与 Review 表一致。

---

### 故事 4：新用户首次使用——小白用户

> **场景**：用户第一次打开启明星，没有任何任务、项目、身份。

用户打开首页看到：
1. Hero 区「你好，启明星用户」
2. 今日最重要卡：空状态「今天还没有设定最重要的任务」+ 「去任务模块」按钮
3. 今日执行卡：全空，显示「今天没有需要动手的任务」
4. 当前项目卡：空状态「还没有项目」+ 「创建项目」按钮
5. 身份进度卡：空状态「还没有身份」+ 「建立身份」按钮
6. 资源中心/学习/生活卡：灰度显示「待开发」标签

用户知道从哪里开始：先建身份，再建任务。

**验收**：空状态引导文案清晰，灰度卡不可误点，不出现报错。

---

### 故事 5：手机端通勤——产品经理老王

> **场景**：老王在地铁上用手机打开启明星，想快速看一眼今天的安排。

老王掏出手机（375px 宽度），打开应用：
1. 首页自动塌缩为单列布局
2. Hero 区缩小，星星图标 32px
3. 今日执行单列展示，任务项触控热区足够大
4. 他点击「新建任务」快速入口，自动打开新建弹窗

地铁晃，他单手操作无误触。

**验收**：375px 无横向滚动，触控热区 ≥ 44px，快速入口可用。

---

## 8. 验收标准（模块级）

### 8.1 功能完整性

- [ ] 所有 8 张现有卡片正常渲染，数据与后端一致
- [ ] `quick_actions` 9 个入口全部渲染并可点击跳转
- [ ] `ai_assistant` 状态卡渲染，已启用/未启用两种状态正确
- [ ] `week_progress` 环形进度渲染，百分比正确
- [ ] `streak` 连续打卡徽章渲染，7 天圆点正确
- [ ] `assets` 长期资产库卡渲染（P2）

### 8.2 性能

- [ ] 首屏 P95 可交互时间 ≤ 800ms（任务量 5000）
- [ ] 无 `list_user_tasks` 全量加载调用
- [ ] 首屏 SQL 查询次数 ≤ 8
- [ ] 骨架屏在数据返回前正确展示，不闪屏

### 8.3 交互

- [ ] 桌面端卡片拖拽排序流畅，排序持久化到 localStorage
- [ ] 拖拽悬停态 `.is-drag-over` 视觉反馈正确
- [ ] 所有进度条 width 过渡 0.5s `--ease-soft`
- [ ] 所有 hover 背景变化 150ms 过渡
- [ ] toast 提示在操作成功/失败时正确触发

### 8.4 状态覆盖

- [ ] 每张卡片都有：默认态 / 空状态 / 加载态 / 错误态
- [ ] 错误态显示「加载失败，点击重试」并可重试
- [ ] planned 模块灰度显示（opacity 0.55 + grayscale 0.3）
- [ ] 归档身份降透明度但仍可见

### 8.5 移动端

- [ ] 375px 宽度无横向滚动
- [ ] 触控热区 ≥ 44×44px
- [ ] 按钮手机端全宽排列
- [ ] hover 效果全部替换为 `:active` 反馈

### 8.6 设计令牌

- [ ] 所有颜色使用 CSS 变量令牌（`--primary` / `--mint` / `--strawberry` 等），不出现硬编码 hex
- [ ] 字号使用 `--text-*` 阶梯
- [ ] 间距使用 `--space-*` 阶梯
- [ ] 圆角使用 `--radius-*` 阶梯
- [ ] 四套主题切换时首页所有元素颜色自动适配

---

## 9. 风险与依赖

### 9.1 技术风险

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 全量改 SQL 查询导致数据口径不一致 | 今日执行数、身份统计数与改造前对不上 | 改造前写快照测试，对比改造前后结果 |
| 手机端长按拖拽与滚动冲突 | 用户想滚动却进入拖拽模式 | 长按 500ms 阈值 + 拖拽方向判断（垂直滚动不触发拖拽） |
| 四套主题切换时环形进度条颜色不对 | week_progress/streak 在暗黑/国风神下颜色刺眼 | 环形进度条颜色全部用 `--primary`，由主题令牌自动适配 |
| localStorage 排序被用户清空 | 排序回到默认顺序 | 读不到 key 时用 `defaultOrder` 兜底，不报错 |

### 9.2 依赖

| 依赖 | 说明 | 阻塞点 |
|------|------|--------|
| 任务模块（M2） | focus_task、今日执行数据来源 | 任务表结构变更需同步 |
| 身份模块（人生维度） | 身份进度卡数据来源 | IdentityRepository.list_user 接口稳定 |
| 项目模块 | 当前项目卡数据来源 | ProjectService.list 接口稳定 |
| 文档模块（知识维度） | 最近沉淀数据来源 | doc_repo.recent 接口稳定 |
| 复盘模块 | streak 数据来源 | Review 表结构不变 |
| AI 助手模块（伙伴维度） | ai_assistant 数据来源 | user.api_key_encrypted 字段存在 |
| 四套主题 | 设计令牌体系 | variables.scss 已定义完毕 |
| Capacitor 7 | 移动端壳 | 手机端交互适配需在真机验证 |

### 9.3 排期建议

| 阶段 | 内容 | 预估工作量 |
|------|------|-----------|
| 第一周 | P0：性能优化（SQL 下推）+ 快速入口卡 + AI 摘要卡落地 | 3 人日 |
| 第二周 | P0：移动端 375px 适配 + 缺陷修复（B-02/B-06/B-07/B-08） | 2 人日 |
| 第三周 | P1：week_progress + streak 落地 + 卡片隐藏配置 | 2 人日 |
| 第四周 | P2：assets 卡 + 手机端拖拽 + 联调测试 | 2 人日 |

---

> 本文档基于 DashboardView.vue（700 行）、dashboard.py（25 行）、dashboard_service.py（486 行）、dashboard.py schema（206 行）、useDashboard.ts（22 行）、variables.scss（523 行）、dimensions.ts（139 行）逐行阅读后撰写。所有功能描述均对应实际代码位置，未凭空臆想。
