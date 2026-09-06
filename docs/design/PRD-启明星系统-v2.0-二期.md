# Venustech System（启明星）产品需求文档 PRD v2.0（二期）

> 版本：v2.0 · 日期：2026-09-06 · 状态：草稿
> 对标文档：PRD-启明星系统-v1.0.md（一期，2993行）
> 一期版本：v0.2.0（9模块深度开发完成）

---

## 第一部分：产品总纲

### 1. 二期定位与目标

#### 1.1 二期定位

一期完成了**核心六模块 + 桌宠 + 基础设施**的深度开发，构建了启明星系统的基础骨架。二期的核心定位是：

**从"能用"到"好用"，从"工具"到"伙伴"，从"单机"到"生态"。**

具体而言：
- **补全新模块**：资源中心、学习成长、生活记录、长期资产库四大模块上线，完成个人OS的完整闭环
- **深化核心亮点**：第二分身从"对话工具"进化为"真正的第二分身"（本地推理+长期记忆+五档自动化）
- **形象体验升级**：桌宠从"动画形象"进化为"有感知的陪伴者"（状态感知+语音+自定义形象）
- **工作流落地**：从零散功能到可复用的工作流系统，支持数学学习/项目开发/小说写作等场景
- **桌面端成型**：Electron打包，真桌宠窗口，系统托盘，成为真正的桌面应用
- **一期考校维护**：对一期已完成的9个模块进行系统性考校、优化和维护，确保质量基线

#### 1.2 二期目标

| 维度 | 目标 | 衡量标准 |
|------|------|----------|
| 功能完整度 | 10个核心模块全部可用 | 资源中心/学习/生活/资产库4个新模块P0功能完成 |
| 第二分身 | 真正具备"分身"能力 | 本地模型推理可用、长期记忆可可视化、五档自动化可配置 |
| 桌宠体验 | 有感知的陪伴者 | 状态感知互动≥5种、本地TTS可用、自定义形象上传可用 |
| 工作流 | 至少3套预设工作流 | 数学学习/项目开发/小说写作工作流可一键应用 |
| 桌面端 | Electron可分发 | Windows安装包可用、桌宠独立窗口、系统托盘 |
| 一期维护 | 9模块质量基线 | 一期所有P0/P1功能无阻断性bug、性能达标 |
| 性能 | 桌面端流畅 | 首屏加载<2s、模块切换<300ms、内存占用<500MB |

#### 1.3 二期不做什么

- **不做云端同步**：云端同步放在三期，二期仅支持同步盘半自动同步
- **不做移动端**：移动端放在三期，二期聚焦桌面端
- **不做插件市场**：插件市场放在三期，二期仅完善插件基础架构
- **不做多分身并存**：多人格放在四期，二期聚焦单分身深度进化

### 2. 目标用户与场景深化

#### 2.1 核心用户画像（深化）

| 用户类型 | 核心需求 | 二期重点满足 |
|----------|----------|-------------|
| 学生 | 学习管理、知识沉淀、复盘 | 学习成长模块、知识卡片、间隔重复、数学学习工作流 |
| 自由职业者 | 项目管理、客户管理、收入追踪 | 项目管理深化、长期资产库、SOP复用 |
| 创业者 | 战略规划、团队协作、资源整合 | 项目管理、工作流系统、资产库 |
| 知识工作者 | 知识管理、写作、灵感 | 知识模块深化、RAG问答、长文写作、小说写作工作流 |
| 开发者 | 代码管理、项目开发、技术沉淀 | 项目开发工作流、代码生成、Skill库 |

#### 2.2 二期核心使用场景

**场景一：学生的一天**
- 早晨：桌宠感知到用户开始学习，切换到"学习中"动作，提醒今日学习计划
- 学习中：知识卡片间隔重复提醒，学习时长自动记录
- 学习后：第二分身自动总结今日学习内容，生成知识卡片候选
- 晚上：复盘模块自动填充学习数据，生成学习周报

**场景二：开发者的项目开发**
- 项目启动：一键应用"项目开发工作流"，自动创建文件夹结构/标签/任务模板
- 开发中：任务自动拆解为子任务，SOP库推荐相关开发流程
- 遇到问题：第二分身基于项目知识库进行RAG问答
- 项目完成：自动生成项目记忆，沉淀为可复用资产

**场景三：写作者的创作流程**
- 灵感触发：第二分身主动提出灵感方向，生成详细提示词
- 创作中：长文写作助手辅助续写/润色，知识库自动关联
- 完成后：作品自动归档到资产库，生成创作复盘

### 3. 产品路线图（二期）

```
二期总周期：约4个月（2026-09 ~ 2027-01）

阶段一：基础维护与新模块骨架（第1-4周）
├── 一期9模块考校维护与bug修复
├── 资源中心模块骨架
├── 学习成长模块骨架
├── 生活记录模块骨架
└── 长期资产库模块骨架

阶段二：新模块核心功能（第5-8周）
├── 资源中心：收集箱/领域库/模板库
├── 学习成长：学习计划/知识卡片/间隔重复
├── 生活记录：习惯打卡/心情追踪/精力管理
└── 长期资产库：SOP/Prompt/Skill/项目记忆

阶段三：第二分身与形象进化（第9-12周）
├── 本地模型推理（Ollama/LM Studio）
├── 长期记忆系统
├── 五档自动化
├── 完整灵感工作流
├── Marvis式状态感知互动
└── 本地TTS语音

阶段四：工作流与强AI（第13-14周）
├── 工作流模板系统（3套预设）
├── 任务自动拆解
├── RAG知识问答
└── 长文写作助手

阶段五：Electron打包与验收（第15-16周）
├── Electron桌面端打包
├── 真桌宠窗口
├── 系统托盘
├── 自动更新
├── 全量测试与验收
└── v1.0正式版发布
```

### 4. 一期考校维护（二期重要组成部分）

#### 4.1 考校维护的必要性

一期完成了9个模块的深度开发，但由于开发周期紧张、多分支并行合并，存在以下需要系统性考校维护的问题：

1. **合并引入的bug**：多分支合并后出现SCSS嵌套错误、HTML重复属性、类型错误等
2. **功能完整性验证**：部分模块P1/P2功能可能未完全实现或存在边界问题
3. **性能基线**：未建立明确的性能指标和测试
4. **用户体验一致性**：各模块交互模式可能不统一
5. **代码质量**：需要进行代码审查和重构
6. **文档同步**：代码与文档可能存在不一致

#### 4.2 考校维护范围

| 模块 | 考校重点 | 维护内容 |
|------|----------|----------|
| M01 首页 | 数据聚合准确性、卡片拖拽稳定性、一屏适配 | 修复数据聚合bug、优化拖拽体验、确保一屏装下 |
| M02 任务 | 状态机完整性、依赖关系计算、模板复用 | 修复状态流转bug、优化依赖计算、完善模板系统 |
| M03 知识 | 编辑器稳定性、双向链接、图谱性能 | 修复编辑器崩溃、优化链接解析、图谱力导向算法优化 |
| M04 第二分身 | SSE稳定性、模型切换、画像准确性 | 修复SSE断连、优化模型切换、完善画像沉淀逻辑 |
| M05 复盘 | 数据填充准确性、导出格式、年度报告 | 修复数据统计bug、优化导出格式、完善年度报告 |
| M06 项目 | 详情页性能、里程碑管理、导出完整性 | 优化详情页加载、修复里程碑CRUD、完善导出 |
| M07 桌宠 | 动作流畅度、状态衰减、互动反馈 | 优化动画性能、修复状态计算、完善互动反馈 |
| M08 设置 | 主题切换完整性、数据清理安全性 | 修复主题切换bug、确保数据清理安全、完善设置项 |
| M09 基础设施 | 事件总线稳定性、插件加载、加密降级 | 修复事件丢失、优化插件加载、完善加密降级 |

#### 4.3 考校维护标准

**功能完整性**：
- 每个模块的P0功能100%可用
- P1功能≥90%可用
- 无阻断性bug（导致模块无法使用的bug）

**性能基线**：
- 页面首屏加载<2s
- 模块切换<300ms
- API响应时间<500ms（本地）
- 内存占用<500MB（桌面端）
- 桌宠动画FPS≥30

**代码质量**：
- TypeScript严格模式零错误
- 前端生产构建成功
- 后端pytest全部通过
- 无console.error（除预期外）

**用户体验**：
- 所有按钮有明确反馈（hover/active/loading）
- 所有操作有结果提示（成功/失败）
- 所有列表有空状态
- 所有表单有校验和错误提示

#### 4.4 考校维护产出

- 《一期模块考校报告》：每个模块的问题清单、修复记录、验收结果
- 《性能测试报告》：性能基线数据、优化记录
- 《代码审查报告》：代码质量问题、重构记录
- 一期版本号从v0.2.0升级到v0.3.0（考校维护完成）

---

## 第二部分：新模块功能需求

### 5. 模块7：资源中心（M7）

#### 5.1 模块定位

**定位**：个人信息的"收集箱"与"资源库"，解决"信息过载"和"找不到"的问题。

**核心价值**：
- 快速捕获：任何信息一键存入收集箱，不打断当前工作
- 系统整理：收集箱定期整理到领域库/项目库/知识库
- 模板复用：常用文档/表格/配置模板化，一键调用

