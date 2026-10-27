"""归一历史遗留的任务状态 "todo" → "pending"

Revision ID: 0022
Revises: 0021
Create Date: 2026-10-27

背景（Phase 2 契约对齐 D-08 的收尾）
=====================================
工作流模块历史上曾把任务落库为 `status="todo"`。该值不在
`TaskService.STATUS_TRANSITIONS` 白名单里，后果是：

  · 任务"创建成功但列表里看不见"（按状态过滤只认白名单）；
  · 任何流转都报 3001，任务永久卡死。

代码侧已在 2026-10-11 修复（生成任务改用合法状态），并留了回归测试；
但**历史数据库里仍残留 todo 行**（本机实测 1 行）。

Phase 2 给 API 响应加了 `TaskStatus` 枚举（Literal）——如果不先归一，
列出这些历史任务时响应校验会直接 500。因此本迁移做一次幂等数据修复。

幂等性
======
`UPDATE ... WHERE status='todo'`，重复执行无副作用；对全新库是 no-op。

downgrade
=========
不做回滚：无法区分"原本就是 pending"与"由 todo 归一而来"的行。数据修复类
迁移的惯例是 downgrade 留空并在注释说明，而不是猜一个可能错的方向。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.migration_helpers import table_exists

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    if not table_exists(conn, "tasks"):
        return
    conn.execute(sa.text("UPDATE tasks SET status = 'pending' WHERE status = 'todo'"))


def downgrade() -> None:
    # 不可逆的数据修复：见文件头说明。
    pass
