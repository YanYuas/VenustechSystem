# ============================================================
# 统一响应格式（对齐前端 types/api.ts ApiResponse）
# ============================================================
from __future__ import annotations

import time
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ApiResponse(BaseModel):
    code: int = 0
    message: str = "success"
    data: Any = None
    timestamp: int = Field(default_factory=lambda: int(time.time()))


def _serialize(data: Any) -> Any:
    """递归把 Pydantic 模型/日期转换为 JSON 可序列化结构。"""
    if isinstance(data, BaseModel):
        return data.model_dump(mode="json")
    if isinstance(data, (list, tuple)):
        return [_serialize(x) for x in data]
    if isinstance(data, dict):
        return {k: _serialize(v) for k, v in data.items()}
    if isinstance(data, datetime):
        return data.isoformat()
    return data


def success(data: Any = None, message: str = "success") -> dict:
    return ApiResponse(code=0, message=message, data=_serialize(data)).model_dump(mode="json")


def error(code: int, message: str) -> dict:
    return ApiResponse(code=code, message=message).model_dump(mode="json")
