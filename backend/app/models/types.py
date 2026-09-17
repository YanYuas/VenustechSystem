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
    """list[str] 存为 JSON 数组，读出兜底为 []。

    注意：必须在本类 __dict__ 里显式声明 cache_ok。
    SQLAlchemy 判定用的是 ``self.__class__.__dict__.get("cache_ok")``（type_api.py:1290），
    只看类自身声明、**不认继承**；仅靠继承 JSONType 的值会被判为"无缓存键"，
    导致所有含 StringListType 列的语句（如 documents.tags）每次执行都重新编译 SQL。
    """

    cache_ok = True

    def process_bind_param(self, value, dialect):  # type: ignore
        if value is None:
            return None
        return json.dumps(list(value), ensure_ascii=False)

    def process_result_value(self, value, dialect):  # type: ignore
        r = super().process_result_value(value, dialect)
        if r is None:
            return []
        return r if isinstance(r, list) else []
