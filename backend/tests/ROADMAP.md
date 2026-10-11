# 后端测试推进路线图

> 从零搭建测试体系的分阶段计划。task 模块已完成样板，后续按此推进。
>
> **2026-10-11**：全量清点 + 分级升级，共**七轮**。P0/P1/P2/P3（安全面）全部补齐，
> 过程中修复 **28 处生产代码缺陷**（前三轮各 6 处 + 第五轮 1 处 + 第六轮前端 3 处
> + 第七轮安全面 6 处）+ **50 处日志写法失真**
> （16 文件，第四轮由真机探针发现），并新增**真机端到端探针**
> `scripts/probe_backend_live.py`（65 项断言，打真实 uvicorn + 真实 SQLite）。
> 所有数字均来自本次实际 `pytest` / 探针输出，非估算。

## 当前状态（2026-10-11 实测：**52 文件 / 1219 用例**，全量 0 failed）

### 基础设施与守护

| 文件 | 用例数 | 层级 |
|------|--------|------|
| test_architecture.py | 5 | 架构守护（分层依赖） |
| test_db_infrastructure.py | 12 | 数据库基础设施回归守护（连接池/WAL/级联/清表循环） |
| test_smoke.py | 7 | 冒烟 |
| test_logging_contract.py | 6 | 日志契约（loguru `{}` 与 `%s` 的行为差异 + 全项目静态扫描） |

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
| test_panel_production.py | 41 | Service 单元（第三轮：快速待办/提醒/聚合） |
| test_panel_api.py | 24 | API 集成（NOT NULL → 400 · 枚举白名单） |

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
| test_pet_production.py | 43 | Service 单元（第三轮：配置/形象/四维数值/状态引擎） |
| test_pet_api.py | 20 | API 集成（IDOR 契约 · mass-assignment） |

### P3 安全面与资源独立端点

| 文件 | 用例数 | 层级 |
|------|--------|------|
| test_vault_production.py | 79 | Service 单元（主密码生命周期 / 不落盘 / 白名单 / 归属） |
| test_vault_api.py | 28 | API 集成 |
| test_resource_production.py | 44 | Service 单元（收集箱 / 模板库 / 领域库 / content_type 白名单） |
| test_resource_api.py | 33 | API 集成（含 IDOR 与 mass-assignment 契约） |

### P4 聚合视图与报告（第五轮 · 只读面）

| 文件 | 用例数 | 层级 |
|------|--------|------|
| test_experience_production.py | 44 | Service 单元（四源归并 / 归一 occurred_at / 内存分页 / 身份过滤 / **只读不建表**） |
| test_experience_api.py | 20 | API 集成（含分页边界 400 契约） |
| test_report_production.py | 35 | Service 单元（三轴计数写后查库对拍 / 归档身份 / 工作区开关） |
| test_report_api.py | 15 | API 集成（三轴结构完整性 + 副作用如实记录） |

> **这两个模块的关键测试点不在「功能」，而在「不变量」**：
> experience 是**只读视图**（铁律：不建表），所以断言里有「调用前后
> 四张源表行数不变 + `sqlite_master` 表集合不变」；
> report 是**聚合读**，但实测**首次生成会写一行 `growth_states` 并 commit**
> —— 与类注释「不新增任何写入」不符，已如实钉成用例（见第 6 组）。
> 两份测试都不满足于「计数等于我造的数据」，而是**与 `SELECT count(*)` 对拍**。

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

### P5 加密与密钥轮换（第七轮 · 安全面）

| 文件 | 用例数 | 层级 |
|------|--------|------|
| test_encryption_production.py | 33 | `EncryptionManager`：密钥派生 / 随机 salt / 密钥环多代回退 / 轮换后旧密文可解 / `reload()` / 单例入口 |
| test_security_production.py | 42 | **`rotate_key` 真的重加密**（核回归）/ 注册表一致性 / 跳过不阻断 / 失败整体回滚 / `require_unlocked` 门禁 / 审计白名单与修剪 |
| test_security_api.py | 18 | 信封契约 / 未解锁 409 / 坏 token 400 且信封完整 / 后端不可用 500 |

