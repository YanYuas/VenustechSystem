# ============================================================
# SQLite 无原生 JSON/数组，用 TypeDecorator 以 TEXT 存 JSON
# ============================================================
from __future__ import annotations

import json

from sqlalchemy.types import Text, TypeDecorator


class JSONType(TypeDecorator):
    """任意 JSON 值（dict/list/标量）存为 TEXT。"""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):  # type: ignore
        if value is None:
            return None
        return json.dumps(value, ensure_ascii=False)

    def process_result_value(self, value, dialect):  # type: ignore
        if value is None:
            return None
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return None


class StringListType(JSONType):
    """list[str] 存为 JSON 数组，读出兜底为 []。"""

    def process_bind_param(self, value, dialect):  # type: ignore
        if value is None:
            return None
        return json.dumps(list(value), ensure_ascii=False)

    def process_result_value(self, value, dialect):  # type: ignore
        r = super().process_result_value(value, dialect)
        if r is None:
            return []
        return r if isinstance(r, list) else []
