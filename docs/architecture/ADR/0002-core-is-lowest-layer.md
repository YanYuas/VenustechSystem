# ADR-0002 `core/` 必须是最底层：业务订阅者上移组合根

- 状态：**已采纳并落地**（2026-10-26）
- 相关：[ARCHITECTURE.md](../../../ARCHITECTURE.md) §4.1、`backend/app/bootstrap/`

## 背景

`core/` 被定义为"基础设施层"：事件总线、加密、缓存、插件、日志、异常、响应、同步。
它本应只被业务层依赖。但审计发现：

```
core/event_handlers.py   →  app.services.ai, app.repositories
core/growth_handlers.py  →  app.services.growth_service, app.repositories
```

即 **基础设施层反向依赖业务层**。后果：

1. `core/` 不再可独立复用——任何只想用加密或事件总线的代码都会被动拉起大半个业务层。
2. 依赖图出现"底层依赖顶层"的环风险，分层规则形同虚设。
3. 新的启动期逻辑（定时器、订阅者）习惯性往 `core/` 塞，持续恶化。

## 决策

1. 把两个订阅者模块移动到 **组合根** `backend/app/bootstrap/`：
   - `bootstrap/event_handlers.py`：业务事件订阅（AI 摘要/标签、通知）
   - `bootstrap/growth_handlers.py`：成长体系订阅（EXP/技能归类）
2. `core/` 的允许依赖收敛为 `{core, models}`（models 是纯数据定义，不算业务逻辑）。
3. 组合根（`main.py`、`bootstrap/`、`api/deps.py`）拥有装配特权，可依赖任意层。
4. 该规则由 `scripts/audit_architecture.py` 的 **R2-core-isolation** 强制，违反即 CI 红。

## 后果

- ✅ `core/` 成为真正可复用、可单测的最底层；依赖图无环。
- ✅ 启动期逻辑有了明确归属（`bootstrap/`），不再污染 `core/`。
- ⚠️ 剩余债务：`core/sync.py` 仍含约 389 行领域逻辑（D-07），需在 Phase 2 拆到
  `services/` 或 `core/sync_adapters` 的端口/适配器结构中，本轮不动以免扩大回归面。

## 替代方案

- 让 `core` 保留订阅者但"约定"不 import 业务层：不可验证，审计已证明会失守。否决。
- 用依赖注入把回调传给 core：增加间接层，且启动期装配本来就应该在组合根。否决。