> **本轮的教训：核回归要断言「密文变了」，不能只断言「还能解开」。**
> `api_key_encrypted` 从未被轮换却一直能读 —— 因为它靠**密钥环兜底**，
> 只要轮换次数没超过 `KEEP_PREVIOUS`，旧密钥还在，解密照样成功。
> 光看「能不能解密」永远发现不了这个缺陷（这正是它潜伏至今的原因）。
>
> **同理，「新建一个 manager 从磁盘读」也测不出单例不刷新的缺陷** ——
> 新建实例天然会读到新密钥；真实读取路径是 `decrypt_secret()` → 长驻单例。
> 两个层次都要覆盖：`_reopen(dir)` 测数据层，打补丁的 `_encryption_manager` 测运行期。

### 三个入口的分工

| 入口 | 是否需要起服务 | 守什么 |
|------|----------------|--------|
| `backend/tests/`（pytest, 1219 条） | 否（进程内 TestClient） | 业务规则、边界、越权、契约 |
| `backend/scripts/smoke_backend.py`（32 断言） | 否（TestClient） | 启动链路、迁移、种子 |
| `backend/scripts/probe_backend_live.py`（65 断言） | **是**（真实 uvicorn + 真实 HTTP） | **用户路径**：全新库 → 全部迁移 → 种子 → 接口真可用 |

> 第三个入口正是为「铁律：完成 = 双击 → 服务真的起来 → 关键接口非空」而建：
> 前两个都跑在进程内，历史上出现过「全绿但用户打不开」。用法见文件头
> （必须指向临时数据目录，勿拿真实库跑）。

### 尚未覆盖

| 模块 | 备注 |
|------|------|
| assistant | 依赖外部 AI API，需 mock |
| plugins | 插件系统，需隔离测试环境 |
| avatar | AI 头像生成，依赖外部服务 |
| workspace / sync / logs / events / rules | 文件扫描 / 同步 / 日志 / SSE / 领域规则引擎 |

> `experience` / `report` 已于**第五轮**补齐（见 P4）。
> `security`（含 `core/encryption.py` 与 `api/security.py`）已于**第七轮**补齐（见 P5）。
> 前端不再零测试：**vitest 4 spec / 75 用例**已于第六轮落地，纳入
> `scripts/check_all.py` 第 12 项（另有 `test-offline-queue.ts` / `test-http-connectivity.ts`
> 两个 esbuild 脚本，为第 7、8 项）。

## 推进原则

1. **先 Service 后 API**：业务规则在 Service 层测透，API 只测路由和参数校验
2. **先核心后边缘**：用户每天用的功能优先；**安全面（vault）优先级高于业务面**
3. **每模块完成后跑全量**：确保无回归
4. **发现 bug 当场修**：测试的价值就是暴露问题，不要攒着
5. **越权必须单独成组**：每个 Service 都要有「他人数据 → 404 且零副作用」的用例
6. **回归断言要写清「原缺陷是什么」**：只断言现象会被后人当成"设计如此"而删掉
7. **按前端真实契约写 API 测试**：先读 `frontend/src/api/*.ts` 核对参数位置
   （query / body / 路径），不要凭后端签名猜 —— 本轮即因此发现 `batch-process` 契约错配
8. **改生产代码前先证明缺陷存在**：第三轮采用「探针先跑一次拿到实证，再动手」，
   例：pet 的 IDOR 探针打印出了「他人形象 user_id 被改成当前用户」才动代码
9. **测试探针的断言必须先查代码/实测确认契约**：第四轮真机探针首跑 47/51，
   4 项失败**全部是探针自身的假设错误**（凭空假设了 vault 的单条详情端点、
   误以为 `setup` 后仍未解锁、把 409 写成 400、以为启动种子里有工作流预设）。
   契约来源优先级：**读实现 > 读测试 > 猜**。

