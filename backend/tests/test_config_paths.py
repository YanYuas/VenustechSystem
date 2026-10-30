# ============================================================
# Phase8 · config 路径解析补缺（覆盖率 top-up，服务于 D-30/31/33/34/35 的
# "全量覆盖率不低于 95.80%" 门禁；不改 app 代码，只补分支测试）
#
# 覆盖：
#   - _default_data_dir() 的三个打包平台分支（win32 / darwin / 其它）；
#   - 开发期 backend/data 旧目录兼容回退（含告警文案）；
#   - documents_dir 属性创建目录；
#   - Settings.db_url / logs_dir 派生路径。
# 所有目录都在 VENUSTECH_TEST_DATA_DIR 内，绝不触碰真实 var/data。
# ============================================================
from __future__ import annotations

import logging
import sys
from pathlib import Path

import pytest

from app import config
from app.config import Settings, _default_data_dir


@pytest.fixture()
def fake_paths():
    d = Path(config.get_settings().data_dir) / "config-test"
    d.mkdir(parents=True, exist_ok=True)
    yield d


class TestFrozenDataDir:
    """打包环境（sys.frozen=True）按平台选系统标准目录。"""

    def test_windows_uses_appdata(self, fake_paths, monkeypatch):
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.setenv("APPDATA", str(fake_paths / "roaming"))
        assert _default_data_dir() == fake_paths / "roaming" / "VenustechSystem"

    def test_windows_without_appdata_falls_back_to_home(self, fake_paths, monkeypatch):
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_paths / "home"))
        monkeypatch.delenv("APPDATA", raising=False)
        assert _default_data_dir() == fake_paths / "home" / "AppData" / "Roaming" / "VenustechSystem"

    def test_macos_uses_library_application_support(self, fake_paths, monkeypatch):
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "platform", "darwin")
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_paths / "home"))
        assert _default_data_dir() == (
            fake_paths / "home" / "Library" / "Application Support" / "VenustechSystem"
        )

    def test_linux_uses_xdg_data_home(self, fake_paths, monkeypatch):
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.setenv("XDG_DATA_HOME", str(fake_paths / "xdg"))
        assert _default_data_dir() == fake_paths / "xdg" / "VenustechSystem"

    def test_linux_without_xdg_falls_back_to_local_share(self, fake_paths, monkeypatch):
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_paths / "home"))
        assert _default_data_dir() == (
            fake_paths / "home" / ".local" / "share" / "VenustechSystem"
        )


class TestLegacyDataDirFallback:
    """开发期 backend/data 兼容回退：var/data 不存在而旧目录存在时告警并回退。"""

    def test_falls_back_to_legacy_dir_with_warning(
        self, fake_paths, monkeypatch, caplog
    ):
        legacy = fake_paths / "legacy-data"
        legacy.mkdir()
        monkeypatch.setattr(config, "_DEV_VAR_DATA", fake_paths / "var-data")
        monkeypatch.setattr(config, "_DEV_LEGACY_DATA", legacy)
        with caplog.at_level(logging.WARNING, logger="app.config"):
            assert _default_data_dir() == legacy
        assert "数据目录回退" in caplog.text
        assert str(legacy) in caplog.text

    def test_uses_var_data_when_it_exists(self, fake_paths, monkeypatch):
        var_data = fake_paths / "var-data"
        var_data.mkdir()
        monkeypatch.setattr(config, "_DEV_VAR_DATA", var_data)
        monkeypatch.setattr(config, "_DEV_LEGACY_DATA", fake_paths / "legacy")
        assert _default_data_dir() == var_data


class TestSettingsDerivedPaths:
    def test_documents_dir_is_created(self, fake_paths):
        settings = Settings(_env_file=None, data_dir=fake_paths / "s1")
        documents = settings.documents_dir
        assert documents == fake_paths / "s1" / "documents"
        assert documents.is_dir()

    def test_db_url_and_logs_dir(self, fake_paths):
        settings = Settings(_env_file=None, data_dir=fake_paths / "s2")
        assert settings.db_url == f"sqlite:///{(fake_paths / 's2' / 'app.db').as_posix()}"
        assert settings.logs_dir.is_dir()
        assert settings.backups_dir.is_dir()
