# ============================================================
# SyncEngine 服务层测试（D-07：core/sync.py 下沉为 services/sync/）
#
# 覆盖目标（行为零变化前提下把旧实现逐条钉住）：
#   1. SYNC_POLICY 表分级：policy_report / synced_tables 排除 derived-skip
#   2. encrypted-only：只同步密文列白名单，明文列（notes）剥除
#   3. filtered：settings 设备相关键前缀（workspace. / sync.）整行排除
#   4. snapshot → diff → apply 往返；LWW + 字段级合并；删除传导默认关闭
#   5. 导出/导入：JSON 包结构、增量游标（sync.last_export_at）、load_package 校验
#   6. 公共 API 面（app.services.sync）与 api/sync.py 的路由接线
#   7. 回归：旧 core/sync.py、core/sync_adapters.py、core/cache.py 已删除
#
# 数据构造用 Folder/Setting/VaultItem —— 与本次重构无关的稳定模型，
# 避免依赖并发改动中的 task schema。
# ============================================================
from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path

import pytest
from sqlalchemy import delete, select

from app.models.base import Base
from app.models.folder import Folder
from app.models.settings import Setting
from app.models.vault import VaultConfig, VaultItem
from app.services.sync import (
    SYNC_PACKAGE_VERSION,
    SYNC_POLICY,
    SyncEngine,
    SyncPolicy,
    policy_of,
)
from app.services.sync.engine import (
    ENCRYPTED_ONLY_COLUMNS,
    SETTINGS_EXCLUDED_PREFIXES,
)


@pytest.fixture()
def pkg_dir():
    """同步包目录：放在测试数据目录内（沙箱下系统 %TEMP% 不可写）。

    conftest 在会话结束时整体删除 VENUSTECH_TEST_DATA_DIR，无需额外清理。
    """
    from app.config import get_settings

    d = Path(get_settings().data_dir) / "sync_test_pkgs"
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True, exist_ok=True)
    yield d
    shutil.rmtree(d, ignore_errors=True)


def _engine(db, user) -> SyncEngine:
    return SyncEngine(db, user.id)


def _folder(db, user_id: str, name: str, **kwargs) -> Folder:
    row = Folder(user_id=user_id, name=name, **kwargs)
    db.add(row)
    db.flush()
    return row


def _setting(db, user_id: str, key: str, value: str | None = "v") -> Setting:
    row = Setting(user_id=user_id, key=key, value=value)
    db.add(row)
    db.flush()
    return row


# ============================================================
# 一、表分级策略
# ============================================================
class TestSyncPolicyReport:
    def test_policy_report_covers_every_orm_table(self):
        """SYNC_POLICY 不得登记 metadata 里不存在的表（防止表改名后策略失效）。"""
        assert set(SYNC_POLICY) <= set(Base.metadata.tables)

    def test_policy_report_values(self, db_session, test_user):
        report = _engine(db_session, test_user).policy_report()
        # 每个 metadata 表都有分级（不多不少）
        assert set(report) == set(Base.metadata.tables)
        assert report["workspace_files"] == "derived-skip"
        assert report["audit_logs"] == "derived-skip"
        assert report["settings_history"] == "derived-skip"
        assert report["vault_items"] == "encrypted-only"
        assert report["vault_config"] == "encrypted-only"
        assert report["settings"] == "filtered"
        assert report["folders"] == "full"
        assert report["tasks"] == "full"

    def test_policy_of_defaults_to_full(self):
        assert policy_of("folders") is SyncPolicy.FULL
        assert policy_of("table_that_does_not_exist") is SyncPolicy.FULL

    def test_policy_enum_values_frozen(self):
        """枚举值是对外契约（前端/同步包/验收用），不得悄悄改字面量。"""
        assert SyncPolicy.FULL.value == "full"
        assert SyncPolicy.DERIVED_SKIP.value == "derived-skip"
        assert SyncPolicy.ENCRYPTED_ONLY.value == "encrypted-only"
        assert SyncPolicy.FILTERED.value == "filtered"

    def test_encrypted_only_whitelist_defined(self):
        assert set(ENCRYPTED_ONLY_COLUMNS) == {"vault_items", "vault_config"}
        assert "secret_encrypted" in ENCRYPTED_ONLY_COLUMNS["vault_items"]
        assert "notes" not in ENCRYPTED_ONLY_COLUMNS["vault_items"]

    def test_settings_excluded_prefixes_frozen(self):
        assert SETTINGS_EXCLUDED_PREFIXES == ("workspace.", "sync.")