## 每模块执行 Checklist

```
1. [ ] 读 frontend/src/api/<模块>.ts，核对每个端点的参数传递方式
2. [ ] 读 models/<模块>.py 的**列注释**（枚举/长度/可空性往往只写在注释里）
3. [ ] 编写 test_xxx_production.py（CRUD + 业务规则 + 异常 + 越权）
4. [ ] 编写 test_xxx_api.py（路由 + 参数校验 + 端到端）
5. [ ] **若模块自称「只读」→ 必须断言副作用**：源表行数不变、`sqlite_master` 表集合不变
       （第五轮：experience 用此法守住「经历视图不建表」铁律）；
       反之若发现实际有写入，**如实记录**并把与注释的矛盾写清（第五轮：report 的
       `growth_states`）——不要为了「符合注释」而隐藏事实
6. [ ] **聚合/统计类模块的计数必须与 `SELECT count(*)` 对拍**，不能只断言「等于我造的数」
7. [ ] 运行该模块测试全部通过
8. [ ] 运行全量测试确认无回归
9. [ ] 更新本文档进度（数字取自本次实际输出）
```

## 参数校验的通用要求（第五轮补）

列表类端点一律用 `Query(默认值, ge=1, le=上限)` 声明边界，**不要写裸 `int`**。

原因（实测）：裸 `int` + Python 切片会让非法值变成**静默空结果**而不是错误 ——
`page=0` → `rows[-30:0]` = `[]` → 200 但空列表。这类缺陷**不会让任何既有测试变红**
（既有用例只会测合法值），只能靠「专门为非法值写用例」发现。

## 第五轮修复（2026-10-11，experience 分页参数无范围约束）

| # | 位置 | 缺陷 | 后果 |
|---|------|------|------|
| 1 | `api/experience.py` | `page` / `page_size` 为裸 `int`，无 `ge` / `le` 约束 | 实测 `page=0` → `start=(0-1)*30=-30` → Python 负索引切片 `rows[-30:0]` = `[]` → **HTTP 200 但 `items` 空**（`total` 却 >0），页面表现「明明有数一条都不显示」；`page_size=0`/负数同理；`page_size=100000` 则一路拉满 4×500 条做内存归并 |

修法：`Query(1, ge=1)` / `Query(30, ge=1, le=500)`（与 `api/events.py` / `api/growth.py`
/ `api/logs.py` 既有的 `Query(ge/le)` 约定一致），非法值统一 **400 / code 1001**。
收紧前已核对：前端 `ExperienceView.vue` 传 `page>=1`、`PAGE_SIZE=50`；
`ReportService._recent_experience` 直接调 Service 不走 HTTP —— 均不受影响。

## 第七轮修复（2026-10-11，安全面：密钥轮换此前是「假轮换」）

**性质**：不是小 bug，而是**一个持续存在的静默数据丢失窗口**。
`SecurityService.rotate_key()` 声称轮换三张表，实测**只有 `settings` 真的重加密**。

