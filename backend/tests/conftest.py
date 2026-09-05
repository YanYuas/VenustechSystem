# ============================================================
# pytest 共享夹具：临时数据目录 + TestClient
# ============================================================
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

TEST_DATA_DIR = BACKEND_DIR / "data_test"

# 模块级设置环境变量（必须在任何 app 导入之前执行）
os.environ["VENUSTECH_DATA_DIR"] = str(TEST_DATA_DIR)
os.environ["VENUSTECH_DEV"] = "false"
os.environ["VENUSTECH_DEMO_SEED"] = "false"

# 清理旧测试数据
if TEST_DATA_DIR.exists():
    shutil.rmtree(TEST_DATA_DIR, ignore_errors=True)


@pytest.fixture(scope="session", autouse=True)
def _env_setup():
    """会话级清理：测试后删除测试数据。"""
    yield
    shutil.rmtree(TEST_DATA_DIR, ignore_errors=True)


@pytest.fixture(scope="session")
def client(_env_setup):
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as c:
        yield c
