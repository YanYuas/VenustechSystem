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
    """加密明文。返回带前缀的密文：dpapi:… 或 plain:…"""
    if _DPAPI_AVAILABLE:
        blob = win32crypt.CryptProtectData(
            plaintext.encode("utf-8"),
            desc="Venustech API Key",
        )
        return "dpapi:" + base64.b64encode(blob).decode("ascii")
    # 降级：仅混淆，非安全 —— 开发期可用
    return "plain:" + base64.b64encode(plaintext.encode("utf-8")).decode("ascii")


def decrypt_secret(ciphertext: str) -> str:
    """解密密文。"""
    if ciphertext.startswith("plain:"):
        return base64.b64decode(ciphertext[6:]).decode("utf-8")
    if ciphertext.startswith("dpapi:") and _DPAPI_AVAILABLE:
        blob = base64.b64decode(ciphertext[6:])
        _, decrypted = win32crypt.CryptUnprotectData(blob)
        return decrypted.decode("utf-8")
    raise ValueError("无法解密：DPAPI 不可用")
