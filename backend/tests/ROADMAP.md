# 后端测试推进路线图

> 从零搭建测试体系的分阶段计划。task 模块已完成样板，后续按此推进。
>
> **2026-10-11**：全量清点 + 分级升级，共两轮。P0/P1/P2/P3（安全面）全部补齐，
> 过程中修复 **12 处生产代码缺陷**（两轮各 6 处，详见文末）。
> 所有数字均来自本次实际 `pytest --collect-only` / `pytest tests/` 输出，非估算。

## 当前状态（2026-10-11 实测：**40 文件 / 873 用例**，全量 31.7s）

### 基础设施与守护

| 文件 | 用例数 | 层级 |
|------|--------|------|
| test_architecture.py | 5 | 架构守护（分层依赖） |
| test_db_infrastructure.py | 12 | 数据库基础设施回归守护（连接池/WAL/级联/清表循环） |
| test_smoke.py | 7 | 冒烟 |

### P0 核心业务

| 文件 | 用例数 | 层级 |
|------|--------|------|
| test_task_production.py | 64 | Service 单元（样板） |
| test_task_api.py | 26 | API 集成（样板） |
| test_document_production.py | 45 | Service 单元 |
| test_document_api.py | 30 | API 集成 |
| test_folder_production.py | 30 | Service 单元 |
| test_folder_api.py | 10 | API 集成 |
| test_project_production.py | 35 | Service 单元 |
| test_project_api.py | 15 | API 集成 |
| test_review_production.py | 30 | Service 单元 |
| test_review_api.py | 15 | API 集成 |
| test_identity_production.py | 25 | Service 单元 |
| test_identity_api.py | 15 | API 集成 |

### P1 系统支撑

| 文件 | 用例数 | 层级 |
|------|--------|------|
| test_settings_production.py | 36 | Service 单元 |
| test_settings_api.py | 10 | API 集成 |
| test_notification_production.py | 16 | Service 单元 |
| test_notification_api.py | 13 | API 集成 |
| test_backup_production.py | 19 | Service 单元 |
| test_backup_api.py | 11 | API 集成（仅拒绝路径） |
| test_conversation_production.py | 18 | Service 单元（含 SSE） |
| test_conversation_api.py | 11 | API 集成 |
| test_dashboard_production.py | 10 | Service 单元 |
| test_dashboard_api.py | 5 | API 集成 |

### P2 领域功能

| 文件 | 用例数 | 层级 |
|------|--------|------|
| test_learning_production.py | 15 | Service 单元 |
| test_learning_api.py | 15 | API 集成 |
| test_life_production.py | 10 | Service 单元 |
| test_life_api.py | 20 | API 集成 |
| test_growth_production.py | 11 | Service 单元 |
| test_growth_api.py | 5 | API 集成 |
| test_asset_production.py | 42 | Service 单元（SOP/Prompt/Skill/项目记忆） |
| test_asset_api.py | 25 | API 集成 |
| test_workflow_production.py | 20 | Service 单元（含应用引擎） |
| test_workflow_api.py | 13 | API 集成 |
| test_health_api.py | 5 | API 集成 |

### P3 安全面与资源独立端点（第二轮补齐）

| 文件 | 用例数 | 层级 |
|------|--------|------|
| test_vault_production.py | 79 | Service 单元（主密码生命周期 / 不落盘 / 白名单 / 归属） |
| test_vault_api.py | 28 | API 集成 |
| test_resource_production.py | 41 | Service 单元（收集箱 / 模板库 / 领域库） |
| test_resource_api.py | 31 | API 集成（含 IDOR 与 mass-assignment 契约） |

> **vault 测试的两条安全纪律**（写入用例注释，勿放宽）：
> 1. **绝不制造「密钥文件真实存在」的场景** —— `run_action` 会真的
>    `Popen("cmd.exe", "/K", "ssh ...")`。只测拒绝路径，并用
>    `monkeypatch.setattr(subprocess, "Popen", ...)` 兜底断言未启动进程。
> 2. **绝不真打网络** —— `test_action_connection` 只做 TCP 探测，
>    用 `monkeypatch.setattr(socket, "create_connection", ...)` 模拟可达/不可达。
>
> `_session_keys`（解锁态）是**进程内存全局**，而 `clean_db` 只清表 ——
> vault 的测试文件必须自带 autouse fixture 清理它，否则跨用例泄漏
> （单用户模式下 `default_user.id` 固定，必然串扰）。

