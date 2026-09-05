# ============================================================
# 认证 / 用户配置（PRD §13.2）
# ============================================================
from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.response import success
from app.core.security import decrypt_secret, encrypt_secret
from app.schemas.auth import (
    ApiVerifyResult,
    InitRequest,
    PetPosition,
    UpdateConfigRequest,
    UserConfigOut,
    VerifyApiRequest,
)
from app.services.ai import AIService


if TYPE_CHECKING:
    from app.models.user import User

router = APIRouter(tags=["auth"])


def _user_out(user: User) -> UserConfigOut:
    pet = user.pet_position or {"x": 1770, "y": 880}
    return UserConfigOut(
        nickname=user.nickname,
        avatar=user.avatar_path or "",
        theme=user.theme or "purple",
        api_key_configured=bool(user.api_key_encrypted),
        automation_level=user.automation_level or "L2",
        pet_position=PetPosition(x=pet.get("x", 1770), y=pet.get("y", 880)),
        pet_topmost=user.pet_topmost,
        inspiration_probability=user.inspiration_probability or 60,
        ai_enabled=user.ai_enabled,
    )


_FIELD_MAP = {
    "nickname": "nickname",
    "avatar": "avatar_path",
    "theme": "theme",
    "automation_level": "automation_level",
    "pet_topmost": "pet_topmost",
    "inspiration_probability": "inspiration_probability",
    "ai_enabled": "ai_enabled",
}


@router.post("/auth/init")
def init(data: InitRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user.nickname = data.nickname
    if data.api_key:
        user.api_key_encrypted = encrypt_secret(data.api_key)
    db.commit()
    db.refresh(user)
    return success(_user_out(user))


@router.get("/auth/me")
def me(user: User = Depends(get_current_user)):
    return success(_user_out(user))


@router.patch("/auth/me")
def update_me(data: UpdateConfigRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    payload = data.model_dump(exclude_unset=True)
    for key, value in payload.items():
        if key in _FIELD_MAP and value is not None:
            setattr(user, _FIELD_MAP[key], value)
    if "pet_position" in payload and payload["pet_position"] is not None:
        pet = payload["pet_position"]
        user.pet_position = {"x": pet.x, "y": pet.y}
    db.commit()
    db.refresh(user)
    return success(_user_out(user))


@router.post("/auth/verify-api")
async def verify_api(data: VerifyApiRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    api_key = data.api_key.strip()
    result: ApiVerifyResult = await AIService(db, user).verify_api(api_key)
    return success(result)
