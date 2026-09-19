# ============================================================
# 保险箱服务（三期 D · 主密码 + 凭据加密存储）
#
# 安全模型（三期规划 §6）：
#   主密码 → PBKDF2(随机 salt) → Fernet 工作密钥。
#   vault_config.verifier = 工作密钥加密的已知常量：
#     设置时生成一次；解锁时尝试解密 —— 解开即密码正确，
#     同时把工作密钥放进进程内存态。主密码不落盘（无哈希可爆破）。
#   解锁态是**进程内存**：重启服务即上锁，符合"本地应用"心智。
# ============================================================
from __future__ import annotations

import socket
import time

import os
import re
from datetime import datetime, timezone
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessException, NotFoundException, ValidationException
from app.models.base import utcnow
from app.models.vault import VaultConfig, VaultItem
from app.core.encryption import EncryptionManager

_VERIFIER_PLAINTEXT = "venustech-vault-verifier-v1"
_UNLOCKED_TIMEOUT_HINT = "服务重启后需要重新解锁"

# ---------- 终端动作（D 收尾） ----------
# 白名单本质：只接受固定模板，动态字段全部过白名单正则 —— 无注入面。
ACTION_TYPES = {"none", "ssh"}
_SAFE_HOST = re.compile(r"^[A-Za-z0-9._-]{1,253}$")
_SAFE_USER = re.compile(r"^[A-Za-z0-9._@-]{1,64}$")
_SAFE_PORT = re.compile(r"^\d{1,5}$")

# 解锁态 = 工作密钥的进程内缓存（键=user_id，值=派生的 Fernet key）。
# 只存内存：服务重启即自动上锁；主密码本身任何时刻都不落盘、不常驻。
_session_keys: dict[str, bytes] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


