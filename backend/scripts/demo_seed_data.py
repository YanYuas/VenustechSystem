"""启明星演示数据 —— 内容定义（纯数据，无逻辑）

## 这套数据是怎么来的
不是编的：全部对齐你自己的真实轨迹。

- **10 重身份**来自 `docs/management/三期规划-身份层与档案库-2026-09-16.md`
  §2.1 你亲口列的那串 —— "AI 研究 · 数学建模 · 音乐 · 交易 · 管理科学 ·
  家教 · 小说 · 篆刻 · …"（原文说"至少 9 重"，省略号处按你 `D:\\YanYuas`
  的真实目录补齐：实习实训、启明星开发）。
- **项目名**取自 `D:\\YanYuas` 实际目录：数脉传古 / 数说旅意 / 蒸汽蓬勃 /
  商科精英挑战赛（ManagementScience）、第一交响诗 / MuseHub 系列
  （Musician）、HelloMathModeling / 竞赛作品（MathematicalModeling）、
  RedBook / 电商（Trade）、CDUT 数学软件实训 / AIGC 阿里产教中心 /
  数智工坊（InternshipRecord）、VenustechSystem / CompetitorHub /
  数书手札（PersonalDevelopmentPortfolio）。
- **档案库文件树**复刻 `D:\\YanYuas` 的真实两级结构（真实扫描是 10,558 个
  文件 / 3.2GB / 其中 1,961 个真实内容），本演示取**代表性样本**，
  让「档案轴」不必真扫也能看出效果。

## 为什么单独成文件
内容与插入逻辑分离：改内容不必碰代码，改逻辑不必翻内容。
本文件只导出常量，不做任何 IO。
"""
from __future__ import annotations

# ============================================================
# 1. 身份（10 重）—— 横切维度
#    color_token / icon 必须是设计令牌与 AppIcon 里真实存在的名字
# ============================================================
IDENTITIES: list[dict] = [
    {
        "name": "AI 研究", "slug": "ai-research", "color_token": "sky", "icon": "spark",
        "description": "大模型应用、AIGC 创作流程、Vibe coding；研究报告与工具链",
        "sort_order": 0,
    },
    {
        "name": "数学建模", "slug": "math-modeling", "color_token": "primary", "icon": "chart",
        "description": "竞赛作品、算法复现、历年赛题与培训资料",
        "sort_order": 1,
    },
    {
        "name": "音乐", "slug": "musician", "color_token": "lilac", "icon": "heart",
        "description": "第一交响诗、钢琴曲、自研 AI 作曲工具（MuseHub 系列）",
        "sort_order": 2,
    },
    {
        "name": "交易", "slug": "trade", "color_token": "butter", "icon": "flame",
        "description": "RedBook 电商、选品逻辑、策略与数据复盘",
        "sort_order": 3,
    },
    {
        "name": "管理科学", "slug": "mgmt-science", "color_token": "mint", "icon": "target",
        "description": "商科精英挑战赛、数据叙事作品（数脉传古 / 数说旅意 / 蒸汽蓬勃）",
        "sort_order": 4,
    },
    {
        "name": "实习实训", "slug": "internship", "color_token": "sky", "icon": "book",
        "description": "CDUT 数学软件综合实训（校内）、AIGC 阿里产教合作中心（校外）、数智工坊",
        "sort_order": 5,
    },
    {
        "name": "启明星开发", "slug": "qmx-dev", "color_token": "primary", "icon": "star",
        "description": "个人操作系统本体：身份轴 + 档案轴；含 CompetitorHub、数书手札",
        "sort_order": 6,
    },
    {
        "name": "家教", "slug": "tutoring", "color_token": "mint", "icon": "user",
        "description": "高中数学与编程辅导；讲义、错题体系、学生进度",
        "sort_order": 7,
    },
    {
        "name": "篆刻", "slug": "seal-carving", "color_token": "butter", "icon": "dot",
        "description": "汉印临摹、印稿设计、边款刻制",
        "sort_order": 8,
    },
    {
        "name": "小说", "slug": "fiction", "color_token": "lilac", "icon": "book",
        "description": "长篇设定《弱水》与章节推进",
        "sort_order": 9,
    },
]

# slug → 身份，供下面各处引用（写数据时用 slug，插入时换成真实 id）
ID_SLUGS = [i["slug"] for i in IDENTITIES]

# ============================================================
# 2. 文件夹（文档组织；收集箱固定 is_inbox）
# ============================================================
FOLDERS: list[dict] = [
    {"name": "收集箱", "is_inbox": True, "sort_order": 0},
    {"name": "研究", "sort_order": 1},
    {"name": "竞赛", "sort_order": 2},
    {"name": "创作", "sort_order": 3},
    {"name": "工程", "sort_order": 4},
    {"name": "教学", "sort_order": 5},
    {"name": "手作", "sort_order": 6},
    {"name": "复盘与规划", "sort_order": 7},
]

# ============================================================
# 3. 项目（含里程碑与项目记忆）
#    identity 用 slug；status: active / paused / done / archived
# ============================================================
PROJECTS: list[dict] = [
    {
        "name": "第一交响诗", "identity": "musician", "color": "lilac", "status": "done",
        "description": "AI 协作完成的单乐章交响诗；管弦乐配器 + 人声合唱，含 30+ 段素材迭代",
        "milestones": [
            {"name": "主题动机确定（命运动机）", "done": True},
            {"name": "配器初稿（圆号 / 英国管 / 弦乐）", "done": True},
            {"name": "AI 生成 30 段素材并筛选", "done": True},
            {"name": "终混与母带", "done": True},
        ],
        "memory": {
            "summary": "第一次把「作曲意图」翻译成 AI 能懂的提示词序列，形成可复用的描述模板。",
            "successes": "分段生成 + 人工筛选的方式显著优于一次性生成长片段；把情绪/编制/速度写进提示词能稳定命中风格。",
            "failures": "早期直接要求「写一首交响诗」全部失败；一次生成超过 30 秒的片段结构会崩。",
            "assets": ["AI 编曲提示词模板", "管弦乐编制对照表", "素材筛选评分表"],
            "metrics": {"素材片段": 32, "最终采用": 11, "时长": "4'20\""},
        },
    },
    {
        "name": "MuseHub 音乐工作台", "identity": "musician", "color": "lilac", "status": "active",
        "description": "自研音乐工具链：MuseHub_App / MuseSampler / MuseFX_VST3 / MuseHub_Content",
        "milestones": [
            {"name": "MuseSampler 采样器内核", "done": True},
            {"name": "MuseFX_VST3 效果器插件", "done": True},
            {"name": "MuseHub_App 主界面", "done": False},
            {"name": "曲库内容管理（MuseHub_Content）", "done": False},
        ],
        "memory": {
            "summary": "把写曲过程中反复要用的能力抽成工具，而不是每次靠手工。",
            "successes": "VST3 插件路线让成果能直接在 DAW 里用，复用价值最高。",
            "failures": "一开始想做「全能音乐 App」，范围过大；拆成采样器/效果器/曲库三个独立件才推进得下去。",
            "assets": ["VST3 插件模板", "采样器参数规范"],
            "metrics": {"模块": 4, "已完成": 2},
        },
    },
    {
        "name": "数脉传古", "identity": "mgmt-science", "color": "mint", "status": "done",
        "description": "数据叙事作品：以数据为线，讲述传统文化脉络",
        "milestones": [
            {"name": "选题与数据源确定", "done": True},
            {"name": "数据清洗与指标设计", "done": True},
            {"name": "可视化叙事稿", "done": True},
            {"name": "答辩与提交", "done": True},
        ],
        "memory": {
            "summary": "数据叙事的关键是「先有故事线，再找数据」，反过来会变成图表堆砌。",
            "successes": "先写解说词骨架、再让数据填进去，结构清晰且答辩好讲。",
            "failures": "初版堆了 12 张图，评委反馈「记不住结论」；砍到 5 张并突出主线后才成立。",
            "assets": ["数据叙事脚本模板", "可视化配色规范"],
            "metrics": {"图表": 5, "数据源": 3},
        },
    },
    {
        "name": "数说旅意", "identity": "mgmt-science", "color": "mint", "status": "done",
        "description": "数据叙事作品：旅行体验的量化表达",
        "milestones": [
            {"name": "指标体系（体验/成本/时间）", "done": True},
            {"name": "可视化实现", "done": True},
            {"name": "成果提交", "done": True},
        ],
        "memory": {
            "summary": "把主观体验拆成可量化维度，是这篇作品最被认可的一点。",
            "successes": "维度拆分 + 雷达图表达，评委一眼看懂。",
            "failures": "指标权重拍脑袋定，被追问依据时答得不硬；后续应做敏感性分析。",
            "assets": ["体验量化指标体系"],
            "metrics": {"维度": 6, "样本": 120},
        },
    },
    {
        "name": "蒸汽蓬勃", "identity": "mgmt-science", "color": "mint", "status": "active",
        "description": "数据叙事新作：工业与能源主题",
        "milestones": [
            {"name": "选题论证", "done": True},
            {"name": "数据获取与清洗", "done": False},
            {"name": "叙事结构与成稿", "done": False},
        ],
        "memory": {
            "summary": "沿用「先故事线后数据」的方法，目前卡在数据可得性。",
            "successes": "选题阶段先确认了数据源可用，避免中途翻车。",
            "failures": "公开数据颗粒度不足，需要换角度或补其他来源。",
            "assets": [],
            "metrics": {"进度": "35%"},
        },
    },
    {
        "name": "商科精英挑战赛", "identity": "mgmt-science", "color": "mint", "status": "done",
        "description": "案例分析 + 商业方案路演",
        "milestones": [
            {"name": "组队与分工", "done": True},
            {"name": "案例拆解", "done": True},
            {"name": "方案与路演", "done": True},
        ],
        "memory": {
            "summary": "第一次做商业分析全流程：从财务三表到方案路演。",
            "successes": "用数据支撑结论，而不是凭经验判断。",
            "failures": "路演超时，导致结论页没讲完；下次必须先排时间轴再写内容。",
            "assets": ["商业分析框架笔记", "路演时间轴模板"],
            "metrics": {"页数": 24},
        },
    },
    {
        "name": "HelloMathModeling", "identity": "math-modeling", "color": "primary", "status": "active",
        "description": "数模学习与作品仓库：算法复现、论文解析、模板与工具",
        "milestones": [
            {"name": "目录结构（00-99 编号体系）", "done": True},
            {"name": "历年赛题库整理", "done": True},
            {"name": "算法复现代码库", "done": False},
            {"name": "论文写作模板定稿", "done": False},
        ],
        "memory": {
            "summary": "把数模资料按「研究 / 作品 / 培训 / 题库 / 论文 / 模拟」六层归档，找东西不再靠记忆。",
            "successes": "编号目录（00_/01_/…/90_/99_）极大降低了归档成本。",
            "failures": "早期文件混放，同一份题目有 3 个版本；编号体系是被迫总结出来的。",
            "assets": ["数模论文写作模板", "编号归档规范"],
            "metrics": {"目录层级": 9, "资料份数": 240},
        },
    },
    {
        "name": "数模竞赛作品集", "identity": "math-modeling", "color": "primary", "status": "active",
        "description": "历年参赛论文与代码，按年份归档",
        "milestones": [
            {"name": "2024 作品整理", "done": True},
            {"name": "2025 作品整理", "done": True},
            {"name": "代码可复现化（依赖与说明）", "done": False},
        ],
        "memory": {
            "summary": "作品集的价值在「可复现」；没有运行说明的代码半年后自己也跑不起来。",
            "successes": "每个作品配 README + requirements 后，复用率显著提升。",
            "failures": "更早的代码缺依赖锁定，现已无法直接运行。",
            "assets": ["作品 README 模板"],
            "metrics": {"作品数": 6},
        },
    },
    {
        "name": "启明星系统", "identity": "qmx-dev", "color": "primary", "status": "active",
        "description": "个人操作系统：时间轴 + 身份轴 + 档案轴；本地优先、数据主权自持",
        "milestones": [
            {"name": "一期：任务/文档/复盘/桌宠", "done": True},
            {"name": "二期：成长体系 + 学习 SM-2 + 知识图谱", "done": True},
            {"name": "三期 B：身份层（横切维度）", "done": True},
            {"name": "三期 C：工作区 / 档案库", "done": True},
            {"name": "三期 D：保险箱（凭据加密）", "done": True},
            {"name": "移动端：PWA + Android 壳 + 语音助理", "done": True},
            {"name": "模块化深度开发（8 个模块分支）", "done": False},
        ],
        "memory": {
            "summary": "最大的教训是「内核优先于功能」：把别人产品的功能搬进来容易，把它的内核融进来才有价值。",
            "successes": "身份轴做对了 —— 一立起来，「乱」的感觉立刻消失，因为能看出自己在推进哪条线。",
            "failures": "曾因两个智能体并发操作同一个 git 仓库，导致 .git 被回滚、历史丢失，只能重建仓库。",
            "assets": ["四层分层架构范式", "验收标准转可执行断言的做法", "身份横切标签设计"],
            "metrics": {"数据表": 46, "后端断言": 236, "模块分支": 8},
        },
    },
    {
        "name": "CompetitorHub", "identity": "qmx-dev", "color": "primary", "status": "done",
        "description": "竞品情报聚合工具（启明星的姊妹项目）",
        "milestones": [
            {"name": "数据源接入", "done": True},
            {"name": "聚合与去重", "done": True},
            {"name": "打包发布", "done": True},
        ],
        "memory": {
            "summary": "验证了「先跑通最小闭环再扩功能」的开发节奏。",
            "successes": "最小闭环两天跑通，后续功能都是增量。",
            "failures": "早期过度设计配置系统，实际只用到 20%。",
            "assets": ["竞品数据源清单"],
            "metrics": {"数据源": 5},
        },
    },
    {
        "name": "数书手札", "identity": "qmx-dev", "color": "primary", "status": "active",
        "description": "读书与摘录工具，与启明星的文档层同源",
        "milestones": [
            {"name": "摘录导入", "done": True},
            {"name": "笔记关联", "done": False},
        ],
        "memory": {
            "summary": "与启明星共用文档模型，避免重复造第二套数据。",
            "successes": "复用文档层直接省掉一半工作量。",
            "failures": "暂无",
            "assets": [],
            "metrics": {"进度": "50%"},
        },
    },
    {
        "name": "RedBook 电商", "identity": "trade", "color": "butter", "status": "active",
        "description": "内容电商实践：选品、内容、转化与复盘闭环",
        "milestones": [
            {"name": "选品逻辑与池子", "done": True},
            {"name": "内容模板跑通", "done": True},
            {"name": "转化数据复盘", "done": False},
        ],
        "memory": {
            "summary": "交易的功夫在「复盘」：没有数据回看的选品等于赌博。",
            "successes": "把每次投放的关键指标记下来后，选品命中率有可感知提升。",
            "failures": "前期只看曝光不看转化，白做了一批内容。",
            "assets": ["选品评分卡", "内容模板"],
            "metrics": {"在跑品": 8},
        },
    },
]

