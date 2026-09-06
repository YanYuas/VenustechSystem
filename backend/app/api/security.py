# ============================================================
# 加密与安全 API（M09 P1）
# ============================================================
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.encryption import get_encryption
from app.core.response import success

router = APIRouter(prefix="/security", tags=["security"])


class EncryptRequest(BaseModel):
    data: str


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
def encrypt_data(req: EncryptRequest):
    """加密文本数据"""
    enc = get_encryption()
    if not enc or not enc.is_available:
        raise HTTPException(status_code=503, detail="加密功能不可用")
    encrypted = enc.encrypt(req.data)
    return success({"encrypted": encrypted.decode("utf-8")})


@router.post("/decrypt")
def decrypt_data(req: DecryptRequest):
    """解密文本数据"""
    enc = get_encryption()
    if not enc or not enc.is_available:
        raise HTTPException(status_code=503, detail="加密功能不可用")
    try:
        decrypted = enc.decrypt(req.token)
        return success({"decrypted": decrypted})
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/key/rotate")
def rotate_key():
    """轮换加密密钥"""
    enc = get_encryption()
    if not enc or not enc.is_available:
        raise HTTPException(status_code=503, detail="加密功能不可用")
    enc.rotate_key()
    return success({"rotated": True})