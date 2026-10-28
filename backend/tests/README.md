# 测试体系规范

> 启明星系统后端测试从零搭建指南。**所有新增/修改测试必须遵循本规范**。
> 架构约束见 `docs/architecture/ARCHITECTURE.md`；请求体 `null` 语义见 ADR-0008。

## 一、测试分层

| 层级 | 文件命名 | 隔离方式 | 速度 | 覆盖目标 |
|------|----------|----------|------|----------|
| 架构守护 | `test_architecture.py` / `scripts/audit_architecture.py` | 无（只读源码 / AST） | 极快 | 分层依赖、路由注册、领域归属不漂移 |
| Service 单元 | `test_xxx_production.py`、`test_xxx_service.py` | 函数级事务回滚（`db_session`） | 快 | 业务规则、状态机、边界、异常路径 |
| API 集成 | `test_xxx_api.py` | 函数级清表（`clean_db` autouse） | 中 | HTTP 路由、参数校验、响应信封、端到端 |
| 契约/专项 | `test_logging_contract.py`、`test_transaction_atomicity.py`、`test_repository_contract.py`、`test_migration_integrity.py` | 视内容而定 | 快/中 | 跨模块契约、事务原子性、迁移基线 |
| 冒烟 | `test_smoke.py` | 清表 | 中 | 核心链路不挂（CI 最小集） |

**原则**：
1. 业务规则优先写 Service 单元测试（快、隔离好、定位准）；
2. API 测试只验证「路由是否正确调用 Service + 响应格式/错误码」，不重复测业务逻辑；
3. 纯函数（`core/response.py`、`schemas/*`、`sync/adapters`）直接单元测试，不拉起 app。

## 二、目录结构与命名

```
backend/tests/
├── conftest.py          # 共享夹具（client / db_session / clean_db / test_user / other_user）
├── factories.py         # 测试数据工厂（make_task / make_document / seed_*_fixture ...）
├── README.md            # 本文档
└── test_*.py
```

- 测试函数：`test_<被测动作>_<场景>_<预期结果>`（好：`test_update_status_completed_sets_completed_at`；差：`test1`、`test_task`）
- 测试类：`Test<模块><场景>`，仅在需要共享 setup/分组时用类
- 一个测试只验证一个行为；多个断言必须围绕同一行为

## 三、AAA 结构与独立性

- 每个用例按 **Arrange（造数据）→ Act（调用）→ Assert（断言）** 顺序书写，中间不夹杂无关逻辑；
- **禁止顺序依赖**：单文件与全量都必须绿；不依赖前一个用例留下的数据（`clean_db` 每例前清表）；
- 模块级全局状态必须显式隔离（例：`core/event_bus` 的类级订阅表、`vault_service` 的解锁态、`plugin_manager` 的单例）——用 fixture 保存/恢复或 `monkeypatch`；
- 慢测试（>1s/例，如迁移完整性、加密 KDF、全量同步包）集中登记在本节末尾表格，新增时补一行，便于本地 `-k` 跳过。

| 慢测试文件 | 原因 | 本地跳过方式 |
|---|---|---|
| `test_migration_integrity.py` | 全量建库/迁移对账 | `-k "not migration"` |
| `test_encryption_production.py` | PBKDF2/Fernet 密钥派生 | `-k "not encryption"` |
| `test_backup_production.py` | 真实文件打包/校验 | `-k "not backup"` |

## 四、Fixture 与数据工厂（唯一入口）

```python
# Service 层：db_session + test_user，结束自动 rollback
def test_xxx(db_session, test_user):
    svc = TaskService(db_session)
    ...

# API 层：client + default_user_id，每例前 clean_db 清表
def test_xxx(client, default_user_id):
    r = client.post("/api/v1/tasks", json={"title": "x"})

# 造数据：现有工厂优先，不要自己 new 真实数据目录
from tests.factories import make_task, make_task_via_api, count_rows
```

**硬约束**：
1. 测试数据目录由 `conftest.py` 指向系统临时目录（`VENUSTECH_TEST_DATA_DIR` 可覆盖）；**任何测试不得读写仓库内真实 `var/data`、`var/demo`**；
2. 需要落盘时一律写到 `VENUSTECH_TEST_DATA_DIR` 下的子目录，并在用例内 `finally` 清理；
3. 不新起独立数据库文件、不跑 seed/demo 脚本、不联网（AI/HTTP 用 Fake/Mock 或 `monkeypatch` 替换）。

## 五、断言风格

