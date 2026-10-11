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

from app.core.encryption import EncryptionManager, get_encryption
from app.core.exceptions import BusinessException, ValidationException
from app.config import get_settings
from app.models.settings import Setting
from app.models.user import User

# 需要跟随密钥轮换重加密的（模型/表, 密文列）。
#
# **登记的唯一判据**：该列的密文是由**全局 EncryptionManager**
# （app/core/encryption.py 的 init_encryption / get_encryption）加出来的。
# 只有这类密文才会因密钥轮换而失效，也才需要重加密。
#
# 2026-10-11 修正（探针实测，回归用例见 tests/test_security_production.py）：
#   ① `users.api_key_encrypted` 旧实现**根本轮换不了**：`encrypt_secret()` 落库的
#      是 `"fernet:" + <Fernet token>`（带前缀，见 app/core/security.py），
#      而旧代码拿整串去 `mgr.decrypt()` → 必然 InvalidToken → 被 `except` 静默
#      `continue`。后果不是立刻报错，而是该列只能靠密钥环兜底；密钥环只留
#      `KEEP_PREVIOUS` 代，实测**第 4 次轮换后 API Key 永久解不开**
#      —— 正是本段注释原本警告的失败模式，却一直在发生。现按前缀对齐。
#   ② `vault_items.secret_encrypted` **不该登记在这里**：它的密文由**保险箱主密码**
#      派生的独立 Fernet 加密（vault_service._require_fernet），与全局密钥无关，
#      `mgr.decrypt` 必然失败 → 每次都静默跳过，却在返回值里谎报"已轮换"。
#      它的轮换在 `VaultService.change_password` 中完成，不归本服务管。
_CIPHER_COLUMNS: list[tuple[str, str]] = [
    ("users", "api_key_encrypted"),
]

# `encrypt_secret()` 给 Fernet 密文加的前缀。解密前必须剥掉、回写后必须还原，
# 否则（a）解不开、（b）`decrypt_secret()` 认不出格式。
_FERNET_PREFIX = "fernet:"


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
        #
        # per_table 只统计**真的解开了、待重写**的行 —— 旧实现拿静态清单
        # 当返回值，在列根本轮换不了的情况下等于谎报（探针实测 rotated=1
        # 却声称 vault_items / users / settings 三表都轮换过）。
        collected: list[tuple[object, str, str, str]] = []  # (row, column, plaintext, prefix)
        per_table: dict[str, int] = {}
        for table, column in _CIPHER_COLUMNS:
            rows = self._rows_of(table)
            for row in rows:
                token = getattr(row, column, None)
                if not token:
                    continue
                raw = str(token)
                # 剥前缀：`encrypt_secret()` 存的是 "fernet:<token>"，
                # 不剥就会喂给 Fernet 一个带前缀的串 → 必然解不开（见本文件顶部说明）
                prefix = ""
                if raw.startswith(_FERNET_PREFIX):
                    prefix, raw = _FERNET_PREFIX, raw[len(_FERNET_PREFIX):]
                # DPAPI 密文由 Windows DPAPI 自行管理密钥，不归本密钥管
                if raw.startswith("dpapi:"):
                    continue
                try:
                    plaintext = mgr.decrypt(raw)
                except Exception:
                    # 解不开 = 非本密钥产物（或数据已损坏）。跳过而非失败：
                    # 不能让一条坏数据把整次轮换拖成回滚。
                    continue
                collected.append((row, column, plaintext, prefix))
                per_table[table] = per_table.get(table, 0) + 1

        # 2) 设置类密文（assistant.deepseek_key）—— 无前缀，直接由本管理器加密
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
        if setting_rows:
            per_table["settings"] = len(setting_rows)

        # 3) 换 key（此后 mgr 已持有新密钥）
        try:
            mgr.rotate_key(new_master_key)

            # 4) 用新密钥重加密写回（前缀必须原样还原，否则 decrypt_secret 认不出）
            rotated = 0
            for row, column, plaintext, prefix in collected:
                setattr(row, column, prefix + mgr.encrypt(plaintext).decode())
                rotated += 1
            for s, plaintext in setting_rows:
                s.value = mgr.encrypt(plaintext).decode()
                rotated += 1
            self.db.commit()
            # 4.5) 让**应用级单例**跟上新密钥。
            #
            # 本方法用的是上面的局部 `mgr`，而 `encrypt_secret()` / `decrypt_secret()`
            # 走的是全局单例（main.py 启动时 init_encryption 建的那个）。单例的
            # `_fernet` 只在进程启动读一次磁盘 —— 不刷新，它就会在**本轮换真正
            # 重写了密文之后**，继续拿内存里的旧密钥去解新密文。症状：
            # 「提示轮换成功，但 API Key 当场失效，重启服务才恢复」。
            # 这一步缺失时 old 代码看不出来（那时 api_key 列根本没被轮换），
            # 是 2026-10-11 让轮换真正生效后才由 smoke_backend 的往返断言测出来的。
            # 仅在单例已存在时刷新，避免在未初始化加密的场景凭空造出后端。
            live = get_encryption()
            if live is not None:
                live.reload()
        except Exception as e:
            self.db.rollback()
            raise BusinessException(f"密钥轮换失败，已回滚：{e}") from e

        return {
            "rotated": rotated,
            # 只列**实际发生重加密**的表（旧实现返回静态清单，会谎报）
            "tables": sorted(per_table),
            "details": per_table,
        }

    def _rows_of(self, table: str) -> list:
        """按表名取本用户的待轮换行。

        必须与 `_CIPHER_COLUMNS` 保持一致：登记了哪张表，这里就要能取到它的行，
        否则该表的密文会在轮换中被静默漏掉（= 轮换后永不可解）。
        `tests/test_security_production.py` 有一组用例专门钉这条一致性。
        """
        if table == "users":
            # api_key_encrypted 存在 users 行上（单用户模型下即本用户）
            return list(
                self.db.scalars(select(User).where(User.id == self.user_id)).all()
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

# 审计日志保留上限（考察修正：原来无上限，长期会持续膨胀）
AUDIT_KEEP = 1000


def audit(db: Session, user_id: str, action: str, *, target: str | None = None,
          ok: bool = True, detail: str | None = None, ip: str | None = None) -> None:
    """写一条审计记录。审计本身永不抛异常（不能因为记日志打断业务）。

    写入后按 AUDIT_KEEP 修剪最旧记录（与 settings_history 的 200 条策略同思路）。
    """
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
        return

    # 修剪：只保留最近 AUDIT_KEEP 条（失败不影响业务，仅记日志）
    try:
        from sqlalchemy import delete, func, select

        total = db.scalar(
            select(func.count()).select_from(AuditLog).where(AuditLog.user_id == user_id)
        ) or 0
        if total > AUDIT_KEEP:
            stale = db.scalars(
                select(AuditLog.id)
                .where(AuditLog.user_id == user_id)
                .order_by(AuditLog.created_at.asc())
                .limit(total - AUDIT_KEEP)
            ).all()
            if stale:
                db.execute(delete(AuditLog).where(AuditLog.id.in_(list(stale))))
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
