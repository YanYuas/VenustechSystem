# ============================================================
# 架构守护测试（对齐架构 v2.0 §18.1.1）
# 保证分层依赖不漂移：api→services→repositories→models
# ============================================================
from __future__ import annotations

from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
APP_DIR = BACKEND_DIR / "app"


def _read(source: str) -> str:
    return (APP_DIR / source).read_text(encoding="utf-8")


class TestArchitecture:
    def test_api_not_import_models_directly(self):
        """api 层禁止运行时直接 import app.models，必须走 services（TYPE_CHECKING 除外）。"""
        import re
        for f in (APP_DIR / "api").glob("*.py"):
            if f.name == "__init__.py":
                continue
            content = f.read_text(encoding="utf-8")
            # 移除 TYPE_CHECKING 块后再检查
            cleaned = re.sub(r"if TYPE_CHECKING:.*?(?=\n\S|\Z)", "", content, flags=re.DOTALL)
            assert "from app.models" not in cleaned, f"api/{f.name} 禁止运行时直接 import models"

    def test_api_not_query_db_directly(self):
        """api 层禁止直接 db.query / SessionLocal，必须走 service。"""
        for f in (APP_DIR / "api").glob("*.py"):
            if f.name in ("__init__.py", "deps.py"):
                continue
            content = f.read_text(encoding="utf-8")
            assert "SessionLocal(" not in content, f"api/{f.name} 不应直接创建 Session"

    def test_service_not_import_fastapi(self):
        """service 层禁止依赖 FastAPI（保持与框架解耦）。"""
        for f in (APP_DIR / "services").rglob("*.py"):
            if f.name == "__init__.py":
                continue
            content = f.read_text(encoding="utf-8")
            assert "fastapi" not in content, f"services/{f.relative_to(APP_DIR/'services')} 禁止 import fastapi"

    def test_repository_not_import_services(self):
        """repositories 层禁止依赖 services（单向依赖）。"""
        for f in (APP_DIR / "repositories").glob("*.py"):
            if f.name == "__init__.py":
                continue
            content = f.read_text(encoding="utf-8")
            assert "from app.services" not in content, f"repositories/{f.name} 禁止依赖 services"

    def test_all_models_registered(self):
        """models/__init__ 导出的模型均可在 metadata 找到表。"""
        from app import models  # noqa: F401
        from app.database import Base

        expected = {
            "users", "tasks", "subtasks", "folders", "documents",
            "document_versions", "backlinks", "conversations", "messages",
            "reviews", "settings",
        }
        actual = set(Base.metadata.tables.keys())
        assert expected <= actual, f"缺失表: {expected - actual}"