**与其他模块的关系**：
- 收集箱 → 处理后 → 知识模块（文档）/ 任务模块（待办）/ 项目模块（项目资料）
- 模板库 → 被知识模块/项目模块/工作流系统调用
- 领域库 → 长期资产库的输入源

#### 5.2 功能架构

```
资源中心
├── 收集箱（Inbox）
│   ├── 快速捕获（文字/链接/图片/文件）
│   ├── 批量处理（分类/打标签/转任务/转文档）
│   └── 定时提醒整理
├── 领域库（Domain Library）
│   ├── 自定义领域分类
│   ├── 领域内资源聚合
│   └── 领域知识图谱
├── 项目库（Project Library）
│   ├── 项目资料自动归集
│   ├── 项目资源版本管理
│   └── 项目完成后归档
├── 学习库（Study Library）
│   ├── 学习资料分类
│   ├── 学习进度追踪
│   └── 与学习成长模块联动
├── 知识库（Knowledge Base）
│   ├── 与知识模块双向同步
│   ├── 知识卡片来源
│   └── 全文检索
├── 指令库（Command Library）
│   ├── AI指令模板
│   ├── 快捷指令
│   └── 与第二分身联动
└── 模板库（Template Library）
    ├── 文档模板
    ├── 表格模板
    ├── 配置模板
    └── 项目模板
```

#### 5.3 收集箱（P0）

**功能描述**：
- 全局快捷键（Ctrl+Shift+N）唤起快速捕获窗口
- 支持输入类型：纯文字、URL链接、图片粘贴、文件拖拽
- 自动解析：URL自动获取标题和预览图、图片自动生成缩略图
- 自动元数据：捕获时间、来源（如果是从浏览器/其他应用）、初始标签建议
- 收集箱列表：按时间倒序，支持搜索、筛选（未处理/已处理/全部）
- 批量处理：多选后批量分类、打标签、转为任务、转为文档、删除
- 单条处理：点击条目展开详情，进行处理操作
- 整理提醒：可配置每日/每周提醒整理收集箱

**交互流程**：
1. 用户按快捷键 → 弹出捕获窗口（300x200，居中）
2. 输入内容/粘贴链接/拖拽文件 → 自动解析
3. 按Enter → 存入收集箱，窗口关闭，显示"已存入收集箱"提示
4. 用户进入资源中心 → 收集箱列表展示所有未处理项
5. 用户点击条目 → 展开详情，选择处理方式
6. 处理完成 → 条目标记为"已处理"，从默认列表隐藏

**数据模型**：
```
inbox_items表：
- id: UUID
- user_id: UUID (外键)
- content_type: enum(text/url/image/file)
- content: TEXT (文字内容或URL)
- title: VARCHAR (自动解析的标题)
- preview_url: VARCHAR (图片/链接预览图)
- file_path: VARCHAR (文件存储路径)
- source: VARCHAR (来源应用/网址)
- tags: JSON (标签数组)
- status: enum(pending/processed/archived)
- processed_at: DATETIME
- created_at: DATETIME
- updated_at: DATETIME
```

#### 5.4 领域库（P1）

**功能描述**：
- 用户自定义领域分类（如：人工智能、投资理财、健身、烹饪）
- 每个领域下可聚合：文档、任务、项目、资源文件、知识卡片
- 领域看板：展示该领域的所有资源，按类型分组
- 领域知识图谱：可视化领域内知识点的关联关系
- 领域统计：资源数量、更新频率、活跃度

**与收集箱的联动**：
- 收集箱处理时可选择"归入领域"
- 归入后自动在领域库中展示

#### 5.5 模板库（P0）

**功能描述**：
- 模板分类：文档模板、表格模板、配置模板、项目模板、提示词模板
- 内置模板：≥10个常用模板（会议纪要、周报、项目计划、读书卡片等）
- 自定义模板：用户可从现有文档"另存为模板"
- 模板变量：支持{{变量名}}占位符，使用时自动替换
- 一键调用：在知识模块新建文档时可选择模板、在项目模块可选择项目模板
- 模板市场（二期后期）：官方/第三方模板分享

**模板变量系统**：
```
模板示例（会议纪要）：
# {{会议主题}}
- 时间：{{日期}}
- 参会人：{{参会人员}}
## 议程
1. {{议程1}}
2. {{议程2}}
## 决议
- {{决议内容}}
## 待办
- [ ] {{待办1}} (负责人：{{负责人}})
```

#### 5.6 资源中心首页

**布局**：
- 顶部：搜索栏 + 新建按钮 + 视图切换（列表/网格）
- 左侧：分类导航（收集箱/领域库/项目库/学习库/知识库/指令库/模板库）
- 主区域：当前分类的资源列表
- 资源卡片：图标/预览图 + 标题 + 类型标签 + 更新时间 + 操作菜单

### 6. 模块8：学习成长（M8）

#### 6.1 模块定位

**定位**：系统化学习管理，从"输入"到"掌握"，构建个人学习闭环。

**核心价值**：
- 学习有计划：目标拆解为可执行的学习任务
- 知识可复用：知识卡片+间隔重复，确保真正掌握
- 进度可追踪：学习时长、复习量、掌握率可视化

**与其他模块的关系**：
- 学习计划 → 生成任务 → 任务模块
- 学习笔记 → 知识模块
- 知识卡片 → 长期资产库
- 学习数据 → 复盘模块自动填充

#### 6.2 功能架构

```
学习成长
├── 学习计划
│   ├── 学习目标管理
│   ├── 目标拆解为学习任务
│   ├── 学习进度追踪
│   └── 学习计划模板
├── 知识卡片
│   ├── 卡片创建（正面问题/背面答案）
│   ├── 卡片分类与标签
│   ├── 卡片编辑器（支持Markdown/图片/代码）
│   └── 从文档一键生成卡片
├── 间隔重复复习
│   ├── SM-2算法实现
│   ├── 每日复习队列
│   ├── 复习质量评分
│   └── 复习提醒（桌宠联动）
├── 学习时长记录
│   ├── 手动记录
│   ├── 自动检测（前台应用/文档编辑时间）
│   ├── 学习计时器（番茄钟）
│   └── 学习时长统计
├── 学习数据统计
│   ├── 每日/每周/每月学习时长
│   ├── 复习量与掌握率
│   ├── 学习趋势图
│   └── 学习报告
└── 学习资源库
    ├── 学习资料关联
    ├── 外部链接管理
    └── 学习笔记归集
```

#### 6.3 学习计划（P0）

**功能描述**：
- 创建学习目标：名称、描述、目标日期、预计总时长
- 目标拆解：将大目标拆分为阶段性里程碑，每个里程碑拆分为学习任务
- 学习任务关联：学习任务可关联到任务模块，支持完成状态同步
- 进度可视化：环形进度图 + 里程碑时间线
- 学习计划模板：预设"考研备考""技能入门""读书计划"等模板

**交互流程**：
1. 用户点击"新建学习计划" → 填写目标信息
2. 系统建议拆解方案（AI辅助，可选）→ 用户确认/调整
3. 生成学习任务列表 → 可选择同步到任务模块
4. 每日学习后标记任务完成 → 进度自动更新
5. 达到里程碑 → 桌宠庆祝 + 复盘提醒

#### 6.4 知识卡片（P0）

**功能描述**：
- 卡片类型：问答卡（正面问题/背面答案）、概念卡（术语/定义）、填空卡、列表卡
- 卡片编辑器：支持Markdown、图片、代码块、公式（LaTeX）
- 卡片分类：按学科/主题/难度分类
- 卡片标签：多标签支持
- 从文档生成：在知识模块文档中选中文字 → "生成知识卡片" → 自动填充正面，用户编辑背面
- 卡片关联：卡片之间可建立关联（前置知识/相关概念）

**卡片编辑器**：
- 正面/背面切换编辑
- 实时预览
- 附件支持（图片/音频）
- 难度标记（1-5星）

#### 6.5 间隔重复复习（P0）

**核心算法（SM-2简化版）**：
```
参数：
- EF (Easiness Factor)：难度系数，初始2.5，范围1.3-2.5
- interval：复习间隔（天）
- repetition：重复次数
- quality：复习质量评分（0-5）

算法：
首次复习：interval=1, repetition=1
复习后：
  if quality < 3: repetition=0, interval=1 (重置)
  else:
    repetition += 1
    if repetition == 1: interval=1
    elif repetition == 2: interval=6
    else: interval = round(interval * EF)
  EF = EF + (0.1 - (5-quality)*(0.08+(5-quality)*0.02))
  EF = max(1.3, EF)
```

**功能描述**：
- 每日复习队列：根据算法计算今日应复习的卡片
- 复习界面：正面展示 → 用户回忆 → 翻转显示背面 → 评分（忘记/模糊/记住/熟练）
- 复习统计：今日复习数、累计复习数、掌握率、平均记忆强度
- 复习提醒：桌宠在设定时间提醒复习
- 复习数据可视化：记忆曲线、掌握率趋势

**复习界面交互**：
1. 显示卡片正面（问题）
2. 用户思考后点击"显示答案"
3. 卡片翻转动画（300ms），显示背面
4. 用户选择评分：
   - 忘记（quality=0）→ 1天后重学
   - 模糊（quality=3）→ 按算法计算间隔
   - 记住（quality=4）→ 按算法计算间隔
   - 熟练（quality=5）→ 按算法计算间隔