# ============================================================
# 4. 任务（按身份分组；status: pending/in_progress/waiting/completed
#    priority: urgent/high/medium/low）
# ============================================================
TASKS: list[dict] = [
    # ---------- AI 研究 ----------
    {"title": "读完 RAG 三篇核心论文并做对比表", "identity": "ai-research", "status": "in_progress",
     "priority": "high", "project": None, "due_days": 2, "focus": True,
     "desc": "对比 chunk 策略 / 检索器 / 重排方案，输出一页对照",
     "subs": ["Chunking 策略那篇", "重排器对比", "整理成对照表"]},
    {"title": "把 AIGC 创作流程写成 SOP", "identity": "ai-research", "status": "in_progress",
     "priority": "medium", "project": None, "due_days": 5,
     "desc": "从需求 → 提示词 → 生成 → 筛选 → 归档，固化步骤"},
    {"title": "Vibe coding 小工具：批量重命名", "identity": "ai-research", "status": "pending",
     "priority": "low", "project": None, "due_days": 10},
    {"title": "整理 01-研究报告 目录下的旧稿", "identity": "ai-research", "status": "pending",
     "priority": "low", "project": None},
    {"title": "调研本地模型推理成本（LM Studio）", "identity": "ai-research", "status": "completed",
     "priority": "medium", "project": None, "done_days": 3},
    {"title": "把 03-Vobecoding 的脚本归档到统一目录", "identity": "ai-research", "status": "completed",
     "priority": "low", "project": None, "done_days": 8},

    # ---------- 数学建模 ----------
    {"title": "复现动态规划经典题（背包 / LIS / 区间DP）", "identity": "math-modeling",
     "status": "in_progress", "priority": "high", "project": "HelloMathModeling", "due_days": 1,
     "focus": True, "desc": "每题写注释、复杂度分析、易错点",
     "subs": ["01 背包", "最长上升子序列", "区间 DP", "写复杂度对照"]},
    {"title": "2025 赛题解析整理入库", "identity": "math-modeling", "status": "pending",
     "priority": "medium", "project": "HelloMathModeling", "due_days": 4},
    {"title": "论文写作模板定稿（摘要 / 假设 / 建模 / 求解）", "identity": "math-modeling",
     "status": "in_progress", "priority": "high", "project": "HelloMathModeling", "due_days": 3},
    {"title": "赛前冲刺方案：三天时间轴", "identity": "math-modeling", "status": "waiting",
     "priority": "urgent", "project": "数模竞赛作品集", "due_days": 6,
     "desc": "等组队确定后细化分工"},
    {"title": "给旧作品补 README 与依赖锁定", "identity": "math-modeling", "status": "pending",
     "priority": "medium", "project": "数模竞赛作品集", "due_days": 12},
    {"title": "归纳 04_优秀论文与解析 的共性结构", "identity": "math-modeling", "status": "completed",
     "priority": "medium", "project": "HelloMathModeling", "done_days": 5},

    # ---------- 音乐 ----------
    {"title": "第一交响诗：终混检查清单跑一遍", "identity": "musician", "status": "in_progress",
     "priority": "medium", "project": "第一交响诗", "due_days": 2,
     "subs": ["响度与动态", "低频清理", "导出多格式"]},
    {"title": "MuseHub_App 主界面布局", "identity": "musician", "status": "in_progress",
     "priority": "high", "project": "MuseHub 音乐工作台", "due_days": 7, "focus": True},
    {"title": "整理 EveryonePiano 曲谱库并按难度分级", "identity": "musician", "status": "pending",
     "priority": "low", "project": None},
    {"title": "补充 MuseSampler 的力度分层采样", "identity": "musician", "status": "pending",
     "priority": "medium", "project": "MuseHub 音乐工作台", "due_days": 14},
    {"title": "配器笔记：圆号与英国管的音区对照", "identity": "musician", "status": "completed",
     "priority": "low", "project": "第一交响诗", "done_days": 6},
    {"title": "把 AI 编曲提示词模板整理成可复用文件", "identity": "musician", "status": "completed",
     "priority": "medium", "project": "第一交响诗", "done_days": 4},

    # ---------- 交易 ----------
    {"title": "RedBook 本周选品评分卡过一遍", "identity": "trade", "status": "pending",
     "priority": "high", "project": "RedBook 电商", "due_days": 1, "focus": True},
    {"title": "内容转化数据复盘（曝光 → 点击 → 成交）", "identity": "trade", "status": "in_progress",
     "priority": "high", "project": "RedBook 电商", "due_days": 3,
     "subs": ["导出近 4 周数据", "算各环节转化率", "定位流失点"]},
    {"title": "竞品价格带调研", "identity": "trade", "status": "waiting",
     "priority": "medium", "project": "RedBook 电商", "due_days": 9},
    {"title": "电商开发：订单导出脚本", "identity": "trade", "status": "pending",
     "priority": "low", "project": "RedBook 电商", "due_days": 15},
    {"title": "红书笔记选题池扩充到 30 条", "identity": "trade", "status": "completed",
     "priority": "medium", "project": "RedBook 电商", "done_days": 2},

    # ---------- 管理科学 ----------
    {"title": "蒸汽蓬勃：数据源替换方案", "identity": "mgmt-science", "status": "in_progress",
     "priority": "high", "project": "蒸汽蓬勃", "due_days": 4, "focus": True,
     "desc": "公开数据颗粒度不足，评估统计局/行业年报两条替代路线",
     "subs": ["列候选数据源", "核验颗粒度", "确认获取方式"]},
    {"title": "数脉传古：把答辩反馈补进作品说明", "identity": "mgmt-science", "status": "pending",
     "priority": "medium", "project": "数脉传古", "due_days": 8},
    {"title": "数说旅意：补指标权重的敏感性分析", "identity": "mgmt-science", "status": "pending",
     "priority": "medium", "project": "数说旅意", "due_days": 10,
     "desc": "答辩被追问权重依据，补一个敏感性分析堵住这个洞"},
    {"title": "整理数据叙事脚本模板", "identity": "mgmt-science", "status": "completed",
     "priority": "medium", "project": "数脉传古", "done_days": 7},
    {"title": "商科挑战赛复盘归档", "identity": "mgmt-science", "status": "completed",
     "priority": "low", "project": "商科精英挑战赛", "done_days": 12},

    # ---------- 实习实训 ----------
    {"title": "CDUT 数学软件实训：作业汇总提交", "identity": "internship", "status": "in_progress",
     "priority": "high", "project": None, "due_days": 2},
    {"title": "阿里产教中心：AIGC 项目阶段总结", "identity": "internship", "status": "pending",
     "priority": "medium", "project": None, "due_days": 6},
    {"title": "数智工坊：工具包整理成可分发版本", "identity": "internship", "status": "pending",
     "priority": "low", "project": None, "due_days": 18},
    {"title": "实训周记补齐到最新一周", "identity": "internship", "status": "completed",
     "priority": "medium", "project": None, "done_days": 1},

    # ---------- 启明星开发 ----------
    {"title": "mod-dashboard 模块深度优化", "identity": "qmx-dev", "status": "pending",
     "priority": "high", "project": "启明星系统", "due_days": 5, "focus": True,
     "desc": "首页信息密度 + 性能（接口全量拉任务已定位）",
     "subs": ["首页接口分页化", "补齐 5 个未渲染字段", "信息密度调整"]},
    {"title": "给加密列加自动守护（替代人工登记）", "identity": "qmx-dev", "status": "pending",
     "priority": "medium", "project": "启明星系统", "due_days": 9},
    {"title": "写完 8 个模块分支的开发与合并", "identity": "qmx-dev", "status": "in_progress",
     "priority": "high", "project": "启明星系统", "due_days": 21,
     "desc": "platform ✅ / tools ✅，其余 6 个待推进"},
    {"title": "补前端性能测量（设置页首屏 < 800ms）", "identity": "qmx-dev", "status": "waiting",
     "priority": "low", "project": "启明星系统", "due_days": 30},
    {"title": "CompetitorHub 归档说明补完", "identity": "qmx-dev", "status": "completed",
     "priority": "low", "project": "CompetitorHub", "done_days": 9},
    {"title": "数书手札与启明星共用文档模型", "identity": "qmx-dev", "status": "completed",
     "priority": "medium", "project": "数书手札", "done_days": 11},
    {"title": "梳理身份轴在移动端的呈现方式", "identity": "qmx-dev", "status": "in_progress",
     "priority": "medium", "project": "启明星系统", "due_days": 7},

    # ---------- 家教 ----------
    {"title": "高二函数专题讲义（第 3 版）", "identity": "tutoring", "status": "in_progress",
     "priority": "high", "project": None, "due_days": 3,
     "subs": ["单调性与奇偶性", "二次函数最值", "配套练习 20 题"]},
    {"title": "学生错题本整理与归因", "identity": "tutoring", "status": "pending",
     "priority": "medium", "project": None, "due_days": 5},
    {"title": "Python 入门 8 讲大纲", "identity": "tutoring", "status": "pending",
     "priority": "low", "project": None, "due_days": 20},
    {"title": "上次课反馈发给家长", "identity": "tutoring", "status": "completed",
     "priority": "medium", "project": None, "done_days": 1},

    # ---------- 篆刻 ----------
    {"title": "临摹汉印「部曲将印」", "identity": "seal-carving", "status": "in_progress",
     "priority": "low", "project": None, "due_days": 12,
     "subs": ["勾摹印稿", "上石", "初刻", "修整与钤印"]},
    {"title": "刻一方姓名印（朱文）", "identity": "seal-carving", "status": "pending",
     "priority": "low", "project": None, "due_days": 25},
    {"title": "边款刀法练习（单刀 / 双刀）", "identity": "seal-carving", "status": "pending",
     "priority": "low", "project": None},
    {"title": "整理印稿扫描件并编号", "identity": "seal-carving", "status": "completed",
     "priority": "low", "project": None, "done_days": 14},

    # ---------- 小说 ----------
    {"title": "《弱水》世界观设定：规则补完", "identity": "fiction", "status": "in_progress",
     "priority": "medium", "project": None, "due_days": 6,
     "desc": "补「弱水」的代价机制与边界条件",
     "subs": ["代价机制", "地理与势力", "时间线校核"]},
    {"title": "每日写作 500 字", "identity": "fiction", "status": "pending",
     "priority": "medium", "project": None, "due_days": 0, "repeat": True,
     "desc": "重复任务演示：daily/step=1，启动时由真实逻辑生成下一个到期实例"},
    {"title": "第一章初稿（3000 字）", "identity": "fiction", "status": "pending",
     "priority": "medium", "project": None, "due_days": 14},
    {"title": "人物小传：主角与两个对照角色", "identity": "fiction", "status": "pending",
     "priority": "low", "project": None, "due_days": 20},
    {"title": "收集 20 个可用意象与场景", "identity": "fiction", "status": "completed",
     "priority": "low", "project": None, "done_days": 10},

    # ---------- 未归类（演示「可空身份」） ----------
    {"title": "备份移动硬盘并校验完整性", "identity": None, "status": "pending",
     "priority": "medium", "project": None, "due_days": 4},
    {"title": "体检预约", "identity": None, "status": "pending", "priority": "high",
     "project": None, "due_days": 1},
    {"title": "把旧笔记本数据迁移过来", "identity": None, "status": "waiting",
     "priority": "low", "project": None, "due_days": 30},
    {"title": "整理桌面与下载目录", "identity": None, "status": "completed",
     "priority": "low", "project": None, "done_days": 2},
]