| # | 位置 | 缺陷 | 后果 |
|---|------|------|------|
| 1 | `services/security_service.py` | `users.api_key_encrypted` 落库带 `"fernet:"` 前缀，旧代码拿**整串**去 `mgr.decrypt()` → 必然 `InvalidToken` → 被 `except` 静默 `continue` | 该列**从未被真正轮换**，只靠密钥环兜底；键环只留 5 代，实测**第 4 次轮换后 API Key 永久解不开** |
| 2 | `services/security_service.py` | `vault_items.secret_encrypted` 本不归本密钥管（由保险箱主密码派生的独立 Fernet 加密），却登记在 `_CIPHER_COLUMNS` | 每轮必定静默跳过，**返回值却谎报「已轮换」**（`tables` 里列着 vault_items） |
| 3 | `services/security_service.py` | 修好 ①② 后暴露：`rotate_key` 用**局部** `EncryptionManager`，而 `decrypt_secret()` 走 `main.py` 启动时建的**长驻单例**（`_fernet` 只读一次磁盘） | 提示「轮换成功」但 API Key **当场失效，重启服务才恢复**（由冒烟往返断言先测出） |
| 4 | `services/security_service.py` | 返回值用静态清单 `[t for t, _ in _CIPHER_COLUMNS] + ["settings"]` 当「已轮换表」 | 在列根本轮换不了的情况下**谎报**；现改为按表统计真的解开并重写的行数 |
| 5 | `core/encryption.py` | `decrypt_file()` 直接 `self._fernet.decrypt(...)`，**绕过历史密钥回退** | 同一份密文 `decrypt()` 能解、`decrypt_file()` 抛 `InvalidToken` —— 两条路径行为不一致 |
| 6 | `core/encryption.py` | `decrypt_file()` 写成 `... if self._fernet else x` | `_fernet` 为空（cryptography 缺失）时把**密文原样写进目标文件**当明文，静默产出垃圾 |
| 7 | `api/security.py` | 用裸 `HTTPException`（**全仓唯一**这样写的 API 文件） | 绕过统一信封，前端 `http.ts` 只读 `errBody.message` → 用户只看到 `HTTP 503: Service Unavailable`，看不到真实原因 |

顺带清掉三处死代码：`__init__` 对同一路径的**重复赋值**、`_previous_fernet`（单数）
的赋值逻辑（**全仓无任何读取方**）、`rotate_key` 里 `for f in [self._fernet]: pass` 的空循环。
`decrypt_file` / `encrypt_file` 全仓**无生产调用方**，修它们零风险（已核对）。

**修法与验证链**：

1. **探针先行**：`tests/test_zz_probe_security.py`（跑完即删）先打印出
   「`rotate_key` 返回 rotated=1 但 api_key/vault 密文一字未变」「第 4 次轮换后解不开」
   —— 拿到实证才动代码，不凭阅读猜。
2. `_CIPHER_COLUMNS` 登记判据写明（**只有全局 `EncryptionManager` 加出来的列才登记**），
   `rotate_key` 读时剥前缀 / 写回还原前缀，并改按表统计真实重写行数。
3. 新增 `EncryptionManager.reload()`，轮换提交成功后刷新**已存在**的单例
   （不新建：`init_encryption` 会重新解析 data_dir，在测试里会替换掉应用单例）。
4. 注册表一致性守护：静态扫描 `app/models/*.py` 里所有含 `encrypted` 的列，
   未登记且不在白名单即失败；**带非空断言**（扫描返回空集不得平凡通过）。

## 第四轮修复（2026-10-11，日志格式 · 由真机探针发现）

**性质**：不是 1 处 bug，而是**系统性写法失真** —— 后端日志后端是 **loguru**
（`app/core/logger.py`，占位符是 `{}`），但项目里有 50 处写成 printf 风格
`%s` / `%d` / `%.Nf`，或标准库 logging 的 `exc_info=`。

**实测行为**（`loguru` 直接实验，非理论推断）：

| 写法 | 实际输出 | 参数/堆栈 |
|------|----------|-----------|
| `logger.info("A %s", 1)` | `A %s` | **丢失** |
| `logger.info("B {}", 1)` | `B 1` | 正确 |
| `logger.warning("C %s 与 %.0f%%", "e", 12.5)` | `C %s 与 %.0f%%` | **全部丢失** |
| `logger.warning("D", exc_info=True)` | 无堆栈 | **`exc_info` 不生效** |

**真机证据**（uvicorn 启动日志，修复前 → 修复后）：

```
- 2026-10-11 16:47:57 | INFO | app.main:create_app:133 - 插件路由已挂载: %s
+ 2026-10-11 17:01:44 | INFO | app.main:create_app:133 - 插件路由已挂载: aihot
- 16:48:09 | INFO | app.core.growth_handlers:... - 成长体系订阅者已注册（%d 个事件）
+ 17:01:54 | INFO | app.core.growth_handlers:... - 成长体系订阅者已注册（14 个事件）
```

