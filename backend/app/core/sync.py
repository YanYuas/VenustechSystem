# ============================================================
# diff-sync 引擎（S6-3b · 总路线 R2 表分级约束）
#
# 定位：让"云同步"从 0 变成 1 的地基。P0 只做抽象层 + 本地适配器
# （导出/导入 JSON 同步包），未来接云适配器时引擎逻辑零改动。
#
# 诚实边界（勿掩盖）：算法本质是 LWW（最后写入胜）+ 只增不删，
# **无真正的冲突解决**。resolve_conflict() 预留接口，当前默认 LWW。
#
# SYNC_POLICY 表分级（R2：引擎诞生的第一天就要有，不能事后补）：
#   full            常规业务表 —— 正常 diff-sync
#   derived-skip    派生数据 —— 不同步（重扫/重算即得，量又大）
#   encrypted-only  只同步密文/加密材料列白名单（明文列剥除）
#   filtered        按键过滤 —— settings 排除设备相关键
# ============================================================
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import Base
from app.models.base import utcnow

SYNC_PACKAGE_VERSION = 1


class SyncPolicy(str, Enum):
    FULL = "full"
    DERIVED_SKIP = "derived-skip"
    ENCRYPTED_ONLY = "encrypted-only"
    FILTERED = "filtered"


# ---------- 表分级注册表（新增表时在这里登记，缺省 = full） ----------
SYNC_POLICY: dict[str, SyncPolicy] = {
    "workspace_files": SyncPolicy.DERIVED_SKIP,   # 派生数据：重扫即得
    "vault_items": SyncPolicy.ENCRYPTED_ONLY,     # 只同步密文材料
    "vault_config": SyncPolicy.ENCRYPTED_ONLY,    # salt + verifier 本身即密文材料
    "settings": SyncPolicy.FILTERED,              # 排除设备相关键
}

# encrypted-only：列白名单（明文列一律剥除，进不了同步包）
ENCRYPTED_ONLY_COLUMNS: dict[str, set[str]] = {
    # notes 是用户手写的明文备注 —— 不进同步通道；其余字段无明文敏感项
    "vault_items": {
        "id", "user_id", "name", "category", "username", "url",
        "secret_encrypted", "identity_id", "action_type", "action_host",
        "action_user", "action_port", "last_accessed_at",
        "created_at", "updated_at", "deleted_at",
    },
    "vault_config": {
        "id", "user_id", "salt", "verifier", "created_at", "updated_at", "deleted_at",
    },
}

# filtered：这些前缀的 settings 键是设备相关配置，不跨机同步
SETTINGS_EXCLUDED_PREFIXES = ("workspace.",)


def policy_of(table: str) -> SyncPolicy:
    return SYNC_POLICY.get(table, SyncPolicy.FULL)


def _canon_value(v: Any) -> Any:
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    return v