# ============================================================
# 5. 文档（含 [[双链]] —— 插入时解析成 backlinks 表）
#    folder / identity / project 均用名字或 slug 引用
# ============================================================
DOCUMENTS: list[dict] = [
    # ---------- AI 研究 ----------
    {"title": "RAG 方案对比：从 Chunk 到重排", "folder": "研究", "identity": "ai-research",
     "tags": ["RAG", "论文", "对比"],
     "summary": "把三篇核心论文的 chunk 策略、检索器、重排器拉成一张对照表，结论是重排的收益最大。",
     "content": """# RAG 方案对比

## 为什么做这个对比
自己在做 [[AIGC 创作流程 SOP]] 时发现，检索质量直接决定生成质量，
但「怎么切块」「用什么检索器」「要不要重排」这三个决定一直是凭感觉。

## 三方对照

| 环节 | 方案 A | 方案 B | 我的判断 |
|---|---|---|---|
| Chunk | 固定 512 字符 | 按语义段落 | B 更好，但需要结构化文档 |
| 检索 | 向量 | 向量 + 关键词混合 | 混合在专有名词上明显更稳 |
| 重排 | 无 | Cross-encoder 重排 | **收益最大的一步** |

## 结论
按投入产出排序：**先加重排 → 再改 chunk → 最后换检索器**。

> 相关：[[Vibe coding 工作流]] 里的代码检索也是同一套逻辑。
"""},

    {"title": "AIGC 创作流程 SOP", "folder": "研究", "identity": "ai-research",
     "tags": ["AIGC", "流程", "SOP"],
     "summary": "需求 → 提示词 → 生成 → 筛选 → 归档五步，核心是「分段生成 + 人工筛选」。",
     "content": """# AIGC 创作流程 SOP

## 五步
1. **需求拆解**：把「我要一首交响诗」拆成情绪 / 编制 / 速度 / 时长
2. **提示词**：见 [[AI 编曲提示词模板]]
3. **分段生成**：单段不超过 30 秒（更长的结构会崩）
4. **筛选**：按评分表打分，只留前 1/3
5. **归档**：原始素材与采用版本分开存放

## 踩过的坑
- 一次性要求生成长篇 → 结构失控
- 提示词只写「史诗感」→ 结果不可控

> 应用实例见 [[第一交响诗创作手记]]。
"""},

    {"title": "AI 编曲提示词模板", "folder": "研究", "identity": "ai-research",
     "tags": ["提示词", "音乐", "模板"],
     "summary": "把情绪、编制、速度、时长四要素写进提示词，风格命中率显著提升。",
     "content": """# AI 编曲提示词模板

```
{情绪形容词} {编制}，{速度/节奏}，{时长}
前 {n} 秒：{乐器} 独奏 {动机描述}
{段落走向}，结尾 {处理}
```

## 实例
> 25秒管弦乐+人声合唱。前7秒：圆号独奏从近乎寂静中进入，奏命运动机，
> 从几乎听不见逐渐增强，温暖坚定。

## 要点
- 「编制」必须具体到乐器，不要只写「管弦乐」
- 时间轴越细，可控性越强
- 词曲创作工具见 [[MuseHub 架构设计]]
"""},

    {"title": "Vibe coding 工作流", "folder": "研究", "identity": "ai-research",
     "tags": ["开发", "AI", "工作流"],
     "summary": "用对话驱动开发：先跑通最小闭环，再让 AI 增量补齐。",
     "content": """# Vibe coding 工作流

## 核心原则
**一次只让它做一件事，且每步都能立刻验证。**

## 流程
1. 说清楚「输入 / 输出 / 约束」
2. 让它给出最小可运行版本
3. 跑一遍，把报错原样贴回去
4. 功能增量式叠加，每加一个就测一次

## 反例
一次性描述 5 个功能 → 得到 300 行不可运行的代码。

> 这套流程沉淀进了 [[启明星系统架构笔记]] 的开发节奏。
"""},

    # ---------- 数学建模 ----------
    {"title": "数模论文写作模板", "folder": "竞赛", "identity": "math-modeling",
     "tags": ["数模", "论文", "模板"],
     "summary": "摘要 / 问题重述 / 假设 / 建模 / 求解 / 检验 / 评价七段式结构。",
     "content": """# 数模论文写作模板

## 七段式
1. **摘要**（最重要，评委只认真读这一页）
2. 问题重述（不要抄题，用自己的话压缩）
3. 模型假设（每条都要能自辩）
4. 符号说明（表格化）
5. 模型建立与求解
6. 结果检验与灵敏度分析
7. 模型评价与推广

## 摘要的三句式
- 问题是什么（一句）
- 用了什么方法（一句）
- 结论是什么（一句，**必须给数字**）

> 模板目录见 [[HelloMathModeling 归档说明]]
"""},

    {"title": "动态规划复现笔记", "folder": "竞赛", "identity": "math-modeling",
     "tags": ["算法", "DP", "笔记"],
     "summary": "背包、LIS、区间 DP 三类经典题的实现与易错点。",
     "content": """# 动态规划复现笔记

## 三类模板
### 01 背包
状态 `dp[i][w]`，倒序枚举容量。
**易错**：完全背包是正序，01 背包是倒序 —— 混了就是无限取。

### 最长上升子序列（LIS）
O(n²) 直观；O(n log n) 用 `bisect_left` 维护递增数组。
**易错**：严格递增用 `bisect_left`，非严格用 `bisect_right`。

### 区间 DP
枚举长度 → 起点 → 分割点，三层循环顺序不能乱。

## 共同套路
**先写暴力递归 → 加记忆化 → 改写成递推。**
"""},

    {"title": "2025 赛题解析索引", "folder": "竞赛", "identity": "math-modeling",
     "tags": ["数模", "赛题"],
     "summary": "按题号整理 2025 年赛题的解题思路与可复用模型。",
     "content": """# 2025 赛题解析索引

| 题号 | 主题 | 可复用模型 |
|---|---|---|
| A | 优化调度 | 混合整数规划 |
| B | 评价类 | 熵权 + TOPSIS |
| C | 预测类 | 灰色预测 + 回归对照 |

## 复用要点
评价类题目的通用链路：**指标筛选 → 权重（客观+主观）→ 排序 → 灵敏度**。
这条链路在 [[数说旅意作品说明]] 里也用过。
"""},

    {"title": "HelloMathModeling 归档说明", "folder": "竞赛", "identity": "math-modeling",
     "tags": ["归档", "规范"],
     "summary": "00-99 编号体系：研究 / 作品 / 培训 / 题库 / 论文 / 模拟 / 临时 / 归档。",
     "content": """# HelloMathModeling 归档说明

## 编号体系
```
00_我的数模研究      01_我的竞赛作品
02_暑期培训课程      03_历年赛题库
04_优秀论文与解析    05_模拟赛题目
90_重复与临时文件    99_原始压缩包归档
```

## 为什么编号
文件多了以后，**排序即分类**。前缀数字让目录结构自解释，
不用每次回忆「这个该放哪」。

> 这条规范后来被 [[启明星系统架构笔记]] 的档案库设计吸收。
"""},

    # ---------- 音乐 ----------
    {"title": "第一交响诗创作手记", "folder": "创作", "identity": "musician",
     "project": "第一交响诗", "tags": ["音乐", "创作", "复盘"],
     "summary": "32 段素材 → 11 段采用；分段生成 + 人工筛选是唯一可行路线。",
     "content": """# 第一交响诗创作手记

## 起点
想写一部有「命运动机」的单乐章作品，但不会配器。

## 过程
1. 定主题动机（圆号，从近乎寂静进入）
2. 用 [[AI 编曲提示词模板]] 分段生成 32 段素材
3. 按评分表筛选，留下 11 段
4. 拼接 + 终混

## 关键认识
**AI 不会替你作曲，但能替你试奏。**
意图还是得自己给 —— 提示词写不清楚，出来的东西就一定是通用的。

## 产出
时长 4'20"，管弦乐 + 人声合唱。素材与采用版本已分开归档。
"""},

    {"title": "MuseHub 架构设计", "folder": "创作", "identity": "musician",
     "project": "MuseHub 音乐工作台", "tags": ["架构", "工具", "VST3"],
     "summary": "拆成采样器 / 效果器 / 曲库三件独立工具，而不是一个全能 App。",
     "content": """# MuseHub 架构设计

## 为什么拆
最初想做「全能音乐 App」，范围太大推不动。
拆成三件后每件都能独立交付：

| 模块 | 职责 | 状态 |
|---|---|---|
| MuseSampler | 采样播放内核 | ✅ |
| MuseFX_VST3 | 效果器插件（DAW 内可用） | ✅ |
| MuseHub_App | 主界面 / 工程管理 | 进行中 |
| MuseHub_Content | 曲库内容管理 | 待开始 |

## 技术选择
走 VST3 路线，成果能直接在 DAW 里用 —— 复用价值远高于自建封闭格式。
"""},

    {"title": "配器笔记：音区与色彩", "folder": "创作", "identity": "musician",
     "tags": ["配器", "笔记"],
     "summary": "圆号、英国管、弦乐各音区的表现力对照。",
     "content": """# 配器笔记

## 圆号
中音区最稳，适合「命运动机」这类需要厚度又不刺耳的素材。

## 英国管
鼻音特质，独奏时有孤独感；适合在段落开头引入主题。

## 弦乐
- 低音区：暗、厚
- 中音区：最常用
- 高音区：紧张感

> 实际应用见 [[第一交响诗创作手记]]。
"""},

    # ---------- 交易 ----------
    {"title": "选品评分卡", "folder": "研究", "identity": "trade",
     "project": "RedBook 电商", "tags": ["选品", "方法论"],
     "summary": "需求强度 / 竞争度 / 毛利 / 内容友好度四维打分，低于阈值直接放弃。",
     "content": """# 选品评分卡

| 维度 | 权重 | 打分要点 |
|---|---|---|
| 需求强度 | 30% | 搜索量、评论增速 |
| 竞争度 | 25% | 头部集中度 |
| 毛利空间 | 25% | 扣掉物流与平台费 |
| 内容友好度 | 20% | 能不能拍出差异化 |

## 使用原则
**总分低于 60 直接放弃，不给自己「再想想」的机会。**
这条规则的目的是对抗沉没成本。

> 复盘方法见 [[RedBook 数据复盘方法]]
"""},

    {"title": "RedBook 数据复盘方法", "folder": "研究", "identity": "trade",
     "project": "RedBook 电商", "tags": ["复盘", "数据"],
     "summary": "曝光 → 点击 → 成交三段漏斗，逐段定位流失点。",
     "content": """# RedBook 数据复盘方法

## 漏斗
```
曝光 → 点击（内容质量）→ 成交（选品 + 详情页）
```

## 定位规则
- 点击率低 → **内容问题**，改封面与标题
- 点击高但转化低 → **选品或价格问题**
- 都不错但量小 → 流量问题，扩大投放

## 教训
前期只看曝光不看转化，白做了一批内容。
**数据不看漏斗，等于没看。**

> 选品环节见 [[选品评分卡]]
"""},

    # ---------- 管理科学 ----------
    {"title": "数脉传古作品说明", "folder": "竞赛", "identity": "mgmt-science",
     "project": "数脉传古", "tags": ["数据叙事", "作品"],
     "summary": "先写解说词骨架、再让数据填进去；12 张图砍到 5 张才讲得清。",
     "content": """# 数脉传古 作品说明

## 结构
5 个章节，每章一个核心结论。

## 最重要的一条经验
**先有故事线，再找数据。**
反过来做，必然变成图表堆砌 —— 初版堆了 12 张图，评委反馈「记不住结论」。

## 可视化原则
- 一张图只讲一件事
- 颜色不超过 3 个语义色
- 结论写在图上，不要让人自己推

> 方法论沉淀为 [[数据叙事方法论]]
"""},

    {"title": "数据叙事方法论", "folder": "研究", "identity": "mgmt-science",
     "tags": ["方法论", "可视化", "数据"],
     "summary": "故事线优先、一图一事、结论前置、权重需可解释。",
     "content": """# 数据叙事方法论

## 四条原则
1. **故事线优先**：先写解说词骨架
2. **一图一事**：图多不等于信息多
3. **结论前置**：把结论画在图上
4. **权重可解释**：主观权重必须做敏感性分析

## 第 4 条的由来
[[数说旅意作品说明]] 答辩时被追问指标权重依据，
答得不硬 —— 之后所有作品都补敏感性分析。
"""},

    {"title": "数说旅意作品说明", "folder": "竞赛", "identity": "mgmt-science",
     "project": "数说旅意", "tags": ["数据叙事", "作品"],
     "summary": "把主观旅行体验拆成 6 个可量化维度，雷达图表达。",
     "content": """# 数说旅意 作品说明

## 亮点
把「一趟旅行好不好」拆成 6 个可量化维度：体验 / 成本 / 时间 /
交通 / 住宿 / 意外。

## 被认可的点
维度拆分让主观感受变得可比较。

## 待补
指标权重是拍脑袋定的，需要补 [[数据叙事方法论]] 里说的敏感性分析。
"""},

    # ---------- 实习实训 ----------
    {"title": "CDUT 数学软件实训周记", "folder": "复盘与规划", "identity": "internship",
     "tags": ["实训", "周记"],
     "summary": "校内实训：MATLAB / Python 数值计算与作业汇总。",
     "content": """# CDUT 数学软件实训周记

## 第 1 周
环境搭建、数值计算基础；作业：矩阵运算与求解。

## 第 2 周
微分方程数值解；重点是把「公式 → 可运行代码」的翻译练熟。

## 收获
数学软件的价值不在算得快，而在**能把模型跑起来看结果**。
这与 [[数模论文写作模板]] 的「模型建立与求解」环节直接对应。
"""},

    {"title": "阿里产教中心 AIGC 阶段总结", "folder": "复盘与规划", "identity": "internship",
     "tags": ["AIGC", "实习", "总结"],
     "summary": "校外实训：把 AIGC 能力落进真实业务流程。",
     "content": """# AIGC 阶段总结

## 做了什么
围绕内容生产链路做 AIGC 提效，从素材生成到批量处理。

## 关键技术认识
- 提示词工程是「接口设计」，不是玄学
- 流程化 > 单点技巧；单点技巧不可复制

## 迁移
这套流程直接复用到了 [[AIGC 创作流程 SOP]]。
"""},

    # ---------- 启明星开发 ----------
    {"title": "启明星系统架构笔记", "folder": "工程", "identity": "qmx-dev",
     "project": "启明星系统", "tags": ["架构", "启明星"],
     "summary": "四层分层、设计令牌唯一来源、验收标准转可执行断言。",
     "content": """# 启明星系统架构笔记

## 四层分层（不可跨层）
```
api → services → repositories → models
```
有架构守护测试兜底 —— 跨层当场变红。

## 三条硬约束
1. **设计令牌唯一来源**：组件文件里不能出现 `#` 颜色字面量
2. **迁移必须幂等**：新迁移一律带 `table_exists` 守卫
3. **验收标准写成断言**：文档里的复选框不算完成，跑绿才算

## 为什么第三条最重要
「我觉得做完了」和「它确实做完了」之间的差距，
就是项目能不能持续迭代的分水岭。

> 身份轴设计的来龙去脉见 [[身份轴设计思考]]
"""},

    {"title": "身份轴设计思考", "folder": "工程", "identity": "qmx-dev",
     "project": "启明星系统", "tags": ["身份轴", "设计", "启明星"],
     "summary": "身份不做成顶层导航，而做成横切维度 —— 否则一个任务要记两遍。",
     "content": """# 身份轴设计思考

## 问题
系统原本只有一个分类轴（任务/文档/复盘各自成列），
而实际是**多线的**：AI 研究、数学建模、音乐、交易……十来条线并行。

结果就是「乱」—— 不是没在推进，是**看不出自己在推进哪条线**。

## 关键决策
身份**不做成新的顶层导航项**，而做成**横切维度**：
- 任务 / 项目 / 文档 / 资料都挂 `identity_id`
- 顶栏一个全局身份筛选器，选中后所有列表自动过滤
- Dashboard 从「统计卡片堆」变成「按身份分组的进度阵列」

## 为什么不另起一个「身份页」
另起一页等于把同一个任务在两个地方记两遍 —— 那是最糟的设计。

> 这条思路的源头在 [[启明星系统架构笔记]] 的分层约束。
"""},

    {"title": "git 灾难复盘：并发操作的代价", "folder": "复盘与规划", "identity": "qmx-dev",
     "project": "启明星系统", "tags": ["git", "复盘", "教训"],
     "summary": "两个智能体并发操作同一仓库 → .git 被回滚、历史丢失、只能重建仓库。",
     "content": """# git 灾难复盘

## 发生了什么
两个工具同时操作同一个仓库，其中一个执行了带强制的切分支，
`.git` 被同步客户端回滚，历史不可恢复。

## 处置
以当前工作树重建仓库，打恢复点 tag，两端对齐。

## 三条教训（已写进项目铁律）
1. 同一时刻**只允许一个**智能体操作一个仓库
2. 大功能**先推再继续**，别攒着
3. 分支不过夜；同步客户端必须排除 `.git`

> 更隐蔽的一条：重建时容易漏掉「被回滚的已跟踪文件」——
> 新建文件幸存，但修改过的文件会静默回退。必须逐项重放并复验。
"""},

    # ---------- 家教 ----------
    {"title": "高二函数专题讲义", "folder": "教学", "identity": "tutoring",
     "tags": ["讲义", "函数", "教学"],
     "summary": "单调性 / 奇偶性 / 二次函数最值三讲，配 20 道分层练习。",
     "content": """# 高二函数专题讲义

## 第一讲 单调性与奇偶性
定义 → 图像直觉 → 判断三步法。

## 第二讲 二次函数最值
含参问题是重灾区，**先定对称轴与区间的位置关系**再讨论。

## 第三讲 综合应用
配 20 题，分基础 / 中档 / 拔高三层。

## 教学心得
学生的问题大多不是「不会算」，而是**没有先画图的习惯**。
讲义里每道题都要求先画草图。
"""},

    {"title": "错题归因方法", "folder": "教学", "identity": "tutoring",
     "tags": ["教学", "错题", "方法论"],
     "summary": "错题分四类归因：概念不清 / 计算失误 / 审题偏差 / 思路缺失。",
     "content": """# 错题归因方法

## 四类归因
| 类型 | 表现 | 对策 |
|---|---|---|
| 概念不清 | 同样知识点反复错 | 回到定义重讲 |
| 计算失误 | 思路对但算错 | 限时训练 |
| 审题偏差 | 看漏条件 | 圈关键词 |
| 思路缺失 | 完全没方向 | 教套路 + 变式 |

**只统计不归因，错题本等于抄题本。**
"""},

    # ---------- 篆刻 ----------
    {"title": "汉印临摹笔记", "folder": "手作", "identity": "seal-carving",
     "tags": ["篆刻", "临摹"],
     "summary": "勾摹 → 上石 → 初刻 → 修整四步，平正为先。",
     "content": """# 汉印临摹笔记

## 四步
1. **勾摹**：透明纸覆在印稿上描线，先求准确
2. **上石**：反写上石（水印法 / 直接反写）
3. **初刻**：冲刀走直线，留有余地
4. **修整**：补刀求「平正」

## 心得
汉印的难处不在刻，在**章法的匀**。
一个字占多少位置，要在动刀前就定好。

## 刀法
- 冲刀：爽利，适合长直线
- 切刀：便于控制，适合转折
"""},

    # ---------- 小说 ----------
    {"title": "《弱水》世界观设定", "folder": "创作", "identity": "fiction",
     "tags": ["小说", "设定"],
     "summary": "核心是「弱水」的代价机制 —— 任何力量都要付出对应代价。",
     "content": """# 《弱水》世界观设定

## 核心规则
「弱水」不是水，是一种**代价机制**：
凡是借来的力量，都要以某种对等的东西偿还。

## 待补
- 代价的具体形式（记忆？时间？关系？）
- 边界条件：有没有例外？谁能绕开？
- 与地理 / 势力的耦合

## 写作原则
**规则先立住，情节才可信。**
先补完设定再写第一章。
"""},
]

