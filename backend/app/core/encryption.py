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
import threading
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.logger import get_logger

logger = get_logger("encryption")


try:
    from cryptography.fernet import Fernet, InvalidToken
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    """同目录临时文件 + fsync + `os.replace` 原子写（D-58）。

    为什么不能直接 `path.write_bytes()`：轮换时进程若在写一半崩溃/被中断，
    会留下半截密钥文件，旧密文将永久不可解。原子替换保证「要么旧内容、
    要么完整新内容」，绝不出现半截状态。
    """
    tmp = path.with_name(f"{path.name}.tmp-{os.getpid()}-{uuid4().hex[:8]}")
    try:
        with open(tmp, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            logger.warning("原子写失败后清理临时文件失败（可手工删除）: {}", tmp)
        raise


def _snapshot_file(path: Path) -> tuple[bool, bytes | None]:
    """记录文件是否存在 + 原始字节（D-58 回滚基准）。"""
    if path.exists():
        return True, path.read_bytes()
    return False, None


def _restore_file(path: Path, existed: bool, data: bytes | None) -> None:
    """把文件恢复到快照状态：存在则原子写回旧字节，原本不存在则删除。"""
    if existed and data is not None:
        _atomic_write_bytes(path, data)
        return
    try:
        path.unlink(missing_ok=True)
    except OSError:
        logger.exception("回滚时删除新增文件失败（请人工检查）: {}", path)


# ---------- D-66：主密钥模式的 salt 历史 / keyring 兼容工具 ----------

def _encode_salt(salt: bytes) -> str:
    """salt 历史以 base64 落盘（salt 本身不是秘密，可公开）。"""
    return base64.b64encode(salt).decode("ascii")


def _decode_salt(value: Any) -> bytes | None:
    try:
        raw = base64.b64decode(str(value).encode("ascii"), validate=True)
    except (ValueError, TypeError):
        return None
    return raw if len(raw) == 16 else None


def _keyring_json(snapshot: tuple[bool, bytes | None]) -> dict:
    """读取 keyring 快照为 dict；不存在/损坏 → 空 dict（历史代际降级）。"""
    if not snapshot[0] or not snapshot[1]:
        return {}
    try:
        ring = json.loads(snapshot[1].decode("utf-8"))
    except (ValueError, TypeError, UnicodeDecodeError):
        return {}
    return ring if isinstance(ring, dict) else {}


def _previous_salts_from_ring(ring: dict) -> list[bytes]:
    salts: list[bytes] = []
    for item in ring.get("previous_salts") or []:
        salt = _decode_salt(item)
        if salt is not None:
            salts.append(salt)
    return salts


def _legacy_keyring_fields(ring: dict) -> dict:
    """保留旧格式「key 明文」字段（previous_keys / 单代 previous）以向后兼容。

    previous_salts 是 D-66 新语义字段，由调用方按 master 轮换逻辑**重新计算**，
    不能原样回填（否则历史永远停留在上一代）。
    """
    fields: dict[str, Any] = {}
    for key in ("previous_keys", "previous"):
        if key in ring:
            fields[key] = ring[key]
    return fields


def _previous_fernets_from_legacy(ring: dict) -> list:
    """旧随机模式 keyring 里的 key 明文条目（向后兼容读取，不再新增）。"""
    result = []
    for raw in (ring.get("previous_keys") or []):
        try:
            result.append(Fernet(raw.encode("utf-8")))
        except Exception:
            continue
    prev1 = ring.get("previous")
    if prev1:
        try:
            result.append(Fernet(prev1.encode("utf-8")))
        except Exception:
            pass
    return result


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
        # 历史代际：随机模式读 keyring 里的 previous_keys；主密钥模式用
        # **当前 master + 历史 salt 重派生**（磁盘只存 salt，不存任何 key 明文）。
        ring: dict = {}
        if self._keyring_file.exists():
            try:
                parsed = json.loads(self._keyring_file.read_text(encoding="utf-8"))
                ring = parsed if isinstance(parsed, dict) else {}
            except (ValueError, TypeError, UnicodeDecodeError):
                ring = {}
        self._previous_fernets = []
        if self._master_key and ring:
            for old_salt in _previous_salts_from_ring(ring):
                try:
                    self._previous_fernets.append(
                        Fernet(self.derive_key(self._master_key, old_salt))
                    )
                except Exception:
                    continue
        # 兼容旧随机模式 keyring（previous_keys / 单代 previous）
        self._previous_fernets.extend(_previous_fernets_from_legacy(ring))
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
        """原子轮换密钥（D-58 原子性 + D-66 主密钥语义）。

        两种模式语义（威胁模型见类 docstring / 报告）：

        · **随机密钥模式**（未设 master）：行为与历史完全一致 —— 生成新随机 key
          写入 `.encryption_key`，旧 key 进 keyring `previous_keys`。
        · **主密钥模式**（构造时传 master_key）：
          - `new_master_key=None`（同 master 轮换）：生成**新 salt**，用当前 master
            重派生新 key；旧 salt 归档进 keyring `previous_salts`，旧代由
            `master + 旧 salt` **重新派生** —— 磁盘上始终只有 salt，**绝不落 key 明文**。
          - 显式换 master：新 salt + 新 master 派生；旧代密文无法由新 master 重派生，
            **必须在服务层做全量重加密**（Production 路径`SecurityService.rotate_key`
            已先解密→换 key→全部重加密）。直接调用 manager 换 master 不保证旧密文可解；
            本实例内存里保留旧 fernet 仅用于同进程内短暂过渡。

        失败语义（D-58）：任一写入失败 → 逆序回滚到旧字节/删除新增，内存保持旧值，
        原异常上抛；成功后才刷新 `_fernet` / `_previous_fernets` / `_master_key`。
        """
        if not self._fernet:
            return
        # 回滚基准：写到的文件都必须先快照
        salt_snapshot = _snapshot_file(self._salt_file)
        key_snapshot = _snapshot_file(self._key_file)
        keyring_snapshot = _snapshot_file(self._keyring_file)
        ring_before = _keyring_json(keyring_snapshot)

        master_mode = self._master_key is not None
        master_changed = bool(
            master_mode
            and new_master_key is not None
            and new_master_key != self._master_key
        )
        active_master = new_master_key if master_changed else self._master_key

        written: list[tuple[Path, tuple[bool, bytes | None]]] = []
        previous_salts: list[bytes] = []
        new_hist: list[str] = []
        try:
            if master_mode:
                # ---------- 主密钥模式：只落 salt / salt 历史，不落 key 明文 ----------
                salt = self.new_salt()
                _atomic_write_bytes(self._salt_file, salt)
                written.append((self._salt_file, salt_snapshot))
                new_key = self.derive_key(active_master, salt)

                if not master_changed:
                    # 同 master 轮换：把当前 salt 归档为历史，旧代可重派生
                    current_salt = salt_snapshot[1] if salt_snapshot[0] else None
                    history = ([current_salt] if current_salt else []) + (
                        _previous_salts_from_ring(ring_before)
                    )
                    previous_salts = history[: self.KEEP_PREVIOUS]
                # 换 master：历史 salt 对新 master 无意义 → 不归档（需服务层重加密）

                payload: dict[str, Any] = {
                    "mode": "master",
                    "previous_salts": [_encode_salt(x) for x in previous_salts],
                }
                # 向后兼容：旧机器上已有的随机模式 keyring 字段原样保留（不新增）
                payload.update(_legacy_keyring_fields(ring_before))
                _atomic_write_bytes(
                    self._keyring_file, json.dumps(payload).encode("utf-8")
                )
                written.append((self._keyring_file, keyring_snapshot))
                try:
                    os.chmod(self._keyring_file, 0o600)
                except OSError:
                    logger.warning("设置密钥环权限失败（不影响加解密）: {}", self._keyring_file)
            else:
                # ---------- 随机密钥模式：行为保持历史一致 ----------
                # 历史语义：即使 manager 未设 master，显式传入 new_master_key 也会
                # 「写 salt + 由该 master 派生 key」（key 文件仍保存派生结果，
                # 供随机模式 _initialize 复用）。此处保持完全一致，避免回归。
                if new_master_key:
                    salt = self.new_salt()
                    _atomic_write_bytes(self._salt_file, salt)
                    written.append((self._salt_file, salt_snapshot))
                    new_key = self.derive_key(new_master_key, salt)
                else:
                    new_key = Fernet.generate_key()
                old_key = key_snapshot[1]
                _atomic_write_bytes(self._key_file, new_key)
                written.append((self._key_file, key_snapshot))
                new_hist = [old_key.decode()] if isinstance(old_key, bytes) else []
                if ring_before:
                    hist = [k for k in (ring_before.get("previous_keys") or [])]
                    cur = ring_before.get("current")
                    if cur and cur not in hist:
                        hist.insert(0, cur)
                    new_hist = (new_hist + hist)[: self.KEEP_PREVIOUS]
                payload = {"current": new_key.decode(), "previous_keys": new_hist}
                if "previous_salts" in ring_before:      # 向后兼容保留
                    payload["previous_salts"] = ring_before["previous_salts"]
                _atomic_write_bytes(
                    self._keyring_file, json.dumps(payload).encode("utf-8")
                )
                written.append((self._keyring_file, keyring_snapshot))
                try:
                    os.chmod(self._keyring_file, 0o600)
                except OSError:
                    logger.warning("设置密钥环权限失败（不影响加解密）: {}", self._keyring_file)
        except Exception:
            logger.exception("密钥轮换失败，正在回滚到旧密钥材料（内存密钥保持不变）")
            for path, snapshot in reversed(written):
                try:
                    _restore_file(path, *snapshot)
                except Exception:
                    logger.exception("轮换回滚失败，请人工检查密钥文件: {}", path)
            raise

        # ---------- 全部落盘成功后才刷新内存（磁盘与内存一致） ----------
        if master_mode:
            old_fernets = list(self._previous_fernets)
            previous: list = []
            for old_salt in previous_salts:
                try:
                    previous.append(Fernet(self.derive_key(active_master, old_salt)))
                except Exception:
                    continue
            previous.extend(_previous_fernets_from_legacy(ring_before))
            if master_changed:
                # 换 master：磁盘不再保留可重派生的旧代；仅本实例内存保留旧 fernet，
                # 供同进程内过渡解密（生产必须走 service 全量重加密）。
                previous = [self._fernet] + old_fernets[: max(0, self.KEEP_PREVIOUS - 1)]
                self._master_key = active_master
            self._previous_fernets = previous
            self._fernet = Fernet(new_key)
        else:
            self._previous_fernets = []
            for raw in new_hist:
                try:
                    self._previous_fernets.append(Fernet(raw.encode("utf-8")))
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
# D-25：懒初始化需要并发安全（首个并发请求可能同时发现未初始化）
_encryption_init_lock = threading.Lock()


def init_encryption(data_dir: Path, master_key: str | None = None) -> EncryptionManager:
    """初始化全局加密管理器（主进程 lifespan 调用；显式覆盖旧实例）。"""
    global _encryption_manager
    _encryption_manager = EncryptionManager(data_dir, master_key)
    return _encryption_manager


def get_encryption() -> EncryptionManager | None:
    """获取全局加密管理器（未初始化时返回 None）。"""
    return _encryption_manager


def ensure_encryption(
    data_dir: Path, master_key: str | None = None
) -> EncryptionManager:
    """获取全局单例；未初始化则懒初始化（双检锁，线程安全）。

    - 已初始化：直接复用（忽略传入的 data_dir —— 全局只有一个密钥库，
      避免"同一进程内两套密钥文件"导致加密/解密不对称）；
    - 未初始化：在锁内初始化一次。适用于单测 / CLI / 插件等未经 lifespan 的场景。

    注意：主进程仍应在 lifespan 里显式 `init_encryption(settings.data_dir)`，
    这里的懒初始化只是兜底；不要在请求路径里用不同 data_dir 反复调用。
    """
    global _encryption_manager
    manager = _encryption_manager
    if manager is not None:
        return manager
    with _encryption_init_lock:
        if _encryption_manager is None:
            _encryption_manager = EncryptionManager(data_dir, master_key)
        return _encryption_manager