### 尚未覆盖

| 模块 | 备注 |
|------|------|
| assistant | 依赖外部 AI API，需 mock |
| plugins | 插件系统，需隔离测试环境 |
| pet | 桌面宠物，逻辑薄、偏前端交互 |
| avatar | AI 头像生成，依赖外部服务 |
| workspace / panel / mood / diary 等零散端点 | 由 dashboard 与 life 间接覆盖 |

> 前端仍为零单元测试（仅 `test-offline-queue.ts` / `test-http-connectivity.ts`
> 两个 esbuild 脚本，已纳入 `scripts/check_all.py` 第 7、8 项）。

## 推进原则

1. **先 Service 后 API**：业务规则在 Service 层测透，API 只测路由和参数校验
2. **先核心后边缘**：用户每天用的功能优先；**安全面（vault）优先级高于业务面**
3. **每模块完成后跑全量**：确保无回归
4. **发现 bug 当场修**：测试的价值就是暴露问题，不要攒着
5. **越权必须单独成组**：每个 Service 都要有「他人数据 → 404 且零副作用」的用例
6. **回归断言要写清「原缺陷是什么」**：只断言现象会被后人当成"设计如此"而删掉
7. **按前端真实契约写 API 测试**：先读 `frontend/src/api/*.ts` 核对参数位置
   （query / body / 路径），不要凭后端签名猜 —— 本轮即因此发现 `batch-process` 契约错配

## 每模块执行 Checklist

```
1. [ ] 读 frontend/src/api/<模块>.ts，核对每个端点的参数传递方式
2. [ ] 编写 test_xxx_production.py（CRUD + 业务规则 + 异常 + 越权）
3. [ ] 编写 test_xxx_api.py（路由 + 参数校验 + 端到端）
4. [ ] 运行该模块测试全部通过
5. [ ] 运行全量测试确认无回归
6. [ ] 更新本文档进度（数字取自本次实际输出）
```

## 本轮修复（第二轮 · 2026-10-11，vault / resource 模块）

| # | 位置 | 缺陷 | 后果 |
|---|------|------|------|
| 1 | `services/resource_service.py` | 构造函数不收 `user_id`，11 个单条操作零归属校验 | **IDOR**：任何登录用户拿到 id 即可读改删他人的收集箱条目 / 模板 / 领域 |
| 2 | `services/resource_service.py` | `update_template` / `update_domain` 收裸 `dict` 直传 `repo.update` | **mass-assignment**：可改 `user_id` / `id` / `use_count` / `is_builtin` / `sort_order` |
| 3 | `services/resource_service.py` | `process_inbox_item` 非法 action 抛裸 `ValueError` | 无 handler 识别 → **500**（应为 400） |
| 4 | `services/resource_service.py` | 无 status 白名单 | 写入永不生效的值既不报错、也永不出现在任何筛选结果里（**静默失败**） |
| 5 | `api/resource.py` + `schemas/resource.py` | `batch-process` 参数绑定与前端封装契约不符 | FastAPI 把 `item_ids: list[str]` 当裸 body 数组、`action` 当 query，而前端封装发的是 `{item_ids, action}` → **任何按封装接线的调用方都会恒定收到「参数错误」**。当前 `batchProcessInbox` 在页面里**尚无调用点**，故未在生产暴露 —— 但接线那天就会踩 |
| 6 | `services/vault_service.py` | `_session_keys` 在模块内被定义两次 | 死代码（后定义覆盖前者）；运行期无影响，但极易误导维护者 |

## 上轮修复（第一轮 · 2026-10-11，asset / workflow 模块）

