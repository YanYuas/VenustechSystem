# ============================================================
# 保险箱模型（三期 D · 凭据库）
#
# 安全设计（三期规划 §6，勿削弱）：
#   - 主密码不存原文、不存哈希：存「校验器」—— 用派生密钥加密的
#     已知常量。解锁 = 尝试解密校验器（顺带拿到工作密钥），一条
#     机制同时完成验证与解密，没有可离线爆破的第二份哈希
#   - 凭据密文只以 Fernet token（base64 文本）落库，密钥只存在于
#     解锁后的内存态，进程重启即上锁
#   - SYNC_POLICY（总路线 D11/A 预留）：secret_encrypted 只同步密文，
#     salt/verifier 可同步 —— 引擎落地时在表分级登记
# ============================================================
from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin


class VaultConfig(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    """保险箱配置（每用户一条）：随机 salt + 主密码校验器。"""

    __tablename__ = "vault_config"
    __table_args__ = (Index("uq_vault_config_user", "user_id", unique=True),)

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    salt: Mapped[str] = mapped_column(String(64), nullable=False)  # hex(16 bytes)
    verifier: Mapped[str] = mapped_column(Text, nullable=False)  # Fernet token（解密成功=密码正确）


class VaultItem(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    """凭据条目。secret 只存密文。"""

    __tablename__ = "vault_items"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False, default="login")  # login/note
    username: Mapped[str | None] = mapped_column(String(200), nullable=True)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    secret_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)  # Fernet token
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)  # 明文备注（用户可选填）
    identity_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    last_accessed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    # ---------- 终端动作（D 收尾 · 白名单模板，禁止任意命令） ----------
    # none / ssh；ssh 动作：secret = 加密存的密钥文件路径，
    # 运行时解密进 `ssh -i "{path}" user@host -p port`（路径必须真实存在）
    action_type: Mapped[str] = mapped_column(String(20), nullable=False, default="none")
    action_host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    action_user: Mapped[str | None] = mapped_column(String(255), nullable=True)
    action_port: Mapped[str | None] = mapped_column(String(10), nullable=True)
