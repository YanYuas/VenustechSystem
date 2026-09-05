# ============================================================
# 认证 / 用户配置 schema（对齐前端 types/user.ts）
# ============================================================
from __future__ import annotations

from pydantic import BaseModel, Field


class PetPosition(BaseModel):
    x: int = 1770
    y: int = 880


class UserConfigOut(BaseModel):
    nickname: str
    avatar: str = ""
    theme: str = "purple"
    api_key_configured: bool = False
    automation_level: str = "L2"
    pet_position: PetPosition = Field(default_factory=PetPosition)
    pet_topmost: bool = True
    inspiration_probability: int = 60
    ai_enabled: bool = True


class InitRequest(BaseModel):
    nickname: str = Field(min_length=1, max_length=50)
    api_key: str = ""


class UpdateConfigRequest(BaseModel):
    nickname: str | None = Field(default=None, max_length=50)
    avatar: str | None = None
    theme: str | None = None
    automation_level: str | None = None
    pet_position: PetPosition | None = None
    pet_topmost: bool | None = None
    inspiration_probability: int | None = Field(default=None, ge=0, le=100)
    ai_enabled: bool | None = None


class ApiVerifyResult(BaseModel):
    valid: bool
    model: str = ""


class VerifyApiRequest(BaseModel):
    api_key: str = ""