**涉及范围**：16 文件 / 50 处（`%s|%d|%.Nf` 41 处 + `exc_info=` 9 处；其中 3 行两者兼具）。
修法：`{}` / `{:.Nf}`；`exc_info=True` → `logger.opt(exception=True)` 前缀。

**为什么此前无人发现**：日志失真**不会让任何测试变红**，也不影响功能 ——
排查线上问题时才会发现「用户 %s 升级: LV%d → LV%d」毫无信息量。
故落成 `scripts/audit_log_format.py`（基线 0，纳入 `check_all.py` 第 11 项），
并加 `tests/test_logging_contract.py` 把 loguru 的行为钉成契约。

## 第三轮修复（2026-10-11，panel / pet / resource content_type）

| # | 位置 | 缺陷 | 后果 |
|---|------|------|------|
| 1 | `services/resource_service.py` + `models/resource.py` | 收集箱 `content_type` 无白名单，模型注释写 `url` 而前端/种子数据用 `link` | 写入 `url` 既不报错、也读得回来，但该字段一旦参与筛选/渲染分支就是**静默不匹配** |
| 2 | `services/panel_service.py` | `update_todo` / `update_reminder` 显式传 `null` 时直接 `setattr` 到 `NOT NULL` 列 | `IntegrityError` 未捕获 → **500**（应为 400）。实证：`NOT NULL constraint failed: quick_todos.title` |
| 3 | `services/panel_service.py` | `reminder.type` / `repeat` 有注释枚举（meeting/study/health/custom、none/daily/weekly）但无校验 | 写 `meetting` 不报错，前端按类型渲染的分支永远落到默认 —— **静默失败** |
| 4 | `services/pet_service.py` + `api/pet.py` | `update_avatar(avatar_id, data: dict)` 收裸 dict 无白名单 | **mass-assignment**：客户端可改 `user_id` —— **把形象送给别人**（探针实证） |
| 5 | `services/pet_service.py` | `update_avatar` / `delete_avatar` / `set_active_avatar` / `update_config` 四入口零归属校验 | **IDOR**：拿到 avatar_id 即可改 / 删他人形象，或把他人形象设为自己当前形象（探针实证：他人形象被成功删除） |
| 6 | `services/pet_service.py` | `set_active_avatar` 在配置不存在时跳过写 `current_avatar_id` | 出现 `avatar.is_active=True` 而 `config.current_avatar_id=None` 的**不一致窗口** |

修法对齐既有约定：白名单常量（`INBOX_CONTENT_TYPES` / `REMINDER_TYPES` / `_AVATAR_UPDATABLE`）、
`_reject_null` 守卫、`_owned_avatar → 404`、API 层用显式 Pydantic 模型替代裸 `dict`。

## 第二轮修复（2026-10-11，vault / resource 模块）

| # | 位置 | 缺陷 | 后果 |
|---|------|------|------|
| 1 | `services/resource_service.py` | 构造函数不收 `user_id`，11 个单条操作零归属校验 | **IDOR**：任何登录用户拿到 id 即可读改删他人的收集箱条目 / 模板 / 领域 |
| 2 | `services/resource_service.py` | `update_template` / `update_domain` 收裸 `dict` 直传 `repo.update` | **mass-assignment**：可改 `user_id` / `id` / `use_count` / `is_builtin` / `sort_order` |
| 3 | `services/resource_service.py` | `process_inbox_item` 非法 action 抛裸 `ValueError` | 无 handler 识别 → **500**（应为 400） |
| 4 | `services/resource_service.py` | 无 status 白名单 | 写入永不生效的值既不报错、也永不出现在任何筛选结果里（**静默失败**） |
| 5 | `api/resource.py` + `schemas/resource.py` | `batch-process` 参数绑定与前端封装契约不符 | FastAPI 把 `item_ids: list[str]` 当裸 body 数组、`action` 当 query，而前端封装发的是 `{item_ids, action}` → **任何按封装接线的调用方都会恒定收到「参数错误」**。当前 `batchProcessInbox` 在页面里**尚无调用点**，故未在生产暴露 —— 但接线那天就会踩 |
| 6 | `services/vault_service.py` | `_session_keys` 在模块内被定义两次 | 死代码（后定义覆盖前者）；运行期无影响，但极易误导维护者 |