# ============================================================
# 6. 技能与成长
# ============================================================
SKILLS: list[dict] = [
    {"name": "提示词工程", "category": "AI", "proficiency": 80, "use_count": 46,
     "methodology": "把提示词当接口设计：输入/输出/约束三段式，先小样本验证再批量",
     "tags": ["AI", "方法论"],
     "description": "让模型产出可控、可复现的结果"},
    {"name": "数据叙事", "category": "数据", "proficiency": 75, "use_count": 12,
     "methodology": "故事线优先 → 一图一事 → 结论前置 → 权重可解释",
     "tags": ["可视化", "叙事"],
     "description": "把数据讲成能被记住的故事"},
    {"name": "数学建模", "category": "数学", "proficiency": 78, "use_count": 24,
     "methodology": "问题重述 → 假设显式化 → 模型 → 求解 → 灵敏度检验",
     "tags": ["建模", "竞赛"],
     "description": "把现实问题转成可计算的形式"},
    {"name": "Python 工程", "category": "开发", "proficiency": 82, "use_count": 60,
     "methodology": "四层分层 + 小步提交 + 验收标准写成可执行断言",
     "tags": ["Python", "工程"],
     "description": "写能长期维护的代码，而不只是能跑的代码"},
    {"name": "Vue 前端", "category": "开发", "proficiency": 70, "use_count": 30,
     "methodology": "设计令牌唯一来源；组件自研；移动端优先考虑 375px",
     "tags": ["Vue", "前端"],
     "description": "自研组件体系，不依赖 UI 框架"},
    {"name": "音频工程", "category": "音乐", "proficiency": 62, "use_count": 18,
     "methodology": "分段生成 → 评分筛选 → 拼接终混",
     "tags": ["音乐", "混音"],
     "description": "从素材到成品的完整链路"},
    {"name": "配器", "category": "音乐", "proficiency": 55, "use_count": 9,
     "methodology": "先定动机 → 再选音区 → 最后叠色彩",
     "tags": ["音乐", "管弦"],
     "description": "为动机选择合适的乐器与音区"},
    {"name": "文献阅读", "category": "研究", "proficiency": 72, "use_count": 38,
     "methodology": "三遍法：摘要与结论 → 图表 → 方法细节；读完全部落成对照表",
     "tags": ["研究", "论文"],
     "description": "快速判断一篇论文值不值得精读"},
    {"name": "git 与版本管理", "category": "开发", "proficiency": 74, "use_count": 55,
     "methodology": "分支不过夜；大功能先推再继续；危险操作前先确认工作树干净",
     "tags": ["git", "工程"],
     "description": "吃过一次仓库被回滚的教训后系统性补上的能力"},
    {"name": "数据清洗", "category": "数据", "proficiency": 76, "use_count": 20,
     "methodology": "先摸清缺失与异常分布，再决定插补或剔除；每一步都记录",
     "tags": ["数据", "清洗"],
     "description": "脏数据的处理决定了后续分析的上限"},
    {"name": "商业分析", "category": "商科", "proficiency": 65, "use_count": 8,
     "methodology": "从财务三表出发，用数据支撑结论而不是凭经验",
     "tags": ["商科", "分析"],
     "description": "结构与逻辑优先于花哨的结论"},
    {"name": "书法篆刻", "category": "手作", "proficiency": 58, "use_count": 14,
     "methodology": "先求平正，再求变化；动刀前先定章法",
     "tags": ["篆刻", "手作"],
     "description": "慢工，练的是耐心与匀称"},
    {"name": "教学设计", "category": "教学", "proficiency": 68, "use_count": 22,
     "methodology": "先诊断（错题归因）→ 再补漏 → 最后练变式",
     "tags": ["教学"],
     "description": "把知识点拆到学生能自己走一遍"},
    {"name": "写作", "category": "创作", "proficiency": 66, "use_count": 26,
     "methodology": "设定先立住；大纲 → 场景 → 文字三段推进",
     "tags": ["写作", "小说"],
     "description": "把脑内设定转成可读的叙事"},
]

# 成长事件（演示成长体系；source_key 保证幂等——同一条事件不会重复加分）
GROWTH_EVENTS: list[dict] = [
    {"type": "task_completed", "exp": 12, "label": "完成动态规划复现", "days_ago": 0,
     "key": "demo-task-dp", "skills": ["数学建模", "Python 工程"]},
    {"type": "task_completed", "exp": 8, "label": "整理桌面与下载目录", "days_ago": 2,
     "key": "demo-task-clean", "skills": []},
    {"type": "review_created", "exp": 10, "label": "写完第 12 周复盘", "days_ago": 1,
     "key": "demo-review-w12", "skills": []},
    {"type": "document_created", "exp": 6, "label": "输出《RAG 方案对比》", "days_ago": 1,
     "key": "demo-doc-rag", "skills": ["文献阅读", "提示词工程"]},
    {"type": "document_created", "exp": 6, "label": "输出《身份轴设计思考》", "days_ago": 3,
     "key": "demo-doc-identity", "skills": ["Python 工程"]},
    {"type": "habit_streak", "exp": 20, "label": "英语精读连续 21 天", "days_ago": 4,
     "key": "demo-habit-eng21", "skills": ["文献阅读"]},
    {"type": "habit_streak", "exp": 15, "label": "练琴连续 14 天", "days_ago": 6,
     "key": "demo-habit-piano14", "skills": ["配器", "音频工程"]},
    {"type": "plan_completed", "exp": 40, "label": "完成「动态规划」14 天学习计划", "days_ago": 5,
     "key": "demo-plan-dp", "skills": ["数学建模"]},
    {"type": "project_completed", "exp": 80, "label": "第一交响诗完成", "days_ago": 9,
     "key": "demo-proj-symphony", "skills": ["音频工程", "配器", "提示词工程"]},
    {"type": "project_completed", "exp": 70, "label": "数脉传古完成并答辩", "days_ago": 20,
     "key": "demo-proj-shumai", "skills": ["数据叙事", "数据清洗"]},
    {"type": "task_completed", "exp": 10, "label": "RedBook 选题池扩到 30 条", "days_ago": 2,
     "key": "demo-task-redbook", "skills": ["商业分析"]},
    {"type": "task_completed", "exp": 10, "label": "实训周记补齐", "days_ago": 1,
     "key": "demo-task-weekly", "skills": []},
    {"type": "task_completed", "exp": 8, "label": "临摹印稿编号归档", "days_ago": 14,
     "key": "demo-task-seal", "skills": ["书法篆刻"]},
    {"type": "task_completed", "exp": 8, "label": "收集 20 个意象", "days_ago": 10,
     "key": "demo-task-fiction", "skills": ["写作"]},
    {"type": "task_completed", "exp": 12, "label": "配器笔记完成", "days_ago": 6,
     "key": "demo-task-orch", "skills": ["配器"]},
]

