# ============================================================
# Phase21 · D-75 桌宠配置前后端契约修复
#
# 背景：`/api/v1/pet/config` 曾返回 `size:"120"` / `speak_scene:"notification"`，
# 而前端契约是 size ∈ {small,medium,large}、speak_scene ∈
# {never,remind,interact,celebrate,always}。本文件钉住三件事：
#   1. seed_demo 演示数据必须写合法枚举（实际执行 seed_companion 后查询 DB）；
#   2. 请求 schema 对非法枚举拒绝（API 走项目统一校验错误 400/1001，不静默吞）；
#   3. 0023 数据迁移把历史脏值归一且幂等/可重复执行，downgrade 不回填脏值。
# ============================================================
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app.models.pet import PetConfig
from app.schemas.pet import UpdatePetConfigRequest
from scripts import seed_demo

PET_SIZES = {"small", "medium", "large"}
SPEAK_SCENES = {"never", "remind", "interact", "celebrate", "always"}

BACKEND_DIR = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = BACKEND_DIR / "migrations"


# ============================================================
# 一、seed_demo 演示数据契约
# ============================================================
class TestSeedDemoPetContract:
    def test_seed_companion_writes_contract_values(
        self, db_session, test_user, monkeypatch
    ):
        """真实执行 seed_companion 后，PetConfig 的 size/speak_scene 必须是合法枚举。"""
        monkeypatch.setattr(seed_demo, "_USER_ID", test_user.id, raising=False)
        monkeypatch.setattr(seed_demo, "_IDMAP", {}, raising=False)

        counts: dict[str, int] = {}
        seed_demo.seed_companion(db_session, counts)

        config = db_session.scalars(
            select(PetConfig).where(PetConfig.user_id == test_user.id)
        ).one()
        assert config.size in PET_SIZES, f"seed 写入了非法 size: {config.size!r}"
        assert config.speak_scene in SPEAK_SCENES, (
            f"seed 写入了非法 speak_scene: {config.speak_scene!r}"
        )
        assert counts["pet_configs"] == 1


# ============================================================
# 二、请求 schema 枚举校验
# ============================================================
class TestPetConfigRequestContract:
    @pytest.mark.parametrize("size", sorted(PET_SIZES))
    def test_valid_size_accepted(self, size):
        assert UpdatePetConfigRequest(size=size).size == size

    @pytest.mark.parametrize("size", ["120", "80", "160", "huge", "SMALL", ""])
    def test_invalid_size_rejected(self, size):
        with pytest.raises(ValidationError) as ei:
            UpdatePetConfigRequest(size=size)
        assert "size" in str(ei.value)

    @pytest.mark.parametrize("scene", sorted(SPEAK_SCENES))
    def test_valid_speak_scene_accepted(self, scene):
        assert UpdatePetConfigRequest(speak_scene=scene).speak_scene == scene

    @pytest.mark.parametrize("scene", ["notification", "remind2", ""])
    def test_invalid_speak_scene_rejected(self, scene):
        with pytest.raises(ValidationError) as ei:
            UpdatePetConfigRequest(speak_scene=scene)
        assert "speak_scene" in str(ei.value)

    def test_none_means_keep_unchanged(self):
        payload = UpdatePetConfigRequest(size=None, speak_scene=None)
        assert payload.model_dump(exclude_none=True) == {}

    def test_api_rejects_invalid_size_with_unified_envelope(self, client):
        r = client.patch("/api/v1/pet/config", json={"size": "120"})

        # 项目统一约定：请求校验错误 → HTTP 400 + code 1001（不是 FastAPI 默认 422）
        assert r.status_code == 400
        body = r.json()
        assert body["code"] == 1001
        assert body["message"].startswith("参数错误")
        assert "size" in body["message"]

    def test_api_rejects_invalid_speak_scene(self, client):
        r = client.patch("/api/v1/pet/config", json={"speak_scene": "notification"})

        assert r.status_code == 400
        assert r.json()["code"] == 1001
        assert "speak_scene" in r.json()["message"]

    def test_api_accepts_contract_values(self, client):
        r = client.patch(
            "/api/v1/pet/config", json={"size": "large", "speak_scene": "celebrate"}
        )

        assert r.status_code == 200
        data = r.json()["data"]
        assert data["size"] == "large"
        assert data["speak_scene"] == "celebrate"


