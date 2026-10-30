# ============================================================
# scripts/seed_demo.py 安全护栏测试（Phase7-D）
#
# 为什么单独测这个脚本：它是**唯一会主动删除整个数据库文件**的入口
# （`--reset`）。护栏写错一次，用户多年的个人数据就没了 —— 这类代码
# 值得用可执行断言钉死，而不是只靠 review。
#
# 注意：本文件**绝不执行** main()/seed_all()（那会真的建库灌数）；
# 只测纯函数与护栏：assert_safe_to_reset / reset_db / bootstrap / 时间助手。
# 所有文件系统操作都在 VENUSTECH_TEST_DATA_DIR 下，用例后清理。
#
# 覆盖率说明：scripts/ 不在 `--cov=app` 统计口径内，本文件的价值是
# 行为护栏（防误删真实库），不是覆盖率数字。
# ============================================================
from __future__ import annotations

import shutil
import uuid
from datetime import timedelta
from pathlib import Path

import pytest

from app.config import get_settings
from scripts import seed_demo


def _temp_dir(prefix: str = "p7d-tmp") -> Path:
    directory = Path(get_settings().data_dir) / f"{prefix}-{uuid.uuid4().hex[:8]}"
    directory.mkdir(parents=True, exist_ok=False)
    return directory


@pytest.fixture()
def temp_dir():
    directory = _temp_dir()
    yield directory
    shutil.rmtree(directory, ignore_errors=True)


class TestResetGuard:
    def test_rejects_real_data_dir(self, temp_dir):
        """真实数据目录（backend/data 或系统默认数据目录）一律拒绝 --reset。"""
        real = seed_demo.BACKEND_DIR / "data"
        with pytest.raises(SystemExit) as ei:
            seed_demo.assert_safe_to_reset(real)
        assert "拒绝在该目录执行 --reset" in str(ei.value)
        assert "真实数据目录" in str(ei.value)

    def test_rejects_dir_without_demo_in_name(self, temp_dir):
        """目录名不含 demo → 拒绝（防止把 --data-dir 误指到正史目录）。"""
        with pytest.raises(SystemExit) as ei:
            seed_demo.assert_safe_to_reset(temp_dir)
        assert "目录名不含 demo" in str(ei.value)

    def test_accepts_demo_named_dir(self, temp_dir):
        demo_dir = temp_dir / "var-demo"
        demo_dir.mkdir()
        assert seed_demo.assert_safe_to_reset(demo_dir) is None


class TestResetDb:
    def test_reset_db_removes_only_sqlite_files(self, temp_dir):
        for suffix in ("app.db", "app.db-wal", "app.db-shm"):
            (temp_dir / suffix).write_bytes(b"x")
        keep = temp_dir / "keep.txt"
        keep.write_text("keep", encoding="utf-8")

        seed_demo.reset_db(temp_dir)

        assert not (temp_dir / "app.db").exists()
        assert not (temp_dir / "app.db-wal").exists()
        assert not (temp_dir / "app.db-shm").exists()
        assert keep.read_text(encoding="utf-8") == "keep"   # 不误删同目录其它文件

    def test_reset_db_on_empty_dir_is_noop(self, temp_dir):
        seed_demo.reset_db(temp_dir)  # 无文件时不抛
        assert list(temp_dir.iterdir()) == []


class TestBootstrapAndTimeHelpers:
    def test_bootstrap_sets_env_and_creates_absolute_dir(self, temp_dir, monkeypatch):
        target = temp_dir / "demo-boot"
        monkeypatch.setenv("VENUSTECH_DATA_DIR", str(get_settings().data_dir))

        returned = seed_demo.bootstrap(str(target))

        # 返回解析后的真实目录，且环境变量已指向它（app.config 在导入期读它）
        assert returned == target
        assert Path(seed_demo.os.environ["VENUSTECH_DATA_DIR"]) == target
        assert target.is_dir()  # bootstrap 负责建目录

    def test_ago_and_aday_are_relative_to_module_now(self):
        # 用模块级 NOW 做基准，避免「测试跨午夜」导致的偶发失败
        assert seed_demo.ago(days=2) == seed_demo.NOW - timedelta(days=2)
        assert seed_demo.aday(days=1) == (seed_demo.NOW - timedelta(days=1)).date()
        assert seed_demo.aday(days=0) == seed_demo.NOW.date()