- 先断言 HTTP 状态码，再断言业务码（`code`），最后断言关键字段；不做全量 dict 比较；
- 异常路径必须覆盖：`404`（不存在）、`400/1001`（参数/校验）、`409/3001`（业务冲突）、`403`（越权）；
- Service 层异常用 `pytest.raises(具体异常类型)` 并检查 message 关键片段；
- 副作用要查库确认（`count_rows(...)` / 重新查询），不能只看响应；
- **禁止 `assert True`、禁止无断言的"跑通即通过"、禁止断言恒真条件**（如 `assert x is not None or True`）；
- 断言失败信息要能自解释（必要时加 `, "省略 project_id 不得解除关联"` 这类说明）。

## 六、ADR-0008：请求体 null 语义

`exclude_unset=True` 是后端 Update 层的统一实现方式，测试必须区分两件事：

| 请求体 | 语义 | 断言要点 |
|---|---|---|
| `{}` / 字段缺失 | 不改 | 原值保持不变 |
| `{"project_id": null}` | 清空 | 响应里该字段为 `None`，且数据库已落库 |

schema 层用 `model_dump(exclude_unset=True)` 断言；API 层用 PATCH 后 GET/响应数据断言（参考 `test_service_boundaries.py::TestNullSemanticsEndToEnd`）。

## 七、覆盖率

- 工具：`pytest-cov==5.0.0` + `coverage==7.17.0`（见 `requirements-dev.txt`）；
- 本地与 CI 同一命令（CI 只报告、**不 hard fail**）：

```bash
cd backend
python -m pytest tests -q --cov=app --cov-report=term-missing
```

- 新增模块时看 `term-missing`：新增代码应有测试覆盖，且优先补"未覆盖行数最多"的模块（不追求总百分比数字）。
- 多人/多任务并行跑覆盖率时，默认的 backend/.coverage 会被并发覆盖导致 JSON 报告残缺；此时用 COVERAGE_FILE=<独立路径> 指定数据文件（CI 单 job 无此问题）。

## 八、运行方式

```bash
cd backend
.\.venv\Scripts\python.exe -m pytest tests -q                 # 全部
.\.venv\Scripts\python.exe -m pytest tests/test_task_api.py -q # 单文件
.\.venv\Scripts\python.exe -m pytest tests -k "focus" -q       # 关键词
.\.venv\Scripts\python.exe -m pytest tests -q --tb=short       # 简短报错
```

## 九、Mock 约定（外部依赖零联网）

涉及 LLM / HTTP / 子进程的测试**一律用替身**，禁止真联网、真等待：

- **HTTP 层**：monkeypatch 模块级 `httpx.AsyncClient`（替身实现 `__aenter__/__aexit__/post/get/stream`），
  并用类级 `script` 列表预排"响应 / 异常"序列，同时记录 `calls` 断言 URL、headers、params；
- **LLM 编排层**：构造 `AIService` 后直接替换 `svc.client` 为 Fake（`chat()` 返回 `AIResponse(content=...)`），
  断言 prompt 里带上下文、temperature 等调用参数，以及非法 JSON / 空响应的降级分支；
- **重试/超时**：monkeypatch `asyncio.sleep` 为空实现，让指数退避测试毫秒级完成；
- **错误映射**：非 2xx → `AIRequestFailedException`、网络错误重试耗尽 → 同上、
  上游不可达 → 降级缓存或 `ok=False`，逐条断言而不是只断言"不抛异常"；
- **全局单例**（`event_bus` / `plugin_manager` / `aihot._cache` / vault 解锁态）：
  用 fixture 保存→清空→恢复，避免用例间串味；插件测试在 `VENUSTECH_TEST_DATA_DIR` 内造插件目录；
- 断言重点 = **调用参数 + 错误映射 + 降级分支**，不要只测 happy path。

## 十、新增模块测试 Checklist

1. [ ] Service 层：CRUD 正常路径
2. [ ] Service 层：状态机 / 业务规则全部边界
3. [ ] Service 层：异常路径（NotFound / Validation / Business）
4. [ ] Service 层：越权访问（其他用户的数据不可见/不可改）
5. [ ] API 层：每个路由至少一个正常 + 一个参数校验失败（含 404/409）
6. [ ] `null` vs 省略语义（若该请求体含可空字段，按 ADR-0008 各写一条）
7. [ ] 工厂函数：在 `factories.py` 中补充该模块的 `make_xxx`（若需重复造数据）
8. [ ] 跑单文件 + 全量，确认无顺序依赖、无残留数据
9. [ ] `ruff check app tests scripts` 通过