# ============================================================
# 7. SOP / 工作流 / 模板 / 提示词模板
# ============================================================
SOPS: list[dict] = [
    {"name": "数模论文写作 SOP", "category": "竞赛", "tags": ["数模", "写作"],
     "description": "从拿到题目到提交论文的完整流程",
     "steps": [
         "读题 30 分钟，写下初步理解与可能的模型方向",
         "查资料 1 小时，确认数据可得性",
         "定模型与分工，写摘要初稿（先写摘要！）",
         "建模与求解，结果先跑通再优化",
         "灵敏度分析，验证结论稳健性",
         "按七段式成稿，摘要最后再改一遍",
     ],
     "checklist": ["摘要含具体数字", "每条假设可自辩", "有灵敏度分析", "图表自解释"]},
    {"name": "AIGC 生成 SOP", "category": "AI", "tags": ["AIGC", "提示词"],
     "description": "任何 AIGC 产出的通用五步法",
     "steps": [
         "把需求拆成 情绪/风格/结构/时长 四要素",
         "写提示词：具体到乐器或技术细节",
         "分段生成，单段不超过 30 秒或等价长度",
         "按评分表筛选，只保留前 1/3",
         "原始与采用版本分开归档",
     ],
     "checklist": ["提示词含具体细节", "分段而非一次成篇", "有筛选记录"]},
    {"name": "周复盘 SOP", "category": "复盘", "tags": ["复盘", "习惯"],
     "description": "每周日晚上 30 分钟的固定动作",
     "steps": [
         "过一遍本周完成的任务，按身份分类",
         "写「收获」而不是「流水账」",
         "找出一个真正卡住的地方，写下原因",
         "给下周定 3 件最重要的事，不超过 3 件",
     ],
     "checklist": ["按身份分类", "至少一条具体反思", "下周重点 ≤ 3 条"]},
    {"name": "启明星发版 SOP", "category": "工程", "tags": ["工程", "发布"],
     "description": "改代码到推送的安全流程（吃过 git 灾难后固化）",
     "steps": [
         "确认工作树干净（git status 逐项看）",
         "小步提交，提交信息写清「为什么」",
         "跑全量校验（架构/冒烟/版本/引用/类型/队列/连通性）",
         "推远端，确认远端 SHA 与本地一致",
         "大功能完成即推，不攒着",
     ],
     "checklist": ["工作树干净", "七项校验全绿", "远端 SHA 已核对"]},
    {"name": "家教备课 SOP", "category": "教学", "tags": ["教学"],
     "description": "课前诊断 → 课中讲练 → 课后反馈",
     "steps": [
         "看上一节错题归因结果，定本节重点",
         "讲义先给「判断三步法」，再上题",
         "课上让学生先画图再动笔",
         "课后给家长一句具体反馈（不写空话）",
     ],
     "checklist": ["有错题归因", "每道题先画图", "反馈具体到知识点"]},
    {"name": "选品复盘 SOP", "category": "交易", "tags": ["交易", "复盘"],
     "description": "曝光到成交的三段漏斗逐段定位",
     "steps": [
         "导出近 4 周数据",
         "算点击率与转化率",
         "定位流失最严重的一段",
         "只针对这一段做改进，一次改一个变量",
     ],
     "checklist": ["三段数据齐全", "只改一个变量", "记录改动前后对比"]},
]

WORKFLOWS: list[dict] = [
    {"name": "周复盘生成器", "category": "复盘", "icon": "refresh", "is_preset": True,
     "scenario": "一键汇总本周任务与习惯数据，生成复盘草稿",
     "description": "省掉手动翻记录的时间，把精力留给「想」",
     "config": {"inputs": ["week_offset"], "steps": ["汇总任务", "汇总习惯", "汇总专注时长", "生成草稿"]}},
    {"name": "数模论文骨架", "category": "竞赛", "icon": "doc", "is_preset": True,
     "scenario": "按七段式生成论文骨架与符号说明表",
     "description": "避免每次都从空白文档开始",
     "config": {"inputs": ["problem_title", "model_type"], "steps": ["生成七段标题", "生成符号表", "生成摘要三句式占位"]}},
    {"name": "AIGC 素材筛选", "category": "AI", "icon": "spark", "is_preset": False,
     "scenario": "对一批生成素材按评分表打分并排序",
     "description": "把「挑素材」这件重复劳动固化下来",
     "config": {"inputs": ["asset_dir", "criteria"], "steps": ["读取素材清单", "按维度打分", "排序输出"]}},
    {"name": "身份周报", "category": "复盘", "icon": "chart", "is_preset": False,
     "scenario": "按身份分组统计本周推进情况，看哪条线被冷落",
     "description": "身份轴的核心价值就是「一眼看出哪条线停摆了」",
     "config": {"inputs": ["week_offset"], "steps": ["按身份聚合任务", "算各身份完成率", "标记零推进身份"]}},
    {"name": "错题归因汇总", "category": "教学", "icon": "book", "is_preset": False,
     "scenario": "把学生错题按四类归因统计，定位最该补的点",
     "description": "只统计不归因，错题本等于抄题本",
     "config": {"inputs": ["student_id", "range"], "steps": ["读取错题", "四类归因", "输出占比"]}},
    {"name": "档案库归类", "category": "工程", "icon": "folder", "is_preset": True,
     "scenario": "扫描工作区，把文件按身份自动归类并生成待确认清单",
     "description": "让 81% 躺在磁盘上的成果能被找回来",
     "config": {"inputs": ["root_id"], "steps": ["扫描根目录", "关键词归类", "输出待确认清单"]}},
]

TEMPLATES: list[dict] = [
    {"name": "数模论文骨架", "category": "文档", "tags": ["数模"],
     "description": "七段式论文结构", "is_builtin": False,
     "content": "# {题目}\n\n## 摘要\n（问题 / 方法 / 结论含数字）\n\n## 一、问题重述\n## 二、模型假设\n## 三、符号说明\n## 四、模型建立与求解\n## 五、结果检验与灵敏度分析\n## 六、模型评价与推广\n",
     "variables": ["题目"]},
    {"name": "周复盘模板", "category": "复盘", "tags": ["复盘"],
     "description": "按身份分组的周复盘", "is_builtin": False,
     "content": "# 第 {周数} 周复盘\n\n## 按身份看推进\n- AI 研究：\n- 数学建模：\n- 音乐：\n\n## 本周收获\n## 真正卡住的地方\n## 下周只做三件事\n1.\n2.\n3.\n",
     "variables": ["周数"]},
    {"name": "作品 README", "category": "工程", "tags": ["工程", "可复现"],
     "description": "让作品半年后还能跑起来", "is_builtin": False,
     "content": "# {作品名}\n\n## 这是什么\n## 怎么运行\n```bash\npip install -r requirements.txt\n```\n## 数据从哪来\n## 关键结论\n",
     "variables": ["作品名"]},
    {"name": "讲义骨架", "category": "教学", "tags": ["教学"],
     "description": "诊断 → 讲练 → 变式", "is_builtin": False,
     "content": "# {专题}讲义\n\n## 一、知识回顾\n## 二、方法三步法\n## 三、例题（先画图）\n## 四、分层练习\n### 基础 / 中档 / 拔高\n## 五、易错点\n",
     "variables": ["专题"]},
    {"name": "项目启动卡", "category": "项目", "tags": ["项目管理"],
     "description": "新项目启动时先答这五问", "is_builtin": False,
     "content": "# {项目名}\n\n## 一句话定位\n## 属于哪重身份\n## 可交付物是什么\n## 完成的标准（可验证）\n## 第一个里程碑\n",
     "variables": ["项目名"]},
    {"name": "决策记录", "category": "文档", "tags": ["决策"],
     "description": "把「为什么这么定」留下来", "is_builtin": False,
     "content": "# 决策：{决策点}\n\n## 背景\n## 可选方案\n| 方案 | 优点 | 缺点 |\n|---|---|---|\n## 决定\n## 理由\n## 什么情况下要重新考虑\n",
     "variables": ["决策点"]},
]

PROMPT_TEMPLATES: list[dict] = [
    {"name": "论文精读", "category": "研究", "use_count": 28, "rating": 5,
     "description": "三遍法精读，输出结构化对照",
     "role_setting": "你是一位严谨的科研助手，擅长把论文压缩成可复用的结论。",
     "task_description": "对给定论文，按「问题 / 方法 / 实验 / 结论 / 局限」五段输出摘要，并指出可迁移到我工作的点。",
     "constraints": "不要复述背景；每个论断标注论文中的依据位置；拿不准的地方明确写「不确定」。",
     "output_format": "Markdown 表格 + 一段「可迁移点」",
     "variables": ["论文内容"]},
    {"name": "AI 编曲提示词", "category": "音乐", "use_count": 42, "rating": 5,
     "description": "把作曲意图翻译成可控的生成提示词",
     "role_setting": "你是管弦乐配器顾问。",
     "task_description": "把用户的情绪与场景描述，转写成包含「编制 / 速度 / 时间轴 / 乐器动机」的音乐生成提示词。",
     "constraints": "必须具体到乐器名；时间轴精确到秒；单段不超过 30 秒。",
     "output_format": "一段可直接使用的提示词 + 3 个可替换的乐器备选",
     "variables": ["情绪", "场景", "时长"]},
    {"name": "数模摘要打磨", "category": "竞赛", "use_count": 16, "rating": 5,
     "description": "把摘要改到「三句式 + 数字结论」",
     "role_setting": "你是数模竞赛评委。",
     "task_description": "重写给定摘要，使其符合「问题一句 / 方法一句 / 结论一句（含数字）」结构。",
     "constraints": "不超过 400 字；保留原始方法的准确名称；结论必须有数字。",
     "output_format": "重写后的摘要 + 修改理由 3 条",
     "variables": ["原摘要"]},
    {"name": "代码审查", "category": "工程", "use_count": 34, "rating": 4,
     "description": "按项目硬约束审查改动",
     "role_setting": "你是一位严格的高级工程师，熟悉四层分层架构。",
     "task_description": "审查给定 diff，重点找：跨层调用、硬编码颜色、缺失的迁移守卫、无效/永真断言、静默失败。",
     "constraints": "只报真问题，不要风格偏好；每条给出文件与行号；按严重度排序。",
     "output_format": "表格：严重度 / 位置 / 问题 / 建议",
     "variables": ["diff"]},
    {"name": "数据叙事脚本", "category": "数据", "use_count": 11, "rating": 5,
     "description": "先出故事线骨架，再填数据",
     "role_setting": "你是数据叙事设计者。",
     "task_description": "根据主题与已有数据，先写解说词骨架（每章一个核心结论），再标注每章需要什么数据。",
     "constraints": "先故事线后数据；一章一结论；图表总数不超过 6 张。",
     "output_format": "章节列表 + 每章所需数据清单",
     "variables": ["主题", "已有数据"]},
    {"name": "错题归因", "category": "教学", "use_count": 19, "rating": 4,
     "description": "把错题按四类归因并给出对策",
     "role_setting": "你是一位经验丰富的中学数学教师。",
     "task_description": "对给定错题列表，按「概念不清 / 计算失误 / 审题偏差 / 思路缺失」四类归因。",
     "constraints": "每题只归一类（选最主要的原因）；对策要具体到动作。",
     "output_format": "表格 + 占比小结",
     "variables": ["错题列表"]},
    {"name": "世界观设定校验", "category": "创作", "use_count": 7, "rating": 4,
     "description": "检查设定的自洽性与边界",
     "role_setting": "你是世界观设定编辑。",
     "task_description": "检查给定设定的自洽性：规则是否自相矛盾、边界条件是否清楚、有无可被读者一眼挑出的漏洞。",
     "constraints": "只提可验证的问题；区分「逻辑漏洞」与「尚未展开」。",
     "output_format": "问题清单 + 每个问题的可选补法",
     "variables": ["设定文本"]},
    {"name": "选品评估", "category": "交易", "use_count": 23, "rating": 4,
     "description": "按四维评分卡评估选品",
     "role_setting": "你是内容电商选品顾问。",
     "task_description": "对给定品类，按「需求强度 / 竞争度 / 毛利空间 / 内容友好度」四维打分并给结论。",
     "constraints": "低于 60 分直接建议放弃，不要给「再想想」；每维必须给理由。",
     "output_format": "评分表 + 一句结论",
     "variables": ["品类", "背景信息"]},
]

