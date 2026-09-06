# ============================================================
# 配置管理（pydantic-settings）
# 环境变量前缀：VENUSTECH_（如 VENUSTECH_PORT / VENUSTECH_DATA_DIR）
# ============================================================
from __future__ import annotations

from functools import lru_cache
import os
import sys
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_data_dir() -> Path:
    """数据目录：打包环境用系统标准位置，开发环境用 ./data。

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
    return Path("./data")


class Settings(BaseSettings):
    """应用配置，全部可由环境变量覆盖，无硬编码。"""

    app_name: str = "启明星系统后端"
    version: str = "0.2.0"

    # 运行
    dev: bool = True
    host: str = "127.0.0.1"
    port: int = 8765

    # CORS 允许来源（逗号分隔，环境变量 VENUSTECH_CORS_ORIGINS 覆盖）
    # 公网部署时通过 VENUSTECH_CORS_ORIGINS=* 允许所有来源
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000"

    # 数据目录（开发默认 ./data，打包后走 %APPDATA%/VenustechSystem，可由环境变量注入）
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
