"""归一 pet_configs 的历史脏值（桌宠契约 D-75）

Revision ID: 0023
Revises: 0022
Create Date: 2026-11-01

背景（Phase21 前后端契约不一致）
================================
前端契约（`frontend/src/features/pet/model.ts`）：
  · size        ∈ {small, medium, large}
  · speak_scene ∈ {never, remind, interact, celebrate, always}

但历史演示 seed（`backend/scripts/seed_demo.py`）与更早的代码曾写入：
  · size        = 80 / 120 / 160（数值或数字字符串）
  · speak_scene = "notification" 等前端未定义值

后果（Lead 浏览器实测）：`/api/v1/pet/config` 返回 `size:"120"` /
`speak_scene:"notification"`，桌宠设置页 BaseSelect 找不到匹配项 → 显示「请选择」；
DesktopPet 按 size 计算宽高也会拿到非法值。

本迁移把历史行归一为合法枚举（请求层已改用 Literal 校验，新写入不会再产生脏值）：
  · 80 → small，120 → medium，160 → large；其它未知 size → medium（安全默认）
  · 未知/空 speak_scene → remind（与列默认值一致）

幂等性
======
只更新 `NOT IN (合法枚举)` 的行，重复执行无副作用；对全新库是 no-op。

downgrade
=========
不做「还原脏值」：无法区分「原本就是合法值」与「由脏值归一而来」的行，猜一个
方向反而可能制造新的非法数据。数据修复类迁移惯例是 downgrade 留空并注释说明。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.migration_helpers import table_exists

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None

_SIZE_CASE = """
UPDATE pet_configs
   SET size = CASE CAST(size AS TEXT)
                WHEN '80'  THEN 'small'
                WHEN '120' THEN 'medium'
                WHEN '160' THEN 'large'
                ELSE 'medium'
              END
 WHERE size IS NULL
    OR CAST(size AS TEXT) NOT IN ('small', 'medium', 'large')
"""

_SPEAK_SCENE_SQL = """
UPDATE pet_configs
   SET speak_scene = 'remind'
 WHERE speak_scene IS NULL
    OR speak_scene NOT IN ('never', 'remind', 'interact', 'celebrate', 'always')
"""


def upgrade() -> None:
    conn = op.get_bind()
    if not table_exists(conn, "pet_configs"):
        return
    conn.execute(sa.text(_SIZE_CASE))
    conn.execute(sa.text(_SPEAK_SCENE_SQL))


def downgrade() -> None:
    # 不可逆的数据归一：见文件头「downgrade」说明。
    pass
