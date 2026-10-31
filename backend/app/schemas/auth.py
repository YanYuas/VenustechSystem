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
    # D-50：与 InitRequest 对齐，PATCH 不允许把昵称置空（前端会显示空白）
    nickname: str | None = Field(default=None, min_length=1, max_length=50)
    # avatar 是头像路径/URL（DB String(500)），不是枚举值；只加长度上限防截断，
    # 资源是否存在由头像资源层负责校验（避免把后端绑死在前端资源目录上）。
    avatar: str | None = Field(default=None, max_length=500)
    # theme 主题包在**前端**应用（cream/guofeng/abyss/epic 存 localStorage），
    # 后端只负责回传该字段；白名单会误拒历史值（purple/dark）并耦合前端主题目录，
    # 因此只按 DB String(20) 加长度上限。
    theme: str | None = Field(default=None, max_length=20)
    automation_level: str | None = None
    pet_position: PetPosition | None = None
    pet_topmost: bool | None = None
    inspiration_probability: int | None = Field(default=None, ge=0, le=100)
    ai_enabled: bool | None = None


class ApiVerifyResult(BaseModel):
    valid: bool
    model: str = ""
    # 失败原因（新增 2026-09-15）：区分「Key 无效」与「网络/服务不可用」，
    # 否则用户会把服务端故障误判为自己 Key 填错，反复重填。默认空串保持向后兼容。
    reason: str = ""


class VerifyApiRequest(BaseModel):
    api_key: str = ""