class TestSyncedTables:
    def test_excludes_derived_skip_tables(self, db_session, test_user):
        tables = _engine(db_session, test_user).synced_tables()
        for skipped in ("workspace_files", "audit_logs", "settings_history"):
            assert skipped not in tables
        assert "folders" in tables
        assert "settings" in tables
        assert "vault_items" in tables

    def test_matches_metadata_order_and_policy_filter(self, db_session, test_user):
        expected = [
            name for name in Base.metadata.tables
            if policy_of(name) is not SyncPolicy.DERIVED_SKIP
        ]
        assert _engine(db_session, test_user).synced_tables() == expected


# ============================================================
# 二、snapshot 的行级过滤
# ============================================================
class TestSnapshotFiltering:
    def test_encrypted_only_strips_plaintext_columns(self, db_session, test_user):
        item = VaultItem(
            user_id=test_user.id,
            name="路由器",
            category="login",
            username="admin",
            secret_encrypted="fernet:fake-token",
            notes="明文备注不该进同步包",
        )
        db_session.add(item)
        config = VaultConfig(user_id=test_user.id, salt="ab" * 16, verifier="fernet:verifier")
        db_session.add(config)
        db_session.flush()

        snap = _engine(db_session, test_user).snapshot()

        row = snap["vault_items"][item.id]
        assert set(row) <= ENCRYPTED_ONLY_COLUMNS["vault_items"]
        assert row["secret_encrypted"] == "fernet:fake-token"
        assert "notes" not in row, "明文列 notes 必须被剥除"
        cfg = snap["vault_config"][config.id]
        assert set(cfg) <= ENCRYPTED_ONLY_COLUMNS["vault_config"]
        assert "salt" in cfg and "verifier" in cfg

    def test_filtered_settings_excludes_device_keys(self, db_session, test_user):
        theme = _setting(db_session, test_user.id, "theme", "dark")
        notify = _setting(db_session, test_user.id, "notify.sound", "true")
        workspace = _setting(db_session, test_user.id, "workspace.enabled", "true")
        cursor = _setting(db_session, test_user.id, "sync.last_export_at", "2026-01-01T00:00:00")

        snap = _engine(db_session, test_user).snapshot()
        settings_rows = snap["settings"]

        assert theme.id in settings_rows
        assert notify.id in settings_rows
        assert workspace.id not in settings_rows, "workspace.* 是设备键，不跨机同步"
        assert cursor.id not in settings_rows, "sync.* 游标不得进同步包"

    def test_snapshot_scoped_to_current_user(self, db_session, test_user, other_user):
        mine = _folder(db_session, test_user.id, "我的文件夹")
        theirs = _folder(db_session, other_user.id, "别人的文件夹")
        snap = _engine(db_session, test_user).snapshot()
        assert mine.id in snap["folders"]
        assert theirs.id not in snap["folders"]

    def test_snapshot_canonicalizes_datetime_to_iso(self, db_session, test_user):
        _folder(db_session, test_user.id, "时间规范化")
        snap = _engine(db_session, test_user).snapshot()
        row = next(iter(snap["folders"].values()))
        assert isinstance(row["created_at"], str)
        assert isinstance(row["updated_at"], str)


