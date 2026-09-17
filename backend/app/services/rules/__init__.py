"""规则引擎（S6-1）：离线可用的领域知识库与学习计划生成。

设计意图：**让「没配 API Key」不再是能力悬崖。**

未配 Key 时，AIService 会降级为 MockLLMClient（只复读用户输入）。
本包提供一条真正的降级路径：13 个领域、52 个能力单元、90 条带达标标准
的任务全部内置为常量，**纯规则、零外部依赖、离线可用**。
"""
from app.services.rules.domain_lib import DOMAIN_LIB, DomainDef, TaskDef, UnitDef

__all__ = ["DOMAIN_LIB", "DomainDef", "TaskDef", "UnitDef"]
