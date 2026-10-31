# ============================================================
# Phase12 · D-49：TaskService.batch 失败原因可观测性
#
# 背景：批量循环里 `except Exception: failed += 1` 只计数，非法优先级 / 任务不存在
# 等原因在日志与响应里都看不到。修复后：`logger.warning("批量操作失败: ...")`
# 记录 task_id / action / reason；**BatchTaskResult 契约不变**（仍只有 affected/failed）。
#
# 日志断言用 loguru sink 捕获真实渲染后的 message（`{}` 占位已格式化）。
# ============================================================
from __future__ import annotations

import pytest
from loguru import logger as loguru_logger

from app.schemas.task import BatchTaskRequest
from app.services.task_service import TaskService
from tests.factories import make_task


@pytest.fixture()
def captured_logs():
    messages: list[str] = []
    sink_id = loguru_logger.add(
        lambda message: messages.append(message.record["message"]), level="WARNING"
    )
    try:
        yield messages
    finally:
        loguru_logger.remove(sink_id)


class TestBatchFailureObservability:
    def test_missing_or_foreign_task_logs_task_id_and_reason(
        self, db_session, test_user, captured_logs
    ):
        existing = make_task(db_session, test_user.id, title="存在的任务")
        db_session.commit()

        result = TaskService(db_session).batch(
            test_user.id,
            BatchTaskRequest(task_ids=[existing.id, "ghost-task-404"], action="complete"),
        )

        # 响应契约不变：仅 affected/failed
        assert result.affected == 1
        assert result.failed == 1
        assert set(type(result).model_fields) == {"affected", "failed"}

        joined = "\n".join(captured_logs)
        assert "批量操作失败" in joined
        assert "ghost-task-404" in joined
        assert "任务不存在或无权访问" in joined

    def test_invalid_priority_logs_task_id_action_and_reason(
        self, db_session, test_user, captured_logs
    ):
        first = make_task(db_session, test_user.id, title="批量A")
        second = make_task(db_session, test_user.id, title="批量B")
        db_session.commit()

        result = TaskService(db_session).batch(
            test_user.id,
            BatchTaskRequest(
                task_ids=[first.id, second.id],
                action="set_priority",
                priority="super-high",
            ),
        )

        assert result.affected == 0
        assert result.failed == 2

        joined = "\n".join(captured_logs)
        assert "批量操作失败" in joined
        assert first.id in joined and second.id in joined
        assert "action=set_priority" in joined
        assert "无效优先级: super-high" in joined
