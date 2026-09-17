# ============================================================
# 同步就绪性审计（为二期 S6-3「同步抽象层 + 本地适配器」铺路）
#
# 为什么需要它：
#   S6-3 的 diff-sync 依赖两样东西在**每一张业务表**上都存在：
#     1) updated_at  —— 判断"这条记录是否变过"（增量同步的基础）
#     2) deleted_at  —— 软删除（否则删除无法同步，只能硬删，多端必然复活数据）
#   实测结果是：只有部分表具备。缺哪张、缺哪列，肉眼翻 30+ 个模型很容易漏。
#   本脚本把答案变成一条命令，schema 演进后可随时重跑。
#
# 用法：cd backend && python scripts/audit_sync_readiness.py
# 退出码恒为 0（这是审计工具，不是守护测试）—— 便于在 CI 里当报告用。
# ============================================================
from __future__ import annotations

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app import models  # noqa: F401,E402  确保全部模型注册
from app.database import Base  # noqa: E402

# 这些是框架/配置类表，不参与用户数据同步，不需要审计
SKIP = {"alembic_version"}


def main() -> int:
    tables = sorted(t for t in Base.metadata.tables if t not in SKIP)

    ready, no_updated, no_deleted, no_both = [], [], [], []

    print("=" * 78)
    print("同步就绪性审计（S6-3 diff-sync 前置条件）")
    print("=" * 78)
    print(f"{'表名':<26}{'updated_at':<13}{'deleted_at':<13}就绪")
    print("-" * 78)

    for name in tables:
        cols = set(Base.metadata.tables[name].columns.keys())
        has_upd = "updated_at" in cols
        has_del = "deleted_at" in cols

        mark_upd = "✓" if has_upd else "✗ 缺"
        mark_del = "✓" if has_del else "✗ 缺"
        if has_upd and has_del:
            status = "✅ 就绪"
            ready.append(name)
        elif has_upd:
            status = "⚠️ 无软删除"
            no_deleted.append(name)
        elif has_del:
            status = "⚠️ 无 updated_at"
            no_updated.append(name)
        else:
            status = "❌ 均缺"
            no_both.append(name)

        print(f"{name:<26}{mark_upd:<13}{mark_del:<13}{status}")

    total = len(tables)
    print("-" * 78)
    print(f"合计 {total} 张表：")
    print(f"  ✅ 完全就绪            {len(ready):>3} 张")
    print(f"  ⚠️ 有 updated_at 缺软删 {len(no_deleted):>3} 张")
    print(f"  ⚠️ 有 deleted_at 缺时间 {len(no_updated):>3} 张")
    print(f"  ❌ 两者都缺            {len(no_both):>3} 张")
    print()

    if ready:
        print(f"已就绪：{', '.join(ready)}")
    if no_deleted or no_updated or no_both:
        need = sorted(set(no_deleted + no_updated + no_both))
        print()
        print(f"需要在 S6-3 落地前补齐（{len(need)} 张）：")
        print(f"  {', '.join(need)}")
        print()
        print("补齐方式建议：在 models/base.py 已有 TimestampMixin / SoftDeleteMixin，")
        print("让对应模型继承即可；schema 变更用新迁移（务必带 migration_helpers 幂等守卫）。")

    return 0


if __name__ == "__main__":
    sys.exit(main())
