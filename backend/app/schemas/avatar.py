# ============================================================
# 第二分身 schema（二期 P1）
# ============================================================
from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class AvatarMemoryOut(BaseModel):
    id: str
    user_id: str
    memory_type: str  # profile/knowledge/event/relation
    category: str | None = None
    title: str
    content: str | None = None
    tags: list = []
    source: str | None = None
    source_id: str | None = None
    confidence: float = 1.0
    is_verified: bool = False
    importance: int = 3
    # 身份轴（三期 B）
    identity_id: str | None = None
    created_at: datetime
    updated_at: datetime


class CreateMemoryRequest(BaseModel):
    memory_type: str = Field(pattern="^(profile|knowledge|event|relation)$")
    category: str | None = None
    title: str = Field(min_length=1, max_length=200)
    content: str | None = None
    tags: list = []
    source: str | None = None
    importance: int = Field(ge=1, le=5, default=3)
    # 身份轴（三期 B）：可空 = 未归类
    identity_id: str | None = None


class AvatarInspirationOut(BaseModel):
    id: str
    user_id: str
    title: str
    description: str | None = None
    domain: str | None = None
    estimated_value: str | None = None
    prompt: str | None = None
    result: str | None = None
    status: str  # generated/selected/executing/completed/discarded
    feedback: str | None = None  # useful/useless/normal
    batch_id: str | None = None
    source_type: str = "active"
    created_at: datetime
    updated_at: datetime


class GenerateInspirationRequest(BaseModel):
    domain: str | None = None
    count: int = Field(ge=1, le=10, default=3)
    source_type: str = "active"


class AvatarConfigOut(BaseModel):
    id: str
    user_id: str
    automation_level: str = "L2"
    local_model_enabled: bool = False
    local_model_provider: str | None = None
    local_model_name: str | None = None
    local_model_url: str | None = None
    cloud_model_enabled: bool = True
    cloud_model_provider: str | None = None
    cloud_model_name: str | None = None
    persona_name: str = "启明星"
    persona_setting: str | None = None
    inspiration_enabled: bool = True
    inspiration_frequency: str = "manual"
    inspiration_domains: list = []
    reply_length: str = "medium"
    language_style: str = "professional"
    creativity: float = 0.7
    operation_overrides: dict = {}
    updated_at: datetime


class UpdateConfigRequest(BaseModel):
    automation_level: str | None = None
    local_model_enabled: bool | None = None
    local_model_provider: str | None = None
    local_model_name: str | None = None
    local_model_url: str | None = None
    cloud_model_enabled: bool | None = None
    cloud_model_provider: str | None = None
    cloud_model_name: str | None = None
    cloud_api_key: str | None = None
    persona_name: str | None = None
    persona_setting: str | None = None
    inspiration_enabled: bool | None = None
    inspiration_frequency: str | None = None
    inspiration_domains: list | None = None
    reply_length: str | None = None
    language_style: str | None = None
    creativity: float | None = None
    operation_overrides: dict | None = None
