# ============================================================
# 加密与安全 API（M09 P1）
# ============================================================
from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.encryption import get_encryption
from app.core.response import success
from app.services.security_service import SecurityService, audit, list_audit, require_unlocked

if TYPE_CHECKING:
    from app.models.user import User

router = APIRouter(prefix="/security", tags=["security"])


class EncryptRequest(BaseModel):
    data: str


class RotateRequest(BaseModel):
    new_master_key: str | None = None


class DecryptRequest(BaseModel):
    token: str


@router.get("/status")
def encryption_status():
    """加密状态"""
    enc = get_encryption()
    if enc:
        return success(enc.get_status())
    return success({"available": False, "reason": "加密模块未初始化"})


@router.post("/encrypt")
def encrypt_data(req: EncryptRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """加密文本数据（mod-platform P0：需保险箱已解锁）"""
    require_unlocked(user.id)
    enc = get_encryption()
    if not enc or not enc.is_available:
        audit(db, user.id, "security.encrypt", ok=False, detail="加密后端不可用")
        raise HTTPException(status_code=503, detail="加密功能不可用")
    audit(db, user.id, "security.encrypt", ok=True)
    encrypted = enc.encrypt(req.data)
    return success({"encrypted": encrypted.decode("utf-8")})


@router.post("/decrypt")
def decrypt_data(req: DecryptRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """解密文本数据（mod-platform P0：需保险箱已解锁）"""
    require_unlocked(user.id)
    enc = get_encryption()
    if not enc or not enc.is_available:
        raise HTTPException(status_code=503, detail="加密功能不可用")
    try:
        decrypted = enc.decrypt(req.token)
        audit(db, user.id, "security.decrypt", ok=True)
        return success({"decrypted": decrypted})
    except ValueError as e:
        audit(db, user.id, "security.decrypt", ok=False, detail=str(e)[:200])
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/key/rotate")
def rotate_key(
    body: RotateRequest | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """轮换加密密钥 —— **并重加密全部历史密文**（旧实现会丢数据）"""
    require_unlocked(user.id)
    try:
        res = SecurityService(db, user.id).rotate_key(body.new_master_key if body else None)
    except Exception as e:
        audit(db, user.id, "security.rotate_key", ok=False, detail=str(e)[:200])
        raise
    audit(db, user.id, "security.rotate_key", ok=True, detail=f"rotated={res['rotated']}")
    return success(res)


@router.get("/audit")
def get_audit(limit: int = 50, db: Session = Depends(get_db),
              user: User = Depends(get_current_user)):
    """安全审计日志（最近 N 条，倒序）"""
    return success({"items": list_audit(db, user.id, limit)})