class SyncEngine:
    """单用户 diff-sync。canon → snapshot → diff → apply。"""

    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id

    # ---------- 可同步表清单 ----------

    def synced_tables(self) -> list[str]:
        """按 SYNC_POLICY 过滤后的表名（保持 metadata 顺序，稳定输出）。"""
        out = []
        for name in Base.metadata.tables:
            if policy_of(name) is SyncPolicy.DERIVED_SKIP:
                continue
            out.append(name)
        return out

    def policy_report(self) -> dict[str, str]:
        return {name: policy_of(name).value for name in Base.metadata.tables}

    # ---------- snapshot（canon） ----------

    def snapshot(self) -> dict[str, dict[str, dict[str, Any]]]:
        """当前用户的全部可同步数据，规范成 JSON 安全的 {表: {id: 行}}。"""
        snap: dict[str, dict[str, dict[str, Any]]] = {}
        for name in self.synced_tables():
            tbl = Base.metadata.tables[name]
            q = select(tbl)
            if "user_id" in tbl.c:
                q = q.where(tbl.c.user_id == self.user_id)
            rows: dict[str, dict[str, Any]] = {}
            for mapping in self.db.execute(q).mappings():
                row = self._canon_row(name, dict(mapping))
                if row is None:
                    continue  # filtered 策略整行排除（如设备相关 settings 键）
                rows[row["id"]] = row
            snap[name] = rows
        return snap

    def _canon_row(self, table: str, row: dict[str, Any]) -> dict[str, Any] | None:
        policy = policy_of(table)
        if policy is SyncPolicy.FILTERED and table == "settings":
            # 整行排除（不是剥字段）：设备相关键不跨机同步
            if str(row.get("key", "")).startswith(SETTINGS_EXCLUDED_PREFIXES):
                return None
        if policy is SyncPolicy.ENCRYPTED_ONLY:
            allow = ENCRYPTED_ONLY_COLUMNS.get(table)
            if allow is not None:
                row = {k: v for k, v in row.items() if k in allow}
        return {k: _canon_value(v) for k, v in row.items()}

    # ---------- diff（三态 + LWW） ----------

    @staticmethod
    def _newer(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
        """LWW：updated_at 大者胜；相同则本地（b）胜 —— 稳定且可重放。"""
        au, bu = a.get("updated_at") or "", b.get("updated_at") or ""
        return a if au > bu else b

    @staticmethod
    def _row_equal(a: dict[str, Any], b: dict[str, Any]) -> bool:
        keys = set(a) | set(b)
        return all(a.get(k) == b.get(k) for k in keys)

    def diff(
        self,
        remote: dict[str, dict[str, dict[str, Any]]],
        propagate_deletes: bool = False,
    ) -> list[dict[str, Any]]:
        """远端快照 vs 本地快照 → 需要应用到本地的行。

        四态：
          remote-only            → 插入
          both & 不同 & 远端较新 → 更新（LWW）
          both & 不同 & 本地较新 → 跳过（导出方向会让远端追上）
          local-only & 开启删除传导 → 墓碑删除（软删，保留 deleted_at）

        删除传导**默认关闭**：远端包若只含部分表/部分数据（例如手工裁剪的
        包），开启会把本地数据误删。仅当对端是"权威全量"时才显式开启。
        """
        local = self.snapshot()
        ops: list[dict[str, Any]] = []
        for table, rrows in remote.items():
            if policy_of(table) is SyncPolicy.DERIVED_SKIP:
                continue  # 包里混入派生数据也不应用（防御）
            lrows = local.get(table, {})
            for rid, rrow in rrows.items():
                rrow = self._canon_row(table, dict(rrow))
                lrow = lrows.get(rid)
                if lrow is None:
                    ops.append({"table": table, "row": rrow, "op": "insert"})
                elif not self._row_equal(lrow, rrow):
                    winner = self._newer(rrow, lrow)
                    if winner is rrow:
                        ops.append({"table": table, "row": rrow, "op": "update"})
        # 删除传导：本地有而远端没有 → 对端已删，本地落墓碑（软删）
        if propagate_deletes:
            for table, lrows in local.items():
                if policy_of(table) is SyncPolicy.DERIVED_SKIP:
                    continue
                rrows = remote.get(table)
                if not rrows:
                    continue  # 对端没给这张表 = 不掌握情况，绝不动本地
                for lid in lrows:
                    if lid not in rrows:
                        ops.append({"table": table, "row": {"id": lid}, "op": "delete"})

        return ops

    def preview(self, remote: dict[str, dict[str, dict[str, Any]]],
                propagate_deletes: bool = False, sample: int = 8) -> dict[str, Any]:
        """导入前预览：只算不改库。返回摘要 + 样例，供人确认后再 apply。"""
        ops = self.diff(remote, propagate_deletes=propagate_deletes)
        by_table: dict[str, dict[str, int]] = {}
        by_op: dict[str, int] = {"insert": 0, "update": 0, "delete": 0}
        for o in ops:
            t = by_table.setdefault(o["table"], {"insert": 0, "update": 0, "delete": 0})
            t[o["op"]] = t.get(o["op"], 0) + 1
            by_op[o["op"]] = by_op.get(o["op"], 0) + 1
        samples = [
            {"table": o["table"], "op": o["op"], "id": o["row"].get("id"),
             "title": (o["row"].get("title") or o["row"].get("name") or o["row"].get("key") or "")}
            for o in ops[:sample]
        ]
        return {
            "total": len(ops),
            "by_op": by_op,
            "by_table": by_table,
            "samples": samples,
            "propagate_deletes": propagate_deletes,
        }

    def resolve_conflict(self, local_row: dict[str, Any], remote_row: dict[str, Any]) -> dict[str, Any]:
        """冲突解决预留接口。当前默认 LWW；将来可替换为字段级合并。"""
        return self._newer(remote_row, local_row)

    # ---------- apply ----------

    def apply(self, ops: list[dict[str, Any]]) -> dict[str, int]:
        """把 diff 结果写入本地库。upsert = 删旧行 + 插新行（SQLite 单事务）。"""
        stats = {"insert": 0, "update": 0, "delete": 0, "skipped": 0}
        now = utcnow()
        for oprec in ops:
            table = oprec["table"]
            tbl = Base.metadata.tables[table]
            row = self._decode_row(table, oprec["row"])

            # 删除传导：写墓碑而非硬删（保留同步所需的 deleted_at）
            if oprec["op"] == "delete":
                if "deleted_at" not in tbl.c:
                    stats["skipped"] += 1
                    continue
                res = self.db.execute(
                    tbl.update()
                    .where(tbl.c.id == row["id"])
                    .where(tbl.c.deleted_at.is_(None))
                    .values(deleted_at=now, updated_at=now)
                )
                stats["delete"] += int(res.rowcount or 0)
                continue

            existing = self.db.execute(
                select(tbl.c.id).where(tbl.c.id == row["id"])
            ).scalar()
            if existing is None:
                if oprec["op"] != "insert":
                    stats["skipped"] += 1
                    continue
                self.db.execute(tbl.insert().values(**row))
                stats["insert"] += 1
            else:
                if oprec["op"] != "update":
                    stats["skipped"] += 1
                    continue
                self.db.execute(tbl.delete().where(tbl.c.id == row["id"]))
                self.db.execute(tbl.insert().values(**row))
                stats["update"] += 1
        self.db.commit()
        return stats

    def _decode_row(self, table: str, row: dict[str, Any]) -> dict[str, Any]:
        """canon 的逆：ISO 字符串还原为 datetime/date（SQLite 列类型要求）。"""
        tbl = Base.metadata.tables[table]
        out: dict[str, Any] = {}
        for k, v in row.items():
            col = tbl.c.get(k)
            if (
                col is not None and isinstance(v, str)
                and isinstance(col.type, (sa.DateTime, sa.Date))
                and len(v) >= 19
            ):
                try:
                    v = datetime.fromisoformat(v)
                except ValueError:
                    pass
            out[k] = v
        return out

    # ---------- 本地适配器（P0）：JSON 同步包 ----------

    def export_to(self, directory: Path) -> Path:
        """导出同步包到本地目录（云适配器未来实现同一契约）。"""
        directory = Path(directory).resolve()
        if not directory.is_dir():
            raise ValueError(f"目录不存在: {directory}")
        stamp = utcnow().strftime("%Y%m%d-%H%M%S")
        path = directory / f"qimingxing-sync-{stamp}.json"
        payload = {
            "version": SYNC_PACKAGE_VERSION,
            "exported_at": utcnow().isoformat(),
            "user_id": self.user_id,
            "policy": self.policy_report(),
            "tables": self.snapshot(),
        }
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return path

    @staticmethod
    def load_package(path: Path) -> dict[str, Any]:
        path = Path(path).resolve()
        if not path.is_file():
            raise ValueError(f"同步包不存在: {path}")
        if path.stat().st_size > 50 * 1024 * 1024:
            raise ValueError("同步包超过 50MB 上限")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("version") != SYNC_PACKAGE_VERSION:
            raise ValueError(f"同步包版本不兼容: {payload.get('version')}")
        return payload
