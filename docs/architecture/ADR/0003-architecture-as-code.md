# ADR-0003 架构即代码：领域地图 + AST 守护 + 债务棘轮

- 状态：**已采纳并落地**（2026-10-26）
- 相关：[ARCHITECTURE.md](../../../ARCHITECTURE.md) §4、§9；`scripts/audit_architecture.py`

## 背景

项目原有的 `backend/tests/test_architecture.py` 只有 5 条**文本包含**断言
（如 `assert "from app.models" not in content`）。2026-10 审计实测：

- 它**通过**了 5/5；
- 但同期存在 `core → services` 的真实反向依赖、16 个 service 绕过 repository、
  路由/模型注册缺口——它一条都没抓到。
- 且唯一 CI 只打 Android 包，这些断言从未在 CI 跑过。

结论：**靠"文档 + 字符串匹配"守架构，等于没守**。

## 决策

1. **领域地图是数据**：`docs/architecture/domains.json` 登记 8 个互斥领域及其模块；
   新增模块必须先登记，否则守护失败。
2. **守护用 AST**：`scripts/audit_architecture.py` 解析真实 import 图（区分运行时与
   `TYPE_CHECKING`），校验分层方向、core 隔离、命名、路由/模型注册、领域归属、根目录契约、
   前端 views 横向依赖。
3. **债务棘轮**：`scripts/architecture_baseline.json` 登记"已确认但暂不修"的违规；
   **基线内降级为 WARN，基线外立即失败**。修掉后必须从基线删除，债务只减不增。
4. **单一入口**：`backend/tests/test_architecture.py` 只做一层薄壳调用该脚本，pytest 与
   `check_all.py`（第 1 项）与 CI 消费同一套规则，不允许两套规则漂移。
5. **跳过 ≠ 通过**：`check_all.py --strict` 下"缺依赖而跳过"视为失败，防止干净环境假绿。

## 后果

- ✅ 架构违规从"事后审计发现"变成"提交时变红"。
- ✅ 领域地图同时是文档与机器契约（人和 CI 读同一份）。
- ⚠️ 规则本身需要维护：新增一类结构约束时，加规则 + 加测试，别只在文档里写。

## 替代方案

- 引入第三方 `import-linter`：功能可用，但需新增依赖且无法校验领域归属/根目录契约。否决。
- 只在 PR review 时人工检查：不可持续（本项目历史上已失守一次）。
