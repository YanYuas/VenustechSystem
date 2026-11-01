# ============================================================
# Phase17 · D-59：sqlite3 日期 adapter 显式注册（消除 Python 3.12+ 弃用告警）
#
# 断言：
#   · date / datetime 绑定后落库为 ISO 文本，格式与旧默认 adapter 完全一致；
#   · 绑定过程不再产生 "The default date adapter is deprecated" 弃用告警；
#   · ORM Date 列写入→读回仍正确（持久化行为不变）。
# ============================================================
from __future__ import annotations

import sqlite3
import warnings
from datetime import date, datetime

from tests.factories import make_task


class TestSqliteDateAdapter:
    def _connect(self, tmp_path) -> sqlite3.Connection:
        conn = sqlite3.connect(str(tmp_path / "adapter.db"))
        conn.execute("CREATE TABLE probe (d TEXT, ts TEXT)")
        return conn

    def test_date_and_datetime_bind_as_iso_text(self, tmp_path):
        conn = self._connect(tmp_path)
        try:
            conn.execute(
                "INSERT INTO probe (d, ts) VALUES (?, ?)",
                (date(2026, 11, 1), datetime(2026, 11, 1, 12, 30, 45, 123456)),
            )
            conn.commit()
            d_text, ts_text = conn.execute("SELECT d, ts FROM probe").fetchone()
        finally:
            conn.close()

        assert d_text == "2026-11-01"                       # 与 sqlite3 默认 date adapter 一致
        assert ts_text == "2026-11-01 12:30:45.123456"      # 空格分隔 ISO，与默认一致

    def test_binding_dates_emits_no_default_adapter_deprecation(self, tmp_path):
        conn = self._connect(tmp_path)
        try:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                conn.execute(
                    "INSERT INTO probe (d, ts) VALUES (?, ?)",
                    (date(2026, 11, 2), datetime(2026, 11, 2, 8, 0, 0)),
                )
                conn.commit()
        finally:
            conn.close()

        bad = [
            str(item.message)
            for item in caught
            if "default date adapter" in str(item.message).lower()
        ]
        assert bad == []        # 显式 adapter 生效，弃用告警消失

    def test_orm_date_roundtrip_unchanged(self, db_session, test_user):
        task = make_task(
            db_session, test_user.id, title="日期往返",
            due_date=date(2026, 11, 3),
        )
        db_session.commit()
        task_id = task.id

        db_session.expire_all()
        reloaded = db_session.get(type(task), task_id)

        assert reloaded.due_date == date(2026, 11, 3)       # 读回仍是 date（非字符串）
