# ============================================================
# Health API 生产级集成测试
#
# 系统健康检查（基础设施）：基础健康 + 详细健康 + 系统信息
# 注意：这是只读端点，无数据库写操作，测试重点是返回结构完整性。
# ============================================================
from __future__ import annotations

import pytest


# ============================================================
# 第 1 组：基础健康 + 详细结构 + 数据库连接 + 系统信息 + 磁盘使用
# ============================================================

class TestHealthApiGroup1BasicDetailedSystem:
    """第1组：基础健康检查 + 详细健康结构 + 数据库连接 + 系统信息 + 磁盘使用。"""

    def test_health_basic_returns_ok(self, client):
        """基础健康检查返回 200，status=ok，包含 service/version/time。

        防什么：health 端点如果报错，Electron 主进程轮询会认为后端未就绪，
        应用无法启动。
        """
        r = client.get("/api/v1/health")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["status"] == "ok"
        assert "service" in data
        assert "version" in data
        assert "time" in data
        assert len(data["time"]) > 0

    def test_health_detailed_complete_structure(self, client):
        """详细健康检查返回完整结构：system/database/storage/paths 四大块。

        防什么：health/detailed 如果漏了某个字段，前端设置页的系统状态
        面板会显示空白。
        """
        r = client.get("/api/v1/health/detailed")
        assert r.status_code == 200
        data = r.json()["data"]

        # 顶层字段
        assert data["status"] == "ok"
        assert "uptime" in data
        assert "data_dir" in data

        # system 块
        assert "system" in data
        for key in ["os", "os_version", "platform", "python_version", "machine", "processor"]:
            assert key in data["system"], f"system 缺少字段: {key}"
        assert len(data["system"]["python_version"]) > 0

        # database 块
        assert "database" in data
        assert "connected" in data["database"]
        assert data["database"]["type"] == "sqlite"
        assert "size_mb" in data["database"]

        # storage 块
        assert "storage" in data
        for key in ["total_gb", "used_gb", "free_gb", "usage_percent"]:
            assert key in data["storage"], f"storage 缺少字段: {key}"

        # paths 块
        assert "paths" in data
        for key in ["data_dir", "backup_dir", "log_dir"]:
            assert key in data["paths"], f"paths 缺少字段: {key}"

    def test_health_detailed_db_connected(self, client):
        """详细健康检查中数据库连接状态为 True（测试环境数据库可连）。

        防什么：_check_db_connection 如果用了裸字符串而非 text() 包裹，
        在 SQLAlchemy 2.0 下会抛 ObjectNotExecutableError 并被吞掉，
        函数恒返回 False——数据库明明可连却报「未连接」。
        """
        r = client.get("/api/v1/health/detailed")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["database"]["connected"] is True

    def test_system_info_complete_structure(self, client):
        """系统信息端点返回完整结构：app/system/data_dir/database_size_mb/disk。

        防什么：system/info 如果漏了某个字段，前端设置页的关于面板
        会显示空白。
        """
        r = client.get("/api/v1/system/info")
        assert r.status_code == 200
        data = r.json()["data"]

        # app 块
        assert "app" in data
        assert "name" in data["app"]
        assert "version" in data["app"]
        assert "slogan" in data["app"]
        assert data["app"]["slogan"] == "方向启明，人生推演"

        # system 块
        assert "system" in data
        assert "os" in data["system"]
        assert "python" in data["system"]

        # 其他字段
        assert "data_dir" in data
        assert "database_size_mb" in data
        assert "disk" in data
        for key in ["total_gb", "used_gb", "free_gb", "usage_percent"]:
            assert key in data["disk"]

    def test_disk_usage_returns_positive_values(self, client):
        """磁盘使用情况返回正值（测试环境磁盘至少有数据）。

        防什么：_get_disk_usage 如果路径不存在或读取失败，会降级为全 0，
        前端磁盘进度条永远显示 0%。
        """
        r = client.get("/api/v1/health/detailed")
        assert r.status_code == 200
        storage = r.json()["data"]["storage"]

        # 总容量 > 0
        assert storage["total_gb"] > 0
        # 已用 + 剩余 ≈ 总量（允许浮点误差）
        assert abs((storage["used_gb"] + storage["free_gb"]) - storage["total_gb"]) < 1.0
        # 使用率在 0-100 之间
        assert 0 <= storage["usage_percent"] <= 100
