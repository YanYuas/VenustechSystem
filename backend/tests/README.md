# 测试体系规范

> 启明星系统后端测试从零搭建指南。所有新模块测试必须遵循本规范。

## 一、测试分层

| 层级 | 文件命名 | 隔离方式 | 速度 | 覆盖目标 |
|------|----------|----------|------|----------|
| 架构守护 | `test_architecture.py` | 无（只读源码） | 极快 | 分层依赖不漂移 |
| Service 单元 | `test_xxx_service.py` | 函数级事务回滚 | 快 | 业务规则、状态机、边界条件、异常路径 |
| API 集成 | `test_xxx_api.py` | 函数级清表 | 中 | HTTP 路由、参数校验、响应格式、端到端流程 |
| 冒烟 | `test_smoke.py` | 清表 | 中 | 核心链路不挂（CI 最小集） |

**原则**：业务规则优先写 Service 单元测试（快、隔离好、定位准）；
API 测试只验证「路由是否正确调用 Service + 响应格式是否正确」，不重复测业务逻辑。

## 二、目录结构

```
tests/
├── conftest.py          # 共享夹具（client / db_session / clean_db / test_user）
├── factories.py         # 测试数据工厂（make_task / make_subtask ...）
├── README.md            # 本文档
├── test_architecture.py # 架构守护（勿动）
├── test_smoke.py        # 冒烟（核心链路，CI 必跑）
├── test_task_service.py # Task Service 单元测试（样板）
└── test_task_api.py     # Task API 集成测试（样板）
```

## 三、Fixture 速查

```python
# Service 层测试：用 db_session + test_user
def test_xxx(db_session, test_user):
    svc = TaskService(db_session)
    task = svc.create(test_user.id, CreateTaskRequest(title="x"))
    # 测试结束自动 rollback，无需清理

# API 层测试：用 client + default_user_id
def test_xxx(client, default_user_id):
    r = client.post("/api/v1/tasks", json={"title": "x"})
    # 每个测试前自动清表（clean_db autouse）

# 造测试数据：用工厂函数
from tests.factories import make_task, make_task_via_api
task = make_task(db_session, test_user.id, status="completed")
task_data = make_task_via_api(client, title="hello")
```

## 四、命名规范

- 测试函数：`test_<被测动作>_<场景>_<预期结果>`
  - 好：`test_update_status_completed_sets_completed_at`
  - 差：`test1` / `test_task` / `test_update`
- 测试类：`Test<模块名><场景>`（仅在需要共享 setup 时用类）
- 一个测试只验证一个行为；多个断言必须围绕同一行为

## 五、断言风格

- 断言响应码 + 业务码 + 关键字段，不做全量 dict 比较
- 异常路径断言 `r.json()["code"]` 等于对应错误码
- Service 层异常用 `pytest.raises(TaskStateException)` 并检查 message
- 副作用断言用 `count_rows(db, "tasks", user_id=uid)` 或重新查询

## 六、运行方式

```bash
cd backend
.\.venv\Scripts\python.exe -m pytest tests/ -v           # 全部
.\.venv\Scripts\python.exe -m pytest tests/test_task_service.py -v  # 单文件
.\.venv\Scripts\python.exe -m pytest tests/ -k "focus"   # 按关键词筛选
.\.venv\Scripts\python.exe -m pytest tests/ --tb=short   # 简短报错
```

## 七、新增模块测试 Checklist

1. [ ] Service 层：CRUD 正常路径
2. [ ] Service 层：状态机 / 业务规则全部边界
3. [ ] Service 层：异常路径（NotFound / Validation / Business）
4. [ ] Service 层：越权访问（其他用户的数据不可见/不可改）
5. [ ] API 层：每个路由至少一个正常 + 一个参数校验失败
6. [ ] 工厂函数：在 factories.py 中补充该模块的 make_xxx
7. [ ] 运行全量测试确认无回归