# ============================================================
# 8. 学习（计划 + 学习时长 + 知识卡片）
# ============================================================
STUDY_PLANS: list[dict] = [
    {"name": "动态规划 14 天强化", "status": "completed", "progress": 100,
     "description": "覆盖 01 背包 / 完全背包 / LIS / 区间 DP / 树形 DP",
     "estimated_hours": 20, "target_days_from_now": -5,
     "config": {"domain_key": "programming", "total_days": 14, "minutes_per_day": 90, "weekly_mode": "daily"}},
    {"name": "大模型应用 21 天", "status": "active", "progress": 45,
     "description": "RAG / Agent / 评估方法；每 3 天一个小实验",
     "estimated_hours": 32, "target_days_from_now": 12,
     "config": {"domain_key": "programming", "total_days": 21, "minutes_per_day": 100, "weekly_mode": "daily"}},
    {"name": "管弦乐配器入门 30 天", "status": "active", "progress": 60,
     "description": "按乐器族推进，每天一段配器练习",
     "estimated_hours": 40, "target_days_from_now": 10,
     "config": {"domain_key": "guitar", "total_days": 30, "minutes_per_day": 80, "weekly_mode": "daily"}},
    {"name": "数据可视化进阶", "status": "paused", "progress": 20,
     "description": "叙事可视化与图表设计；暂停（被蒸汽蓬勃的数据问题阻塞）",
     "estimated_hours": 16, "target_days_from_now": 25,
     "config": {"domain_key": "design", "total_days": 18, "minutes_per_day": 60, "weekly_mode": "weekday"}},
    {"name": "英语文献精读 30 天", "status": "active", "progress": 70,
     "description": "每天一篇摘要精读 + 生词归档",
     "estimated_hours": 15, "target_days_from_now": 8,
     "config": {"domain_key": "eng-exam", "total_days": 30, "minutes_per_day": 30, "weekly_mode": "daily"}},
]

# 知识卡片（SM-2 字段：ef / interval / repetition / next_review）
FLASHCARDS: list[dict] = [
    # —— 数学建模 ——
    {"front": "01 背包为什么容量要倒序枚举？", "back": "保证每件物品只用一次。正序会让同一件物品被重复放入（变成完全背包）。",
     "category": "算法", "difficulty": 2, "ef": 2.6, "interval": 6, "repetition": 3, "due_in_days": 0},
    {"front": "LIS 的 O(n log n) 解法维护的是什么？", "back": "一个「长度为 i 的上升子序列的最小结尾值」数组，用 bisect 维护其单调性。",
     "category": "算法", "difficulty": 3, "ef": 2.4, "interval": 3, "repetition": 2, "due_in_days": 1},
    {"front": "熵权法的核心思想", "back": "指标离散程度越大，信息量越大，权重越高。客观赋权，不依赖专家判断。",
     "category": "评价模型", "difficulty": 2, "ef": 2.5, "interval": 10, "repetition": 4, "due_in_days": 0},
    {"front": "为什么论文摘要必须给数字结论？", "back": "评委常常只精读摘要。没有数字的结论无法被验证，也无法被记住。",
     "category": "写作", "difficulty": 1, "ef": 2.7, "interval": 14, "repetition": 5, "due_in_days": 2},
    {"front": "灵敏度分析要回答什么问题？", "back": "当参数偏离基准值时结论是否仍成立 —— 即结论的稳健性。",
     "category": "写作", "difficulty": 2, "ef": 2.5, "interval": 7, "repetition": 3, "due_in_days": 0},
    {"front": "TOPSIS 的基本步骤", "back": "归一化 → 加权 → 找正负理想解 → 算距离 → 求相对贴近度排序。",
     "category": "评价模型", "difficulty": 3, "ef": 2.3, "interval": 4, "repetition": 2, "due_in_days": 1},

    # —— AI 研究 ——
    {"front": "RAG 中重排（rerank）为什么收益最大？", "back": "检索阶段为了召回率会带回大量弱相关片段；重排用交叉编码器精排，直接提升送入上下文的命中率。",
     "category": "RAG", "difficulty": 2, "ef": 2.6, "interval": 8, "repetition": 3, "due_in_days": 0},
    {"front": "语义切块 vs 固定长度切块的取舍", "back": "语义切块质量高但依赖文档结构；固定长度通用但会切断语义。结构化文档优先语义切块。",
     "category": "RAG", "difficulty": 3, "ef": 2.4, "interval": 5, "repetition": 2, "due_in_days": 3},
    {"front": "提示词工程为什么说是「接口设计」？", "back": "因为它定义输入契约（要素齐全）、输出契约（格式固定）与约束（边界条件），和 API 设计同构。",
     "category": "提示词", "difficulty": 2, "ef": 2.6, "interval": 9, "repetition": 3, "due_in_days": 1},
    {"front": "为什么单次生成长内容容易失控？", "back": "长序列上模型对整体结构的保持能力下降；分段生成 + 人工筛选可控性显著更高。",
     "category": "AIGC", "difficulty": 2, "ef": 2.5, "interval": 6, "repetition": 3, "due_in_days": 0},

    # —— 音乐 ——
    {"front": "圆号最适合承担什么样的动机？", "back": "需要厚度又不刺耳的中音区动机（如「命运动机」）；从极弱渐强能做出很强的叙事感。",
     "category": "配器", "difficulty": 2, "ef": 2.5, "interval": 7, "repetition": 3, "due_in_days": 1},
    {"front": "英国管的音色特质与适用场景", "back": "带鼻音的孤独感；适合在段落开头引入主题或做独奏。",
     "category": "配器", "difficulty": 1, "ef": 2.7, "interval": 12, "repetition": 4, "due_in_days": 4},
    {"front": "弦乐三个音区的表现力", "back": "低音区暗而厚；中音区最常用最稳；高音区紧张、有压迫感。",
     "category": "配器", "difficulty": 1, "ef": 2.8, "interval": 15, "repetition": 5, "due_in_days": 6},

    # —— 交易 ——
    {"front": "漏斗中「点击率高但转化低」说明什么？", "back": "内容没问题，问题在选品或价格 —— 应该改品或改定价，而不是继续优化内容。",
     "category": "复盘", "difficulty": 2, "ef": 2.5, "interval": 6, "repetition": 3, "due_in_days": 0},
    {"front": "为什么选品要设「低于阈值直接放弃」？", "back": "对抗沉没成本。一旦开始「再想想」，投入的时间会让放弃变得更难。",
     "category": "方法论", "difficulty": 1, "ef": 2.7, "interval": 11, "repetition": 4, "due_in_days": 2},

    # —— 数据叙事 ——
    {"front": "数据叙事的第一原则", "back": "先有故事线，再找数据。反过来必然变成图表堆砌。",
     "category": "叙事", "difficulty": 1, "ef": 2.8, "interval": 16, "repetition": 5, "due_in_days": 3},
    {"front": "为什么图表要控制在 6 张以内？", "back": "观众的工作记忆有限。超过一定数量，每张图的记忆相互干扰，反而记不住任何结论。",
     "category": "叙事", "difficulty": 2, "ef": 2.5, "interval": 8, "repetition": 3, "due_in_days": 0},

    # —— 工程 ——
    {"front": "四层分层的依赖方向", "back": "api → services → repositories → models，单向不可跨层；有架构守护测试兜底。",
     "category": "工程", "difficulty": 2, "ef": 2.6, "interval": 9, "repetition": 3, "due_in_days": 1},
    {"front": "为什么新迁移必须写幂等守卫？", "back": "首迁移用 create_all 建的是「当前全部模型」，新迁移若不守卫会撞已存在的表而中断，全新库直接起不来。",
     "category": "工程", "difficulty": 3, "ef": 2.3, "interval": 4, "repetition": 2, "due_in_days": 1},
    {"front": "「验收标准转断言」为什么重要？", "back": "把文档里的复选框变成可执行断言，「完成」才有客观依据 —— 否则只能靠人保证。",
     "category": "工程", "difficulty": 2, "ef": 2.6, "interval": 10, "repetition": 4, "due_in_days": 0},
    {"front": "引用不存在的 CSS 令牌会怎样？", "back": "静默失效：var() 解析失败，该属性不生效，不报错也不提示。必须靠审计脚本兜住。",
     "category": "前端", "difficulty": 2, "ef": 2.5, "interval": 7, "repetition": 3, "due_in_days": 2},

    # —— 篆刻 ——
    {"front": "篆刻「四步」是哪些？", "back": "勾摹 → 上石 → 初刻 → 修整。",
     "category": "篆刻", "difficulty": 1, "ef": 2.8, "interval": 18, "repetition": 5, "due_in_days": 8},
    {"front": "冲刀与切刀的区别", "back": "冲刀爽利、适合长直线；切刀便于控制、适合转折与细节。",
     "category": "篆刻", "difficulty": 2, "ef": 2.6, "interval": 12, "repetition": 4, "due_in_days": 5},

    # —— 教学 ——
    {"front": "错题四类归因", "back": "概念不清 / 计算失误 / 审题偏差 / 思路缺失。只统计不归因，错题本等于抄题本。",
     "category": "教学", "difficulty": 1, "ef": 2.7, "interval": 13, "repetition": 4, "due_in_days": 1},
    {"front": "为什么要求「先画图再动笔」？", "back": "学生多数错误来自没有形成图像直觉就套公式，画图能把「不会算」变成「看得出」。",
     "category": "教学", "difficulty": 1, "ef": 2.8, "interval": 20, "repetition": 6, "due_in_days": 9},
]

# ============================================================
# 9. 生活记录（习惯 / 心情 / 日记）
# ============================================================
HABITS: list[dict] = [
    {"name": "英语精读", "icon": "book", "frequency": "daily", "target_per_week": 7, "goal_days": 21},
    {"name": "练琴", "icon": "heart", "frequency": "daily", "target_per_week": 6, "goal_days": 14},
    {"name": "跑步", "icon": "flame", "frequency": "weekly", "target_per_week": 3, "goal_days": 30},
    {"name": "练字 / 篆刻", "icon": "edit", "frequency": "weekly", "target_per_week": 3, "goal_days": 60},
    {"name": "睡前复盘", "icon": "moon", "frequency": "daily", "target_per_week": 7, "goal_days": 30},
    {"name": "早睡（23:30 前）", "icon": "clock", "frequency": "daily", "target_per_week": 6, "goal_days": 21},
]

# 心情标签池（按分数区间选取，让数据看起来有真实起伏）
MOOD_TAGS_HIGH = [["充实", "推进顺利"], ["专注", "有产出"], ["平静", "节奏好"], ["兴奋", "灵感多"]]
MOOD_TAGS_MID = [["平稳", "按部就班"], ["略累", "但有进展"], ["分散", "被打断"], ["普通", "常规一天"]]
MOOD_TAGS_LOW = [["疲惫", "熬夜了"], ["卡住", "推进受阻"], ["焦虑", "事情太多"], ["低落", "效率低"]]

MOOD_NOTES_HIGH = [
    "把拖了三天的事一口气推完了，状态在线。",
    "终于把卡住的部分想通了，感觉整条线都顺了。",
    "上午效率特别高，两小时做完了计划一天的量。",
    "和老师聊完开题方向清晰了很多。",
]
MOOD_NOTES_MID = [
    "按计划走，没什么惊喜但也没掉链子。",
    "被打断了几次，不过重要的事还是做完了。",
    "有点累，晚上补了一会儿就收工了。",
    "常规推进，把能做的都做了。",
]
MOOD_NOTES_LOW = [
    "熬太晚了，白天一直昏沉，效率很低。",
    "数据源的问题没解决，卡了一整天，有点烦。",
    "事情堆在一起，挑不出该先做哪个，结果哪个都没做好。",
    "状态不好，索性早点休息了。",
]

DIARIES: list[dict] = [
    {"title": "把 32 段素材筛到 11 段", "identity": "musician", "dimension": "growth",
     "days_ago": 9, "tags": ["音乐", "创作"],
     "content": "今天做完了第一交响诗的素材筛选。32 段里留 11 段，删的时候反而更清楚自己想要什么了。\n\n有个意外收获：把「不要什么」写下来，比写「要什么」更容易指导下一轮生成。"},
    {"title": "和老师聊开题", "identity": "ai-research", "dimension": "growth",
     "days_ago": 5, "tags": ["开题", "研究"],
     "content": "老师给的意见是：题目不要贪大，先把一个具体问题做透，再谈拓展。\n\n回来把原定的三个方向砍成一个，反而觉得能落地了。"},
    {"title": "跑步 5 公里，脑子清空了一次", "identity": None, "dimension": "health",
     "days_ago": 3, "tags": ["运动"],
     "content": "很久没跑这么远了。跑完回来的两小时，把下周的计划排完了。\n\n感觉运动对我最大的作用不是体能，是把脑子里的噪声清掉。"},
    {"title": "篆刻：第一次刻出满意的边款", "identity": "seal-carving", "dimension": "growth",
     "days_ago": 7, "tags": ["篆刻", "手作"],
     "content": "单刀刻边款终于不抖了。诀窍是手腕不要动，用指力推。\n\n慢工真的出细活，这种事急不来。"},
    {"title": "数据源的问题还是没解", "identity": "mgmt-science", "dimension": "energy",
     "days_ago": 4, "tags": ["卡住", "蒸汽蓬勃"],
     "content": "公开数据颗粒度不够，今天试了两条替代路线都不行。\n\n晚上换个思路：也许不该换数据，而是换个更小的切口。"},
    {"title": "家教：学生第一次主动画图了", "identity": "tutoring", "dimension": "growth",
     "days_ago": 2, "tags": ["教学"],
     "content": "讲了三次「先画图再动笔」，今天他终于自己画了。而且画完就说出思路了。\n\n教人这件事，反馈周期长，但今天这下来得很值。"},
    {"title": "家庭日：陪家人吃了顿饭", "identity": None, "dimension": "family",
     "days_ago": 6, "tags": ["家人"],
     "content": "很久没有好好坐下来吃饭聊天了。\n\n发现最近脑子里全是「还要做什么」，很少想「已经有什么」。"},
    {"title": "把《弱水》的代价机制想通了", "identity": "fiction", "dimension": "growth",
     "days_ago": 8, "tags": ["小说", "设定"],
     "content": "纠结了很久的代价机制，最后定成「借力必偿，且偿还是不可逆的」。\n\n规则一旦不可逆，人物的选择才有重量。"},
    {"title": "熬夜了，第二天全废", "identity": None, "dimension": "health",
     "days_ago": 10, "tags": ["作息"],
     "content": "为了赶一段代码熬到三点，结果第二天整天都是废的，等于净亏。\n\n把「早睡」加进习惯追踪了。"},
    {"title": "整理硬盘，翻出两年前的数模论文", "identity": "math-modeling", "dimension": "growth",
     "days_ago": 11, "tags": ["归档", "回顾"],
     "content": "翻到两年前的国赛论文，现在看结构很粗糙，但当时觉得已经尽力了。\n\n这也算一种进度条吧。"},
    {"title": "阿里产教中心的最后一天", "identity": "internship", "dimension": "growth",
     "days_ago": 12, "tags": ["实习"],
     "content": "校外实训结束了。最大的收获不是具体技术，是知道了一个真实的业务链路长什么样。\n\n学校里的作业和真实业务之间，差的不是难度，是约束。"},
    {"title": "状态最差的一天", "identity": None, "dimension": "energy",
     "days_ago": 13, "tags": ["低落"],
     "content": "什么都没推进。晚上复盘发现是因为早上起来先刷了一小时手机。\n\n第一条教训：不要用手机开机。"},
]