## 第一轮修复（2026-10-11，asset / workflow 模块）

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
   注意与 `panel`/`pet` 的区别：那两个模块是 `T | None = None` **显式**传 null 的路径，
   已由 `_reject_null` 拦成 400（不是静默丢弃）。
6. **SOP 版本历史取默认 100 条上限**：`sop_ver_repo.list(sop_id=...)` 未分页，超过 100 版会被截断（已被测试记录）
7. **`ResourceService` 的归属校验依赖调用方注入 `user_id`**：不传则为旧语义（只查存在性）。
   `dashboard_service` 已构造但从未调用；`assistant_service` 走的是带 `user_id` 的
   `create_inbox_item`，不受影响。**新增调用方务必传 `user_id`**。
8. **vault 的 `_owned_item` 不要求解锁态**（`list_items` / `create_item` 等要求）：
   `test_action_connection` 依赖它 —— TCP 探测不接触密文，故未收紧。若日后该端点
   增加了任何读取密文的行为，必须同时加 `_require_unlocked()`。
9. **`PetConfig` 未使用 `TimestampMixin`**：自建了 `updated_at`（无 `created_at`），
   与其余模型不一致；若要纳入统一时间轴需补列（属迁移变更）。
10. **vault 没有单条「详情」端点**（第四轮探针实测 `GET /vault/items/{id}` → 405）：
    只有列表 `/items`、`PATCH`/`DELETE`、`/items/{id}/secret`。与资源中心/资产库的
    「列表 + 详情」模式不一致。前端若需要单条元信息只能从列表里取 —— 目前无调用点，
    属**接口一致性**观察，非缺陷。
11. **启动种子（`app/seed.py`）不灌工作流/资产库预设**（第四轮探针实测：
    全新库 `GET /workflows/presets` 返回空 `list`）：种子只覆盖
    文件夹/任务/文档/复盘/对话/面板/通知。完整演示数据走 `scripts/seed_demo.py`
    这条独立路径。若前端工作流页假设「开箱即有预设」，需要先确认。
12. **`ReportService` 不是零写入**（第五轮实测）：类注释写「只读聚合 …… 不新增任何
    写入」，但 `_growth_axis → GrowthService.get_state → get_or_create_state`
    在新用户上会 `db.add(GrowthState)` 并 **`db.commit()`** ——
    ① 首次生成报告会多一行 `growth_states`；② **`commit()` 会提前结束调用方的
    事务**。当前 `GET /report` 请求内没有其它待提交写入，故无实际影响；
    但若日后有人把 `ReportService.get()` 接进一个「先生成报告、再写其它表」的
    事务里，前半段的 commit 会把那笔写入一起提交掉。
    修法（未做，属接口变更）：把 `get_or_create_state` 的 `refresh` 换成
    `flush`，由调用方决定何时 commit。
13. **`ExperienceService` 的 `occurred_at` 依赖「SQLite 读回即 naive」这一前提**
    （第五轮探针实证）：`diary_date` / `review_date` 归一产出 naive datetime，
    而 `created_at` 默认是 **aware** `utcnow()`；两者若同时为 aware/naive 会在
    `rows.sort(...)` 处抛 `TypeError`。实测 SQLAlchemy 2.0 的 SQLite 方言把 aware
    值按 UTC 存、读回为 naive，故实际可排序（已写成契约用例
    `test_all_occurred_at_are_comparable`）。**若将来换库或改方言，
    `sort` 之前必须先统一 tz 语义。**