5. 自动进入下一张卡片
6. 完成今日队列 → 显示复习总结

#### 6.6 学习时长记录（P1）

**功能描述**：
- 手动记录：选择学习主题、输入时长、添加备注
- 番茄钟：25分钟专注+5分钟休息，自动记录
- 自动检测（可选）：检测前台应用是否为学习相关（文档编辑器/浏览器学习网站），累计时长
- 学习日历：热力图展示每日学习时长
- 统计图表：每日/每周/每月学习时长柱状图、学习趋势折线图

#### 6.7 学习数据统计（P1）

**功能描述**：
- 学习概览：总学习时长、总卡片数、已掌握卡片数、连续学习天数
- 学习报告：周报/月报自动生成，包含学习时长、复习量、掌握率、目标进度
- 与复盘模块联动：学习数据自动填充到复盘模板
- 年度学习报告：年度学习总结，里程碑、高频标签、学习曲线

### 7. 模块9：生活记录（M9）

#### 7.1 模块定位

**定位**：工作之外的全人管理，记录生活的每个维度，实现工作生活平衡。

**核心价值**：
- 习惯可养成：习惯打卡+连续天数+提醒
- 情绪可觉察：心情追踪+趋势分析+情绪诱因识别
- 精力可管理：精力记录+高效时段分析+作息建议
- 生活可回顾：时间线展示+年度生活报告

**与其他模块的关系**：
- 习惯打卡 → 任务模块（可转为待办）
- 心情/精力数据 → 复盘模块自动填充
- 生活记录 → 长期资产库（生活智慧沉淀）

#### 7.2 功能架构

```
生活记录
├── 四维日记
│   ├── 家庭/健康/精力/成长四维
│   ├── 每日一句话记录
│   ├── 图文混排
│   └── 日记模板
├── 习惯打卡
│   ├── 自定义习惯
│   ├── 每日打卡
│   ├── 连续天数统计
│   ├── 打卡提醒
│   └── 习惯数据统计
├── 心情追踪
│   ├── 每日心情评分（1-5）
│   ├── 心情标签
│   ├── 文字记录
│   ├── 心情趋势图
│   └── 情绪诱因分析
├── 精力管理
│   ├── 每日精力水平记录
│   ├── 高效时段分析
│   ├── 精力趋势图
│   └── 作息建议
├── 健康数据（手动）
│   ├── 体重记录
│   ├── 睡眠记录
│   ├── 运动记录
│   └── 健康趋势图
├── 生活时间线
│   ├── 按时间线展示所有生活记录
│   ├── 筛选（维度/类型/时间）
│   └── 年度回顾
└── 年度生活报告
    ├── 年度数据聚合
    ├── 习惯达成率
    ├── 心情分布
    ├── 里程碑事件
    └── Markdown导出
```

#### 7.3 四维日记（P1）

**功能描述**：
- 四个维度：家庭、健康、精力、成长
- 每日每个维度一句话记录（可选）
- 支持图文混排（图片/表情/标签）
- 日记模板：预设"每日三件好事""感恩日记""成功日记"等模板
- 日记日历：按日期查看，有记录的日期标记
- 日记搜索：全文搜索

#### 7.4 习惯打卡（P0）

**功能描述**：
- 自定义习惯：名称、图标、颜色、目标频率（每日/每周N次）、提醒时间
- 每日打卡：一键打卡，支持补打卡（可配置是否允许）
- 连续天数：当前连续天数、最长连续天数、总打卡天数
- 打卡日历：热力图展示打卡情况
- 打卡提醒：桌宠在设定时间提醒打卡
- 习惯统计：打卡率、连续天数趋势、本周/本月完成情况
- 习惯归档：完成的习惯可归档，保留历史数据

**习惯创建示例**：
```
习惯名称：早起
图标：🌅
颜色：金色
频率：每日
提醒时间：07:00
目标：连续30天
```

#### 7.5 心情追踪（P0）

**功能描述**：
- 心情评分：1-5分（很差/不好/一般/不错/很好），对应5种表情
- 心情标签：预设标签（开心/焦虑/平静/疲惫/兴奋等）+ 自定义标签
- 文字记录：可选，记录心情原因或事件
- 心情趋势图：近7天/30天心情折线图
- 心情分布：饼图展示各心情占比
- 情绪诱因分析：基于标签和文字，分析影响心情的主要因素（AI辅助，可选）
- 与复盘联动：心情数据自动填充到复盘模板

**心情记录交互**：
1. 用户点击"记录心情" → 弹出心情选择器
2. 选择心情评分（5个大表情按钮）
3. 选择心情标签（多选，可选）
4. 输入文字记录（可选）
5. 点击保存 → 存入记录，显示"已记录"提示

#### 7.6 精力管理（P1）

**功能描述**：
- 精力记录：每日分时段（上午/下午/晚上）记录精力水平（1-5）
- 高效时段分析：基于历史数据，分析用户的高效时段
- 精力趋势图：近7天/30天精力变化
- 精力与心情关联：分析精力与心情的相关性
- 作息建议：基于精力数据，建议最佳工作/休息时段

#### 7.7 健康数据（P2）

**功能描述**：
- 体重记录：每日/每周记录，趋势图
- 睡眠记录：入睡时间/起床时间/睡眠质量，趋势图
- 运动记录：运动类型/时长/强度，统计
- 健康趋势：综合展示各项健康指标变化
- 二期不接硬件，全部手动记录

#### 7.8 生活时间线与年度报告（P1）

**生活时间线**：
- 按时间倒序展示所有生活记录（日记/打卡/心情/健康）
- 支持按维度筛选（家庭/健康/精力/成长）
- 支持按类型筛选（日记/习惯/心情/健康）
- 支持时间范围筛选
- 每条记录可展开详情

**年度生活报告**：
- 年度数据聚合：总日记数、习惯打卡总数、心情分布、健康指标变化
- 习惯达成率：各习惯的年度完成率、最长连续天数
- 心情分布：年度心情占比、心情最好/最差的月份
- 里程碑事件：用户标记的重要生活事件
- Markdown导出：可导出为完整年度报告文档

### 8. 模块10：长期资产库（M10）

#### 8.1 模块定位

**定位**：个人可复用资产的沉淀与调用，构建个人复利系统。

**核心价值**：
- 经验不丢失：项目完成后自动沉淀经验教训
- 能力可复用：SOP/Prompt/Skill标准化，一键调用
- 智慧可传承：个人方法论系统化，可检索可复用

**与其他模块的关系**：
- 项目完成 → 自动生成项目记忆 → 资产库
- 高频工作流程 → 沉淀为SOP → 资产库
- AI提示词 → 沉淀为Prompt模板 → 资产库
- 个人方法论 → 沉淀为Skill → 资产库
- 执行任务时 → 智能推荐相关资产

#### 8.2 功能架构

```
长期资产库
├── SOP流程库
│   ├── SOP创建（步骤+检查清单+模板）
│   ├── SOP分类与标签
│   ├── SOP版本管理
│   ├── 一键调用SOP
│   ├── SOP使用统计
│   └── SOP模板市场（二期后期）
├── Prompt模板库
│   ├── Prompt创建（角色+任务+约束+变量）
│   ├── Prompt分类
│   ├── 变量替换系统
│   ├── 使用统计
│   └── 与第二分身联动
├── Skill技能库
│   ├── Skill创建（方法论文档化）
│   ├── Skill分类
│   ├── Skill关联资源
│   ├── Skill评级
│   └── Skill使用记录
├── 项目记忆
│   ├── 项目完成后自动生成
│   ├── 项目总结（成果/经验/教训）
│   ├── 可复用模板提取
│   ├── 项目记忆检索
│   └── 项目记忆关联
├── 资产关联
│   ├── 资产与任务/项目/文档双向关联
│   ├── 资产之间关联
│   └── 关联图谱
├── 智能推荐
│   ├── 执行任务时推荐相关SOP
│   ├── 对话时推荐相关Prompt
│   ├── 学习时推荐相关Skill
│   └── 推荐反馈优化
└── 资产版本
    ├── 版本历史
    ├── 版本对比
    ├── 版本回滚
    └── 变更记录
```

#### 8.3 SOP流程库（P0）

**功能描述**：
- SOP结构：名称、描述、分类、标签、步骤列表、检查清单、关联模板
- 步骤：序号、标题、描述、预计时长、负责人（个人使用时为自己）
- 检查清单：每个步骤可关联检查项，执行时逐项勾选
- 一键调用：点击"执行SOP" → 生成任务列表（每个步骤一个任务）+ 检查清单
- SOP模板：从现有任务列表"另存为SOP"
- 使用统计：执行次数、平均完成时长、完成率
- SOP版本：修改后自动保存版本，可对比/回滚

