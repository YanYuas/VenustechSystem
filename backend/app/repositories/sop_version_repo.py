# ============================================================
# SOP版本 Repository（二期 M10）
# ============================================================
from __future__ import annotations

from app.repositories.base import BaseRepository
from app.models.asset import SOPVersion


class SOPVersionRepository(BaseRepository[SOPVersion]):
    """SOP版本 数据访问层"""
    model = SOPVersion