# ============================================================
# 三、diff / apply
# ============================================================
class TestDiffAndApply:
    def test_snapshot_diff_apply_roundtrip(self, db_session, test_user):
        """导出方向：snapshot 得到远端包；本地丢行后 diff→apply 能原样恢复。"""
        folder = _folder(db_session, test_user.id, "往返文件夹")
        engine = _engine(db_session, test_user)

        remote = engine.snapshot()
        assert folder.id in remote["folders"]

        # 模拟本地缺行（例如换了设备/新装库）
        db_session.execute(delete(Folder).where(Folder.id == folder.id))
        db_session.flush()
        db_session.expire_all()
        assert db_session.get(Folder, folder.id) is None

        ops = engine.diff(remote)
        folder_ops = [o for o in ops if o["table"] == "folders"]
        assert [o["op"] for o in folder_ops] == ["insert"]
        assert folder_ops[0]["row"]["name"] == "往返文件夹"

        stats = engine.apply(ops)
        assert stats["insert"] >= 1
        restored = db_session.get(Folder, folder.id)
        db_session.refresh(restored)
        assert restored is not None
        assert restored.name == "往返文件夹"

    def test_lww_remote_newer_wins_and_merges_empty_fields(self, db_session, test_user):
        """远端较新 → 赢；远端为空的字段保留本地非空值（O5 字段级合并）。"""
        parent = _folder(db_session, test_user.id, "父文件夹")
        child = _folder(db_session, test_user.id, "子文件夹", parent_id=parent.id)
        engine = _engine(db_session, test_user)
        remote = engine.snapshot()
        remote_row = remote["folders"][child.id]
        remote_row["updated_at"] = "2999-01-01T00:00:00"
        remote_row["name"] = "远端改名"
        remote_row["parent_id"] = None  # 远端空值不得覆盖本地非空

        ops = engine.diff(remote)
        child_ops = [o for o in ops if o["table"] == "folders" and o["row"].get("id") == child.id]
        assert len(child_ops) == 1 and child_ops[0]["op"] == "update"
        assert child_ops[0]["row"]["name"] == "远端改名"
        assert child_ops[0]["row"]["parent_id"] == parent.id

        engine.apply(child_ops)
        db_session.expire_all()
        updated = db_session.get(Folder, child.id)
        assert updated.name == "远端改名"
        assert updated.parent_id == parent.id

    def test_local_newer_is_skipped(self, db_session, test_user):
        folder = _folder(db_session, test_user.id, "本地较新")
        engine = _engine(db_session, test_user)
        remote = engine.snapshot()
        remote["folders"][folder.id]["name"] = "更旧的远端名"
        remote["folders"][folder.id]["updated_at"] = "2000-01-01T00:00:00"

        ops = engine.diff(remote)
        assert [o for o in ops if o["table"] == "folders"] == []

    def test_delete_propagation_off_by_default(self, db_session, test_user):
        a = _folder(db_session, test_user.id, "会被删的")
        _folder(db_session, test_user.id, "保留的")
        engine = _engine(db_session, test_user)
        remote = engine.snapshot()
        remote["folders"].pop(a.id)  # 远端没有它

        assert [o for o in engine.diff(remote) if o["table"] == "folders"] == []

    def test_delete_propagation_opt_in_writes_tombstone(self, db_session, test_user):
        a = _folder(db_session, test_user.id, "墓碑测试")
        keep = _folder(db_session, test_user.id, "不该动")
        engine = _engine(db_session, test_user)
        remote = engine.snapshot()
        remote["folders"].pop(a.id)

        ops = engine.diff(remote, propagate_deletes=True)
        folder_ops = [o for o in ops if o["table"] == "folders"]
        assert {(o["op"], o["row"]["id"]) for o in folder_ops} == {("delete", a.id)}

        stats = engine.apply(folder_ops)
        assert stats["delete"] == 1
        db_session.expire_all()
        assert db_session.get(Folder, a.id).deleted_at is not None
        assert db_session.get(Folder, keep.id).deleted_at is None

    def test_remote_derived_skip_rows_are_ignored(self, db_session, test_user):
        """防御：即使同步包里混入 derived-skip 表，diff 也不应用。"""
        engine = _engine(db_session, test_user)
        remote = {"workspace_files": {"x": {"id": "x", "rel_path": "a.txt"}}}
        assert engine.diff(remote) == []

    def test_preview_reports_counts_without_writing(self, db_session, test_user):
        folder = _folder(db_session, test_user.id, "预览用")
        engine = _engine(db_session, test_user)
        remote = engine.snapshot()
        # 模拟本地缺行 → 预览应报 insert，但不得写库
        db_session.execute(delete(Folder).where(Folder.id == folder.id))
        db_session.flush()
        db_session.expire_all()

        preview = engine.preview(remote)
        assert preview["total"] >= 1
        assert preview["by_op"]["insert"] >= 1
        assert preview["propagate_deletes"] is False
        assert db_session.get(Folder, folder.id) is None


