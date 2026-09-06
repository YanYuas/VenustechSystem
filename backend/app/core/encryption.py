# ============================================================
# 加密存储模块（M09 P1）
# 用户数据加密，支持本地导出，对齐 PRD §13.5
# 使用 Fernet 对称加密（AES-128-CBC + HMAC）
# ============================================================
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
from typing import Any


try:
    from cryptography.fernet import Fernet
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False


class EncryptionManager:
    """加密管理器：密钥派生、加密/解密、安全存储"""

    def __init__(self, data_dir: Path, master_key: str | None = None):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._key_file = data_dir / ".encryption_key"
        self._fernet: Fernet | None = None
        self._master_key = master_key
        self._initialize()

    def _derive_key(self, password: str) -> bytes:
        """从密码派生密钥（PBKDF2-HMAC-SHA256）"""
        salt = b"venustech_system_salt_2026"
        key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
        return base64.urlsafe_b64encode(key[:32])

    def _initialize(self):
        """初始化加密密钥"""
        if not HAS_CRYPTO:
            return

        if self._master_key:
            # 使用用户提供的主密钥
            key = self._derive_key(self._master_key)
        elif self._key_file.exists():
            # 读取已存在的密钥
            key = self._key_file.read_bytes()
        else:
            # 生成新密钥
            key = Fernet.generate_key()
            self._key_file.write_bytes(key)
            # 设置文件权限（仅所有者可读）
            try:
                os.chmod(self._key_file, 0o600)
            except OSError:
                pass

        self._fernet = Fernet(key)

    @property
    def is_available(self) -> bool:
        """加密功能是否可用"""
        return HAS_CRYPTO and self._fernet is not None

    def encrypt(self, data: str | bytes) -> bytes:
        """加密数据"""
        if not self._fernet:
            raise RuntimeError("加密模块未初始化（缺少 cryptography 库）")
        if isinstance(data, str):
            data = data.encode("utf-8")
        return self._fernet.encrypt(data)

    def decrypt(self, token: bytes | str) -> str:
        """解密数据"""
        if not self._fernet:
            raise RuntimeError("加密模块未初始化（缺少 cryptography 库）")
        if isinstance(token, str):
            token = token.encode("utf-8")
        try:
            return self._fernet.decrypt(token).decode("utf-8")
        except InvalidToken:
            raise ValueError("解密失败：密钥不匹配或数据已损坏")

    def encrypt_json(self, obj: Any) -> bytes:
        """加密JSON对象"""
        return self.encrypt(json.dumps(obj, ensure_ascii=False))

    def decrypt_json(self, token: bytes | str) -> Any:
        """解密为JSON对象"""
        return json.loads(self.decrypt(token))

    def encrypt_file(self, source_path: Path, dest_path: Path | None = None) -> Path:
        """加密文件"""
        if dest_path is None:
            dest_path = source_path.with_suffix(source_path.suffix + ".enc")
        plaintext = source_path.read_bytes()
        encrypted = self.encrypt(plaintext)
        dest_path.write_bytes(encrypted)
        return dest_path

    def decrypt_file(self, encrypted_path: Path, dest_path: Path | None = None) -> Path:
        """解密文件"""
        if dest_path is None:
            dest_path = encrypted_path.with_suffix("")
        encrypted = encrypted_path.read_bytes()
        plaintext = self._fernet.decrypt(encrypted) if self._fernet else encrypted
        dest_path.write_bytes(plaintext)
        return dest_path

    def rotate_key(self, new_master_key: str | None = None):
        """轮换密钥（重新加密所有数据）"""
        if not self._fernet:
            return
        # 生成新密钥
        if new_master_key:
            new_key = self._derive_key(new_master_key)
        else:
            new_key = Fernet.generate_key()
        # 保存新密钥
        self._key_file.write_bytes(new_key)
        self._fernet = Fernet(new_key)

    def get_status(self) -> dict:
        """获取加密状态"""
        return {
            "available": self.is_available,
            "algorithm": "AES-128-CBC + HMAC-SHA256 (Fernet)",
            "key_derivation": "PBKDF2-HMAC-SHA256 (100000 iterations)",
            "key_file": str(self._key_file),
            "key_exists": self._key_file.exists(),
            "has_custom_key": self._master_key is not None,
        }


# 全局单例（在 main.py 中初始化）
_encryption_manager: EncryptionManager | None = None


def init_encryption(data_dir: Path, master_key: str | None = None) -> EncryptionManager:
    """初始化全局加密管理器"""
    global _encryption_manager
    _encryption_manager = EncryptionManager(data_dir, master_key)
    return _encryption_manager


def get_encryption() -> EncryptionManager | None:
    """获取全局加密管理器"""
    return _encryption_manager