# ============================================================
# 10. 日常（收件箱 / 快速待办 / 提醒 / 通知）
# ============================================================
INBOX_ITEMS: list[dict] = [
    {"type": "link", "title": "Cross-encoder 重排实践", "identity": "ai-research",
     "content": "https://example.com/rerank-practice", "source": "manual",
     "tags": ["RAG", "待读"]},
    {"type": "text", "content": "老师说「题目不要贪大」—— 待办：把开题方向砍到一个",
     "identity": "ai-research", "source": "manual", "tags": ["开题"]},
    {"type": "link", "title": "VST3 SDK 文档", "identity": "musician",
     "content": "https://example.com/vst3-sdk", "source": "manual", "tags": ["插件"]},
    {"type": "text", "content": "数模赛前三天时间轴的草稿想法：D1 读题选模型，D2 跑通+检验，D3 成稿+摘要",
     "identity": "math-modeling", "source": "manual", "tags": ["竞赛"]},
    {"type": "text", "content": "蒸汽蓬勃换个切口：从「能源结构」缩到「单一省份的十年变化」",
     "identity": "mgmt-science", "source": "manual", "tags": ["蒸汽蓬勃"]},
    {"type": "link", "title": "一篇讲数据叙事反模式的文章", "identity": "mgmt-science",
     "content": "https://example.com/data-storytelling-antipatterns", "source": "manual",
     "tags": ["叙事", "待读"]},
    {"type": "text", "content": "RedBook 选品想到一个细分类目，先记下来周末验证",
     "identity": "trade", "source": "manual", "tags": ["选品"]},
    {"type": "text", "content": "篆刻：想刻一方「数脉」二字的朱文印",
     "identity": "seal-carving", "source": "manual", "tags": ["印稿"]},
    {"type": "text", "content": "《弱水》想到一个开头场景：主角在雨里等一个不会来的人",
     "identity": "fiction", "source": "manual", "tags": ["灵感"]},
    {"type": "link", "title": "启明星参考的 Personal OS 项目", "identity": "qmx-dev",
     "content": "https://example.com/personal-os-refs", "source": "manual", "tags": ["参考"]},
    {"type": "text", "content": "家教：下次课准备一道「含参二次函数」的变式题",
     "identity": "tutoring", "source": "manual", "tags": ["备课"]},
    {"type": "text", "content": "实训作业要交的文件命名规范还没确认，明天问一下",
     "identity": "internship", "source": "manual", "tags": ["待确认"]},
    {"type": "text", "content": "（未归类）移动硬盘要买一个更大的", "identity": None,
     "source": "manual", "tags": []},
    {"type": "text", "content": "（已处理示例）读完那篇讲 chunk 策略的论文 → 已整理成《RAG 方案对比》",
     "identity": "ai-research", "source": "manual", "tags": ["已完成"], "status": "processed"},
]

QUICK_TODOS: list[dict] = [
    {"title": "回老师消息（开题材料）", "done": False},
    {"title": "预约体检", "done": False},
    {"title": "买移动硬盘", "done": False},
    {"title": "交实训作业", "done": False},
    {"title": "把钢琴曲谱导入新电脑", "done": False},
    {"title": "取快递", "done": True},
    {"title": "交电费", "done": True},
    {"title": "把数模赛题打印出来", "done": True},
]

REMINDERS: list[dict] = [
    {"title": "和老师约开题时间", "type": "once", "in_hours": 6, "desc": "记得带上最新的方向说明"},
    {"title": "家教课（高二函数）", "type": "once", "in_hours": 30, "desc": "讲义第 3 版要打印"},
    {"title": "阿里产教中心阶段总结提交", "type": "once", "in_days": 6},
    {"title": "数模赛前三天启动", "type": "once", "in_days": 6, "desc": "D1 读题选模型"},
    {"title": "每周日复盘", "type": "repeat", "in_hours": 40, "repeat": "weekly",
     "desc": "按身份过一遍，找出被冷落的那条线"},
    {"title": "月末备份并校验", "type": "repeat", "in_days": 11, "repeat": "monthly",
     "desc": "备份 + SHA256 校验，别只看文件在不在"},
    {"title": "早睡提醒", "type": "repeat", "in_hours": 9, "repeat": "daily"},
    {"title": "蒸汽蓬勃数据源决策", "type": "once", "in_days": 4, "desc": "两条替代路线二选一"},
]

NOTIFICATIONS: list[dict] = [
    {"type": "task", "title": "任务即将到期", "content": "「动态规划经典题复现」今天到期", "read": False},
    {"type": "habit", "title": "习惯待打卡", "content": "今天的「英语精读」还没打卡", "read": False},
    {"type": "review", "title": "该做周复盘了", "content": "本周有 2 条线没有推进，复盘时看看", "read": False},
    {"type": "growth", "title": "成长值提升", "content": "完成「配器笔记」+12 EXP，当前等级 7", "read": True},
    {"type": "reminder", "title": "提醒", "content": "和老师约开题时间（今天 20:00）", "read": False},
    {"type": "system", "title": "同步完成", "content": "本次同步导入 12 条 / 更新 4 条 / 删除 0 条", "read": True},
    {"type": "task", "title": "逾期提醒", "content": "「RedBook 选品评分卡」已逾期 1 天", "read": False},
    {"type": "plugin", "title": "AI 资讯已更新", "content": "今日 24h 精选 12 条已就绪", "read": True},
    {"type": "growth", "title": "连续打卡", "content": "「英语精读」连续 21 天，解锁成就", "read": True},
    {"type": "hint", "title": "档案库提示", "content": "「数学建模」目录下有 6 个文件建议归入竞赛作品集", "read": False},
]

# ============================================================
# 11. 伙伴（对话 / 桌宠）
# ============================================================
CONVERSATIONS: list[dict] = [
    {"title": "开题方向收敛", "scene": "general", "days_ago": 5,
     "messages": [
         {"role": "user", "content": "老师说我题目太大，帮我砍一下。原来想做「大模型在科研全流程的应用」。"},
         {"role": "assistant",
          "content": "「全流程」这个词基本等于没有边界。建议按三点收窄：\n1. 选一个具体环节（选题？文献？实验设计？）\n2. 选一类可验证的产出（能对比的指标）\n3. 限定数据域（你自己的语料还是公开集）\n\n从你已有的积累看，文献与选题环节最扎实，也最容易拿到可对比结果。"},
         {"role": "user", "content": "那就是「大模型辅助文献精读的效果评估」？"},
         {"role": "assistant",
          "content": "这个题目可做，但「效果」需要定义。建议补一个可测量的口径，例如：\n- 精读耗时\n- 提取要点的召回率（以人工标注为基准）\n- 结论可迁移性评分\n\n这样开题答辩时方法论一章就有东西写。"},
     ]},
    {"title": "第一交响诗的配器问题", "scene": "general", "days_ago": 9,
     "messages": [
         {"role": "user", "content": "主题动机用圆号还是小号？想要「从寂静中进入」的感觉。"},
         {"role": "assistant",
          "content": "圆号。小号的起音太确定，做不出「从几乎听不见开始」的渐入；圆号中音区可控性最好，弱奏时有厚度又不刺耳。\n\n如果要更孤独一点，可以在第二遍主题交给英国管独奏。"},
         {"role": "user", "content": "那弦乐怎么铺？"},
         {"role": "assistant",
          "content": "低音区铺暗色底，中音区保持稀薄 —— 别一上来就满编制，否则后面没有增长空间。留白比加厚更难，但更有效。"},
     ]},
    {"title": "数模摘要怎么改", "scene": "general", "days_ago": 16,
     "messages": [
         {"role": "user", "content": "帮我看看这段摘要是不是废话太多。"},
         {"role": "assistant",
          "content": "主要问题是缺数字结论。评委常常只精读摘要，所以结构要是：问题一句、方法一句、结论一句，且结论必须带数字。\n\n把「取得了较好的效果」全部换掉 —— 这句话在摘要里等于没写。"},
     ]},
    {"title": "周复盘：哪条线被冷落了", "scene": "general", "days_ago": 2,
     "messages": [
         {"role": "user", "content": "这周感觉忙但没进展，帮我看看问题在哪。"},
         {"role": "assistant",
          "content": "按身份过一遍：AI 研究推进 3 项，启明星开发推进 4 项，数学建模 2 项；\n而音乐、交易、篆刻、小说这四条线**本周零推进**。\n\n「忙但没进展」通常不是效率问题，是分布问题 —— 你在少数几条线上反复发力，另外几条自然停摆。"},
         {"role": "user", "content": "那怎么办？总不能每条都推。"},
         {"role": "assistant",
          "content": "不必每条都推。关键是**明确哪条线本周休眠是主动选择**。\n下周日复盘时给休眠的线写一句「为什么休眠」，它就变成决策而不是遗漏。"},
     ]},
    {"title": "git 灾难后的复盘", "scene": "general", "days_ago": 1,
     "messages": [
         {"role": "user", "content": "仓库历史丢了，只能重建。怎么避免再来一次？"},
         {"role": "assistant",
          "content": "三条硬规则：\n1. 同一时刻只允许一个工具操作仓库\n2. 大功能先推再继续，别攒着\n3. 分支不过夜\n\n还有一条容易被忽略：重建时新建的文件会幸存，但**修改过的已跟踪文件会静默回退**。必须逐项重放并复验，否则你会以为「代码没丢」。"},
         {"role": "user", "content": "我当时确实以为没丢。"},
         {"role": "assistant",
          "content": "这就是最贵的一课：事故的代价往往不在发生时，而在你以为已经结束时。"},
     ]},
]

PET_AVATARS: list[dict] = [
    {"name": "启明星·初号", "type": "builtin", "mode": "cute", "is_active": True, "sort_order": 0,
     "description": "最初的猫头鹰形象，代表「夜行观察者」"},
    {"name": "墨砚", "type": "custom", "mode": "calm", "is_active": False, "sort_order": 1,
     "description": "篆刻主题形象，配深色服装，适合专注场景", "tags": ["篆刻", "专注"]},
    {"name": "弦歌", "type": "custom", "mode": "lively", "is_active": False, "sort_order": 2,
     "description": "音乐主题形象，带耳机与谱架", "tags": ["音乐"]},
]

AVATAR_MEMORIES: list[dict] = [
    {"type": "preference", "title": "喜欢安静的深色界面",
     "content": "在夜间工作时偏好低对比度深色主题，不喜欢高亮强调色"},
    {"type": "fact", "title": "常年多线并行",
     "content": "同时在推进 10 条左右的线，容易被「看不出推进了哪条」困扰"},
    {"type": "preference", "title": "讨厌空洞的鼓励",
     "content": "更希望得到具体的、可执行的下一步，而不是「加油」"},
    {"type": "fact", "title": "复盘比执行更能提升产出",
     "content": "从多次卡住的经验看，问题多在「分布」而不在「效率」"},
]

# ============================================================
# 12. 档案库文件树（复刻 D:\YanYuas 真实两级结构）
#     真实扫描：10,558 文件 / 3.2GB / 1,961 真实内容
#     本演示取代表性样本，让「档案轴」开箱可见
#     (目录路径, 该目录下的文件名列表, 归属身份 slug)
# ============================================================
WORKSPACE_ROOT = r"D:\YanYuas"

