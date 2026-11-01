# ============================================================
# Phase17 · D-60：weekly 重复任务「无匹配目标日」必须有可诊断日志
#
# 原实现 target is None 时静默 continue，用户/排查者看不到模板为何没生成实例。
# 修复后打 debug（含 task_id / 规则 / base_date），行为不变（仍不生成）。
# ============================================================
from __future__ import annotations

from datetime import date, timedelta

from loguru import logger as loguru_logger

from app.services.task_service import TaskService
from tests.factories import make_task


def _capture(level: str = "DEBUG"):
    messages: list[str] = []
    sink_id = loguru_logger.add(
        lambda message: messages.append(message.record["message"]), level=level
    )
    return messages, sink_id


class TestWeeklyRecurringSkipLog:
    def test_weekly_without_reachable_weekday_logs_task_id_and_rule(
        self, db_session, test_user
    ):
        today = date.today()
        # base_date 在未来 100 天 → weekly 的 60 天窗口内永远找不到 >= base_date 的星期
        template = make_task(
            db_session, test_user.id, title="不可达周报",
            due_date=today + timedelta(days=100),
            recurrence={"type": "weekly", "days": [0], "interval": 1},
        )
        db_session.commit()

        messages, sink_id = _capture()
        try:
            created = TaskService(db_session).generate_recurring_instances(test_user.id)
        finally:
            loguru_logger.remove(sink_id)

        assert created == 0                                  # 行为不变：不生成
        skip_logs = [m for m in messages if "周期任务无匹配目标日" in m]
        assert skip_logs, "缺少可诊断日志"
        assert template.id in skip_logs[0]
        assert "weekly" in skip_logs[0]
        assert "days" in skip_logs[0] or "[0]" in skip_logs[0]

    def test_reachable_weekly_template_still_generates_and_does_not_log_skip(
        self, db_session, test_user
    ):
        today = date.today()
        make_task(
            db_session, test_user.id, title="正常周报",
            # 模板 due_date 设为上周同日：目标日=今天（不与模板自身判重）
            due_date=today - timedelta(days=7),
            recurrence={"type": "weekly", "days": [today.weekday()], "interval": 1},
        )
        db_session.commit()

        messages, sink_id = _capture()
        try:
            created = TaskService(db_session).generate_recurring_instances(test_user.id)
        finally:
            loguru_logger.remove(sink_id)

        assert created == 1
        assert [m for m in messages if "周期任务无匹配目标日" in m] == []
