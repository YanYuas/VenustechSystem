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
    from cryptography.fernet import Fernet, InvalidToken
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False


class EncryptionManager:
    """加密管理器：密钥派生、加密/解密、安全存储"""

    # PBKDF2 迭代次数（OWASP 2023+ 建议的下限之上）
    PBKDF2_ITERATIONS = 200_000
    # 历史密钥保留代数（考察修正：原来只有一代，连续轮换会丢更早的密钥）
    KEEP_PREVIOUS = 5

    def __init__(self, data_dir: Path, master_key: str | None = None):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._key_file = data_dir / ".encryption_key"
        self._salt_file = data_dir / ".encryption_key.salt"
        # 密钥环（PRD 8.2）：保留多代历史密钥。轮换中断时旧密文仍可用
        # previous 解密 —— 避免"换了 key 却还没来得及重加密"造成的静默数据丢失。
        # 2026-10-11：此处原有一次重复赋值（同一路径连写两遍），已删。
        self._keyring_file = data_dir / ".encryption_keys.json"
        self._fernet: Fernet | None = None
        # 历史密钥列表（考察修正）：原来只保留一代 previous，连续轮换两次
        # 就会丢弃更早的密钥，导致用旧密钥加密的密文永久解不开。
        # 现改为保留多代（KEEP_PREVIOUS 代），解密时依次尝试。
        self._previous_fernets: list[Fernet] = []
        self._master_key = master_key
        self._initialize()

    @staticmethod
    def derive_key(password: str, salt: bytes) -> bytes:
        """从密码派生 Fernet 密钥。

        安全修正（总路线 D0）：salt **必须随机**且与密文/校验器一起存储
        —— 硬编码全局 salt 会让相同密码在不同用户间派生出相同密钥，
        且彩虹表可跨库复用。PBKDF2-HMAC-SHA256。
        """
        key = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, EncryptionManager.PBKDF2_ITERATIONS
        )
        return base64.urlsafe_b64encode(key[:32])

    @staticmethod
    def new_salt() -> bytes:
        return os.urandom(16)

    def _initialize(self):
        """初始化加密密钥"""
        if not HAS_CRYPTO:
            return

        if self._master_key:
            # 使用用户提供的主密钥：随机 salt 持久化在密钥文件旁边
            if self._salt_file.exists():
                salt = self._salt_file.read_bytes()
            else:
                salt = self.new_salt()
                self._salt_file.write_bytes(salt)
                try:
                    os.chmod(self._salt_file, 0o600)
                except OSError:
                    pass
            key = self.derive_key(self._master_key, salt)
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
        # 密钥环里的历史密钥用于解密历史密文（轮换中断 / 多代轮换场景）
        self._previous_fernets = []
        try:
            if self._keyring_file.exists():
                ring = json.loads(self._keyring_file.read_text(encoding="utf-8"))
                for prev in (ring.get("previous_keys") or []):
                    try:
                        self._previous_fernets.append(Fernet(prev.encode("utf-8")))
                    except Exception:
                        continue
                # 兼容旧格式（单代 previous）
                prev1 = ring.get("previous")
                if prev1:
                    try:
                        self._previous_fernets.append(Fernet(prev1.encode("utf-8")))
                    except Exception:
                        pass
        except Exception:
            self._previous_fernets = []
        # 2026-10-11：此处原有一段把 ring["previous"] 读进 `self._previous_fernet`
        # （单数）的逻辑。该属性**全仓没有任何读取方**（decrypt() 只用复数
        # `_previous_fernets`），且仅在存在旧格式键时才被赋值 —— 纯死代码，已删。

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
            # PRD 8.2：轮换中断后旧密文用历史密钥仍可解密（多代依次尝试）
            for prev in self._previous_fernets:
                try:
                    return prev.decrypt(token).decode("utf-8")
                except InvalidToken:
                    continue
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
        """解密文件。

        2026-10-11 修正两处（探针实测，回归用例见 tests/test_encryption_production.py）：

          ① 旧实现直接 `self._fernet.decrypt(...)`，**绕过了历史密钥回退** ——
             同一份密文，`decrypt()` 在轮换后仍能解开（会依次试 previous），
             `decrypt_file()` 却抛 InvalidToken。两条路径行为不一致是隐患。
             改为统一走 `self.decrypt()`。
          ② 旧实现写成 `self._fernet.decrypt(x) if self._fernet else x` ——
             `_fernet` 为空（cryptography 缺失）时会把**密文原样写进目标文件**
             当明文，静默产出垃圾。改为由 `decrypt()` 明确抛 RuntimeError。
        """
        if dest_path is None:
            dest_path = encrypted_path.with_suffix("")
        plaintext = self.decrypt(encrypted_path.read_bytes()).encode("utf-8")
        dest_path.write_bytes(plaintext)
        return dest_path

    def rotate_key(self, new_master_key: str | None = None):
        """轮换密钥（重新加密所有数据）"""
        if not self._fernet:
            return
        # 生成新密钥
        if new_master_key:
            salt = self.new_salt()
            self._salt_file.write_bytes(salt)
            new_key = self.derive_key(new_master_key, salt)
        else:
            new_key = Fernet.generate_key()
        # 保留旧密钥为 previous（供历史密文解密），再落新密钥
        old_key = self._key_file.read_bytes() if self._key_file.exists() else None
        self._key_file.write_bytes(new_key)
        # 历史密钥：当前生效中的 -> 入历史列表，保留最近 KEEP_PREVIOUS 代
        new_hist = ([old_key.decode() if isinstance(old_key, bytes) else old_key]
                    if old_key else [])
        # 2026-10-11：此处原有一个 `for f in [self._fernet]: pass` 的空循环
        # （注释自称"占位说明"，实际什么都没做且极易误导），已删。
        try:
            if self._keyring_file.exists():
                ring = json.loads(self._keyring_file.read_text(encoding="utf-8"))
                hist = [k for k in (ring.get("previous_keys") or [])]
                cur = ring.get("current")
                if cur and cur not in hist:
                    hist.insert(0, cur)
                new_hist = (new_hist + hist)[:self.KEEP_PREVIOUS]
        except Exception:
            pass
        try:
            self._keyring_file.write_text(
                json.dumps({
                    "current": (new_key.decode()
                                if isinstance(new_key, bytes) else str(new_key)),
                    "previous_keys": new_hist,
                }), encoding="utf-8"
            )
            try:
                os.chmod(self._keyring_file, 0o600)
            except OSError:
                pass
        except OSError:
            pass
        self._previous_fernets = []
        for k in new_hist:
            try:
                self._previous_fernets.append(Fernet(k.encode("utf-8")))
            except Exception:
                continue
        self._fernet = Fernet(new_key)

    def reload(self) -> None:
        """重新从磁盘读取密钥与密钥环，就地刷新本实例。

        为什么需要它（2026-10-11，由 smoke_backend 的「轮换后仍可解密」往返断言测出）：
        密钥轮换发生在 `SecurityService.rotate_key` 里，那里自己 new 了一个
        **局部** EncryptionManager；而 `decrypt_secret()` / `encrypt_secret()`
        （app/core/security.py）走的是 main.py 启动时建的**全局单例**。
        单例的 `_fernet` 只在进程启动时读一次磁盘 —— 不在轮换后刷新，它就会
        一直用内存里的**旧密钥**去解刚用新密钥写回的行。症状极具误导性：

            「密钥轮换成功」提示正常 → 但 API Key 当场失效 → **重启服务才恢复**。

        用 `reload()` 而不是 `init_encryption()`：后者要重新解析 data_dir，
        在测试里（data_dir 被 monkeypatch 到 tmp_path）会凭空替换掉应用单例、
        污染同会话其他用例；`reload()` 复用本实例已确立的 `self.data_dir`，
        目录不一致时也只是原地重读、天然幂等。
        """
        self._initialize()

    def get_status(self) -> dict:
        """获取加密状态"""
        return {
            "available": self.is_available,
            "algorithm": "AES-128-CBC + HMAC-SHA256 (Fernet)",
            "key_derivation": f"PBKDF2-HMAC-SHA256 ({self.PBKDF2_ITERATIONS} iterations, random salt)",
            "key_file": str(self._key_file),
            "key_exists": self._key_file.exists(),
            "has_custom_key": self._master_key is not None,
            "has_previous_key": bool(self._previous_fernets),
            "previous_key_count": len(self._previous_fernets),
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