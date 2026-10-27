# ============================================================
# 同步领域服务（D-07：原 core/sync.py 整体下沉）
#
# 为什么在 services/ 而不是 core/：
#   diff-sync 的"表分级策略 / 密文列白名单 / settings 键过滤 /
#   导出游标 / LWW 合并"是业务能力，不是无业务语义的基础设施。
#   它依赖 ORM metadata 与业务表结构，因此归入 platform 领域的
#   service 层；core/ 只保留真正与业务无关的机制（event_bus /
#   encryption / logger 等）。
#
# 对外只暴露稳定 API；`app.services.sync.engine` 是实现细节。
# ============================================================
from __future__ import annotations

from app.services.sync.engine import (
    SYNC_PACKAGE_VERSION,
    SYNC_POLICY,
    SyncEngine,
    SyncPolicy,
    policy_of,
)

__all__ = [
    "SyncEngine",
    "SyncPolicy",
    "SYNC_POLICY",
    "SYNC_PACKAGE_VERSION",
    "policy_of",
]
