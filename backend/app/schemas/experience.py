# ============================================================
# 经历视图 Schema（S6-4）
#
# 铁律（总路线 R1）：**不新建经历表**。经历 = 四源（日记/复盘/
# 分身记忆/项目记忆）在读取时的聚合视图 —— 只在此处归并展示，
# 存储仍然是四张源表各自一份真相。
# ============================================================
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ExperienceSource = Literal["diary", "review", "avatar_memory", "project_memory"]


class ExperienceItem(BaseModel):
    id: str
    source: ExperienceSource
    source_label: str
    title: str
    snippet: str | None = None
    identity_id: str | None = None
    occurred_at: datetime


class ExperienceOut(BaseModel):
    items: list[ExperienceItem]
    total: int
    page: int
    page_size: int
    # 各源条数（当前过滤条件下），前端可用于空态提示
    source_counts: dict[str, int] = Field(default_factory=dict)