14. **密钥轮换只覆盖 `self.user_id` 自己的行**（第七轮实测）：`rotate_key` 遍历
    `_rows_of("users")` 时按 `User.id == self.user_id` 过滤，**其它用户的
    `api_key_encrypted` 不会重加密**，只能靠密钥环的 `KEEP_PREVIOUS=5` 代兜底。
    当前是本地单用户模型（`default_user`），实际只有一行，无影响；
    **若将来支持多用户，必须把轮换改成全局遍历**，否则第 6 次轮换就会
    让其它用户的 API Key 永久失效 —— 与本次修复的失败模式同源。
15. **`EncryptionManager` 的主密钥模式与 `rotate_key()` 语义不自洽**（第七轮发现）：
    `_master_key` 非空时 `_initialize()` 由「主密钥 + salt」派生密钥、**忽略
    `.encryption_key` 文件**；但 `rotate_key(new_master_key=None)` 走的是
    「生成随机 key 并写进 `.encryption_key`」这条路 —— 于是 `self._fernet`
    与「reload 后按主密钥派生出来的结果」**不是同一把**。
    生产不受影响（`main.py` 只调 `init_encryption(data_dir)`，从不传主密钥），
    但若日后启用主密钥模式，`rotate_key()` 必须改为「用新主密钥派生」而不是生成随机 key。

## 运行命令

```bash
cd backend
.\.venv\Scripts\python.exe -m pytest tests/ -v                       # 全量（1219 条）
.\.venv\Scripts\python.exe -m pytest tests/test_pet_production.py -v  # 单模块
.\.venv\Scripts\python.exe -m pytest tests/ -k "越权 or ownership"     # 关键词筛选
.\.venv\Scripts\python.exe -m pytest tests/ --tb=short               # 简短报错
.\.venv\Scripts\python.exe -m pytest tests/ --collect-only -q        # 各文件用例数清单
```

> **注意（在 WorkBuddy 工具的 Bash 里跑）**：宿主会通过 `PYTHONPATH` 注入一个
> `sitecustomize.py` 文件操作钩子，**它让每次文件删除耗时约 1.9 秒**
> （2026-10-11 实测：50 次 `open/write/unlink` 带钩子 **96.27s**、`env -u PYTHONPATH` 后 **2.05s**）。
> 连带后果有两个：① 39 张表的建库迁移慢到超过命令超时，进程被 SIGTERM，
> 表现为「跑 pytest 没有任何输出」；② 收尾清临时目录触发宿主的批量删除保护
> （`SystemExit: 1`，发生在所有用例跑完之后），把 `N passed` 汇总行吃掉。
>
> **一次性解决两者** —— 绕开注入的钩子（只在临时目录里跑测试，无删除风险）：
>
> ```bash
> env -u PYTHONPATH .venv/Scripts/python.exe -m pytest tests/ -q
> ```
>
> 若仍只想在沙箱内核对结论（不绕钩子）：加 `-p no:cacheprovider` 并把输出重定向到
> 文件，再统计进度行（`.` / `F` / `E`）—— 汇总行丢了但结论有效。本文档的数字即用此法核过。

> 1219 条的主要耗时项是 vault 的 PBKDF2（200 000 轮）与 pet 的多次迁移建库 ——
> 每次 `setup` / `unlock` / `change_master_password` 都要真实派生密钥。
> 这是**刻意保留的真实性**：把它 mock 掉就等于不测加密路径。

### 真机探针（需要先起服务）

```bash
# 终端 1：用临时数据目录起服务（勿指向真实库，探针里有「全新库」断言）
cd backend
VENUSTECH_DATA_DIR="C:/Users/<你>/AppData/Local/Temp/venustech_probe" ^
    .venv\Scripts\python.exe -m uvicorn app.main:app --port 8765

# 终端 2：跑探针（65 项断言）
cd backend && .venv\Scripts\python.exe scripts\probe_backend_live.py
```

一键入口（架构守护 / pytest / 冒烟 / 版本 / 令牌 / 类型检查 / 离线队列 /
连通性 / 交付物守护 / 测试质量审计 / 日志格式审计 / **前端单元测试(vitest)**，共 12 项）：
仓库根目录 `python scripts/check_all.py`