**SOP示例（代码审查）**：
```
名称：代码审查SOP
分类：开发
步骤：
1. 理解需求（10min）- 阅读PR描述和关联需求
2. 检查架构（15min）- 模块划分、依赖关系、命名规范
3. 检查功能（20min）- 逻辑正确性、边界条件、错误处理
4. 检查性能（10min）- 时间复杂度、内存使用、N+1查询
5. 检查安全（10min）- 输入校验、SQL注入、XSS、敏感信息
6. 编写审查意见（15min）- 分类标注、建议方案、优先级
检查清单：
- [ ] 所有变量有明确类型
- [ ] 无硬编码配置
- [ ] 错误处理完整
- [ ] 有单元测试
- [ ] 无性能明显问题
```

#### 8.4 Prompt模板库（P0）

**功能描述**：
- Prompt结构：名称、分类、描述、角色设定、任务描述、约束条件、输出格式、变量列表
- 变量系统：{{变量名}}占位符，使用时弹出变量输入表单
- 分类：写作/编程/分析/翻译/创意/其他
- 使用统计：使用次数、平均输出质量（用户评分）
- 与第二分身联动：在对话界面可快速选择Prompt模板
- 从对话保存：满意的对话可"保存为Prompt模板"

**Prompt变量示例**：
```
名称：文章润色
分类：写作
角色：你是一位资深编辑，擅长中文写作润色
任务：请对以下文章进行润色，保持原意，提升表达
约束：
- 不改变文章结构
- 不添加新观点
- 语言风格：{{风格}}
输出格式：直接输出润色后的文章
变量：
- 风格：正式/轻松/学术/商业
- 原文：多行文本
```

#### 8.5 Skill技能库（P1）

**功能描述**：
- Skill结构：名称、分类、描述、方法论文档、关联资源、熟练度评级
- 方法论文档：完整的Skill说明（原则/步骤/案例/注意事项），支持Markdown
- 关联资源：可关联文档/项目/SOP/Prompt
- 熟练度评级：入门/熟练/精通（用户自评或基于使用次数）
- 使用记录：每次使用Skill的记录和成果
- Skill检索：全文检索+标签筛选

#### 8.6 项目记忆（P0）

**功能描述**：
- 自动生成：项目标记为"完成"时，自动触发项目记忆生成
- AI辅助总结：第二分身基于项目数据（任务/文档/对话/复盘）生成项目总结草稿
- 项目记忆结构：
  - 项目概况：名称、周期、目标、最终成果
  - 成功经验：做对了什么、可复用的方法
  - 失败教训：踩了什么坑、如何避免
  - 可复用资产：提取的SOP/Prompt/Skill/模板
  - 关键数据：任务完成率、耗时统计、质量评估
- 用户编辑：AI生成的草稿用户可编辑补充
- 项目记忆检索：按项目/标签/时间检索
- 项目记忆关联：与其他资产双向关联

**项目记忆生成流程**：
1. 用户将项目标记为"完成"
2. 系统提示"是否生成项目记忆？"
3. 用户确认 → 第二分身开始分析项目数据（异步）
4. 生成完成 → 通知用户"项目记忆已生成"
5. 用户查看/编辑 → 保存到资产库
6. 系统建议"是否提取可复用资产？" → 用户选择提取SOP/Prompt等

#### 8.7 智能推荐（P1）

**功能描述**：
- 任务执行时：根据任务标题/标签，推荐相关的SOP和Skill
- 对话时：根据对话内容，推荐相关的Prompt模板
- 学习时：根据学习主题，推荐相关的Skill和知识卡片
- 推荐展示：非侵入式侧边栏/底部提示，用户可忽略
- 反馈机制：用户可标记"有用/无用"，优化推荐算法
- 推荐算法：二期基于关键词匹配+使用频率，三期升级为语义匹配

#### 8.8 资产库首页

**布局**：
- 顶部：搜索栏 + 新建资产按钮 + 视图切换
- 左侧：分类导航（SOP/Prompt/Skill/项目记忆/全部）
- 主区域：资产卡片列表
- 资产卡片：类型图标 + 名称 + 分类标签 + 使用次数 + 更新时间 + 操作菜单
- 统计概览：各类型资产数量、本月使用次数、最常用资产

---

## 第三部分：现有模块进化

### 9. 第二分身进化（M4深化）

#### 9.1 本地模型推理（P0）

**功能描述**：
- 接入Ollama和LM Studio，支持完全离线的本地模型推理
- 自动检测：启动时扫描本地运行的Ollama/LM Studio服务
- 模型列表：获取本地可用模型列表，展示模型大小/参数/描述
- 模型推荐：根据用户硬件配置（内存/GPU）推荐合适模型（3B/7B/13B）
- 弱AI功能走本地：自动标签/摘要/语义搜索/简单对话
- 强AI功能走云端：复杂推理/长文写作/RAG问答（用户可配置）
- 混合模式：可配置哪些功能走本地、哪些走云端

**本地模型管理界面**：
- 连接状态：已连接/未连接，显示服务地址
- 模型列表：模型名、参数大小、已下载/未下载
- 模型下载：一键下载模型（显示进度）
- 当前选择：选择默认本地模型
- 性能测试：一键测试模型推理速度（tokens/s）

**技术实现**：
- Ollama：REST API（http://localhost:11434）
- LM Studio：OpenAI兼容API（http://localhost:1234/v1）
- 统一抽象：LocalAIProvider接口，实现OllamaProvider和LMStudioProvider
- 自动降级：本地模型不可用时自动切换到云端或Mock

#### 9.2 长期记忆系统（P0）

**双层记忆架构**：
```
短期记忆（Short-term Memory）
├── 最近N轮对话上下文（默认20轮）
├── 当前会话的临时信息
└── 会话结束后归档或遗忘

长期记忆（Long-term Memory）
├── 用户画像（User Profile）
│   ├── 基本信息：职业/兴趣/目标/价值观
│   ├── 行为模式：工作习惯/学习习惯/作息规律
│   ├── 偏好设置：语言风格/回复长度/详细程度
│   └── 知识结构：已知领域/学习中领域/未知领域
├── 知识记忆（Knowledge Memory）
│   ├── 从文档中提取的关键知识点
│   ├── 从对话中学习的用户观点
│   ├── 从复盘中总结的经验教训
│   └── 语义向量存储（本地向量库）
├── 事件记忆（Event Memory）
│   ├── 重要事件记录（项目完成/里程碑/习惯达成）
│   ├── 时间戳+事件描述+情感标签
│   └── 可回溯可查询
└── 关系记忆（Relation Memory）
    ├── 人/事/物之间的关系
    ├── 项目-任务-文档关联
    └── 概念之间的关联
```

**记忆更新机制**：
- 实时更新：对话中提取的信息实时更新短期记忆
- 批量更新：每日凌晨（可配置时间）批量分析当天数据，更新长期记忆
- 触发更新：重要操作（项目完成/复盘保存）触发即时记忆更新
- 记忆合并：相似信息自动合并，避免冗余

**记忆可视化与管理**：
- "分身知道我什么"页面：分类展示所有长期记忆
- 记忆编辑：用户可编辑/补充/删除记忆
- 记忆重置：可选择重置某类记忆或全部记忆
- 记忆来源：每条记忆显示来源（哪次对话/哪个文档/哪个复盘）
- 记忆可信度：AI提取的记忆标注可信度，用户可确认/否认

**记忆检索机制**：
- 对话时：基于当前对话内容，语义检索相关长期记忆
- 注入上下文：将检索到的记忆注入系统提示词
- 记忆优先级：用户画像 > 知识记忆 > 事件记忆
- 上下文窗口管理：记忆注入不超过总上下文的30%

#### 9.3 五档自动化（P0）

**自动化档位定义**：

| 档位 | 名称 | 行为 | 适用用户 |
|------|------|------|----------|
| L1 | 完全手动 | 只在被问时回答，不主动做任何操作 | 新手/谨慎用户 |
| L2 | 建议不执行 | 主动提建议，需用户确认后执行 | 大多数用户 |
| L3 | 低风险自动 | 自动打标签/摘要/整理，高风险需确认 | 进阶用户 |
| L4 | 大部分自动 | 大部分操作自动，仅删除/覆盖/发送确认 | 高级用户 |
| L5 | 完全自主 | 全自动，用户只看结果 | 极客/信任用户 |

**各档位具体行为**：

| 操作 | L1 | L2 | L3 | L4 | L5 |
|------|----|----|----|----|-----|
| 回答问题 | ✓ | ✓ | ✓ | ✓ | ✓ |
| 主动提建议 | ✗ | ✓ | ✓ | ✓ | ✓ |
| 自动打标签 | ✗ | 建议 | ✓ | ✓ | ✓ |
| 自动摘要 | ✗ | 建议 | ✓ | ✓ | ✓ |
| 自动整理收集箱 | ✗ | 建议 | ✓ | ✓ | ✓ |
| 自动创建任务 | ✗ | 建议 | 确认 | ✓ | ✓ |
| 自动修改文档 | ✗ | 建议 | 确认 | 确认 | ✓ |
| 自动发送消息 | ✗ | 建议 | 确认 | 确认 | 确认 |
| 自动删除 | ✗ | 建议 | 确认 | 确认 | 确认 |
| 自动覆盖 | ✗ | 建议 | 确认 | 确认 | 确认 |

**强制确认操作**（所有档位都需确认）：
- 删除任何数据
- 覆盖已有内容
- 发送对外消息
- 修改系统设置
- 导出/备份数据

