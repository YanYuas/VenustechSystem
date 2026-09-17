# ============================================================
# 用户配置 Schema（PRD §15.11）
# ============================================================
from __future__ import annotations

from pydantic import BaseModel, Field


class SettingsOut(BaseModel):
    """配置字典。所有值统一为字符串，布尔用 'true' / 'false'。"""

    values: dict[str, str]


class UpdateSettingsRequest(BaseModel):
    values: dict[str, str] = Field(..., description="待写入的键值对（批量）")
