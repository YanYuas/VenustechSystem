# ============================================================
# 配置管理（pydantic-settings）
# 环境变量前缀：VENUSTECH_（如 VENUSTECH_PORT / VENUSTECH_DATA_DIR）
# ============================================================
from __future__ import annotations

from functools import lru_cache
import logging
import os
import sys
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 开发/源码运行的数据目录（相对**仓库根**解析，与 CWD 无关）：
#   var/data  —— 目标位置（ARCHITECTURE.md §7 / ADR-0004：运行期数据统一在 var/）
#   backend/data —— 旧位置，仅作一次性迁移兼容回退（见下方 _default_data_dir）
_DEV_VAR_DATA = Path(__file__).resolve().parents[2] / "var" / "data"
_DEV_LEGACY_DATA = Path(__file__).resolve().parents[1] / "data"


def _default_data_dir() -> Path:
    """数据目录：打包环境用系统标准位置，开发/源码运行用仓库根 var/data。

    - Windows: %APPDATA%/VenustechSystem
    - macOS: ~/Library/Application Support/VenustechSystem
    - Linux: ~/.local/share/VenustechSystem
    """
    if getattr(sys, "frozen", False):
        if sys.platform == "win32":
            base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        elif sys.platform == "darwin":
            base = str(Path.home() / "Library" / "Application Support")
        else:
            base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
        return Path(base) / "VenustechSystem"
    # 开发/源码运行：**相对仓库根解析，而不是相对当前工作目录**。
    #
    # 为什么不能写相对 CWD 的路径：从仓库根执行 `uvicorn app.main:app` 或在 IDE
    # 里指定别的 working directory 时，会静默创建第二份数据库（用户看到"数据全
    # 没了"）。这是真实事故来源（2026-10 审计发现根目录已出现 data/ 残留）。
    # 现约定：默认数据目录恒为 <仓库根>/var/data，与启动方式无关。
    #
    # 兼容回退（一次性迁移辅助，2026-10-27 var/ 迁移时引入）：
    #   老 checkout 的真实库还在 backend/data，而 var/data 尚未迁移时，回退到
    #   旧目录并告警，避免"升级代码后数据看起来全没了"。
    #   删除条件（满足任一即可删掉本分支）：
    #     · 所有用户数据都已迁移到 var/data（本次 runbook 完成 + 发布一版后）；
    #     · ARCHITECTURE.md §7 移除 backend/data 兼容说明时同步删除。
    if not _DEV_VAR_DATA.exists() and _DEV_LEGACY_DATA.exists():
        logging.getLogger(__name__).warning(
            "数据目录回退：%s 不存在但旧目录 %s 存在，本次使用旧目录。"
            "请按 docs/runbooks/backup.md 把数据迁移到 var/data（一次性兼容分支，可删除）。",
            _DEV_VAR_DATA,
            _DEV_LEGACY_DATA,
        )
        return _DEV_LEGACY_DATA
    return _DEV_VAR_DATA


class Settings(BaseSettings):
    """应用配置，全部可由环境变量覆盖，无硬编码。"""

    app_name: str = "启明星系统后端"
    version: str = "1.0.0"

    # 运行
    dev: bool = True
    host: str = "127.0.0.1"
    port: int = 8765

    # CORS 允许来源（逗号分隔，环境变量 VENUSTECH_CORS_ORIGINS 覆盖）
    # 公网部署时通过 VENUSTECH_CORS_ORIGINS=* 允许所有来源
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000,https://localhost,capacitor://localhost"

    # 数据目录（开发/源码运行默认 <仓库根>/var/data；打包后走 %APPDATA%/VenustechSystem，
    # 可由环境变量 VENUSTECH_DATA_DIR 注入）
    data_dir: Path = _default_data_dir()

    # 日志
    log_level: str = "INFO"

    # AI（DeepSeek 兼容 OpenAI 格式）
    ai_base_url: str = "https://api.deepseek.com/v1"
    ai_model: str = "deepseek-chat"
    ai_timeout: float = 30.0

    # 首次启动是否灌演示数据（PRD §36.2）
    demo_seed: bool = True

    model_config = SettingsConfigDict(
        env_prefix="VENUSTECH_",
        env_file=".env",
        extra="ignore",
    )

    # ---- 派生路径 ----
    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def db_path(self) -> Path:
        d = self.data_dir
        d.mkdir(parents=True, exist_ok=True)
        return d / "app.db"

    @property
    def db_url(self) -> str:
        return f"sqlite:///{self.db_path.as_posix()}"

    @property
    def logs_dir(self) -> Path:
        d = self.data_dir / "logs"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def backups_dir(self) -> Path:
        d = self.data_dir / "backups"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def documents_dir(self) -> Path:
        d = self.data_dir / "documents"
        d.mkdir(parents=True, exist_ok=True)
        return d


@lru_cache
def get_settings() -> Settings:
    return Settings()
