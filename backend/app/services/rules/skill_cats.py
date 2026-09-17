# ============================================================
# 技能分类表（S6-2 · 成长体系之技能树）
#
# 来源：交付物 A《地球Online（大学版）》assets/js/app.js 的 SKILL_CATS
#       （源文件 L1094–L1117）
#
# 生成方式：**脚本提取，非手工转录**
#   python scripts/extract_skill_cats.py
#   如需增删分类或关键词，改本文件即可（引擎侧无需改动）。
#
# 规模：22 个分类 / 164 个关键词（实测）
#
# 与源注释的差异（以实测为准）
#   源注释写的是「技能分类（30个，自动识别 + 等级累计）」，
#   但实际只有 22 条。注释与数据不一致时以数据为准 ——
#   本文件由提取器生成并带规模断言，不会被注释误导。
#
# 已知局限（需后续处理，勿当 bug 修）
#   分类偏建筑/校园场景（含「建筑建造」及 sketchup / rhino / 评图 等关键词），
#   与启明星「自由职业者 / 创业者 / 开发者」画像不完全匹配。
#   本表是纯数据，**扩容不需要改任何代码**，故先原样迁入不缩水。
# ============================================================
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SkillCat:
    """技能分类：id 稳定标识、name 展示名、kws 关键词（用于自动归类）。"""

    id: str
    name: str
    kws: tuple[str, ...]


SKILL_CATS: tuple[SkillCat, ...] = (
    SkillCat(
        id="photography",
        name="摄影",
        kws=("摄影", "拍照", "拍片", "相机", "photo", "camera", "shoot", "vlog", "视频", "录像", "拍",),
    ),
    SkillCat(
        id="writing",
        name="写作",
        kws=("写", "文章", "投稿", "稿", "博客", "日记", "公众号", "文案", "创作",),
    ),
    SkillCat(
        id="reading",
        name="阅读",
        kws=("阅读", "读书", "看书", "书评", "读完", "读完一本",),
    ),
    SkillCat(
        id="design",
        name="设计",
        kws=("设计", "海报", "排版", "UI", "插画", "ps", "ai", "figma", "sketch", "构图",),
    ),
    SkillCat(
        id="coding",
        name="编程",
        kws=("代码", "编程", "开发", "debug", "程序", "算法", "leetcode", "python", "java", "js", "vue", "sql",),
    ),
    SkillCat(
        id="speaking",
        name="演讲",
        kws=("演讲", "present", "分享", "上台", "汇报", "答辩", "路演", "ppt", "宣讲",),
    ),
    SkillCat(
        id="art",
        name="绘画",
        kws=("画", "插画", "油画", "水彩", "素描", "手绘", "板绘",),
    ),
    SkillCat(
        id="data",
        name="数据分析",
        kws=("分析", "数据", "pandas", "统计", "excel", "表格", "spss",),
    ),
    SkillCat(
        id="study",
        name="学业",
        kws=("课程", "上课", "毕业", "绩点", "gpa", "考试", "模考", "期末",),
    ),
    SkillCat(
        id="language",
        name="语言",
        kws=("雅思", "托福", "口语", "背单词", "英语", "法语", "日语", "韩语", "单词",),
    ),
    SkillCat(
        id="travel",
        name="旅行",
        kws=("旅行", "出行", "旅游", "city walk", "citywalk", "独自旅行", "去看看",),
    ),
    SkillCat(
        id="sport",
        name="运动",
        kws=("运动", "跑步", "羽毛球", "篮球", "足球", "瑜伽", "健身房", "锻炼", "打球",),
    ),
    SkillCat(
        id="work",
        name="实习工作",
        kws=("实习", "工作", "求职", "面试", "简历", "公司", "入职",),
    ),
    SkillCat(
        id="project",
        name="项目比赛",
        kws=("项目", "比赛", "竞赛", "参赛", "作品集", "黑客松", "hackathon",),
    ),
    SkillCat(
        id="build",
        name="建筑建造",
        kws=("建筑", "建造", "模型", "立面", "剖面", "sketchup", "rhino", "cad", "评图",),
    ),
    SkillCat(
        id="media",
        name="视频制作",
        kws=("视频", "剪辑", "短片", "剪映", "pr", "导演", "vlog",),
    ),
    SkillCat(
        id="idea",
        name="灵感想法",
        kws=("灵感", "想法", "创意", "突然想到",),
    ),
    SkillCat(
        id="plan",
        name="策划组织",
        kws=("策划", "组织", "安排", "协调", "管理", "统筹",),
    ),
    SkillCat(
        id="doc",
        name="文档材料",
        kws=("文档", "材料", "报告", "纪要", "汇总",),
    ),
    SkillCat(
        id="survey",
        name="探索发现",
        kws=("探索", "发现", "调研", "考察", "田野",),
    ),
    SkillCat(
        id="mount",
        name="户外登山",
        kws=("登山", "徒步", "露营", "爬山", "户外",),
    ),
    SkillCat(
        id="find",
        name="方向定位",
        kws=("方向", "定位", "目标", "定位", "人生方向",),
    ),
)


SKILL_CAT_BY_ID: dict[str, SkillCat] = {c.id: c for c in SKILL_CATS}


__all__ = ["SKILL_CATS", "SKILL_CAT_BY_ID", "SkillCat"]