# ============================================================
# 三、0023 数据归一化迁移
# ============================================================
@pytest.fixture()
def migration_env(tmp_path):
    """独立临时数据目录 + alembic 执行器（不触碰 conftest 测试库）。"""
    from app import config as app_config

    data_dir = tmp_path / "pet_migration_data"
    data_dir.mkdir(parents=True, exist_ok=True)
    previous = os.environ.get("VENUSTECH_DATA_DIR")

    def _point() -> None:
        os.environ["VENUSTECH_DATA_DIR"] = str(data_dir)
        app_config.get_settings.cache_clear()

    def _config():
        from alembic.config import Config

        cfg = Config()
        cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
        return cfg

    def upgrade(target: str) -> None:
        from alembic import command

        _point()
        command.upgrade(_config(), target)

    def downgrade(target: str) -> None:
        from alembic import command

        _point()
        command.downgrade(_config(), target)

    yield data_dir, upgrade, downgrade

    if previous is None:
        os.environ.pop("VENUSTECH_DATA_DIR", None)
    else:
        os.environ["VENUSTECH_DATA_DIR"] = previous
    app_config.get_settings.cache_clear()


def _insert_config(conn: sqlite3.Connection, row_id: str, size: str, scene: str) -> None:
    # 0001 冻结 DDL 预建了 pet_configs（部分 NOT NULL 列没有 server default），
    # 这里显式补齐全部 NOT NULL 列，模拟「历史脏数据行」。
    conn.execute(
        "INSERT INTO pet_configs ("
        "id, user_id, enabled, size, opacity, always_on_top, auto_start, "
        "position_x, position_y, state_awareness_enabled, action_switch_interval, "
        "show_bubble, bubble_duration, click_interaction, draggable, right_click_menu, "
        "tts_enabled, tts_rate, tts_pitch, tts_volume, speak_scene, "
        "intimacy, satiety, mood, energy, updated_at"
        ") VALUES (?, ?, 1, ?, 1.0, 1, 0, 0, 0, 1, 30, 1, 5, 1, 1, 1, 0, 1.0, 1.0, 0.8, ?, "
        "60, 60, 60, 60, '2026-01-01 00:00:00')",
        (row_id, f"user-{row_id}", size, scene),
    )


def _rows(conn: sqlite3.Connection) -> dict[str, tuple[str, str]]:
    return {
        row[0]: (row[1], row[2])
        for row in conn.execute("SELECT id, size, speak_scene FROM pet_configs").fetchall()
    }


class TestMigration0023PetNormalize:
    def test_0023_normalizes_legacy_values(self, migration_env):
        data_dir, upgrade, _downgrade = migration_env
        upgrade("0022")

        conn = sqlite3.connect(str(data_dir / "app.db"))
        try:
            _insert_config(conn, "c80", "80", "notification")
            _insert_config(conn, "c120", "120", "never")
            _insert_config(conn, "c160", "160", "")
            _insert_config(conn, "cok", "small", "celebrate")
            _insert_config(conn, "cbad", "huge", "bogus")
            conn.commit()
        finally:
            conn.close()

        upgrade("head")

        conn = sqlite3.connect(str(data_dir / "app.db"))
        try:
            rows = _rows(conn)
            version = conn.execute("SELECT version_num FROM alembic_version").fetchone()[0]
            assert version == "0023"
        finally:
            conn.close()

        assert rows["c80"] == ("small", "remind")
        assert rows["c120"] == ("medium", "never")
        assert rows["c160"] == ("large", "remind")
        assert rows["cok"] == ("small", "celebrate")       # 合法值原样保留
        assert rows["cbad"] == ("medium", "remind")        # 未知值走安全默认

    def test_0023_is_idempotent_and_downgrade_keeps_normalized(
        self, migration_env
    ):
        data_dir, upgrade, downgrade = migration_env
        upgrade("0022")
        conn = sqlite3.connect(str(data_dir / "app.db"))
        try:
            _insert_config(conn, "c80", "80", "notification")
            conn.commit()
        finally:
            conn.close()

        upgrade("head")
        first = None
        conn = sqlite3.connect(str(data_dir / "app.db"))
        try:
            first = _rows(conn)
        finally:
            conn.close()

        # 回退到 0022 再升级：0023 会再执行一次，但对已归一值幂等
        downgrade("0022")
        conn = sqlite3.connect(str(data_dir / "app.db"))
        try:
            after_downgrade = _rows(conn)      # downgrade 为 no-op：不回填脏值
        finally:
            conn.close()
        assert after_downgrade == first

        upgrade("head")
        conn = sqlite3.connect(str(data_dir / "app.db"))
        try:
            after_reupgrade = _rows(conn)
        finally:
            conn.close()
        assert after_reupgrade == first == {"c80": ("small", "remind")}