# ============================================================
# 四、导出包 / 增量游标 / 导入
# ============================================================
class TestExportImportAndCursor:
    def test_full_export_writes_package_and_advances_cursor(self, db_session, test_user, pkg_dir):
        _folder(db_session, test_user.id, "导出文件夹")
        engine = _engine(db_session, test_user)

        path = engine.export_to(pkg_dir)
        assert path.exists() and path.name.startswith("qimingxing-sync-")

        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["version"] == SYNC_PACKAGE_VERSION
        assert payload["user_id"] == test_user.id
        assert payload["incremental"] is False
        assert payload["since"] is None
        assert payload["policy"]["workspace_files"] == "derived-skip"
        assert payload["row_count"] == sum(len(v) for v in payload["tables"].values())
        assert payload["tables"]["folders"]

        # 游标：全量导出同样推进（否则首次增量退化为全量）
        db_session.expire_all()
        cursor = db_session.scalars(
            select(Setting).where(
                Setting.user_id == test_user.id, Setting.key == "sync.last_export_at"
            )
        ).first()
        assert cursor is not None and cursor.value
        assert cursor.value.startswith("20")

    def test_incremental_export_only_contains_new_rows(self, db_session, test_user, pkg_dir):
        old = _folder(db_session, test_user.id, "旧的")
        engine = _engine(db_session, test_user)
        engine.export_to(pkg_dir)

        new = _folder(db_session, test_user.id, "增量后的新行")
        inc_path = engine.export_to(pkg_dir, incremental=True)

        payload = json.loads(inc_path.read_text(encoding="utf-8"))
        assert inc_path.name.endswith("-inc.json")
        assert payload["incremental"] is True
        assert payload["since"] is not None
        assert new.id in payload["tables"]["folders"]
        assert old.id not in payload["tables"]["folders"], "游标前的行不应再进增量包"

    def test_export_rejects_missing_directory(self, db_session, test_user, pkg_dir):
        with pytest.raises(ValueError):
            _engine(db_session, test_user).export_to(pkg_dir / "not-exists")

    def test_load_package_rejects_missing_and_wrong_version(self, pkg_dir):
        with pytest.raises(ValueError):
            SyncEngine.load_package(pkg_dir / "missing.json")

        bad = pkg_dir / "bad.json"
        bad.write_text(json.dumps({"version": SYNC_PACKAGE_VERSION + 1, "tables": {}}), encoding="utf-8")
        with pytest.raises(ValueError):
            SyncEngine.load_package(bad)

    def test_import_roundtrip_restores_deleted_row(self, db_session, test_user, pkg_dir):
        folder = _folder(db_session, test_user.id, "导入恢复")
        engine = _engine(db_session, test_user)
        path = engine.export_to(pkg_dir)

        db_session.execute(delete(Folder).where(Folder.id == folder.id))
        db_session.flush()
        db_session.expire_all()
        assert db_session.get(Folder, folder.id) is None

        payload = SyncEngine.load_package(path)
        ops = engine.diff(payload["tables"])
        stats = engine.apply(ops)
        assert stats["insert"] >= 1
        db_session.expire_all()
        restored = db_session.get(Folder, folder.id)
        assert restored is not None and restored.name == "导入恢复"

    def test_import_package_from_other_user_is_api_level_guard(self):
        """用户归属校验在 api 层（api/sync.py 的 403 语义），引擎只消费 tables。"""
        src = (Path(__file__).resolve().parents[1]
               / "app" / "api" / "sync.py").read_text(encoding="utf-8")
        assert "同步包属于其他用户，拒绝导入" in src


# ============================================================
# 五、公共 API 面 / 路由接线 / 旧位置已移除
# ============================================================
class TestPublicSurface:
    def test_public_api_reexports(self):
        import app.services.sync as pkg
        assert pkg.SyncEngine is SyncEngine
        assert pkg.SyncPolicy is SyncPolicy
        assert pkg.SYNC_POLICY is SYNC_POLICY
        assert pkg.SYNC_PACKAGE_VERSION == SYNC_PACKAGE_VERSION
        assert pkg.policy_of is policy_of

    def test_api_sync_uses_service_package(self):
        src = (Path(__file__).resolve().parents[1]
               / "app" / "api" / "sync.py").read_text(encoding="utf-8")
        assert "from app.services.sync import SyncEngine" in src
        assert "app.core.sync" not in src

    def test_legacy_core_modules_removed(self):
        for legacy in ("app.core.sync", "app.core.sync_adapters", "app.core.cache"):
            assert importlib.util.find_spec(legacy) is None, f"{legacy} 应已删除"

    def test_policy_endpoint_is_wired(self, client, default_user_id):
        r = client.get("/api/v1/sync/policy")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["policy"]["workspace_files"] == "derived-skip"
        assert "tasks" in data["policy"]
        assert "workspace_files" not in data["synced_tables"]
