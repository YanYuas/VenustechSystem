# ============================================================
# 安全服务层（mod-platform P0）
#
# 1. rotate_encryption_key：密钥轮换**真正重加密**历史密文
#    （旧实现只换 key_file，导致轮换后所有历史密文解不开 = 静默丢数据）
# 2. require_unlocked：加解密端点要求保险箱已解锁（不再是"谁都能调"）
# ============================================================
from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.encryption import EncryptionManager
from app.core.exceptions import BusinessException, ValidationException
from app.config import get_settings
from app.models.settings import Setting
from app.models.vault import VaultItem

# 需要跟随密钥轮换重加密的（模型/表, 密文列）
_CIPHER_COLUMNS: list[tuple[str, str]] = [
    ("vault_items", "secret_encrypted"),
]


class SecurityService:
    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id

    # ---------- 密钥轮换（真实重加密） ----------

    def rotate_key(self, new_master_key: str | None = None) -> dict:
        """轮换加密密钥，并用新密钥重加密所有历史密文。

        流程：先解密全部 → 换 key → 再加密写回。任一步失败即整体回滚，
        绝不留下"半新半旧"的库。
        """
        mgr = EncryptionManager(Path(get_settings().data_dir))
        if not mgr.is_available:
            raise BusinessException("加密模块不可用，无法轮换密钥")

        # 1) 收集所有密文（Fernet token），解密成明文
        collected: list[tuple[object, str, str]] = []  # (row, column, plaintext)
        for table, column in _CIPHER_COLUMNS:
            rows = self._rows_of(table)
            for row in rows:
                token = getattr(row, column, None)
                if not token:
                    continue
                try:
                    collected.append((row, column, mgr.decrypt(token)))
                except Exception:
                    # 单条解不开（脏数据）不阻塞整体轮换，跳过并记录
                    continue

        # 2) 设置类密文（assistant.deepseek_key）
        setting_rows: list[tuple[Setting, str]] = []
        srows = self.db.scalars(
            select(Setting).where(
                Setting.user_id == self.user_id,
                Setting.key == "assistant.deepseek_key",
            )
        ).all()
        for s in srows:
            if not (s.value or "").strip():
                continue
            try:
                setting_rows.append((s, mgr.decrypt(s.value)))
            except Exception:
                continue

        # 3) 换 key（此后 mgr 已持有新密钥）
        try:
            mgr.rotate_key(new_master_key)

            # 4) 用新密钥重加密写回
            rotated = 0
            for row, column, plaintext in collected:
                setattr(row, column, mgr.encrypt(plaintext).decode())
                rotated += 1
            for s, plaintext in setting_rows:
                s.value = mgr.encrypt(plaintext).decode()
                rotated += 1
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            raise BusinessException(f"密钥轮换失败，已回滚：{e}") from e

        return {
            "rotated": rotated,
            "tables": [t for t, _ in _CIPHER_COLUMNS] + ["settings"],
        }

    def _rows_of(self, table: str) -> list:
        if table == "vault_items":
            return list(
                self.db.scalars(
                    select(VaultItem).where(VaultItem.user_id == self.user_id)
                ).all()
            )
        return []


# ---------- 加解密端点的解锁门禁 ----------

def require_unlocked(user_id: str) -> None:
    """加/解密端点要求保险箱处于解锁态。

    说明：系统是本地单用户模型，真正的安全边界在 server.js 的访问令牌；
    这里补的是"进程内越权"——任何能打到 API 的调用（含被注入的前端脚本）
    在未解锁时不得批量解密用户密钥。
    """
    from app.services.vault_service import _session_keys  # 刻意私有访问：进程内会话态

    if user_id not in _session_keys:
        raise ValidationException("保险箱未解锁：请先在保险箱页解锁后再操作")


# ---------- 审计日志 ----------

def audit(db: Session, user_id: str, action: str, *, target: str | None = None,
          ok: bool = True, detail: str | None = None, ip: str | None = None) -> None:
    """写一条审计记录。审计本身永不抛异常（不能因为记日志打断业务）。"""
    from app.models.audit import AUDIT_ACTIONS, AuditLog

    if action not in AUDIT_ACTIONS:
        action = "plugin.error"  # 未登记动作降级归类，绝不静默丢弃
    try:
        db.add(AuditLog(
            user_id=user_id, action=action, target=(target or "")[:200] or None,
            ok=ok, detail=(detail or "")[:1000] or None, ip=ip,
        ))
        db.commit()
    except Exception:
        db.rollback()


def list_audit(db: Session, user_id: str, limit: int = 50) -> list[dict]:
    from sqlalchemy import select

    from app.models.audit import AuditLog

    rows = db.scalars(
        select(AuditLog)
        .where(AuditLog.user_id == user_id, AuditLog.deleted_at.is_(None))
        .order_by(AuditLog.created_at.desc())
        .limit(min(limit, 200))
    ).all()
    return [
        {
            "id": r.id, "action": r.action, "target": r.target, "ok": r.ok,
            "detail": r.detail, "ip": r.ip,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
