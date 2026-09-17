# ============================================================
# 演示数据种子（PRD §36.2 路演预设 · 大量扩充版）
# 首次启动自动灌入：
#   文件夹 5 + 任务 22（含子任务）+ 文档 15（含 [[链接]]/摘要）+ 复盘 10 + 对话 3 + 待办 5 + 提醒 5 + 通知 6
# ============================================================
from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.base import utcnow
from app.repositories import (
    ConversationRepository,
    DocumentRepository,
    FolderRepository,
    MessageRepository,
    NotificationRepository,
    QuickTodoRepository,
    ReminderRepository,
    ReviewRepository,
    SubtaskRepository,
    TaskRepository,
    UserRepository,
)
from app.services.document_service import count_words


def seed_if_empty(db: Session) -> bool:
    """若尚无 default_user 则灌入演示数据。返回是否执行了种子。"""
    ur = UserRepository(db)
    user = ur.get_by_username("default_user")
    if user is not None:
        return False

    user = ur.create(
        username="default_user",
        nickname="启明星用户",
        pet_position={"x": 1770, "y": 880},
    )

    today = date.today()

    # ================= 文件夹 =================
    fr = FolderRepository(db)
    inbox = fr.create(user_id=user.id, name="收集箱", is_inbox=True, sort_order=0)
    learn = fr.create(user_id=user.id, name="学习", sort_order=1)
    work = fr.create(user_id=user.id, name="工作", sort_order=2)
    create = fr.create(user_id=user.id, name="创作", sort_order=3)
    project = fr.create(user_id=user.id, name="项目", sort_order=4)

    # ================= 任务（22） =================
    tr = TaskRepository(db)
    # —— 启明星开发 ——
    t1 = tr.create(user_id=user.id, title="完成PRD文档", status="in_progress", priority="high",
                   project_tag="启明星开发", is_focus=True, description="整理需求文档并输出正式版", sort_order=0)
    t2 = tr.create(user_id=user.id, title="设计桌宠动作帧", status="pending", priority="high",
                   project_tag="启明星开发", description="完成8种动作的帧动画设计", sort_order=1)
    t3 = tr.create(user_id=user.id, title="后端 API 联调", status="in_progress", priority="high",
                   project_tag="启明星开发", description="跑通 5 模块接口", sort_order=2)
    t4 = tr.create(user_id=user.id, title="实现任务看板视图", status="pending", priority="medium",
                   project_tag="启明星开发", due_date=today + timedelta(days=1), sort_order=3)
    t5 = tr.create(user_id=user.id, title="路演彩排", status="waiting", priority="urgent",
                   project_tag="启明星开发", due_date=today + timedelta(days=2), sort_order=4)
    t6 = tr.create(user_id=user.id, title="UI 画廊定稿", status="completed", priority="medium",
                   project_tag="启明星开发", completed_at=utcnow() - timedelta(days=1), sort_order=5)
    # —— 数学建模 ——
    t7 = tr.create(user_id=user.id, title="历年真题分析", status="pending", priority="medium",
                   project_tag="数学建模", due_date=today, description="做近三年真题梳理", sort_order=10)
    t8 = tr.create(user_id=user.id, title="动态规划算法复现", status="in_progress", priority="high",
                   project_tag="数学建模", description="经典 DP 题代码实现", sort_order=11)
    t9 = tr.create(user_id=user.id, title="论文模板准备", status="pending", priority="medium",
                   project_tag="数学建模", sort_order=12)
    t10 = tr.create(user_id=user.id, title="赛前冲刺方案", status="waiting", priority="urgent",
                    project_tag="数学建模", due_date=today + timedelta(days=3), sort_order=13)
    # —— 小说创作 ——
    t11 = tr.create(user_id=user.id, title="世界观设定细化", status="in_progress", priority="medium",
                    project_tag="小说创作", description="补充弱水规则细节", sort_order=20)
    t12 = tr.create(user_id=user.id, title="第一章初稿", status="pending", priority="medium",
                    project_tag="小说创作", sort_order=21)
    t13 = tr.create(user_id=user.id, title="女主角色卡", status="completed", priority="medium",
                    project_tag="小说创作", completed_at=utcnow() - timedelta(days=2), sort_order=22)
    # —— 外贸系统 ——
    t14 = tr.create(user_id=user.id, title="需求评审会议", status="waiting", priority="high",
                    project_tag="外贸系统", due_date=today, sort_order=30)
    t15 = tr.create(user_id=user.id, title="接口联调测试", status="in_progress", priority="high",
                    project_tag="外贸系统", description="订单模块接口", sort_order=31)
    t16 = tr.create(user_id=user.id, title="部署演练", status="pending", priority="medium",
                    project_tag="外贸系统", due_date=today + timedelta(days=4), sort_order=32)
    # —— 学习成长 ——
    t17 = tr.create(user_id=user.id, title="英语单词打卡", status="in_progress", priority="low",
                    project_tag="学习成长", due_date=today, sort_order=40)
    t18 = tr.create(user_id=user.id, title="阅读《深度工作》", status="pending", priority="low",
                    project_tag="学习成长", sort_order=41)
    t19 = tr.create(user_id=user.id, title="间隔重复复习", status="in_progress", priority="low",
                    project_tag="学习成长", due_date=today, sort_order=42)
    # —— 生活 ——
    t20 = tr.create(user_id=user.id, title="体检预约", status="pending", priority="medium",
                    due_date=today + timedelta(days=1), sort_order=50)
    t21 = tr.create(user_id=user.id, title="整理房间", status="completed", priority="low",
                    completed_at=utcnow() - timedelta(days=1), sort_order=51)
    t22 = tr.create(user_id=user.id, title="每日运动", status="in_progress", priority="low",
                    due_date=today, sort_order=52)

    # 子任务
    sr = SubtaskRepository(db)
    sr.create(task_id=t1.id, title="梳理需求清单", completed=True, sort_order=0)
    sr.create(task_id=t1.id, title="输出PRD初稿", completed=True, sort_order=1)
    sr.create(task_id=t1.id, title="评审修订", completed=False, sort_order=2)
    sr.create(task_id=t3.id, title="任务模块联调", completed=True, sort_order=0)
    sr.create(task_id=t3.id, title="对话 SSE 联调", completed=False, sort_order=1)
    sr.create(task_id=t8.id, title="背包问题", completed=True, sort_order=0)
    sr.create(task_id=t8.id, title="最长公共子序列", completed=False, sort_order=1)
    sr.create(task_id=t8.id, title="区间 DP", completed=False, sort_order=2)
    sr.create(task_id=t14.id, title="整理会议纪要", completed=True, sort_order=0)
    sr.create(task_id=t14.id, title="输出需求清单", completed=False, sort_order=1)

    # ================= 文档（15） =================
    dr = DocumentRepository(db)
    d1_c = "本文档记录启明星系统的整体架构设计。采用 Electron + Vue3 + FastAPI + SQLite 技术栈，以第二分身为核心差异化亮点，构建任务、知识、复盘的一体化闭环。详见 [[第二分身产品思路]]。"
    d1 = dr.create(user_id=user.id, title="项目架构设计笔记", folder_id=inbox.id,
                   content=d1_c, tags=["架构", "设计"], word_count=count_words(d1_c), version=2,
                   summary="启明星系统技术架构设计，模块化单体 + 本地优先。")
    d2_c = "第二分身不是聊天机器人，而是住在用户电脑里的 AI 伙伴。她阅读用户的文档，学习思维方式，主动整理知识，以二次元形象陪伴用户，是产品的情感连接点。"
    d2 = dr.create(user_id=user.id, title="第二分身产品思路", folder_id=inbox.id,
                   content=d2_c, tags=["AI", "产品"], word_count=count_words(d2_c), version=1)
    d3_c = "用户故事集：学生希望管理课程与笔记；自由职业者需要多项目并行；创业者追求认知减负；知识工作者依赖个人知识库。"
    d3 = dr.create(user_id=user.id, title="用户故事集", folder_id=inbox.id,
                   content=d3_c, tags=["产品", "PRD"], word_count=count_words(d3_c), version=1)
    d4_c = "数学建模历年真题分析：重点关注离散优化与统计建模两类题型，结合往届获奖论文提炼通用解法框架，配套代码与模板。"
    d4 = dr.create(user_id=user.id, title="数学建模-历年题分析", folder_id=learn.id,
                   content=d4_c, tags=["数学", "建模"], word_count=count_words(d4_c), version=1,
                   summary="离散优化 + 统计建模两大题型解法框架。")
    d5_c = "动态规划笔记：背包问题、最长公共子序列、区间 DP 的核心转移方程与模板代码，附典型例题。"
    d5 = dr.create(user_id=user.id, title="算法笔记-动态规划", folder_id=learn.id,
                   content=d5_c, tags=["算法"], word_count=count_words(d5_c), version=1)
    d6_c = "英语高频词汇表：按主题分类整理（工作/学习/生活），含例句与记忆技巧。"
    d6 = dr.create(user_id=user.id, title="英语高频词汇表", folder_id=learn.id,
                   content=d6_c, tags=["英语"], word_count=count_words(d6_c), version=1)
    d7_c = "周会纪要 0825：同步启明星开发进度、桌宠动作设计排期、路演素材准备计划，明确下周里程碑。"
    d7 = dr.create(user_id=user.id, title="周会纪要-0825", folder_id=work.id,
                   content=d7_c, tags=["会议"], word_count=count_words(d7_c), version=1)
    d8_c = "外贸系统需求评审：梳理订单、客户、商品三大模块，明确接口边界与数据字典。"
    d8 = dr.create(user_id=user.id, title="外贸系统需求评审", folder_id=work.id,
                   content=d8_c, tags=["外贸", "需求"], word_count=count_words(d8_c), version=1)
    d9_c = "开发计划 v2：按纵向切片推进，两周一个可用里程碑，先跑通核心闭环再扩展。"
    d9 = dr.create(user_id=user.id, title="开发计划-v2", folder_id=work.id,
                   content=d9_c, tags=["计划"], word_count=count_words(d9_c), version=1)
    d10_c = "小说世界观设定：弱水三千，只取一瓢。海灵一族生活于弱水之上，以记忆为食，人类的分身由记忆凝结而成。"
    d10 = dr.create(user_id=user.id, title="小说设定-世界观", folder_id=create.id,
                    content=d10_c, tags=["小说", "设定"], word_count=count_words(d10_c), version=1)
    d11_c = "第一章初见：她沿着弱水缓行，岸边的记忆碎片在脚下闪烁。少年伸手，指尖触到一片温热——那是他遗忘的某个夏天。参考 [[小说设定-世界观]]。"
    d11 = dr.create(user_id=user.id, title="第一章-初见", folder_id=create.id,
                    content=d11_c, tags=["小说"], word_count=count_words(d11_c), version=1,
                    ai_suggested_tags=["开篇", "相遇"])
    d12_c = "角色卡-女主：海灵一族，擅长倾听记忆，性格温柔但坚定，口头禅是『我记着你的每一件事』。"
    d12 = dr.create(user_id=user.id, title="角色卡-女主", folder_id=create.id,
                    content=d12_c, tags=["小说", "角色"], word_count=count_words(d12_c), version=1)
    d13_c = "路演脚本 v1：20 分钟流程——开场痛点、产品演示（任务/知识/第二分身高潮）、复盘闭环、二期畅想。含关键话术与应急预案。"
    d13 = dr.create(user_id=user.id, title="路演脚本-v1", folder_id=project.id,
                    content=d13_c, tags=["路演", "演讲"], word_count=count_words(d13_c), version=1)
    d14_c = "灵感集：把模块化架构应用到插件系统；第二分身的人格切换；工作流模板市场。好想法先记下来。"
    d14 = dr.create(user_id=user.id, title="灵感集", folder_id=project.id,
                    content=d14_c, tags=["灵感"], word_count=count_words(d14_c), version=1)
    d15_c = "月度总结模板：本月完成、关键成果、问题与反思、下月目标。用于周期性复盘沉淀。"
    d15 = dr.create(user_id=user.id, title="月度总结模板", folder_id=project.id,
                    content=d15_c, tags=["模板", "复盘"], word_count=count_words(d15_c), version=1)

    # ================= 复盘：7 天日报 + 3 周周报 =================
    rvr = ReviewRepository(db)
    gains_pool = [
        "明确了产品定位，完成核心模块定义",
        "前端三栏布局重构完成，数据链路跑通",
        "搞定任务看板与拖拽换列",
        "全局搜索接入真实接口",
        "桌宠联动庆祝动作上线",
        "复盘闭环补全：自动填充 + AI 反思",
        "整理了一批高质量灵感",
    ]
    for i in range(7):
        d = today - timedelta(days=i)
        rvr.create(
            user_id=user.id, type="daily", review_date=d,
            data={
                "completed_tasks": f"1. {gains_pool[i]}\n2. 处理日常任务与消息",
                "unfinished_tasks": "1. Tiptap 编辑器集成（二期）",
                "gains": gains_pool[i],
                "reflections": [
                    {"question": "今天最有成就感的是什么？", "answer": gains_pool[i]},
                    {"question": "有什么可以做得更好的地方？", "answer": "时间分配可以更聚焦"},
                    {"question": "明天最重要的一件事？", "answer": "推进路演准备"},
                ],
                "tomorrow_plan": "1. 完善演示数据\n2. 路演彩排",
                "mood": 4 if i % 2 == 0 else 5,
                "energy": 3 + (i % 3),
            },
        )
    for w in range(3):
        monday = today - timedelta(days=today.weekday() + 7 * w)
        rvr.create(
            user_id=user.id, type="weekly", review_date=monday,
            data={
                "completed_tasks": f"第 {w + 1} 周：后端骨架、前端接线、进度推进到 {48 + w * 8}%",
                "unfinished_tasks": "Electron 打包、Tiptap",
                "gains": "每周都有可演示的增量",
                "reflections": [
                    {"question": "本周关键突破？", "answer": f"完成第 {w + 1} 个里程碑"},
                    {"question": "下周焦点？", "answer": "路演闭环"},
                ],
                "tomorrow_plan": "推进到 70%，补齐交互闭环",
                "mood": 4,
                "energy": 4,
            },
        )

    # ================= 对话：3 段 =================
    cvr = ConversationRepository(db)
    mr = MessageRepository(db)
    c1 = cvr.create(user_id=user.id, title="关于知识管理的对话")
    mr.create(conversation_id=c1.id, role="user", content="你好，介绍一下你自己")
    mr.create(conversation_id=c1.id, role="assistant",
              content="你好，我是你的第二分身！我可以读你的文档、帮你整理知识、给灵感，还会用你喜欢的形象陪着你。有什么想聊的？", tokens=42)
    mr.create(conversation_id=c1.id, role="user", content="我有很多散落的笔记，怎么整理比较好？")
    mr.create(conversation_id=c1.id, role="assistant",
              content="建议先统一进收集箱，我用自动摘要和标签帮你归类；重要的笔记加上 [[双向链接]] 形成知识网络。要不要我帮你看最近的文档？", tokens=58)
    c2 = cvr.create(user_id=user.id, title="路演准备头脑风暴")
    mr.create(conversation_id=c2.id, role="user", content="路演最该突出什么？")
    mr.create(conversation_id=c2.id, role="assistant",
              content="核心就一个：第二分身。它是别人没有的差异化。开场 2 分钟讲痛点，中间 7 分钟给分身的高光演示——文档保存后自动摘要、对话基于文档回答、灵感一键成提示词。", tokens=64)
    mr.create(conversation_id=c2.id, role="user", content="那演示数据呢？")
    mr.create(conversation_id=c2.id, role="assistant",
              content="我已经为你预置了完整的演示数据：22 个任务、15 篇文档、10 篇复盘、3 段对话，打开即有内容。路演前记得彩排一遍数据流。", tokens=56)
    c3 = cvr.create(user_id=user.id, title="今日复盘辅助")
    mr.create(conversation_id=c3.id, role="user", content="帮我看看今天的复盘")
    mr.create(conversation_id=c3.id, role="assistant",
              content="你完成了 3 个任务，新建 2 篇文档。有个任务逾期了——'路演彩排'。要不要我帮你拆一下路演准备步骤？", tokens=48)
    mr.create(conversation_id=c3.id, role="user", content="好，拆一下")
    mr.create(conversation_id=c3.id, role="assistant",
              content="1. 检查演示数据完整性 2. 走一遍 20 分钟脚本 3. 录屏备选 4. 准备应急预案。每一步都可以直接转成任务，要我帮你建吗？", tokens=52)

    # ================= 左侧面板：待办 + 提醒 =================
    qtr = QuickTodoRepository(db)
    qtr.create(user_id=user.id, title="回复客户邮件", completed=False, sort_order=0)
    qtr.create(user_id=user.id, title="准备项目周报材料", completed=False, sort_order=1)
    qtr.create(user_id=user.id, title="设计项目原型评审", completed=True, sort_order=2, completed_at=utcnow() - timedelta(hours=6))
    qtr.create(user_id=user.id, title="整理调研笔记", completed=False, sort_order=3)
    qtr.create(user_id=user.id, title="预约牙医", completed=True, sort_order=4, completed_at=utcnow() - timedelta(days=2))

    now = datetime.utcnow()
    rmr = ReminderRepository(db)
    rmr.create(user_id=user.id, title="项目周会", remind_at=now + timedelta(hours=2),
               type="meeting", description="每周同步开发进度", repeat="weekly")
    rmr.create(user_id=user.id, title="每日学习计划", remind_at=now + timedelta(hours=8),
               type="study", repeat="daily", description="每天20:00深度学习 45 分钟")
    rmr.create(user_id=user.id, title="体检预约", remind_at=now + timedelta(days=1),
               type="health", description="明天09:00体检，记得空腹")
    rmr.create(user_id=user.id, title="小说截稿提醒", remind_at=now + timedelta(days=3),
               type="custom", description="第一章初稿截止")
    rmr.create(user_id=user.id, title="英语打卡", remind_at=now + timedelta(hours=1),
               type="study", repeat="daily", description="背 20 个新单词")

    # ================= 通知 =================
    nr = NotificationRepository(db)
    nr.create(user_id=user.id, type="info", title="欢迎使用启明星", content="你的个人操作系统已就绪，方向启明，人生推演。", is_read=False)
    nr.create(user_id=user.id, type="success", title="PRD 文档已生成摘要", content="《项目架构设计笔记》已自动生成摘要，可查看并应用。", is_read=False, source_type="document")
    nr.create(user_id=user.id, type="warning", title="有任务即将逾期", content="路演彩排、赛前冲刺方案即将到期，请留意。", is_read=False, source_type="task")
    nr.create(user_id=user.id, type="info", title="周报已自动填充", content="本周复盘数据已自动汇总，可一键转为周报。", is_read=True, source_type="review")
    nr.create(user_id=user.id, type="success", title="灵感已生成", content="基于《路演脚本-v1》生成了一条新灵感。", is_read=False, source_type="document")
    nr.create(user_id=user.id, type="info", title="备份已完成", content="上周数据已自动备份到本地 backups 目录。", is_read=True)

    return True
