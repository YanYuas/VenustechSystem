# ============================================================
# 领域知识库（S6-1 · 阶段六「外部交付物内核融合」）
#
# 来源：交付物 A《地球Online（大学版）》assets/js/app.js 的 DOMAIN_LIB
#       （源文件 3380 行中的 L1653–L1952）
#
# 生成方式：**脚本提取，非手工转录**
#   python scripts/extract_domain_lib.py
#   路径为「括号匹配切片 → Node 求值 → JSON → Python 源码」，
#   以保证 90 条中文长文本零错漏、且完整性可被断言锁定。
#   **如需扩充或修正领域库，请改本文件并同步更新上面的断言基线。**
#
# 规模：13 领域 / 52 能力单元 / 90 条任务
#       其中带「达标标准」90/90（100%）
#       标记「可重复练习」25 条
#
# 为什么这块值得整体迁入（而不是重写）：
#   每条任务都写了**做到什么程度算完成**（standard），且 90 条无一遗漏。
#   这不是「多练多听」式的泛泛建议，而是可直接执行、且有验收标准的
#   真实内容投入 —— 也是交付物 A 里最不可替代的资产。
#
# 字段命名规范化（括号内为源头字段，便于对照与更新）：
#   TaskDef.task        做什么        (do)
#   TaskDef.duration    预估时长      (time)
#   TaskDef.acceptance  达标标准      (standard)
#   TaskDef.repeatable  可重复练习    (repeat)
#   TaskDef.beginner_only 零基础专用  (beginnerOnly)
#
# 关于 beginner_only 的现状（已核对，**不是遗漏，请勿当 bug 修**）：
#   源数据把该标记标在**任务**层级，而源实现的 buildUnitDefs() 读取的是
#   **单元**层级 `u.beginnerOnly` —— 读到的恒为 undefined，即该过滤
#   **从未生效过**。本模块忠实保留数据，但**刻意不实现这个过滤**：
#   源作者的本意到底是「过滤整个单元」还是「过滤单条任务」，无法从
#   代码推断，贸然实现等于发明一种未经证实的行为。
#   待有明确产品输入后再决定是否启用（届时需同时补单元级字段）。
# ============================================================
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TaskDef:
    """单条学习任务（四要素见文件头字段对照）。"""

    task: str
    duration: str
    acceptance: str
    repeatable: bool = False
    beginner_only: bool = False


@dataclass(frozen=True)
class UnitDef:
    """能力单元：围绕同一能力点的一组任务。"""

    name: str
    tasks: tuple[TaskDef, ...]


@dataclass(frozen=True)
class DomainDef:
    """学习领域：含匹配模式（正则源码）与最终验证任务。"""

    key: str
    name: str
    patterns: tuple[str, ...]
    verify_task: str
    units: tuple[UnitDef, ...]