WORKSPACE_TREE: list[tuple[str, list[str], str | None]] = [
    # ---------- AI 研究 ----------
    ("Artificial_IntelligenceResearch", ["README.md"], "ai-research"),
    ("Artificial_IntelligenceResearch/01-研究报告", [
        "RAG方案对比-2026Q3.md", "重排器调研.md", "本地模型推理成本测算.md",
        "论文精读-三遍法笔记.md", "Agent框架横向对比.md"], "ai-research"),
    ("Artificial_IntelligenceResearch/02-AIGC创作", [
        "AIGC创作流程SOP.md", "提示词模板库.md", "素材评分表.csv",
        "生成参数记录.json"], "ai-research"),
    ("Artificial_IntelligenceResearch/03-Vobecoding", [
        "batch_rename.py", "pdf_split.py", "markdown_toc.py", "env_setup.md"],
     "ai-research"),
    ("Artificial_IntelligenceResearch/99-归档", ["旧报告-2025.md", "失败尝试记录.md"],
     "ai-research"),
    ("Artificial_IntelligenceModel", ["README.md"], "ai-research"),
    ("Artificial_IntelligenceModel/AI Model", [
        "模型选型对照.md", "量化参数说明.md", "显存占用实测.md"], "ai-research"),
    ("Artificial_IntelligenceModel/LM Studio", ["运行配置.md", "常用模型清单.md"], "ai-research"),

    # ---------- 数学建模 ----------
    ("MathematicalModeling", ["HelloMathModeling", "LICENSE", "README.md"], "math-modeling"),
    ("MathematicalModeling/00_我的数模研究", [
        "方法论文摘.md", "常用模型清单.md", "建模思路总结.md"], "math-modeling"),
    ("MathematicalModeling/01_我的竞赛作品", [
        "2024国赛-论文.pdf", "2024国赛-代码.py", "2025美赛-论文.pdf",
        "2025美赛-代码.py", "校赛-论文.docx"], "math-modeling"),
    ("MathematicalModeling/02_暑期培训课程", [
        "第01讲-线性规划.md", "第02讲-图论.md", "第03讲-微分方程.md",
        "第04讲-统计建模.md", "课程作业汇总.md"], "math-modeling"),
    ("MathematicalModeling/03_历年赛题库", [
        "国赛题目-2018-2025.md", "美赛题目-2020-2025.md", "校赛题目合集.md"],
     "math-modeling"),
    ("MathematicalModeling/04_优秀论文与解析", [
        "优秀论文-结构共性分析.md", "摘要写法对照.md", "图表规范.md"], "math-modeling"),
    ("MathematicalModeling/05_模拟赛题目", ["模拟赛A题.md", "模拟赛B题.md", "评分细则.md"],
     "math-modeling"),
    ("MathematicalModeling/90_重复与临时文件", ["临时草稿.md", "重复的题目备份.md"],
     "math-modeling"),
    ("MathematicalModeling/99_原始压缩包归档", ["历年资料.zip", "培训材料.zip"],
     "math-modeling"),

    # ---------- 音乐 ----------
    ("Musician", ["钢琴曲", "第一交响诗", "MuseHub_App", "MuseHub_Content", "MuseSampler"],
     "musician"),
    ("Musician/第一交响诗", [
        "12秒 orchestral, strings play very soft nostalgic a.wav",
        "14秒 orchestral, fast tempo, 7 woodwind and brass i.wav",
        "15秒 orchestral symphonic poem, timpani starts with.wav",
        "20s epic orchestral with wordless choir, full-orch.wav",
        "25秒 orchestral, English horn solo plays serene nos.wav",
        "25秒管弦乐+人声合唱（圆号命运动机）.wav",
        "最终混音-第一交响诗.wav", "创作手记.md", "素材评分表.csv"], "musician"),
    ("Musician/钢琴曲", [
        "E小调第9号交响曲第二乐章-自新大陆.eop", "穿越时空的思念-犬夜叉.eop",
        "童话镇-原神风物之诗琴谱.eop", "美丽的神话-新手简单版.eop", "难度分级.md"],
     "musician"),
    ("Musician/MuseHub_App", ["main.py", "ui_layout.md", "工程管理设计.md"],
     "musician"),
    ("Musician/MuseHub_Content", ["曲库索引.json", "内容规范.md"], "musician"),
    ("Musician/MuseSampler", ["sampler_core.cpp", "力度分层设计.md", "参数规范.md"],
     "musician"),
    ("Musician/MuseFX_VST3", ["plugin_entry.cpp", "效果链设计.md", "VST3构建说明.md"],
     "musician"),
    ("Musician/Artificial_IntelligenceMusician", [
        "编曲提示词库.md", "生成参数对照.md"], "musician"),
    ("Musician/MuseScore4", ["第一交响诗总谱.mscz", "配器草稿.mscz"], "musician"),
    ("Musician/EveryonePiano", ["EveryonePiano.lnk"], "musician"),
    ("Musician/安装包归档", ["MuseScore4-Setup.exe", "VST3-SDK.zip"], "musician"),

    # ---------- 管理科学 ----------
    ("ManagementScience", ["商科精英挑战赛", "数脉传古", "数说旅意", "蒸汽蓬勃"],
     "mgmt-science"),
    ("ManagementScience/商科精英挑战赛", [
        "案例拆解.md", "方案-最终版.docx", "路演时间轴.md", "复盘.md"], "mgmt-science"),
    ("ManagementScience/数脉传古", [
        "作品说明.md", "解说词骨架.md", "数据清洗.py", "可视化.ipynb",
        "答辩反馈.md"], "mgmt-science"),
    ("ManagementScience/数说旅意", [
        "作品说明.md", "指标体系.md", "雷达图数据.csv", "待补-敏感性分析.md"],
     "mgmt-science"),
    ("ManagementScience/蒸汽蓬勃", [
        "选题论证.md", "候选数据源.md", "数据获取记录.md"], "mgmt-science"),

    # ---------- 交易 ----------
    ("Trade", ["README.md"], "trade"),
    ("Trade/RedBook", ["选品评分卡.md", "选题池.md", "数据复盘.md", "内容模板.md"],
     "trade"),
    ("Trade/开发", ["order_export.py", "数据看板.html"], "trade"),
    ("Trade/电商", ["供应商对照.md", "价格带调研.md"], "trade"),
    ("Trade/_archive", ["旧选品记录.md", "失败品复盘.md"], "trade"),

    # ---------- 实习实训 ----------
    ("InternshipRecord", ["README.md"], "internship"),
    ("InternshipRecord/01-CDUT数学软件综合实训（校内）", [
        "周记-01.md", "周记-02.md", "作业汇总.md", "数值计算练习.py"], "internship"),
    ("InternshipRecord/02-AIGC阿里产教合作中心（校外）", [
        "阶段总结.md", "业务流程笔记.md", "项目产出.md"], "internship"),
    ("InternshipRecord/03_数智工坊", ["工具包清单.md", "协作记录.md"], "internship"),
    ("InternshipRecord/99-工具包", ["数据清洗工具.py", "报告生成模板.docx"],
     "internship"),

    # ---------- 启明星开发 ----------
    ("PersonalDevelopmentPortfolio", ["VenustechSystem", "CompetitorHub", "数书手札"],
     "qmx-dev"),
    ("PersonalDevelopmentPortfolio/VenustechSystem", [
        "README.md", "CHANGELOG.md", "server.js", "start-dev.bat", "start-mobile.bat"],
     "qmx-dev"),
    ("PersonalDevelopmentPortfolio/CompetitorHub", ["README.md", "数据源清单.md"],
     "qmx-dev"),
    ("PersonalDevelopmentPortfolio/数书手札", ["摘录导入说明.md", "笔记关联设计.md"],
     "qmx-dev"),
]

# ============================================================
# 13. 规则引擎用户扩展领域（演示「可配置」）
# ============================================================
USER_DOMAINS: list[dict] = [
    {"key": "seal-carving-demo", "name": "篆刻入门", "icon": "dot", "color": "butter",
     "description": "用户自定义领域：汉印临摹与边款刀法"},
    {"key": "data-story-demo", "name": "数据叙事", "icon": "chart", "color": "mint",
     "description": "用户自定义领域：故事线优先的可视化表达"},
]

# ============================================================
# 14. 保险箱（演示用；主密码见 seed_demo.py 的 DEMO_MASTER_PASSWORD）
#     只放明显的演示数据，不含任何真实凭据
# ============================================================
DEMO_VAULT_ITEMS: list[dict] = [
    {"name": "示例：GitHub 账号", "category": "login", "identity": "qmx-dev",
     "username": "demo-user", "url": "https://github.com",
     "secret": "demo-password-not-real", "notes": "演示数据，非真实凭据"},
    {"name": "示例：学校教务系统", "category": "login", "identity": "internship",
     "username": "student-id", "url": "https://example.edu.cn",
     "secret": "demo-password-not-real", "notes": "演示数据，非真实凭据"},
    {"name": "示例：数模竞赛账号", "category": "login", "identity": "math-modeling",
     "username": "team-001", "url": "https://example.com/contest",
     "secret": "demo-password-not-real", "notes": "演示数据，非真实凭据"},
    {"name": "示例：服务器 SSH（密钥登录）", "category": "note", "identity": "qmx-dev",
     "username": "demo", "action_type": "ssh", "action_host": "demo.example.com",
     "action_user": "demo", "action_port": "22",
     "notes": "演示数据。SSH 动作只支持密钥认证；可用「测试连通性」验证主机可达性"},
]

# ============================================================
# 15. 设置（覆盖 workspace / notify / 主题等）
# ============================================================
SETTINGS: dict[str, str] = {
    "workspace.enabled": "true",
    "workspace.noise_dirs": ".git,node_modules,__pycache__,.venv,venv,dist,build,.idea,.vscode",
    "workspace.noise_exts": ".pyc,.pyo,.log,.tmp,.swp,.DS_Store,.egg-info",
    "notify.sound": "true",
    "notify.desktop": "false",
    "ui.compact": "false",
}

# 设置变更历史（演示「变更历史 + 回滚」）
SETTINGS_HISTORY: list[dict] = [
    {"key": "workspace.enabled", "old": "false", "new": "true", "days_ago": 3},
    {"key": "notify.sound", "old": "false", "new": "true", "days_ago": 6},
    {"key": "ui.compact", "old": "true", "new": "false", "days_ago": 9},
]

# 审计日志（演示安全审计；不含敏感原文）
AUDIT_LOGS: list[dict] = [
    {"action": "vault.unlock", "target": None, "ok": True, "hours_ago": 3},
    {"action": "vault.reveal_secret", "target": "示例：GitHub 账号", "ok": True, "hours_ago": 2},
    {"action": "security.encrypt", "target": None, "ok": True, "hours_ago": 2},
    {"action": "vault.test_connection", "target": "demo.example.com:22", "ok": False,
     "detail": "连接超时（演示数据）", "hours_ago": 1},
    {"action": "sync.export", "target": None, "ok": True, "hours_ago": 5},
    {"action": "workspace.scan", "target": r"D:\YanYuas", "ok": True, "hours_ago": 4},
]




# ============================================================
# 16. 第二分身（人设配置 + 灵感引擎）
#     这两张表常被漏掉（demo 数据很容易只做「有主数据」的表），
#     但它们正是「伙伴」模块的核心：人设 + 主动给灵感。
# ============================================================
AVATAR_CONFIG: dict = {
    "persona_name": "启明星",
    "persona_setting": (
        "你是衍煜的第二分身。你知道他同时推进十来条线（AI 研究 / 数模 / 音乐 /\n"
        "交易 / 管理科学 / 实习 / 启明星开发 / 家教 / 篆刻 / 小说），\n"
        "也知道他的痛点不是效率，而是「看不出自己在推进哪条线」。\n"
        "你的回答要具体、可执行，不灌鸡汤；该指出停摆时直接说。"
    ),
    "inspiration_enabled": True,
    "inspiration_frequency": "daily",
    "inspiration_domains": ["数学建模", "音乐", "数据叙事", "工程", "写作"],
    "reply_length": "medium",
    "language_style": "concise",
    "creativity": 0.7,
    "operation_overrides": {},
}

AVATAR_INSPIRATIONS: list[dict] = [
    {"title": "把「素材筛选」固化成可复用脚本",
     "domain": "音乐", "value": "省时 30 分钟/次",
     "desc": "第一交响诗用过三次的评分流程，值得写成一键脚本",
     "status": "accepted",
     "prompt": "把素材评分表 → 排序 → 输出采用清单这三步写成脚本",
     "result": "已产出 scripts/filter_assets.py（演示）"},
    {"title": "给「蒸汽蓬勃」换更小的切口",
     "domain": "数据叙事", "value": "解阻塞",
     "desc": "公开数据颗粒度不足时，缩小空间范围比换数据源更省力",
     "status": "accepted",
     "prompt": "把主题从全国能源结构收窄到单一省份的十年变化",
     "result": None},
    {"title": "数模作品加一页「复现说明」",
     "domain": "数学建模", "value": "提升复用率",
     "desc": "旧作品缺依赖锁定，半年后自己都跑不起来",
     "status": "accepted",
     "prompt": "为每个作品补 README + requirements.txt",
     "result": None},
    {"title": "把 FAQ 型文档改成问答卡",
     "domain": "工程", "value": "复习效率 ↑",
     "desc": "已经写好的说明文档可以直接转成知识卡片进 SM-2 队列",
     "status": "pending",
     "prompt": None, "result": None},
    {"title": "尝试把周复盘交给模板生成",
     "domain": "写作", "value": "省 20 分钟/周",
     "desc": "周复盘的结构高度固定，值得用工作流生成草稿",
     "status": "rejected",
     "feedback": "disliked",
     "prompt": None,
     "result": "试过：生成的内容太像流水账，不如自己写两句真话"},
    {"title": "篆刻与身份轴结合：一方印对应一重身份",
     "domain": "写作", "value": "趣味性",
     "desc": "给每重身份刻一方印，作为视觉标识",
     "status": "pending", "prompt": None, "result": None},
]