| # | 位置 | 缺陷 | 后果 |
|---|------|------|------|
| 1 | `services/workflow_service.py` | 生成任务 `status="todo"`（非法状态） | 任何流转都报 3001，任务永久卡死且列表查不到 |
| 2 | `services/workflow_service.py` | 标签/模板去重查询未带 `user_id` | 他人有同名数据时，本用户静默不创建 |
| 3 | `services/asset_service.py` | 详情/更新/删除/使用**只校验存在性** | IDOR：拿到 id 即可读改删他人资产 |
| 4 | `services/asset_service.py`、`workflow_service.py` | PATCH 裸 dict 无差别 `setattr` | 可改 `user_id` / `id` / `use_count` / `rating` / `is_preset` |
| 5 | `services/asset_service.py` | `project_id` 仅靠外键兜底 | 不存在的 id → IntegrityError 未捕获 → 500；他人的 id 被静默接受 |
| 6 | `api/asset.py` | `rating` 查询参数无范围约束 | 0 / -99 / 1e9 都能写进 `rating` 列 |

## 已知技术债（测试中发现）

1. **expire_on_commit=False 导致关系缓存不刷新**：task.add_subtask 已修复，其他模块可能存在同类问题
2. **SQLite DateTime 时区丢失**：utcnow() 返回 aware，存库后变 naive，focus_stop 已修复，其他涉及时间计算的模块需检查
3. **FocusSession 模型未在 models/__init__.py 导出**：已修复，需检查是否有其他模型遗漏
4. **venv Python 解释器损坏**：uv 管理的 Python 被清理，已用系统 Python 替换 trampoline
5. **PATCH 不支持把字段置空**：`{k: v for k, v in data.items() if v is not None}` 会丢弃 `null`，
   语义已被测试钉死（需要清空请传空串）。若要支持置空需引入 `exclude_unset` 语义，属接口变更。
   同类语义也存在于 vault（`update_item(secret=None)` = 不改，不是清空）。
6. **SOP 版本历史取默认 100 条上限**：`sop_ver_repo.list(sop_id=...)` 未分页，超过 100 版会被截断（已被测试记录）
7. **`ResourceService` 的归属校验依赖调用方注入 `user_id`**：不传则为旧语义（只查存在性）。
   `dashboard_service` 已构造但从未调用；`assistant_service` 走的是带 `user_id` 的
   `create_inbox_item`，不受影响。**新增调用方务必传 `user_id`**。
8. **vault 的 `_owned_item` 不要求解锁态**（`list_items` / `create_item` 等要求）：
   `test_action_connection` 依赖它 —— TCP 探测不接触密文，故未收紧。若日后该端点
   增加了任何读取密文的行为，必须同时加 `_require_unlocked()`。
9. **收集箱 `content_type` 无白名单，且前端取值与模型注释不一致**：
   `InboxItem.content_type` 注释写 `text/url/image/file`，但 `ResourceCenterView.vue`
   的选项是 `text/link/image/file`（**link vs url**）。因为两端都没有白名单/枚举约束，
   目前能正常存取 —— 但该字段一旦被用于筛选或渲染分支，这个拼写差就会变成静默不匹配。
   （`create_inbox_item` 只校验 `content_type` 长度 1-20，见 `schemas/resource.py`）

## 运行命令

```bash
cd backend
.\.venv\Scripts\python.exe -m pytest tests/ -v                       # 全量（873 条，约 32s）
.\.venv\Scripts\python.exe -m pytest tests/test_vault_production.py -v  # 单模块
.\.venv\Scripts\python.exe -m pytest tests/ -k "越权 or ownership"     # 关键词筛选
.\.venv\Scripts\python.exe -m pytest tests/ --tb=short               # 简短报错
.\.venv\Scripts\python.exe -m pytest tests/ --collect-only -q        # 各文件用例数清单
```

> 873 条比上一轮的 694 条慢（15s → 32s），瓶颈是 vault 的 PBKDF2（200 000 轮）——
> 每次 `setup` / `unlock` / `change_master_password` 都要真实派生密钥。
> 这是**刻意保留的真实性**：把它 mock 掉就等于不测加密路径。

一键入口（架构守护 / pytest / 冒烟 / 版本 / 令牌 / 类型检查 / 离线队列 /
连通性 / 交付物守护 / **测试质量审计**，共 10 项）：仓库根目录 `python scripts/check_all.py`