# 匹配用正则在引擎侧统一以 re.IGNORECASE 编译，
# 对应源实现「先 toLowerCase() 再 test()」的语义。
DOMAIN_LIB: tuple[DomainDef, ...] = (
    DomainDef(
        key="ielts",
        name="雅思",
        patterns=("雅思|ielts",),
        verify_task="完整模拟一次雅思考试：听力+阅读+写作+口语同一天完成（口语录音、写作手写），按官方标准给自己估一个总分，并把这次经历记录下来。",
        units=(
            UnitDef(
                name="听力 · 精听与定位",
                tasks=(
                    TaskDef(
                        task="做一篇剑桥雅思听力 Section 1：第一遍正常做题；第二遍逐句暂停，把没听出来的词全部写下来，按\"不认识 / 认识但没反应过来 / 连读吞音\"分类",
                        duration="40分钟",
                        acceptance="一页分类清单，至少 10 个词",
                    ),
                    TaskDef(
                        task="练定位法：读题时先圈出关键词（数字/专有名词/转折词），听的时候只盯关键词前后，不追求听懂每个词",
                        duration="30分钟",
                        acceptance="能说出每道题自己是靠哪个词定位到的",
                    ),
                    TaskDef(
                        task="精听一段 Section 3 学术对话：逐句听写，一句最多重播 3 遍，然后对照原文用红笔标出听错的地方",
                        duration="40分钟",
                        acceptance="听写准确率 70% 以上",
                    ),
                    TaskDef(
                        task="限时完成一个完整 Section 并对答案，把错题原因分成\"走神 / 词汇不认识 / 连读没听出 / 语速跟不上\"四类，找出今天最主要的一种",
                        duration="35分钟",
                        acceptance="失分主因明确，写在笔记里",
                        repeatable=True,
                    ),
                ),
            ),
            UnitDef(
                name="阅读 · 定位与同义替换",
                tasks=(
                    TaskDef(
                        task="限时 20 分钟完成一篇雅思阅读真题，做完把错题分成\"没定位到 / 没认出同义替换 / 句子没读懂 / 时间不够\"，找出今天最主要的失分原因",
                        duration="40分钟",
                        acceptance="错题全部归因，主因明确",
                        repeatable=True,
                    ),
                    TaskDef(
                        task="把今天做过的阅读里\"题目↔原文\"的同义替换抄成词对卡片（例如 rely on → depend on）",
                        duration="25分钟",
                        acceptance="至少 8 组替换词对",
                    ),
                    TaskDef(
                        task="挑一篇剑桥阅读，把其中的长难句逐句翻译成中文写下来，再对照官方译文检查偏差",
                        duration="40分钟",
                        acceptance="独立翻出 10 个长难句",
                    ),
                    TaskDef(
                        task="专攻一种你最错的题型（判断题/段落匹配/填空），连做 4 组同题型，总结出自己的三步解题流程",
                        duration="45分钟",
                        acceptance="写出自己的解题步骤（3 步以上）",
                    ),
                ),
            ),
            UnitDef(
                name="写作 · 大小作文",
                tasks=(
                    TaskDef(
                        task="搭 Task 1 框架：开头一句改写题目 + 两个主体段（各写一个最明显的趋势或对比）+ 结尾一句总括；用一套剑桥真题的数据亲手写一遍",
                        duration="30分钟",
                        acceptance="能不看范例默写框架",
                    ),
                    TaskDef(
                        task="限时 25 分钟写一篇 Task 1，写完找一篇 7 分范文逐句对照，圈出范文有而你没有的数据表达",
                        duration="50分钟",
                        acceptance="一篇完整小作文 + 一张差距清单",
                    ),
                    TaskDef(
                        task="给 5 个 Task 2 高频话题（教育/科技/环境/工作/社会）各列一份提纲：观点 + 2 个支持理由 + 1 个反例，不写全文",
                        duration="35分钟",
                        acceptance="5 份提纲，每份 3 分钟内能口头展开",
                    ),
                    TaskDef(
                        task="限时 40 分钟写一篇 Task 2 大作文，写完用三问自查：观点有没有回应题目？每段有没有例子？连接词是不是只会用 however？",
                        duration="50分钟",
                        acceptance="一篇完整大作文 + 自查结果",
                        repeatable=True,
                    ),
                ),
            ),
            UnitDef(
                name="口语 · Part 1/2/3",
                tasks=(
                    TaskDef(
                        task="把当季口语题库 Part 1 的 20 个话题各回答一遍并录音，回听标出所有卡壳超过 3 秒的地方",
                        duration="40分钟",
                        acceptance="20 段录音 + 卡壳清单",
                    ),
                    TaskDef(
                        task="做 Part 2 素材卡：准备 5 张\"人物 / 地点 / 经历 / 物品 / 想法\"素材卡，尝试用同一张卡覆盖 2 个不同话题",
                        duration="40分钟",
                        acceptance="5 张素材卡，每张能讲满 2 分钟",
                    ),
                    TaskDef(
                        task="随机抽一个 Part 2 话题，限时 1 分钟准备，录音说满 2 分钟；回听数一下\"emm / 就是说\"出现的次数并记下来",
                        duration="20分钟",
                        acceptance="一段 2 分钟录音 + 口头禅统计",
                        repeatable=True,
                    ),
                    TaskDef(
                        task="练 Part 3 思路：抽 5 道抽象题，用\"直接回答 → 两个角度 → 举一个例子\"的结构口头回答并录音",
                        duration="30分钟",
                        acceptance="5 段结构完整的录音",
                    ),
                ),
            ),
            UnitDef(
                name="整套真题实战",
                tasks=(
                    TaskDef(
                        task="按考试时间完整做一套剑桥真题：听力 40 分钟 + 阅读 60 分钟连做、中间不休息；对答案算分，写三行复盘——哪里掉分最多 / 为什么 / 明天补哪块",
                        duration="约 3 小时（可拆两个半天）",
                        acceptance="一套完整成绩 + 三行复盘",
                        repeatable=True,
                    ),
                ),
            ),
        ),
    ),
    DomainDef(
        key="eng-exam",
        name="英语考试",
        patterns=("托福|toefl|四六级|四级|六级|cet|考研英语|专四|专八",),
        verify_task="按考试时间完整做一套真题并算分，写三行复盘：哪里掉分最多、为什么、接下来补哪块，并记录为一段真实经历。",
        units=(
            UnitDef(
                name="听力 · 精听",
                tasks=(
                    TaskDef(
                        task="精听一篇真题听力：第一遍做题，第二遍逐句暂停跟读，把没听出来的词按\"不认识 / 没反应过来 / 连读吞音\"分类记录",
                        duration="40分钟",
                        acceptance="一页分类清单，至少 10 个词",
                    ),
                    TaskDef(
                        task="限时做一套听力真题，对答案后把错题原因分成\"走神 / 词汇 / 语速 / 题没读完\"四类，找出主要失分原因",
                        duration="35分钟",
                        acceptance="失分主因明确",
                        repeatable=True,
                    ),
                ),
            ),
            UnitDef(
                name="阅读 · 定位与替换",
                tasks=(
                    TaskDef(
                        task="限时做一篇阅读真题，把错题分成\"没定位到 / 没认出同义替换 / 句子没读懂 / 时间不够\"，找出今天最主要的失分原因",
                        duration="35分钟",
                        acceptance="错题全部归因",
                        repeatable=True,
                    ),
                    TaskDef(
                        task="把这篇阅读里题目和原文的同义替换抄成词对卡片",
                        duration="25分钟",
                        acceptance="至少 8 组替换词对",
                    ),
                ),
            ),
            UnitDef(
                name="写作与词汇",
                tasks=(
                    TaskDef(
                        task="限时写一篇考试作文，写完对照一篇高分范文逐句圈出差距（哪里没例子 / 哪里连接生硬 / 哪个表达中式）",
                        duration="50分钟",
                        acceptance="一篇作文 + 一张差距清单",
                    ),
                    TaskDef(
                        task="背一篇高分范文后合上默写，对照原文标出漏掉的连接词和好表达，抄进自己的本子",
                        duration="30分钟",
                        acceptance="默写还原 80% 以上",
                    ),
                    TaskDef(
                        task="记一组真题高频词（50 个）：先全部过一遍，只挑出\"完全不认识\"的重点背，背完让同学抽 20 个",
                        duration="40分钟",
                        acceptance="抽查 20 个对 18 个",
                    ),
                ),
            ),
            UnitDef(
                name="整套真题实战",
                tasks=(
                    TaskDef(
                        task="按考试时间完整做一套真题（含作文），对答案算分，写三行复盘：哪里掉分最多 / 为什么 / 明天补哪块",
                        duration="约 2.5 小时（可拆两个半天）",
                        acceptance="一套完整成绩 + 三行复盘",
                        repeatable=True,
                    ),
                ),
            ),
        ),
    ),
    DomainDef(
        key="eng-speaking",
        name="英语口语",
        patterns=("英语口语|口语|spoken|英音|美音|英文对话|和外国人",),
        verify_task="和真人进行一次 15 分钟以上的全英文对话（语伴/外教/同学均可），结束后写下 3 句当时想说但没说出来的话。",
        units=(
            UnitDef(
                name="发音与语调",
                tasks=(
                    TaskDef(
                        task="选一段 1 分钟的英文视频做 shadowing：听一句跟一句，模仿到语调几乎一样，录下来和原音对比",
                        duration="30分钟",
                        acceptance="录音和原音听不出明显语调差异",
                    ),
                ),
            ),
            UnitDef(
                name="日常表达",
                tasks=(
                    TaskDef(
                        task="用英语自言自语描述今天做了什么并录音 3 分钟；回听记下 3 处卡壳，查好说法后再录一遍",
                        duration="20分钟",
                        acceptance="两版录音，第二版卡壳明显减少",
                    ),
                    TaskDef(
                        task="随机抽一个话题，用\"观点 + 两个理由 + 一个例子\"的结构口头说满 2 分钟并录音",
                        duration="20分钟",
                        acceptance="一段结构完整的 2 分钟录音",
                        repeatable=True,
                    ),
                ),
            ),
            UnitDef(
                name="真实对话",
                tasks=(
                    TaskDef(
                        task="和真人用英语对话 15 分钟（语伴/外教/同学），结束后写下 3 句当时没说出来的句子",
                        duration="15分钟",
                        acceptance="对话真的发生了 + 3 句补充",
                        repeatable=True,
                    ),
                ),
            ),
        ),
    ),
    DomainDef(
        key="photography",
        name="摄影",
        patterns=("摄影|相机|拍人像|手动模式|单反|微单|拍照",),
        verify_task="使用手动模式（M档），独立完成一组 8 张以上的人像作品并做基础后期，发给被拍的人确认满意。",
        units=(
            UnitDef(
                name="曝光三要素",
                tasks=(
                    TaskDef(
                        task="用同一个场景拍 9 张照片：3 张只改光圈、3 张只改快门、3 张只改 ISO，每组记下参数；最后不看教程，自己说出三个参数分别控制什么、互相怎么影响",
                        duration="45分钟",
                        acceptance="9 张照片 + 能独立讲清三要素",
                    ),
                    TaskDef(
                        task="用 M 档在室内拍一张曝光正常的照片，只允许看直方图判断曝光，不许靠屏幕效果猜",
                        duration="20分钟",
                        acceptance="直方图不贴左右两侧",
                        repeatable=True,
                    ),
                ),
            ),
            UnitDef(
                name="对焦与景深",
                tasks=(
                    TaskDef(
                        task="拍一组对比照片：同一朵花用最近对焦距离和最远对焦距离各拍一张，再用最大光圈和最小光圈各拍一张，观察背景虚化的变化",
                        duration="30分钟",
                        acceptance="4 张对比照，能说清光圈和对焦距离分别怎么影响虚化",
                    ),
                    TaskDef(
                        task="练手动选对焦点：给会动的对象（人/宠物）拍 10 张，要求每张眼睛都清晰",
                        duration="30分钟",
                        acceptance="10 张里至少 8 张眼睛清晰",
                        repeatable=True,
                    ),
                ),
            ),
            UnitDef(
                name="构图",
                tasks=(
                    TaskDef(
                        task="带着\"三分法、对称、引导线、框架\"四种构图出门拍一小时，每种至少拍 3 张，回家各标出最好的一张",
                        duration="60分钟",
                        acceptance="12 张照片 + 4 张精选",
                    ),
                    TaskDef(
                        task="选一张你最喜欢的照片，分析它的构图、光线和拍摄时机，写 100 字",
                        duration="20分钟",
                        acceptance="一段 100 字的照片分析",
                    ),
                ),
            ),
            UnitDef(
                name="光线",
                tasks=(
                    TaskDef(
                        task="同一个人分别在大中午直射光下、树荫下、傍晚黄金时刻各拍一张半身像，对比皮肤质感和阴影差别",
                        duration="40分钟",
                        acceptance="3 张对比照 + 能说出哪种光最适合人像",
                    ),
                ),
            ),
            UnitDef(
                name="人像实战",
                tasks=(
                    TaskDef(
                        task="给一位朋友拍一组 10 张的人像：拍之前先聊 5 分钟让对方放松，想好 3 个姿势和 2 个机位；拍完挑 3 张做基础后期发给对方",
                        duration="90分钟",
                        acceptance="交付一组人像作品",
                        repeatable=True,
                    ),
                ),
            ),
        ),
    ),
    DomainDef(
        key="video",
        name="视频剪辑",
        patterns=("premiere|剪映|剪辑|剪视频|final cut|达芬奇|vlog|视频制作",),
        verify_task="使用至少 10 段原始素材，独立剪出一条 60 秒以上、带字幕和配乐的完整视频，发布出去或交付给需要的人。",
        units=(
            UnitDef(
                name="素材管理与粗剪",
                tasks=(
                    TaskDef(
                        task="新建项目导入 10 段素材，按\"废镜头 / 可用 / 精选\"分三堆，把精选素材在时间线上粗排一遍，剪出一条 60 秒的无声粗剪",
                        duration="60分钟",
                        acceptance="一条 60 秒粗剪时间线",
                    ),
                    TaskDef(
                        task="只用快捷键（剪切 C / 选择 V）完成一条 30 秒视频的全部剪切，全程不碰鼠标",
                        duration="40分钟",
                        acceptance="全程快捷键完成",
                    ),
                ),
            ),
            UnitDef(
                name="节奏",
                tasks=(
                    TaskDef(
                        task="把同一段素材剪两版：一版平均每 3 秒一个镜头、一版平均每 6 秒一个镜头，配同一首音乐播放对比，写下哪版更合适以及为什么",
                        duration="50分钟",
                        acceptance="两版对比 + 一段判断理由",
                    ),
                ),
            ),
            UnitDef(
                name="音频与字幕",
                tasks=(
                    TaskDef(
                        task="给一条视频做声音处理：BGM 音量压到人声以下、人声降噪、在转场处加一个音效；导出后戴耳机检查人声和音乐不打架",
                        duration="40分钟",
                        acceptance="戴耳机听，人声清晰、音乐不抢",
                    ),
                    TaskDef(
                        task="给一条 2 分钟的视频上完所有字幕：统一字体字号、在安全区内、每句不超过 15 字，看完只需要改 3 处以内",
                        duration="50分钟",
                        acceptance="一条完整字幕视频",
                    ),
                ),
            ),
            UnitDef(
                name="调色与导出",
                tasks=(
                    TaskDef(
                        task="用调色工具给同一条视频调三种风格（明亮日系 / 电影感冷暖对比 / 黑金），导出三个版本对比",
                        duration="50分钟",
                        acceptance="3 个导出版本",
                    ),
                    TaskDef(
                        task="按平台正确规格导出一条 1080p 视频（H.264、码率合理），检查清晰度和文件大小",
                        duration="25分钟",
                        acceptance="导出文件规格正确、清晰度无损",
                    ),
                ),
            ),
            UnitDef(
                name="完整作品",
                tasks=(
                    TaskDef(
                        task="从拍/找素材到剪完发布，独立完成一条 60 秒以上、有明确主题的完整视频（含字幕和配乐）",
                        duration="约 3 小时（可分几天）",
                        acceptance="一条发布出去的成片",
                        repeatable=True,
                    ),
                ),
            ),
        ),
    ),
    DomainDef(
        key="cooking",
        name="做饭",
        patterns=("做饭|烹饪|烧菜|炒菜|厨艺|家常菜|下厨",),
        verify_task="连续 3 天独立完成一荤一素一汤的晚餐，其中至少 2 道菜是第一次做的，家人或室友吃完给出评价。",
        units=(
            UnitDef(
                name="刀工与备菜",
                tasks=(
                    TaskDef(
                        task="练切一盘土豆丝：先切片再切丝，切完把第一根和最后一根摆在一起拍照对比",
                        duration="40分钟",
                        acceptance="最后 5 根明显比前 5 根均匀",
                    ),
                    TaskDef(
                        task="给一顿两人餐做完整备菜：3 个菜的全部食材洗切配好、调料按菜分小碗装好，然后才开火",
                        duration="40分钟",
                        acceptance="开火前所有食材就位",
                    ),
                ),
            ),
            UnitDef(
                name="火候与基础炒",
                tasks=(
                    TaskDef(
                        task="独立完成一道西红柿炒蛋，重点练习判断下锅顺序和火候；做完记录一次\"哪里没做好、下次准备改什么\"",
                        duration="30分钟",
                        acceptance="一道菜 + 一条复盘",
                        repeatable=True,
                    ),
                    TaskDef(
                        task="做一道青椒肉丝，练习\"热锅凉油\"防粘和肉丝滑炒，目标是肉丝不粘锅底、不发柴",
                        duration="40分钟",
                        acceptance="锅底干净、肉丝嫩",
                    ),
                ),
            ),
            UnitDef(
                name="调味",
                tasks=(
                    TaskDef(
                        task="煮三碗同样的清汤面，分别只放盐、盐+糖、盐+糖+一点酱油，尝出层次差别并写下感受",
                        duration="30分钟",
                        acceptance="能说出糖和酱油分别起什么作用",
                    ),
                    TaskDef(
                        task="做一次蛋炒饭，盐分三次放（炒蛋前 / 中途 / 出锅前），体会分次调味和均匀咸味",
                        duration="30分钟",
                        acceptance="蛋炒饭咸味均匀",
                    ),
                ),
            ),
            UnitDef(
                name="家常菜单",
                tasks=(
                    TaskDef(
                        task="独立完成一荤一素一汤的三菜晚餐（如可乐鸡翅 + 清炒时蔬 + 紫菜蛋花汤），全程不看视频，卡住了只看文字菜谱",
                        duration="90分钟",
                        acceptance="三菜同时上桌、温度都在",
                        repeatable=True,
                    ),
                    TaskDef(
                        task="自选一道从没做过的家常菜独立完成，餐后写两行复盘：火候或调味哪里翻车了、下次改什么",
                        duration="60分钟",
                        acceptance="一道新菜 + 两行复盘",
                        repeatable=True,
                    ),
                ),
            ),
        ),
    ),
    DomainDef(
        key="presentation",
        name="Presentation",
        patterns=("presentation|汇报|演讲|脱稿|上台|发言|\\bpre\\b",),
        verify_task="独立准备并脱稿完成一次 5 分钟以上的完整 pre，全程不念稿，并留有录音。",
        units=(
            UnitDef(
                name="内容结构",
                tasks=(
                    TaskDef(
                        task="把你想讲的主题用\"结论先行\"写成一页纸：一句话核心观点 + 3 个支撑理由 + 每个理由 1 个例子",
                        duration="30分钟",
                        acceptance="一页纸讲稿骨架",
                    ),
                    TaskDef(
                        task="给你的 pre 写开头 30 秒的逐字稿并计时读 5 遍，删到 30 秒以内",
                        duration="25分钟",
                        acceptance="开头能在 30 秒内讲完",
                    ),
                ),
            ),
            UnitDef(
                name="幻灯片",
                tasks=(
                    TaskDef(
                        task="把一页字最多的旧 PPT 改成\"一页一个观点 + 一张图 + 不超过 20 字\"，改完给同学看，10 秒内能说出这页讲什么",
                        duration="40分钟",
                        acceptance="通过 10 秒测试",
                    ),
                ),
            ),
            UnitDef(
                name="表达与脱稿",
                tasks=(
                    TaskDef(
                        task="对着手机录一遍 3 分钟的 pre，回看并统计三个数据：\"嗯啊\"次数、眼神离开镜头次数、每分钟语速",
                        duration="25分钟",
                        acceptance="三个数据都记下来",
                    ),
                    TaskDef(
                        task="用关键词卡片法脱稿讲同一内容：每张卡片只写 3 个词，讲 3 遍，最后一遍录音",
                        duration="30分钟",
                        acceptance="能不念稿讲满 3 分钟",
                    ),
                ),
            ),
            UnitDef(
                name="实战与问答",
                tasks=(
                    TaskDef(
                        task="找一位朋友当面讲一遍，请对方随时在你逻辑跳跃的地方喊停，记下所有被喊停的点",
                        duration="30分钟",
                        acceptance="一张\"逻辑断点\"清单",
                    ),
                    TaskDef(
                        task="请朋友针对你的 pre 提 3 个刁钻问题，练习\"停顿 1 秒 → 复述问题 → 分点回答\"的应答结构",
                        duration="25分钟",
                        acceptance="3 个问题都能结构化回答",
                    ),
                ),
            ),
        ),
    ),
    DomainDef(
        key="programming",
        name="编程",
        patterns=("python|编程|代码|写程序|爬虫|学开发|java|前端",),
        verify_task="独立编写一个能实际运行、解决你自己真实问题的小工具（脚本/网页均可），并连续使用一周。",
        units=(
            UnitDef(
                name="环境与第一个程序",
                tasks=(
                    TaskDef(
                        task="装好 Python 和编辑器，写第一个程序：让用户输入生日，输出\"你活了多少天\"",
                        duration="40分钟",
                        acceptance="程序跑通、结果正确",
                        beginner_only=True,
                    ),
                    TaskDef(
                        task="写一个猜数字游戏（1-100，提示大了/小了），写完自己玩一遍验证逻辑",
                        duration="40分钟",
                        acceptance="游戏能正常玩",
                    ),
                ),
            ),
            UnitDef(
                name="语法与逻辑",
                tasks=(
                    TaskDef(
                        task="用循环+条件分别打印：九九乘法表、菱形星号图案、FizzBuzz",
                        duration="50分钟",
                        acceptance="三个输出都正确",
                    ),
                    TaskDef(
                        task="写一个脚本读取一个 txt 文件，统计每个词出现的次数，输出前 10 名",
                        duration="60分钟",
                        acceptance="前 10 名输出正确",
                    ),
                ),
            ),
            UnitDef(
                name="数据与文件",
                tasks=(
                    TaskDef(
                        task="用列表+字典做一个你的书单/影单管理器：能添加、删除、按评分排序，数据存成 JSON 文件",
                        duration="90分钟",
                        acceptance="重启程序后数据还在",
                    ),
                ),
            ),
            UnitDef(
                name="小项目实战",
                tasks=(
                    TaskDef(
                        task="写一个爬虫抓取一个公开网页的标题列表，存成 CSV",
                        duration="90分钟",
                        acceptance="CSV 里至少 20 行数据",
                    ),
                    TaskDef(
                        task="做一个你自己真的会用到的小工具（自动整理下载文件夹 / 周报模板生成器 / 生日提醒都行），写到能用为止",
                        duration="2 小时（可分几天）",
                        acceptance="真的在用它",
                        repeatable=True,
                    ),
                ),
            ),
        ),
    ),
    DomainDef(
        key="design",
        name="设计",
        patterns=("photoshop|figma|海报|平面|学设计|做设计|\\bps\\b|\\bui\\b",),
        verify_task="为一件真实的事（社团招新 / 活动宣传 / 自己的生日会）设计一张完整海报并交付使用。",
        units=(
            UnitDef(
                name="工具基础",
                tasks=(
                    TaskDef(
                        task="做一个\"公众号封面\"尺寸的练习：新建画布、置入图片、打标题、导出，全流程走一遍",
                        duration="40分钟",
                        acceptance="导出一张封面图",
                        beginner_only=True,
                    ),
                    TaskDef(
                        task="临摹一张你觉得好的海报：同样的版式自己重新做一遍（字体和图片可以不同）",
                        duration="90分钟",
                        acceptance="两张对比图放一起看",
                    ),
                ),
            ),
            UnitDef(
                name="排版",
                tasks=(
                    TaskDef(
                        task="做 4 个版本的同一张文字海报：分别只改对齐方式 / 字号对比 / 留白 / 信息层级，感受哪个最清楚",
                        duration="60分钟",
                        acceptance="4 个版本 + 能说出最好的那个为什么好",
                    ),
                ),
            ),
            UnitDef(
                name="配色",
                tasks=(
                    TaskDef(
                        task="从 3 张优秀作品里吸色，各做一套 5 色配色板（主色/辅色/强调色/深/浅），马上用到自己的海报里",
                        duration="40分钟",
                        acceptance="3 套配色板 + 一张用上的海报",
                    ),
                ),
            ),
            UnitDef(
                name="完整产出",
                tasks=(
                    TaskDef(
                        task="为一件真实的事设计一张海报并交付，收集使用者的一条反馈",
                        duration="2 小时（可分几天）",
                        acceptance="有人真的用了你的海报",
                        repeatable=True,
                    ),
                ),
            ),
        ),
    ),
    DomainDef(
        key="drawing",
        name="画画",
        patterns=("画画|素描|插画|手绘|板绘|学画",),
        verify_task="完成一张不少于 1 小时的完整作品（临摹或原创均可），和第一天的练习页放在一起对比。",
        units=(
            UnitDef(
                name="线条",
                tasks=(
                    TaskDef(
                        task="画满一页：直线、曲线、圆各 20 个，要求手不抖、线条收得住；隔天再来一页，两页放一起对比",
                        duration="30分钟",
                        acceptance="第二页明显更稳",
                        repeatable=True,
                    ),
                ),
            ),
            UnitDef(
                name="比例",
                tasks=(
                    TaskDef(
                        task="用铅笔测量法临摹 3 张照片：先定大比例，再抠细节；画完和原图叠在一起找比例错的地方",
                        duration="60分钟",
                        acceptance="3 张临摹 + 错位标注",
                    ),
                ),
            ),
            UnitDef(
                name="明暗",
                tasks=(
                    TaskDef(
                        task="画一个球体的明暗：高光、亮面、明暗交界线、反光、投影五个调子都画出来，只用一支铅笔",
                        duration="40分钟",
                        acceptance="五个调子都能分辨出来",
                    ),
                ),
            ),
            UnitDef(
                name="完整作品",
                tasks=(
                    TaskDef(
                        task="完成一张完整的临摹或写生作品（不少于 1 小时），中途不看手机",
                        duration="60分钟以上",
                        acceptance="一张成品",
                        repeatable=True,
                    ),
                ),
            ),
        ),
    ),
    DomainDef(
        key="writing",
        name="写作",
        patterns=("写作|写文章|写公众号|文案|写小说|写故事",),
        verify_task="独立写一篇结构完整的文章（800 字以上）并公开发布（公众号/知乎/小红书均可）。",
        units=(
            UnitDef(
                name="素材库",
                tasks=(
                    TaskDef(
                        task="建一个素材库（备忘录/笔记本都行），本周每天收集 3 条好素材（金句/故事/数据），周末分类整理",
                        duration="每天 10 分钟",
                        acceptance="21 条素材，至少分 3 类",
                    ),
                ),
            ),
            UnitDef(
                name="结构",
                tasks=(
                    TaskDef(
                        task="拆解 2 篇你喜欢的文章：给每一段标注功能（观点/例子/过渡/金句），然后套这个结构写一篇 500 字短文",
                        duration="90分钟",
                        acceptance="一篇有结构的短文",
                    ),
                ),
            ),
            UnitDef(
                name="开头与修改",
                tasks=(
                    TaskDef(
                        task="给同一个主题写 5 个不同的开头（提问 / 场景 / 金句 / 数据 / 直接冲突），发给朋友选最想读下去的一个",
                        duration="40分钟",
                        acceptance="5 个开头 + 一个投票结果",
                    ),
                    TaskDef(
                        task="把一篇旧文章删掉 30% 的字数且不损失信息，再朗读一遍改掉所有拗口的句子",
                        duration="40分钟",
                        acceptance="更短的版本读起来更顺",
                    ),
                ),
            ),
            UnitDef(
                name="完整产出",
                tasks=(
                    TaskDef(
                        task="写一篇完整的短文并公开发布，24 小时后回来看数据和评论",
                        duration="2 小时（可分几天）",
                        acceptance="公开发布一篇",
                        repeatable=True,
                    ),
                ),
            ),
        ),
    ),
    DomainDef(
        key="guitar",
        name="吉他弹唱",
        patterns=("吉他|尤克里里|ukulele|弹唱",),
        verify_task="不看谱边弹边唱完成一首完整的歌，录下来发给朋友听。",
        units=(
            UnitDef(
                name="基础和弦",
                tasks=(
                    TaskDef(
                        task="学会 C、G、Am、Em 四个和弦：每个按住后从上到下逐根弦弹，保证每根弦都发声清晰",
                        duration="40分钟",
                        acceptance="四个和弦都清晰发声",
                    ),
                ),
            ),
            UnitDef(
                name="和弦转换",
                tasks=(
                    TaskDef(
                        task="练转换：C→G→Am→Em 循环，开节拍器 60bpm，每小节换一次，连续 3 分钟不断",
                        duration="30分钟",
                        acceptance="3 分钟不断",
                        repeatable=True,
                    ),
                ),
            ),
            UnitDef(
                name="节奏与弹唱",
                tasks=(
                    TaskDef(
                        task="练 4 种扫弦节奏型，跟着一首慢歌从头扫到尾",
                        duration="40分钟",
                        acceptance="完整扫完一首歌",
                    ),
                    TaskDef(
                        task="选一首只用这 4 个和弦的歌：先只唱不弹 → 再只弹不唱 → 最后合起来，录一遍",
                        duration="60分钟",
                        acceptance="能边弹边唱完整首",
                    ),
                ),
            ),
        ),
    ),
    DomainDef(
        key="fitness",
        name="健身",
        patterns=("健身|跑步|减脂|增肌|锻炼|运动|引体|马甲线",),
        verify_task="按自己定的每周训练表连续执行 2 周，并记录每次的训练内容和一个能对比的数值（配速/个数/重量）。",
        units=(
            UnitDef(
                name="基础动作模式",
                tasks=(
                    TaskDef(
                        task="学三个基础动作（深蹲 / 俯卧撑 / 平板支撑），每个 3 组；用手机侧面录像，对照标准动作找出自己的 2 个问题",
                        duration="40分钟",
                        acceptance="3 段录像 + 问题清单",
                    ),
                    TaskDef(
                        task="隔天重复：深蹲 3×12、俯卧撑 3×8（跪姿也行）、平板支撑 3×30 秒，和上次的录像对比",
                        duration="30分钟",
                        acceptance="动作比上次标准",
                        repeatable=True,
                    ),
                ),
            ),
            UnitDef(
                name="有氧耐力",
                tasks=(
                    TaskDef(
                        task="慢跑或快走 30 分钟，记下配速和结束时的心率；每周 2-3 次，目标是比第一次更轻松",
                        duration="30分钟",
                        acceptance="配速/心率有记录",
                        repeatable=True,
                    ),
                ),
            ),
            UnitDef(
                name="计划与记录",
                tasks=(
                    TaskDef(
                        task="定一张每周训练表（每周几天、每次练什么），贴在显眼的地方，本周按表完成并打勾",
                        duration="20分钟",
                        acceptance="一张表 + 本周打卡",
                    ),
                    TaskDef(
                        task="记录三天全部饮食，估算热量，找出最大的一个问题（奶茶/夜宵/不吃早餐），只改这一项",
                        duration="20分钟",
                        acceptance="三天记录 + 一个改进",
                    ),
                ),
            ),
        ),
    ),
)


__all__ = ["DOMAIN_LIB", "DomainDef", "TaskDef", "UnitDef"]