**档位切换**：
- 设置页可切换全局档位
- 切换时显示该档位的行为说明和风险提示
- 可单独配置某类操作的自动化级别（覆盖全局）
- 桌宠可根据用户反馈自动建议调整档位

#### 9.4 完整灵感工作流（P0）

**灵感工作流全流程**：
```
灵感触发 → 方向生成 → 提示词撰写 → 一键执行 → 反馈优化
    ↓           ↓           ↓           ↓           ↓
  主动/被动  多方向候选  详细提示词  发给强AI   有用/无用
```

**灵感触发**：
- 主动触发：用户点击"给我灵感"按钮
- 被动触发：基于用户数据（文档/任务/对话），桌宠主动提出灵感
- 触发时机：用户空闲时、完成任务后、每日固定时间
- 灵感来源：用户画像、最近活动、知识库、热点话题（可选联网）

**方向生成**：
- 一次生成3-5个灵感方向
- 每个方向包含：标题、简短描述、相关领域、预估价值
- 用户可选择一个方向深入，或要求"再来一批"

**提示词撰写**：
- 用户选择方向后，自动生成详细提示词
- 提示词包含：角色设定、任务描述、约束条件、输出格式、参考资料
- 用户可编辑提示词
- 提示词可保存到Prompt模板库

**一键执行**：
- 点击"执行" → 将提示词发给强AI模型
- 流式展示生成结果
- 结果可保存为文档、转为任务、加入收集箱

**反馈优化**：
- 每个灵感可标记"有用/无用/一般"
- 有用的灵感进入灵感历史，可回溯复用
- 反馈数据用于优化后续灵感生成（偏好学习）

**灵感历史**：
- 所有生成的灵感记录存档
- 按时间/领域/评分筛选
- 可重新激活未执行的灵感
- 可查看灵感的执行结果

#### 9.5 第二分身设置页

**新增设置项**：
- 模型配置：云端模型/本地模型选择、API Key管理
- 记忆管理：查看/编辑/重置长期记忆
- 自动化档位：全局档位+单项操作配置
- 灵感设置：灵感开关、触发频率、灵感领域偏好
- 人格设定：角色设定词编辑、预设人格选择
- 对话设置：回复长度、语言风格、创造力参数

### 10. 桌宠形象进化（M7深化）

#### 10.1 Marvis式状态感知互动（P0）

**状态感知维度**：

| 感知维度 | 数据来源 | 对应动作 |
|----------|----------|----------|
| 时间感知 | 系统时间 | 工作/午休/下午茶/夜间/深夜动作 |
| 活跃感知 | 键盘/鼠标输入检测 | 工作中/休息中动作 |
| 任务感知 | 当前任务状态 | 专注/轻松/庆祝动作 |
| 心情感知 | 用户最近心情记录 | 开心/关心/鼓励动作 |
| 天气感知（可选） | 系统位置+天气API | 晴天/雨天动作 |

**时间驱动动作**：
- 06:00-09:00：早起动作（伸懒腰/打哈欠）
- 09:00-12:00：工作动作（打字/思考/查看文件）
- 12:00-14:00：午休动作（吃饭/打瞌睡）
- 14:00-18:00：工作动作（专注/讨论）
- 18:00-19:00：下班动作（收拾/放松）
- 19:00-23:00：休闲动作（看书/听音乐/玩游戏）
- 23:00-06:00：夜间动作（睡觉/守夜）

**活跃感知实现**：
- 监听全局键盘/鼠标事件（Electron端）
- 5分钟无输入 → 切换到"休息中"动作
- 持续输入 → 切换到"工作中"动作
- 输入强度变化（快速打字/缓慢移动）→ 对应不同工作动作

**任务感知**：
- 当前有进行中任务且标记为"今日最重要" → 专注动作
- 任务完成 → 庆祝动作（撒花/跳舞）
- 任务逾期 → 关心动作（皱眉/提醒）

#### 10.2 本地TTS语音（P1）

**功能描述**：
- 集成Piper本地TTS引擎，完全离线
- 内置2-3个音色（可扩展）
- 支持语速/音调/音量调节
- 桌宠说话时显示语音气泡+播放语音
- 可配置说话场景：提醒时/互动时/庆祝时/始终不说话
- 默认关闭，用户可在设置中开启

**技术实现**：
- Piper TTS：轻量级本地神经语音合成
- 模型文件：随安装包附带（约50MB/音色）
- 异步播放：不阻塞UI
- 中断机制：新语音可中断当前播放

#### 10.3 自定义形象上传（P1）

**功能描述**：
- 用户上传自己的二次元形象图（PNG，建议透明背景）
- 形象适配工具：
  - 裁剪：选择主体区域
  - 缩放：适配桌宠窗口大小
  - 动作映射：将用户形象映射到预设动作骨架
- 动作适配：
  - 简单模式：静态形象+表情切换（眼睛/嘴巴变化）
  - 进阶模式：用户提供多帧动作图，按动作切换
- 形象管理：可保存多套形象，随时切换
- 形象市场（二期后期）：官方/第三方形象包下载

**形象上传流程**：
1. 用户点击"上传形象" → 选择图片文件
2. 系统展示预览 + 裁剪框 → 用户调整裁剪区域
3. 选择适配模式：简单（静态+表情）/ 进阶（多帧动作）
4. 简单模式：系统自动识别眼睛/嘴巴位置（AI辅助），用户可微调
5. 进阶模式：用户上传各动作帧（可选，不上传则用默认动作）
6. 保存形象 → 立即应用

#### 10.4 桌宠设置增强

**新增设置项**：
- 状态感知开关：是否启用状态感知互动
- 语音设置：TTS开关、音色选择、语速、说话场景
- 形象管理：当前形象、形象列表、上传新形象
- 互动设置：点击互动开关、拖拽开关、右键菜单开关
- 显示设置：透明度、大小、始终置顶、开机自启
- 动作设置：动作切换频率、是否显示气泡、气泡时长

### 11. 强AI能力扩展

#### 11.1 任务自动拆解（P1）

**功能描述**：
- 用户输入大目标（如"完成数学建模竞赛论文"）
- AI自动拆解为：
  - 阶段划分（准备/实施/收尾）
  - 每个阶段的子任务列表
  - 每个任务的预估时长
  - 任务依赖关系
  - 建议的时间安排
- 用户可编辑调整拆解结果
- 确认后一键创建任务（带依赖关系和预估时长）
- 可选择关联到项目

**拆解结果展示**：
- 树形结构展示阶段→任务
- 每个任务可编辑：标题、描述、预估时长、优先级
- 拖拽调整任务顺序和层级
- 时间线预览：基于预估时长和依赖关系生成甘特图预览

**与项目模块联动**：
- 拆解时可选择"创建新项目"或"关联到现有项目"
- 创建项目后，任务自动归属到该项目
- 项目里程碑自动对应阶段

#### 11.2 RAG知识问答（P1）

**功能描述**：
- 基于用户全部知识库（文档+知识卡片+项目记忆）的语义检索问答
- 用户提问 → 系统检索相关知识片段 → 注入AI上下文 → 生成回答
- 回答显示引用来源（哪些文档/卡片），可点击跳转
- 支持追问：基于上一轮对话继续提问
- 支持"仅基于知识库回答"模式（不使用AI自身知识）

**技术实现**：
- 本地向量库：SQLite + sqlite-vec（或chromadb本地模式）
- 向量化：本地模型（bge-small等）或云端API
- 索引更新：文档保存时自动更新向量索引
- 检索：Top-K相似片段（默认5条）
- 增量索引：只更新变更的文档，不重建全库

**RAG设置**：
- 检索范围：全部文档/指定文件夹/知识卡片/项目记忆
- 引用数量：3-10条
- 回答模式：仅知识库/知识库+AI知识
- 索引管理：重建索引、查看索引状态、排除特定文件夹

#### 11.3 长文写作助手（P1）

**功能描述**：
- 基于知识库的长文写作辅助
- 功能包括：
  - 续写：基于当前文档上下文继续写作
  - 润色：选中文字 → 润色（保持原意/提升表达/调整风格）
  - 摘要：生成长文摘要（简短/详细/结构化）
  - 扩写：选中文字 → 扩展内容（加细节/加案例/加解释）
  - 翻译：中英互译
  - 大纲生成：基于主题生成文章大纲
- 所有操作在文档编辑器内完成，不离开编辑界面
- 修改前后对比：接受/拒绝/部分接受

**写作助手交互**：
1. 用户在文档编辑器中选中文字（或不选中，对全文操作）
2. 点击"AI助手"按钮 → 选择操作类型
3. AI流式生成结果，在侧边栏展示
4. 用户可编辑AI生成的内容
5. 点击"应用" → 替换选中文字（或插入到光标位置）
6. 可查看修改历史，支持回滚

### 12. 工作流模板系统

#### 12.1 工作流定义

**什么是工作流**：
工作流 = 模块组合 + 视图配置 + 规则 + 模板 + SOP + 自动化

一个工作流定义了：
- 使用哪些模块（如：任务+知识+复盘+资产库）
- 各模块的视图配置（如：任务看板按阶段分组）
- 自动化规则（如：完成任务后自动创建复盘）
- 模板集合（如：文档模板/任务模板/SOP）
- 标签体系（如：预设标签分类）
- 文件夹结构（如：预设文件夹层级）