class VaultService:
    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id

    # ---------- 状态 ----------

    def status(self) -> dict:
        config = self._config()
        return {
            "configured": config is not None,
            "unlocked": self.user_id in _session_keys,
            "items_count": self._count_items(),
            "hint": None if (config and self.user_id in _session_keys) else _UNLOCKED_TIMEOUT_HINT,
        }
    # ---------- 主密码生命周期 ----------

    def setup(self, master_password: str) -> dict:
        if len(master_password) < 8:
            raise ValidationException("主密码至少 8 位")
        if self._config() is not None:
            raise BusinessException("保险箱已初始化。如需重置请先删除全部凭据（防误覆盖）")
        salt = EncryptionManager.new_salt()
        key = EncryptionManager.derive_key(master_password, salt)
        fernet = Fernet(key)
        row = VaultConfig(
            user_id=self.user_id,
            salt=salt.hex(),
            verifier=fernet.encrypt(_VERIFIER_PLAINTEXT.encode()).decode(),
        )
        self.db.add(row)
        self.db.commit()
        _session_keys[self.user_id] = key
        return self.status()

    def unlock(self, master_password: str) -> dict:
        config = self._require_config()
        salt = bytes.fromhex(config.salt)
        key = EncryptionManager.derive_key(master_password, salt)
        try:
            plain = Fernet(key).decrypt(config.verifier.encode()).decode()
        except InvalidToken:
            raise ValidationException("主密码错误")
        if plain != _VERIFIER_PLAINTEXT:  # 防御性：校验器被篡改
            raise BusinessException("校验器异常：保险箱数据可能已损坏")
        _session_keys[self.user_id] = key
        return self.status()

    def lock(self) -> dict:
        _session_keys.pop(self.user_id, None)
        return self.status()

    def change_master_password(self, old_password: str, new_password: str) -> dict:
        if len(new_password) < 8:
            raise ValidationException("新主密码至少 8 位")
        config = self._require_config()
        old_salt = bytes.fromhex(config.salt)
        old_key = EncryptionManager.derive_key(old_password, old_salt)
        old_fernet = Fernet(old_key)
        try:
            plain = old_fernet.decrypt(config.verifier.encode()).decode()
        except InvalidToken:
            raise ValidationException("原主密码错误")
        if plain != _VERIFIER_PLAINTEXT:
            raise BusinessException("校验器异常：保险箱数据可能已损坏")

        # 用新密钥重加密全部凭据密文（原地轮换）
        new_salt = EncryptionManager.new_salt()
        new_key = EncryptionManager.derive_key(new_password, new_salt)
        new_fernet = Fernet(new_key)
        items = self.db.scalars(
            select(VaultItem).where(
                VaultItem.user_id == self.user_id,
                VaultItem.secret_encrypted.is_not(None),
            )
        ).all()
        for item in items:
            plain_secret = old_fernet.decrypt(item.secret_encrypted.encode()).decode()
            item.secret_encrypted = new_fernet.encrypt(plain_secret.encode()).decode()
        config.salt = new_salt.hex()
        config.verifier = new_fernet.encrypt(_VERIFIER_PLAINTEXT.encode()).decode()
        self.db.commit()
        _session_keys[self.user_id] = new_key
        return self.status()

    # ---------- 凭据 CRUD（全部要求解锁态） ----------

    def list_items(self) -> list[dict]:
        self._require_unlocked()
        rows = self.db.scalars(
            select(VaultItem)
            .where(VaultItem.user_id == self.user_id)
            .order_by(VaultItem.category, VaultItem.name)
        ).all()
        return [self._item_out(r, with_secret=False) for r in rows]

    def create_item(self, *, name: str, category: str, username: str | None,
                    url: str | None, secret: str | None, notes: str | None,
                    identity_id: str | None,
                    action_type: str = "none", action_host: str | None = None,
                    action_user: str | None = None, action_port: str | None = None) -> dict:
        self._require_unlocked()
        self._ensure_identity_owned(identity_id)
        action = self._validate_action(action_type, action_host, action_user, action_port)
        row = VaultItem(
            user_id=self.user_id, name=name.strip(), category=category,
            username=username, url=url, notes=notes, identity_id=identity_id,
            secret_encrypted=self._encrypt_secret(secret),
            **action,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return self._item_out(row)

    def update_item(self, item_id: str, *, name: str | None = None,
                    category: str | None = None, username: str | None = None,
                    url: str | None = None, secret: str | None = None,
                    notes: str | None = None, identity_id: str | None = None,
                    action_type: str | None = None, action_host: str | None = None,
                    action_user: str | None = None, action_port: str | None = None) -> dict:
        self._require_unlocked()
        row = self._owned_item(item_id)
        if name is not None:
            row.name = name.strip()
        if category is not None:
            row.category = category
        if username is not None:
            row.username = username
        if url is not None:
            row.url = url
        if notes is not None:
            row.notes = notes
        if identity_id is not None:
            self._ensure_identity_owned(identity_id)
            row.identity_id = identity_id
        if secret is not None:
            row.secret_encrypted = self._encrypt_secret(secret)
        # 动作字段：显式传入才覆盖（整体校验，避免半套配置）
        if any(v is not None for v in (action_type, action_host, action_user, action_port)):
            merged = self._validate_action(
                action_type if action_type is not None else row.action_type,
                action_host if action_host is not None else row.action_host,
                action_user if action_user is not None else row.action_user,
                action_port if action_port is not None else row.action_port,
            )
            for k, v in merged.items():
                setattr(row, k, v)
        self.db.commit()
        self.db.refresh(row)
        return self._item_out(row)

    def delete_item(self, item_id: str) -> dict:
        self._require_unlocked()
        row = self._owned_item(item_id)
        self.db.delete(row)
        self.db.commit()
        return {"deleted": True, "id": item_id}

    def reveal_secret(self, item_id: str) -> dict:
        """按需解密单条凭据。这是明文出系统的唯一出口，要求解锁态。"""
        self._require_unlocked()
        row = self._owned_item(item_id)
        if not row.secret_encrypted:
            return {"secret": None}
        try:
            secret = self._require_fernet().decrypt(row.secret_encrypted.encode()).decode()
        except InvalidToken:
            raise BusinessException("解密失败：密钥不匹配（主密码可能已被更换）")
        row.last_accessed_at = utcnow()
        self.db.commit()
        return {"secret": secret}

    # ---------- 终端动作（D 收尾 · 白名单模板） ----------

    @staticmethod
    def _validate_action(action_type: str | None, host: str | None,
                         user: str | None, port: str | None) -> dict:
        """动作字段整体校验。返回写入 DB 的字段字典。"""
        t = (action_type or "none").strip()
        if t not in ACTION_TYPES:
            raise ValidationException(f"不支持的动作类型（白名单: {sorted(ACTION_TYPES - {'none'})}）")
        if t == "none":
            return {"action_type": "none", "action_host": None, "action_user": None, "action_port": None}
        if not host or not _SAFE_HOST.match(host):
            raise ValidationException("SSH 主机名含非法字符（仅允许字母/数字/./_/-）")
        if user and not _SAFE_USER.match(user):
            raise ValidationException("SSH 用户名含非法字符")
        if port is not None and port != "" and not _SAFE_PORT.match(port):
            raise ValidationException("端口必须是数字")
        if port and not (1 <= int(port) <= 65535):
            raise ValidationException("端口超出范围 1-65535")
        return {
            "action_type": "ssh",
            "action_host": host,
            "action_user": user or None,
            "action_port": port or None,
        }

    def run_action(self, item_id: str) -> dict:
        """执行凭据的终端动作（当前白名单：ssh -i 密钥路径）。

        安全约束（一条都不许退）：
        - 要求解锁态（密钥路径是加密存的，运行时解密）
        - 动态字段全部经 _validate_action 白名单正则 —— 无注入面
        - secret 必须是真实存在的密钥文件路径（不支持把密码塞进命令行）
        - 只启动固定模板命令，绝不拼接用户提供的其他片段
        """
        import subprocess

        self._require_unlocked()
        row = self._owned_item(item_id)
        if row.action_type == "none":
            raise ValidationException("该凭据未配置终端动作")
        if not row.secret_encrypted:
            raise ValidationException("SSH 动作需要密钥文件路径（存于凭据的 secret 中）")
        host = row.action_host
        if not host:
            raise ValidationException("SSH 动作缺少主机名")
        if host and not _SAFE_HOST.match(host):
            raise BusinessException("主机名异常：保险箱数据可能已被篡改")

        secret_path = self._require_fernet().decrypt(row.secret_encrypted.encode()).decode()
        key_path = Path(secret_path).expanduser()
        if not key_path.is_file():
            raise ValidationException(f"密钥文件不存在: {key_path}")

        target = f"{row.action_user}@{host}" if row.action_user else host
        command = f'ssh -i "{key_path}"'
        if row.action_port:
            command += f" -p {row.action_port}"
        command += f' "{target}"'

        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
        subprocess.Popen(["cmd.exe", "/K", command], creationflags=creationflags)
        row.last_accessed_at = utcnow()
        self.db.commit()
        return {"opened": True, "action": "ssh", "command": command}

    # ---------- 内部 ----------

    def _encrypt_secret(self, secret: str | None) -> str | None:
        if secret is None or secret == "":
            return None
        return self._require_fernet().encrypt(secret.encode()).decode()

    def _require_fernet(self) -> Fernet:
        """解锁态下取工作密钥（仅进程内存缓存，重启即失效）。"""
        key = _session_keys.get(self.user_id)
        if key is None:
            raise BusinessException("保险箱已上锁，请先解锁")
        return Fernet(key)

    def _config(self) -> VaultConfig | None:
        return self.db.scalar(
            select(VaultConfig).where(VaultConfig.user_id == self.user_id)
        )

    def _require_config(self) -> VaultConfig:
        config = self._config()
        if config is None:
            raise BusinessException("保险箱尚未初始化，请先设置主密码")
        return config

    def _require_unlocked(self) -> None:
        if self.user_id not in _session_keys:
            raise BusinessException("保险箱已上锁，请先解锁")

    def test_action_connection(self, item_id: str) -> dict:
        """SSH 动作连通性测试（P1-5）：只探测 TCP 可达性。

        安全边界（勿放宽）：
        - host/port **只从已存凭据读取**，不接受请求体传入 —— 否则这个方法
          就成了任意 host:port 探测原语（SSRF / 端口扫描）。
        - 仅完成 TCP 三次握手即关闭，不建立 SSH 会话、不发送任何密钥或凭据。
        - 3 秒超时，不重试。
        """
        item = self._owned_item(item_id)
        if item.action_type != "ssh":
            raise ValidationException("该凭据未配置 SSH 动作（action_type != ssh）")

        host = (item.action_host or "").strip()
        if not host:
            raise ValidationException("未配置主机地址（action_host）")
        # 拒绝明显的注入/畸形输入：主机名只允许字母数字点横线冒号（IPv6 用方括号写法）
        if not re.fullmatch(r"[A-Za-z0-9._:\-\[\]]{1,255}", host):
            raise ValidationException("主机地址含非法字符")

        raw_port = (item.action_port or "22").strip() or "22"
        if not raw_port.isdigit():
            raise ValidationException("端口必须是数字")
        port = int(raw_port)
        if not (1 <= port <= 65535):
            raise ValidationException("端口须在 1-65535 之间")

        started = time.perf_counter()
        try:
            with socket.create_connection((host, port), timeout=3):
                elapsed = int((time.perf_counter() - started) * 1000)
                return {
                    "reachable": True, "host": host, "port": port,
                    "elapsed_ms": elapsed, "error": None,
                }
        except OSError as e:
            elapsed = int((time.perf_counter() - started) * 1000)
            return {
                "reachable": False, "host": host, "port": port,
                "elapsed_ms": elapsed, "error": str(e)[:200],
            }

    def _owned_item(self, item_id: str) -> VaultItem:
        row = self.db.get(VaultItem, item_id)
        if row is None or row.user_id != self.user_id or row.deleted_at is not None:
            raise NotFoundException("凭据不存在")
        return row

    def _count_items(self) -> int:
        return len(self.db.scalars(
            select(VaultItem.id).where(VaultItem.user_id == self.user_id)
        ).all())

    def _ensure_identity_owned(self, identity_id: str | None) -> None:
        if identity_id is None:
            return
        from app.repositories.identity_repo import IdentityRepository
        identity = IdentityRepository(self.db).get(identity_id)
        if identity is None or identity.user_id != self.user_id or identity.deleted_at is not None:
            raise ValidationException("身份不存在")

    @staticmethod
    def _item_out(row: VaultItem, with_secret: bool = False) -> dict:
        return {
            "id": row.id, "name": row.name, "category": row.category,
            "username": row.username, "url": row.url, "notes": row.notes,
            "identity_id": row.identity_id,
            "has_secret": row.secret_encrypted is not None,
            "last_accessed_at": row.last_accessed_at.isoformat() if row.last_accessed_at else None,
            "created_at": row.created_at.isoformat(),
            "updated_at": row.updated_at.isoformat(),
            "action_type": row.action_type, "action_host": row.action_host,
            "action_user": row.action_user, "action_port": row.action_port,
        }


# 解锁期间的工作密钥缓存（仅进程内存；重启即失效=自动上锁）
_session_keys: dict[str, bytes] = {}
