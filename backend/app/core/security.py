# ============================================================
# 敏感信息加密（API Key）
# 一期：Windows DPAPI（pywin32）→ 未装时安全降级为 base64 占位
# TODO(D07): 二期强制 DPAPI，降级标记仅用于开发
# ============================================================
from __future__ import annotations

import base64

try:  # Windows DPAPI，未装 pywin32 时降级
    import win32crypt  # type: ignore
    _DPAPI_AVAILABLE = True
except ImportError:  # pragma: no cover
    _DPAPI_AVAILABLE = False


def encrypt_secret(plaintext: str) -> str:
    """加密明文。返回带前缀的密文：dpapi:…

    安全修正（mod-platform P0）：DPAPI 不可用时**不再静默降级为 base64
    占位**（那等于明文落库）。非开发环境直接拒绝写入，逼迫显式处理。
    """
    if _DPAPI_AVAILABLE:
        blob = win32crypt.CryptProtectData(
            plaintext.encode("utf-8"),
            desc="Venustech API Key",
        )
        return "dpapi:" + base64.b64encode(blob).decode("ascii")
    # 回退 1：Fernet（AES-128-CBC+HMAC，文件密钥，真实加密）—— 不是明文
    from app.core.encryption import get_encryption

    enc = get_encryption()
    if enc is not None and enc.is_available:
        return "fernet:" + enc.encrypt(plaintext).decode()

    # 回退 2：仅开发模式允许占位（本地跑通流程用），生产一律拒绝
    from app.config import get_settings

    if get_settings().dev:
        return "plain:" + base64.b64encode(plaintext.encode("utf-8")).decode("ascii")
    raise RuntimeError(
        "无可用加密后端（DPAPI 与 Fernet 均不可用）且当前非开发模式：拒绝以明文存储密钥"
    )


def decrypt_secret(ciphertext: str) -> str:
    """解密密文。支持 dpapi: / fernet: / plain:（仅历史兼容读取）。"""
    if ciphertext.startswith("plain:"):
        return base64.b64decode(ciphertext[6:]).decode("utf-8")
    if ciphertext.startswith("fernet:"):
        from app.core.encryption import get_encryption

        enc = get_encryption()
        if enc is None or not enc.is_available:
            raise ValueError("无法解密：Fernet 加密后端不可用")
        return enc.decrypt(ciphertext[7:])
    if ciphertext.startswith("dpapi:") and _DPAPI_AVAILABLE:
        blob = base64.b64decode(ciphertext[6:])
        _, decrypted = win32crypt.CryptUnprotectData(blob)
        return decrypted.decode("utf-8")
    raise ValueError("无法解密：密文格式不支持或对应后端不可用")