#### 12.2 预设工作流（P0）

**工作流一：数学学习工作流**

```
适用场景：学生数学学习、竞赛备考
模块组合：学习成长 + 知识 + 任务 + 复盘 + 资产库

预设配置：
- 文件夹结构：
  /数学
    /高等数学
    /线性代数
    /概率论
    /错题本
- 标签体系：
  难度：简单/中等/困难
  类型：概念/公式/例题/错题
  掌握度：未学/学习中/已掌握/需复习
- 任务模板：
  - 章节学习（看视频→做笔记→做题→复盘）
  - 错题整理（错题→分析→重做→归档）
- 文档模板：
  - 章节笔记模板
  - 错题本模板
  - 公式推导模板
- SOP：
  - 错题整理SOP
  - 考前复习SOP
- 自动化规则：
  - 标记"已掌握"的知识点 → 7天后自动创建复习任务
  - 错题重做正确 → 自动移到"已掌握"
- 视图配置：
  - 任务按"章节"分组
  - 知识按"难度+类型"筛选
```

**工作流二：项目开发工作流**

```
适用场景：软件项目开发、产品开发
模块组合：项目 + 任务 + 知识 + 第二分身 + 资产库

预设配置：
- 文件夹结构：
  /项目名
    /需求文档
    /设计文档
    /技术方案
    /会议纪要
    /复盘总结
- 标签体系：
  阶段：需求/设计/开发/测试/上线
  优先级：P0/P1/P2/P3
  类型：功能/bug/优化/文档
- 任务模板：
  - 功能开发（需求分析→设计→编码→测试→上线）
  - Bug修复（复现→定位→修复→验证→回归）
- 文档模板：
  - 需求文档模板
  - 技术方案模板
  - 会议纪要模板
  - 项目复盘模板
- SOP：
  - 代码审查SOP
  - 发布流程SOP
  - Bug处理SOP
- 自动化规则：
  - 任务标记"开发完成" → 自动创建测试任务
  - 项目完成 → 自动生成项目记忆
- 视图配置：
  - 任务看板按"阶段"列
  - 项目时间线视图
```

**工作流三：小说写作工作流**

```
适用场景：长篇小说创作、网文写作
模块组合：知识 + 任务 + 第二分身 + 复盘 + 资产库

预设配置：
- 文件夹结构：
  /作品名
    /世界观设定
    /人物设定
    /大纲
    /正文
    /素材积累
- 标签体系：
  内容：设定/人物/情节/伏笔/素材
  状态：构思/草稿/修改/定稿
  卷章：卷一/卷二/...
- 任务模板：
  - 章节写作（列大纲→写正文→修改→定稿）
  - 人物设定（外貌→性格→背景→关系→成长弧）
- 文档模板：
  - 人物设定模板
  - 世界观设定模板
  - 章节大纲模板
- SOP：
  - 章节写作SOP
  - 人物设定SOP
  - 伏笔回收SOP
- 自动化规则：
  - 完成章节 → 自动创建下一章大纲任务
  - 标记"定稿" → 自动归档到正文
- 视图配置：
  - 文档按"卷章"树状展示
  - 任务按"写作阶段"分组
```

#### 12.3 工作流应用（P0）

**一键应用流程**：
1. 用户进入"工作流中心" → 浏览预设工作流
2. 选择工作流 → 查看详情（包含的模块/模板/规则）
3. 点击"应用工作流" → 配置参数（如：项目名称/学习科目）
4. 系统自动执行：
   - 创建文件夹结构
   - 导入模板集合
   - 创建标签体系
   - 配置自动化规则
   - 设置视图配置
   - 创建初始任务
5. 应用完成 → 提示"工作流已应用"，可跳转到对应模块

**自定义工作流（P1）**：
- 用户可从当前配置"保存为工作流"
- 工作流编辑器：可视化配置模块/模板/规则/视图
- 工作流导出/导入：JSON格式，可分享

#### 12.4 工作流中心

**布局**：
- 预设工作流展示（卡片式，含图标/名称/描述/适用场景）
- 我的工作流（已应用的工作流列表）
- 工作流详情页（包含的所有配置项）
- 应用历史记录

---

## 第四部分：API接口设计

### 13. 新增API设计规范

#### 13.1 设计原则（延续一期）

- RESTful风格，统一前缀 `/api/v2`（二期新增接口）
- 统一响应格式：`{ code, message, data }`
- 分页参数：`page`、`page_size`
- 排序参数：`sort_by`、`sort_order`
- 筛选参数：各模块自定义
- 认证方式：Bearer Token（延续一期）

#### 13.2 资源中心API

```
# 收集箱
GET    /api/v2/inbox              # 收集箱列表（分页+筛选）
POST   /api/v2/inbox              # 创建收集箱条目
GET    /api/v2/inbox/{id}         # 获取条目详情
PUT    /api/v2/inbox/{id}         # 更新条目
DELETE /api/v2/inbox/{id}         # 删除条目
POST   /api/v2/inbox/{id}/process # 处理条目（分类/转任务/转文档）
POST   /api/v2/inbox/batch        # 批量处理

# 模板库
GET    /api/v2/templates          # 模板列表（分类筛选）
POST   /api/v2/templates          # 创建模板
GET    /api/v2/templates/{id}     # 获取模板详情
PUT    /api/v2/templates/{id}     # 更新模板
DELETE /api/v2/templates/{id}     # 删除模板
POST   /api/v2/templates/{id}/use # 使用模板（变量替换）

# 领域库
GET    /api/v2/domains            # 领域列表
POST   /api/v2/domains            # 创建领域
GET    /api/v2/domains/{id}       # 领域详情（含资源聚合）
PUT    /api/v2/domains/{id}       # 更新领域
DELETE /api/v2/domains/{id}       # 删除领域
```

#### 13.3 学习成长API

```
# 学习计划
GET    /api/v2/study/plans           # 学习计划列表
POST   /api/v2/study/plans           # 创建学习计划
GET    /api/v2/study/plans/{id}      # 计划详情
PUT    /api/v2/study/plans/{id}      # 更新计划
DELETE /api/v2/study/plans/{id}      # 删除计划
POST   /api/v2/study/plans/{id}/sync # 同步到任务模块

# 知识卡片
GET    /api/v2/study/cards           # 卡片列表（分类/标签筛选）
POST   /api/v2/study/cards           # 创建卡片
GET    /api/v2/study/cards/{id}      # 卡片详情
PUT    /api/v2/study/cards/{id}      # 更新卡片
DELETE /api/v2/study/cards/{id}      # 删除卡片
POST   /api/v2/study/cards/from-doc  # 从文档生成卡片

# 间隔重复
GET    /api/v2/study/review/today    # 今日复习队列
POST   /api/v2/study/review/{cardId} # 提交复习评分
GET    /api/v2/study/review/stats    # 复习统计

# 学习时长
GET    /api/v2/study/time            # 学习时长记录
POST   /api/v2/study/time            # 记录学习时长
GET    /api/v2/study/time/stats      # 学习时长统计
```

#### 13.4 生活记录API

```
# 习惯
GET    /api/v2/life/habits           # 习惯列表
POST   /api/v2/life/habits           # 创建习惯
GET    /api/v2/life/habits/{id}      # 习惯详情
PUT    /api/v2/life/habits/{id}      # 更新习惯
DELETE /api/v2/life/habits/{id}      # 删除习惯
POST   /api/v2/life/habits/{id}/check-in  # 打卡
GET    /api/v2/life/habits/{id}/stats    # 习惯统计

# 心情
GET    /api/v2/life/moods            # 心情记录列表
POST   /api/v2/life/moods            # 记录心情
GET    /api/v2/life/moods/stats      # 心情统计

# 日记
GET    /api/v2/life/diaries          # 日记列表
POST   /api/v2/life/diaries          # 创建日记
GET    /api/v2/life/diaries/{id}     # 日记详情
PUT    /api/v2/life/diaries/{id}     # 更新日记
DELETE /api/v2/life/diaries/{id}     # 删除日记

# 年度报告
GET    /api/v2/life/annual-report/{year}  # 年度生活报告
```

#### 13.5 长期资产库API

```
# SOP
GET    /api/v2/assets/sops           # SOP列表
POST   /api/v2/assets/sops           # 创建SOP
GET    /api/v2/assets/sops/{id}      # SOP详情
PUT    /api/v2/assets/sops/{id}      # 更新SOP
DELETE /api/v2/assets/sops/{id}      # 删除SOP
POST   /api/v2/assets/sops/{id}/execute  # 执行SOP（生成任务）
GET    /api/v2/assets/sops/{id}/versions # SOP版本列表

# Prompt
GET    /api/v2/assets/prompts        # Prompt列表
POST   /api/v2/assets/prompts        # 创建Prompt
GET    /api/v2/assets/prompts/{id}   # Prompt详情
PUT    /api/v2/assets/prompts/{id}   # 更新Prompt
DELETE /api/v2/assets/prompts/{id}   # 删除Prompt

# Skill
GET    /api/v2/assets/skills         # Skill列表
POST   /api/v2/assets/skills         # 创建Skill
GET    /api/v2/assets/skills/{id}    # Skill详情
PUT    /api/v2/assets/skills/{id}    # 更新Skill
DELETE /api/v2/assets/skills/{id}    # 删除Skill

# 项目记忆
GET    /api/v2/assets/project-memories       # 项目记忆列表
POST   /api/v2/assets/project-memories       # 创建项目记忆
POST   /api/v2/assets/project-memories/generate  # AI生成项目记忆
GET    /api/v2/assets/project-memories/{id}  # 详情
PUT    /api/v2/assets/project-memories/{id}  # 更新

# 智能推荐
GET    /api/v2/assets/recommend      # 获取推荐（基于上下文）
POST   /api/v2/assets/recommend/feedback  # 推荐反馈
```

