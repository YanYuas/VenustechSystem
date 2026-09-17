# ============================================================
# 身份 Schema（三期 B 阶段）
# ============================================================
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class IdentityOut(BaseModel):
    id: str
    name: str
    slug: str
    color_token: str
    icon: str
    description: str | None = None
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CreateIdentityRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=60)
    slug: str = Field(..., min_length=1, max_length=60, pattern=r"^[a-z0-9][a-z0-9-]*$")
    color_token: str = Field("primary", max_length=40, pattern=r"^[a-z][a-z0-9-]*$")
    icon: str = Field("star", max_length=40)
    description: str | None = Field(None, max_length=500)
    sort_order: int = 0


class UpdateIdentityRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=60)
    color_token: str | None = Field(None, max_length=40, pattern=r"^[a-z][a-z0-9-]*$")
    icon: str | None = Field(None, max_length=40)
    description: str | None = Field(None, max_length=500)
    sort_order: int | None = None
    is_active: bool | None = None