#### 13.6 第二分身进化API

```
# 本地模型
GET    /api/v2/ai/local/models       # 获取本地模型列表
POST   /api/v2/ai/local/connect      # 连接本地模型服务
POST   /api/v2/ai/local/test         # 测试本地模型推理速度

# 长期记忆
GET    /api/v2/memory                # 获取长期记忆（分类筛选）
PUT    /api/v2/memory/{id}           # 更新记忆
DELETE /api/v2/memory/{id}           # 删除记忆
POST   /api/v2/memory/reset          # 重置记忆（按类型或全部）
GET    /api/v2/memory/sources        # 记忆来源统计

# 灵感
GET    /api/v2/inspiration           # 获取灵感（主动/被动）
POST   /api/v2/inspiration/generate  # 生成灵感方向
POST   /api/v2/inspiration/{id}/execute  # 执行灵感
GET    /api/v2/inspiration/history   # 灵感历史
POST   /api/v2/inspiration/{id}/feedback  # 灵感反馈
```

---

## 第五部分：数据模型扩展

### 14. 新增表结构

#### 14.1 资源中心

```sql
-- 收集箱
CREATE TABLE inbox_items (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id),
  content_type VARCHAR(20) NOT NULL, -- text/url/image/file
  content TEXT,
  title VARCHAR(500),
  preview_url VARCHAR(1000),
  file_path VARCHAR(1000),
  source VARCHAR(500),
  tags JSON DEFAULT '[]',
  status VARCHAR(20) DEFAULT 'pending', -- pending/processed/archived
  processed_at DATETIME,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 模板
CREATE TABLE templates (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id),
  name VARCHAR(200) NOT NULL,
  category VARCHAR(50) NOT NULL, -- doc/sheet/config/project/prompt
  description TEXT,
  content TEXT NOT NULL, -- 模板内容（含变量占位符）
  variables JSON DEFAULT '[]', -- 变量定义列表
  tags JSON DEFAULT '[]',
  is_builtin BOOLEAN DEFAULT FALSE,
  use_count INTEGER DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 领域
CREATE TABLE domains (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id),
  name VARCHAR(100) NOT NULL,
  description TEXT,
  icon VARCHAR(50),
  color VARCHAR(20),
  sort_order INTEGER DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

#### 14.2 学习成长

```sql
-- 学习计划
CREATE TABLE study_plans (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id),
  name VARCHAR(200) NOT NULL,
  description TEXT,
  target_date DATE,
  estimated_hours INTEGER,
  progress INTEGER DEFAULT 0,
  status VARCHAR(20) DEFAULT 'active', -- active/paused/completed/archived
  config JSON DEFAULT '{}', -- 里程碑/任务配置
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 知识卡片
CREATE TABLE flashcards (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id),
  plan_id UUID REFERENCES study_plans(id),
  front TEXT NOT NULL, -- 正面（问题）
  back TEXT NOT NULL,  -- 背面（答案）
  card_type VARCHAR(20) DEFAULT 'qa', -- qa/concept/cloze/list
  category VARCHAR(100),
  tags JSON DEFAULT '[]',
  difficulty INTEGER DEFAULT 3, -- 1-5
  -- SM-2参数
  ef REAL DEFAULT 2.5,
  interval INTEGER DEFAULT 0,
  repetition INTEGER DEFAULT 0,
  next_review DATE,
  last_reviewed_at DATETIME,
  review_count INTEGER DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 学习时长记录
CREATE TABLE study_time_logs (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id),
  plan_id UUID REFERENCES study_plans(id),
  subject VARCHAR(200),
  duration INTEGER NOT NULL, -- 分钟
  note TEXT,
  source VARCHAR(50), -- manual/pomodoro/auto
  logged_date DATE NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

#### 14.3 生活记录

```sql
-- 习惯
CREATE TABLE habits (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id),
  name VARCHAR(100) NOT NULL,
  icon VARCHAR(50),
  color VARCHAR(20),
  frequency VARCHAR(20) DEFAULT 'daily', -- daily/weekly
  target_per_week INTEGER DEFAULT 7,
  reminder_time TIME,
  goal_days INTEGER,
  status VARCHAR(20) DEFAULT 'active', -- active/archived
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 习惯打卡记录
CREATE TABLE habit_checkins (
  id UUID PRIMARY KEY,
  habit_id UUID NOT NULL REFERENCES habits(id),
  user_id UUID NOT NULL REFERENCES users(id),
  checkin_date DATE NOT NULL,
  note TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(habit_id, checkin_date)
);

-- 心情记录
CREATE TABLE mood_logs (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id),
  score INTEGER NOT NULL, -- 1-5
  tags JSON DEFAULT '[]',
  content TEXT,
  logged_date DATE NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 日记
CREATE TABLE diaries (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id),
  dimension VARCHAR(20), -- family/health/energy/growth
  title VARCHAR(200),
  content TEXT,
  diary_date DATE NOT NULL,
  tags JSON DEFAULT '[]',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

#### 14.4 长期资产库

```sql
-- SOP
CREATE TABLE sops (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id),
  name VARCHAR(200) NOT NULL,
  category VARCHAR(100),
  description TEXT,
  steps JSON NOT NULL, -- 步骤列表
  checklist JSON DEFAULT '[]', -- 检查清单
  tags JSON DEFAULT '[]',
  use_count INTEGER DEFAULT 0,
  version INTEGER DEFAULT 1,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- SOP版本
CREATE TABLE sop_versions (
  id UUID PRIMARY KEY,
  sop_id UUID NOT NULL REFERENCES sops(id),
  version INTEGER NOT NULL,
  content JSON NOT NULL,
  change_note TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Prompt模板
CREATE TABLE prompt_templates (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id),
  name VARCHAR(200) NOT NULL,
  category VARCHAR(50),
  description TEXT,
  role_setting TEXT,
  task_description TEXT,
  constraints TEXT,
  output_format TEXT,
  variables JSON DEFAULT '[]',
  use_count INTEGER DEFAULT 0,
  rating REAL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Skill
CREATE TABLE skills (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id),
  name VARCHAR(200) NOT NULL,
  category VARCHAR(100),
  description TEXT,
  methodology TEXT, -- 方法论文档（Markdown）
  proficiency VARCHAR(20) DEFAULT 'beginner', -- beginner/intermediate/expert
  tags JSON DEFAULT '[]',
  use_count INTEGER DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 项目记忆
CREATE TABLE project_memories (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id),
  project_id UUID REFERENCES projects(id),
  name VARCHAR(200) NOT NULL,
  summary TEXT, -- 项目概况
  successes TEXT, -- 成功经验
  failures TEXT, -- 失败教训
  extracted_assets JSON DEFAULT '[]', -- 提取的可复用资产
  key_metrics JSON DEFAULT '{}', -- 关键数据
  tags JSON DEFAULT '[]',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

#### 14.5 第二分身进化

```sql
-- 长期记忆
CREATE TABLE long_term_memories (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id),
  memory_type VARCHAR(50) NOT NULL, -- profile/knowledge/event/relation
  category VARCHAR(100),
  content TEXT NOT NULL,
  source_type VARCHAR(50), -- conversation/document/review/manual
  source_id UUID,
  confidence REAL DEFAULT 0.8, -- 可信度0-1
  is_verified BOOLEAN DEFAULT FALSE, -- 用户是否确认
  embedding BLOB, -- 向量
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 灵感记录
CREATE TABLE inspirations (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id),
  title VARCHAR(200) NOT NULL,
  description TEXT,
  domain VARCHAR(100),
  prompt TEXT, -- 生成的详细提示词
  status VARCHAR(20) DEFAULT 'generated', -- generated/executed/dismissed
  feedback VARCHAR(20), -- useful/useless/normal
  result TEXT, -- 执行结果
  source VARCHAR(50), -- active/passive
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  executed_at DATETIME
);
```

#### 14.6 工作流

```sql
-- 工作流
CREATE TABLE workflows (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id),
  name VARCHAR(200) NOT NULL,
  description TEXT,
  icon VARCHAR(50),
  category VARCHAR(50), -- study/dev/writing/custom
  config JSON NOT NULL, -- 完整工作流配置
  is_builtin BOOLEAN DEFAULT FALSE,
  use_count INTEGER DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 工作流应用记录
CREATE TABLE workflow_applications (
  id UUID PRIMARY KEY,
  workflow_id UUID NOT NULL REFERENCES workflows(id),
  user_id UUID NOT NULL REFERENCES users(id),
  params JSON DEFAULT '{}', -- 应用时的参数
  status VARCHAR(20) DEFAULT 'applied', -- applied/active/removed
  applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 15. 数据迁移策略

- 二期新增表通过Alembic迁移创建（0005_xxx）
- 一期表结构不变，仅新增外键关联
- 本地向量索引独立存储（不进SQLite主库，单独文件）
- 配置数据迁移：一期设置项保留，新增二期设置项

---

## 第六部分：非功能需求

### 16. Electron桌面端（P2）

#### 16.1 打包要求

- 框架：Electron + electron-builder
- 支持平台：Windows 10/11（优先）、macOS（二期后期）
- 安装包格式：Windows NSIS安装包（.exe）
- 安装包大小：<200MB（含运行时+默认模型）
- 自动更新：electron-updater，支持增量更新

#### 16.2 桌面端特性

**真桌宠窗口**：
- 桌宠从网页内组件升级为独立的Electron窗口
- 窗口特性：透明背景、无边框、始终置顶、可拖拽、点击穿透（非交互区域）
- 窗口大小：桌宠模式150x200，人形模式600x800
- 多显示器支持：可拖拽到任意显示器

**系统托盘**：
- 托盘图标：启明星Logo
- 托盘菜单：显示/隐藏主窗口、显示/隐藏桌宠、主题切换、设置、检查更新、退出
- 托盘气泡：通知提醒、桌宠消息

**全局快捷键**：
- 快速捕获：Ctrl+Shift+N
- 全局搜索：Ctrl+K
- 显示/隐藏主窗口：Ctrl+Shift+M
- 显示/隐藏桌宠：Ctrl+Shift+P
- 用户可自定义快捷键

**开机自启**：
- 安装时可选择开机自启
- 设置页可开关
- 自启时最小化到托盘

**文件关联**：
- 关联.venustech备份文件
- 双击备份文件可导入

#### 16.3 性能要求

| 指标 | 要求 |
|------|------|
| 应用启动时间 | <3s（冷启动）、<1s（热启动） |
| 首屏加载 | <2s |
| 模块切换 | <300ms |
| API响应（本地） | <500ms |
| 内存占用（空闲） | <300MB |
| 内存占用（使用中） | <500MB |
| CPU占用（空闲） | <2% |
| 桌宠动画FPS | ≥30 |
| 本地模型推理 | ≥5 tokens/s（7B模型） |

### 17. 数据安全升级

#### 17.1 定时自动备份

- 可配置备份频率：每日/每周/每月
- 可配置备份时间（默认凌晨3点）
- 可配置保留份数（默认7份）
- 备份格式：.venustech（ZIP压缩+元数据）
- 备份位置：默认数据目录/backups，可自定义
- 备份通知：备份完成后桌宠通知
- 备份验证：自动验证备份文件完整性

#### 17.2 同步盘半自动同步

- 支持将数据目录放在OneDrive/iCloud/坚果云等同步盘
- SQLite冲突检测：检测到数据库文件被外部修改时提示
- 合并策略：
  - 新增数据：自动合并
  - 修改数据：保留最新版本，冲突时提示用户选择
  - 删除数据：需用户确认
- 同步状态指示：设置页显示最后同步时间、同步状态

#### 17.3 加密仓库升级

- 一期已实现AES-128-CBC加密基础
- 二期升级：
  - 可选AES-256加密（更高安全级别）
  - 用户主密码保护（忘记密码不可恢复）
  - 加密范围可选：全部数据/仅敏感字段/仅文档内容
  - 加密性能优化：批量加密、增量加密
  - 密码强度检测

### 18. 兼容性要求

- Windows 10 1903+ / Windows 11
- macOS 12+（二期后期）
- 屏幕分辨率：最低1280x720，推荐1920x1080+
- 本地模型最低配置：8GB内存（3B模型）、16GB内存（7B模型）
- 无需联网即可使用基础功能（本地模型+本地数据）

---

## 第七部分：插件生态深化

### 19. 插件系统二期增强

一期已完成插件基础架构（发现/加载/启用禁用/热重载）。二期增强：

#### 19.1 插件API扩展

- UI扩展：插件可注入侧边栏面板、设置页、菜单项
- 数据扩展：插件可注册自定义数据类型和表
- 事件扩展：插件可订阅和发布自定义事件
- AI扩展：插件可注册自定义AI Provider
- 主题扩展：插件可注册自定义主题包

#### 19.2 插件开发文档

- 完整的插件开发指南
- API参考文档
- 插件示例（3个：示例主题/示例面板/示例AI Provider）
- 插件调试工具

#### 19.3 插件市场（二期后期）

- 官方插件仓库
- 插件搜索/分类/评分
- 一键安装/更新/卸载
- 插件审核机制

---

## 第八部分：验收标准与里程碑

### 20. 二期验收标准

#### 20.1 功能验收

| 模块 | P0功能 | 验收标准 |
|------|--------|----------|
| 资源中心 | 收集箱、模板库 | 收集箱可捕获/处理；模板可创建/使用/变量替换 |
| 学习成长 | 学习计划、知识卡片、间隔重复 | 计划可创建/追踪；卡片可创建/复习；SM-2算法正确 |
| 生活记录 | 习惯打卡、心情追踪 | 习惯可创建/打卡/统计；心情可记录/趋势展示 |
| 长期资产库 | SOP、Prompt、项目记忆 | SOP可创建/执行；Prompt可创建/变量替换；项目记忆可生成/编辑 |
| 第二分身 | 本地推理、长期记忆、五档自动化、灵感工作流 | 本地模型可连接/推理；记忆可可视化/管理；档位可切换/行为正确；灵感可生成/执行 |
| 桌宠 | 状态感知互动 | 时间/活跃状态可感知/动作切换正确 |
| 一期维护 | 9模块考校 | 无阻断bug、性能达标、文档同步 |

#### 20.2 性能验收

- 所有性能指标达到第16.3节要求
- 前端生产构建成功
- 后端pytest全部通过
- TypeScript严格模式零错误

#### 20.3 体验验收

- 所有新模块有完整的空状态/加载状态/错误状态
- 所有操作有明确反馈
- 桌宠互动流畅无卡顿
- 本地模型推理可用（有本地模型环境时）

### 21. 二期里程碑

| 里程碑 | 时间 | 交付物 | 版本号 |
|--------|------|--------|--------|
| M1：一期考校维护完成 | 第4周 | 考校报告、bug修复、v0.3.0 | v0.3.0 |
| M2：新模块骨架完成 | 第4周 | 4个新模块页面+API骨架 | v0.4.0 |
| M3：新模块P0完成 | 第8周 | 资源中心/学习/生活/资产库P0功能 | v0.5.0 |
| M4：第二分身进化完成 | 第12周 | 本地推理/长期记忆/五档自动化/灵感 | v0.6.0 |
| M5：形象进化+强AI完成 | 第14周 | 状态感知/TTS/任务拆解/RAG/写作助手 | v0.7.0 |
| M6：工作流系统完成 | 第14周 | 3套预设工作流+自定义工作流 | v0.8.0 |
| M7：Electron打包完成 | 第16周 | Windows安装包、自动更新 | v0.9.0 |
| M8：二期正式发布 | 第16周 | 全量测试、文档、v1.0 | v1.0.0 |

### 22. 风险登记册

| 风险 | 概率 | 影响 | 应对措施 |
|------|------|------|----------|
| 本地模型推理性能不足 | 中 | 高 | 提供模型大小选择，弱AI功能可降级到规则引擎 |
| Electron打包复杂度超预期 | 中 | 中 | 提前调研，预留缓冲时间，必要时先发布Web版 |
| 新模块开发量超预期 | 高 | 中 | 严格按P0/P1优先级，P2功能可延后到三期 |
| SM-2算法用户不适应 | 低 | 低 | 提供简化模式（仅"记住/忘记"两档） |
| 长期记忆提取不准确 | 中 | 中 | 记忆可视化+用户编辑确认机制，可信度标注 |
| 数据迁移出问题 | 低 | 高 | 迁移前自动备份，提供回滚机制 |

---

## 附录

### 附录A：二期技术栈增量

| 类别 | 技术 | 用途 |
|------|------|------|
| 桌面端 | Electron + electron-builder + electron-updater | 桌面打包与自动更新 |
| 本地TTS | Piper TTS | 离线语音合成 |
| 向量数据库 | sqlite-vec / chromadb | RAG语义检索 |
| 本地AI | Ollama / LM Studio API | 本地模型推理 |
| 全局监听 | Electron globalShortcut / iohook | 全局快捷键/输入感知 |

### 附录B：二期新增快捷键

| 快捷键 | 功能 |
|--------|------|
| Ctrl+Shift+N | 快速捕获（收集箱） |
| Ctrl+Shift+M | 显示/隐藏主窗口 |
| Ctrl+Shift+P | 显示/隐藏桌宠 |
| Ctrl+Shift+L | 开始/暂停学习计时 |
| Ctrl+Shift+H | 记录心情 |

### 附录C：文档变更记录

| 版本 | 日期 | 变更内容 |
|------|------|----------|
| v2.0-draft | 2026-09-06 | 二期PRD初稿，对标一期PRD框架 |

---

> 本文档为二期PRD草稿，后续将根据开发进展持续更新。
> 一期PRD：PRD-启明星系统-v1.0.md（2993行）
> 项目仓库：https://github.com/YanYuas/VenustechSystem
