# Changelog

本项目所有重要变更都记录在此文件。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### Changed — Phase 12：事件总线修复 + A 类 API 补测 + 大型组件测试（2026-10-31）

**D-48/D-49 修复**
- **D-48（P2）** `event_bus` 异步 handler 在无运行事件循环时会**静默丢失**（`get_event_loop()` 自动建未运行 loop → `create_task` 排队永不执行、`called` 仍 +1）：改为 `get_running_loop()` try/except，无运行循环逐 handler `asyncio.run()` 同步兜底；有循环时正常排队，并给 task 加 `add_done_callback` 把延迟失败/取消写入 history/stats + 日志（`called` 语义 = 成功排队即计，注释+测试固定）。
- **D-49（P3）** `task_service` 批量操作失败从"只计数"改为逐条 `logger.warning("批量操作失败: task_id={} action={} reason={}")`（缺失/越权/异常三类原因），`BatchTaskResult` 契约不变。

**测试与覆盖率**
- 后端：**1927 passed**（1897 → +30：event_bus 异步投递 6 / 批量可观测 2 / A 类 API 端点 23 / 防御分支更新）；覆盖率 **97.98% → 98.33%**；`api/auth.py`、`api/avatar.py`、`api/conversation.py`、`service/asset_service.py`、`service/pet_service.py` **未覆盖行全部清零**；CI 阈值保持 97%。
- 前端：**504 passed / 34 files**（457 → +47：DesktopPet 24 / DocumentGraph 13 / AppIcon 10）；lines 82.09%、branches 89.73%、functions **49.2%**（分母 591→628、covered 274→309）；阈值 `{81,88,45,81}` → **`{81,88,48,81}`**；`docs/guides/frontend.md §九` 阈值规则补"波动需连跑两次确认稳定"与 Phase12 示例。

**新登记 5 个问题（D-50~D-54，未修）**
- D-50（P3）`PATCH /auth/me` 的 nickname 缺 `min_length`（init 要求 ≥1）→ 允许置空昵称；
- D-51（P3）`POST /auth/verify-api` 空 Key 会真实请求 provider（应先校验非空）；
- D-52（P3）`DesktopPet` 初始 1s 定时器未纳入卸载清理；
- D-53（P3）`DesktopPet` 低精力玩耍提示被随机气泡覆盖；`petClass` 未映射部分动作类；
- D-54（P3）`DocumentGraph` 力导向 tick 无 `document.hidden` 暂停/节流。

### Changed — Phase 11：备份恢复数据安全 + 路由/壳层测试 + 覆盖率审计（2026-10-31）

**D-46/D-47 修复（数据安全，P2/P3）**
- **D-46（P2）** `BackupService.import_` 由「rename 旧库 → `write_bytes` 新库」改为**临时文件 + `fsync` + `os.replace()` 原子替换**；替换失败自动从 `.bak` `copy2` 恢复（既恢复活动库又保留人工回滚点），copy 也失败时给出明确手工回滚日志，不掩盖原异常；API 契约/返回结构不变。
- **D-47（P3）** `.bak` 命名改 `YYYYmmdd_HHMMSS_mmm_<uuid6>`（毫秒+短 uuid），同秒连续恢复不再冲突/覆盖回滚点。
- 抽出 `_atomic_write_replace` / `_rollback_failed_import` / `_warn_version_mismatch` / `_cleanup_wal_files` 纯函数，便于进程内安全单测。
- **备份子进程测试 flake 加固**：`_run_child` 仅对瞬时错误（`database is locked` / `disk I/O error`）重试最多 2 次且每次换新临时目录，永久错误不重试；不再硬编码源码行号（改锚点动态解析）。

**测试与覆盖率**
- 后端：**1897 passed**（1844 → +53：备份恢复 10→22、防御分支审计 41）；覆盖率 **96.68% → 97.98%**；`backup_service` 99.4%；CI 阈值 96→**97%**。
- 防御分支审计分类：D 类（`import_` 破坏性路径）由子进程测试覆盖；B 类给出不可达证据（49 张表全含 `deleted_at`、monthly 日期钳制、`HAS_CRYPTO=False` 环境）；C 类为迁移回调专属；剩余 A 类约 50 行已列下一轮优先级。
- 前端：**457 passed / 31 files**（403 → +54：router 20 / TopNav 19 / LeftInfoPanel 15）；覆盖率 **lines 44.01% → 82.42%**、branches 90.0%；函数百分比下降是**统计面扩大**（router 测试真实 `await` 24 个 lazy view，分母 382→591、covered 245→274 上升）而非回退；阈值 **{43,81,67,43} → {81,88,45,81}**，并新增「**统计面变化时如何调整阈值**」规则（百分比 + covered/total 双记录、covered 下降禁止下调）。

**新登记 2 个问题（D-48/D-49，未修）**
- **D-48（P2）** `core/event_bus.py` async handler 在无运行 loop 时 `get_event_loop()` 自动创建未运行 loop → `create_task()` 排队永不执行，**handler 静默丢失**（`called` 仍 +1、无日志）；
- **D-49（P3）** `task_service` 批量操作失败只计数、无日志/原因（可观测性缺口）。

### Changed — Phase 10：修剩余 P2/P3 + 组件测试 + 备份恢复安全测试（2026-10-30）

**D-39~D-45 修复（均带回归测试 + 负向验证）**
- **D-42（P2）** `main.py` demo_seed 由 **fatal 改 fail-open**（try/except + rollback + exception 日志），seed 失败不再阻断启动；
- **D-43（P2）** `register_event_handlers()` / `register_growth_handlers()` 各自独立 fail-open（一个失败不影响另一个/启动）；
- **D-44** 自动备份由"只备份第一个用户"改为**遍历全部用户**（per-user 独立 Session/try，聚合计数，无用户不报错）；
- **D-39** `notifiedIds` 改 `Map<id,时间戳>` + 24h TTL + 容量清理，消除级联再通知；**D-40** BaseSelect 外部改值同时清搜索词；**D-41** BaseModal 关闭动画期卸载补发 `closed`（恰好一次）；
- **D-45（P2，新发现）** 多行日志调用里的 `%s` 被扫描器漏检（`backup_service` 版本告警、`ai/client` 两处）→ 3 处改 `{}`；`audit_log_format.py` 改为**跨行调用**检测并新增 `scan_source()` + 3 条回归测试。

**测试与覆盖率**
- 后端：**1841 passed**（1823 → +18：lifespan fail-open 24→32、备份恢复子进程 10、日志跨行回归 3）；覆盖率 **96.63% → 96.68%**（main.py/bootstrap 100%）。
- 新增 `test_backup_import_subprocess.py`（10 条）：**子进程 + 独立数据目录**真实跑 import_——成功替换（数据回滚到备份时刻、`.bak` 生成、完整性 ok）、旧包兼容、版本不一致告警、篡改校验和/截断 ZIP/缺清单/他人备份四种拒绝且**库字节不变**；含 tokenize 守卫禁止父进程出现 `import_` 标识符。
- 前端：**403 passed / 28 files**（344 → +59：BaseCard 8 / BaseSwitch 10 / BaseInput 16 / OfflineQueueIndicator 20 + D-39/40/41 回归 5）；lines **41.54% → 44.01%**、branches 82.36%、functions 68.06%；阈值 `{40,79,64,40}` → **`{43,81,67,43}`**。

**新登记 2 个遗留（D-46/D-47，未修）**
- D-46（P2）`import_` 在「改名旧库→写新库」之间无自动回滚（写失败/崩溃会留下缺失或半截 DB；建议临时文件 + `os.replace` 原子替换）；
- D-47（P3）`.bak` 秒级时间戳同秒冲突（Windows 抛错 / POSIX 覆盖最早回滚副本）。

### Changed — Phase 9：修剩余 P2/P3 + 生命周期测试 + CI 增强（2026-10-30）

**D-36~D-38 修复（均带回归测试 + 负向验证）**
- **D-36（P2）** `useSettingsSync.loadDataDir` 硬编码 `http://127.0.0.1:8765/api/v1/health` → 改 `` `${getApiBase()}/health` ``，移动端/Tailscale 覆盖 base 后不再误报"后端未连接"；baseURL 覆盖回归测试。
- **D-37** 三个同步 catch 由空实现改为 `reportUnexpected()`：`ApiError` 保持静默（http 层已提示），非 ApiError 意外错误补 `toast.error` 兜底（导出/包列表/导入），4 条测试覆盖两类分支。
- **D-38** `useReminderWatcher.notifiedIds` 加 `NOTIFIED_MAX=500` 上限，按插入顺序淘汰最旧，跨 tick 去重语义不变；容量回归测试。

**测试与覆盖率**
- 后端：**1823 passed**（1743 → +80：lifespan fail-open 24 / bootstrap handlers 44 / startup auto-backup 12）；覆盖率 **95.91% → 96.63%**；`app/main.py` 84→**100%**、`bootstrap/event_handlers` 66→**100%**、`growth_handlers` 95→**100%**、`backup_service` 82→**99%**；CI 阈值 95→**96%**。
- 前端：**344 passed / 24 files**（291 → +53：dimensions 14 / BaseSelect 18 / BaseModal 16 + D-36/37/38 回归 5）；lines **37.44% → 41.54%**、branches 80.46%、functions 65.86%；阈值 `{36,78,63,36}` → **`{40,79,64,40}`**。
- 测试覆盖了 lifespan 的 fatal/fail-open 双策略、事件订阅注册、文档 AI 摘要/标签独立持久化、任务通知、成长经验结算、自动备份到期/校验/修剪、异常处理器信封与不泄堆栈、`__main__` 启动参数（runpy 假 uvicorn，不占端口）。

**CI 增强**
- `windows-startup.yml` 支持 **PR 触发**（paths 与 push 一致；仅无人值守的 `contents: read`，无 secrets），并在文件头写明 Windows 分钟成本。
- 后端/前端覆盖率产物上传 artifact：`backend-coverage`（coverage.xml）、`frontend-coverage`（coverage-summary.json），保留 7 天，上传失败不阻断（`continue-on-error`）。
- 修正既有口径不一致：backend 覆盖率命令 `--cov-fail-under` 实际值 88 与步骤名 95 不符，已对齐为 96。

**新登记 6 个问题（D-39~D-44，未修）**
- **P2**：`app/main.py` demo_seed 分支无 try/except（seed 失败直接阻断启动，与其它 fail-open 不一致）；订阅注册无 try/except（异常中断启动）。
- P3：提醒 id 淘汰级联再通知理论风险、BaseSelect 搜索词不重置、BaseModal closed 在动画期卸载不触发、自动备份只对第一个用户。

### Changed — Phase 8：修剩余 P2/P3 + 测试补缺 + 启动脚本进 CI（2026-10-30）

**D-29~D-35 全部修复（均带回归测试 + 负向验证）**
- **D-30/D-31** `assistant_service` 日期解析 **+14 天 bug**：`周X` 分支重复叠加 offset、`下周X` 分支 `delta += delta`（含 `if False` 死代码）→ 分别改为"未来最近周X"与"下一自然周周X"；补一周 7 天矩阵 + numeric-time 矩阵 + 跨周边界用例。
- **D-32** `domain_engine` 阶段公式使 4 单元通用兜底计划永不出现 phase 3 → `phase=min(3,(i*3)//total+1)`；total≥3 恒三段齐全、首 1 末 3 不跳阶，内置 13 个领域分布同步修正（3 单元 `[1,1,2]→[1,2,3]` 等）。
- **D-29** `GlobalSearch` 空态可达：`realResults` 排除恒定操作项，文案改"没有找到相关内容，可试试下面的操作"，操作项仍常驻。
- **D-33** `app/seed.py` `datetime.utcnow()` → aware `utcnow()`；**D-34** `delete_root` 清理 `_SCAN_PROGRESS` 僵尸条目；**D-35** `app/main.py` 3 处 f-string 日志 → loguru `{}` 惰性占位。

**测试与覆盖率**
- 后端：**1743 passed**（1706 → +37）；覆盖率 **95.80% → 95.92%**；assistant / workspace_service / seed / domain_engine 均 **100%**。
- 前端：**291 passed / 21 files**（239 → +52：useReminderWatcher 18 / useSettingsConfig 17 / useSettingsSync 17）；lines **32.24% → 37.44%**、branches 79.0%、functions 64.04%；阈值 `{31,76,59,31}` → **`{36,78,63,36}`**。
- 测试基建：架构负向探针 uuid 文件名防并发假红已在 Phase 7 落地并通过本轮验证。

**启动脚本进 CI（D-11 收尾）**
- 新增 `.github/workflows/windows-startup.yml`：windows-latest 上真跑 `python scripts/audit_delivery.py` + `pwsh -File ops/start.ps1 -Mode dev -Verify`（启动→端口+健康检查→自动停止），失败上传 `var/logs/**` artifact；首次真实结果随本提交触发。
- runbook `startup.md` 新增 §5（CI 冒烟：触发/步骤/无 venv 回退证据/失败排障）。

**登记 3 个新遗留（D-36~D-38，未修）**
- D-36（P2）`useSettingsSync.loadDataDir` 硬编码 `127.0.0.1:8765`（移动端/局域网可能误报后端未连接）；
- D-37（P3）导出/导入 catch 为空（非 http 错误静默）；
- D-38（P3）`useReminderWatcher` 模块级 `notifiedIds` 无上限清理。

### Changed — Phase 7：修 P1/P2 缺陷 + 日志统一 + 覆盖率棘轮（2026-10-30）

**D-22~D-28 全部修复（均带回归测试 + 负向验证）**
- **D-24（P1）** `aihot` 双重响应信封 + 死分支：`_fetch` 改返回裸结果、端点只包一层 `success()`；`daily()` 用 `ok` 判断后 **404→fallback 成功分支运行期可达**（真实 HTTP 路径测试断言 3 次请求顺序 + `source=live/fallback-*`）。
- **D-22** `_TIME_HINTS` 长词前置："大后天" → +3（原被 "后天" 抢先 +2）；"今天晚上" 优先 "今天"。
- **D-23** `ai/client.chat()` 缺字段/异常结构/非法 JSON → `AIRequestFailedException("AI 响应格式异常…")`（保留 cause 链），6 种坏结构参数化测试。
- **D-25** 加密单例：新增 `core.encryption.ensure_encryption()`（双检锁线程安全），`AssistantService` 复用；7 条测试含 4 线程并发同一实例。
- **D-26** 日志后端统一：12 个文件 stdlib `logging.getLogger` → loguru `get_logger`（`config.py` 因 `logger.py→config` 导入环保留 stdlib 并进白名单），21 处 f-string 日志改 `{}` 惰性占位；契约新增 4 条规则（禁止 `logging.getLogger`/白名单须有理由/caplog 按需桥/logger 必须真 loguru）并修复 `logger.opt(...)` 漏检；**顺带修掉 health/dashboard/pet 的 latent AttributeError**（`opt()` 挂在 stdlib logger 上）。
- **D-27** `useSettingsDiagnostics` 的 400ms `ruleTimer` 增加 `onScopeDispose` 清理（卸载后不再发预览请求）。
- **D-28** `offlineQueue.init()` 幂等（`listenersBound` + dispose 复位），重复 init 不叠加网络监听。

**测试与覆盖率**
- 后端：**1706 passed**（1588 → +118）；覆盖率 **92.02% → 95.76%**；重点模块 workspace_service/app/seed.py/domain_engine/vault_service **全部 100%**、aihot/assistant 100%、ai/client 99%；CI 覆盖率阈值 **91% → 95%**（阻断）。
- 前端：**239 passed / 18 files**（196 → +43：GlobalSearch 14 / AdvancedSection 12 / SystemDiagnosticsSection 14 + D-27/D-28 回归 3）；lines **20.95% → 32.24%**、branches 73.25→77.7、functions 53.65→60.42；阈值棘轮 `{20,72,52,20}` → **`{31,76,59,31}`**；`maxWorkers: 2` 修复 16 核下 jsdom+VTU 并发 OOM（`FATAL ERROR: Zone Allocation failed`）。
- 顺带修复 `GlobalSearch` 搜索失败时丢失常驻操作项的组件行为缺口（失败降级 = 仅操作项）。
- 测试基建：`test_architecture.py` 的 R1/R2/R14 负向探针改 **uuid 文件名**，消除多 agent 并行 pytest 时的互踩假红；`test_service_boundaries`、`test_aihot_plugin` 的 NO_ASSERT 用例补真实断言。

**登记 7 个新问题（D-29~D-35，未修）**
- D-30/D-31（P2）：`assistant_service` 的 `周X`/`下周X` 分支日期**重复 +7** → 解析成 +14 天（应 +7；含 `if False` 死代码）；
- D-32（P2）：`domain_engine` 阶段公式使 4 单元通用兜底计划**永不出现 phase 3**（长尾技能/无 API Key 默认路径少"整合实战"阶段）；
- D-29（P3）GlobalSearch 空态不可达；D-33 `app/seed.py` utcnow 弃用；D-34 workspace 扫描进度僵尸条目；D-35 `app/main.py` 3 处 f-string 日志。

### Changed — Phase 6：修测试发现的真 bug + 测试补缺（2026-10-28）

**真 bug 修复（D-17~D-21，均带回归测试 + 负向验证）**
- **D-17** `PATCH /auth/me` 传 `pet_position` 必 500：`model_dump()` 后按对象取 `.x` → 改 dict 取值，并处理嵌套部分坐标（只传 x 时保留 y）；strict xfail 转正 + 5 条边界测试。
- **D-18** `api/logs.py` 清日志失败分支对 stdlib logger 调 loguru `.opt()` → AttributeError：根因是同一文件混用两套日志后端，统一 `get_logger`（loguru），保留 `opt(exception=True)`；加写失败回归测试（接口 200 + failed 列表 + 不抛 500）。
- **D-19** `api/logs.py` 读日志错误分支返回裸 dict → 改用 `error()` 统一信封，补错误响应契约测试。
- **D-20（P1，IDOR）** `avatar_service` memory/inspiration 写操作无归属校验：7 个写方法加 `user_id` 前置并校验（不匹配抛 NotFound，不泄漏存在性）；`api/avatar.py` 全部调用点传 `user.id`；新增 13 条 IDOR 用例（B 越权 7 个写操作全部 404 + **独立 Session** 复核数据未变、owner 操作成功、不可探测存在性）。
- **D-21** SSE 请求未带 `X-API-Token`（启用访问令牌后流式对话 401）：`sse.ts` 与普通请求对齐；+2 条头断言测试。
- （Phase 5 尾）CI 首跑 Linux 发现日志路径穿越返回 404 而非 400 → 已改为显式拒绝分隔符/上跳（跨平台一致）。

**测试补缺**
- 后端 **+118 条**（`test_assistant_service` 38 / `test_ai_services` 37 / `test_aihot_plugin` 22 / `test_plugin_manager_deep` 21），全部 mock LLM/HTTP 零联网；全量 **1588 passed**；覆盖率 **89.04% → 92.02%**（assistant 28.5→95.2%、ai/client 45.4→99.0%、plugin_manager 82→98.3%、aihot 28.1→93.8%）；CI 覆盖率阈值 **88% → 91%**（阻断）。
- 前端 **+59 条**（useConversation 20 / offlineQueue store 14 / useSettingsDiagnostics 25），**196 passed**；lines **12.76% → 20.95%**、branches 68.57→73.25、functions 44.93→53.65；`vitest.config.ts` 阈值棘轮 **{12,65,40,12} → {20,72,52,20}** 并接入 CI 阻断步骤。
- 规范：`backend/tests/README.md` 新增 Mock 约定；`docs/guides/frontend.md` 补覆盖率阈值棘轮规则（只升不降）。

**测试又发现 7 个问题（登记 D-22~D-28，未修）**
- D-22 `assistant_service._TIME_HINTS`：**"大后天" 先命中 "后天"** → 解析 +2 天（应 +3），测试按当前行为钉住；
- D-23 `ai/client.chat()` 200 缺 `choices` 抛裸 KeyError，未映射 `AIRequestFailedException`；
- D-24 `aihot` **双重响应信封** + `daily()` 对信封取 `ok` 恒 None → 404 回退成功分支运行期永远走不到（**P1，建议下轮先修**）；
- D-25 `AssistantService._encryption()` 每次 new 而非复用全局单例；
- D-26 多个模块 stdlib logger + loguru `{}` 风格混用（参数被丢弃）；
- D-27 `useSettingsDiagnostics` ruleTimer 未在 dispose 清理；
- D-28 `offlineQueue` store 重复 init 会重复注册网络监听。

### Changed — Phase 5：结构治理 + 测试质量 + 启动可靠性（2026-10-28）

**项目文件夹结构治理（可执行契约）**
- 新增 `scripts/audit_workspace_hygiene.py`（零第三方依赖）：A tracked 泄漏（DB/密钥/token/node_modules/dist/覆盖率产物）、B `.gitignore` 语义契约（26 条示例路径 + `var/.gitkeep` 锚点）、C 根目录契约、D `var/` 顶层白名单（`data/demo/legacy/backups/logs/tmp`）、E 覆盖率产物；支持 `--check` / `--fix-local` / `--ci`，接入 `check_all.py` **第 16 项**与 `repo-guard`。
- 清理本机 **193MB** 垃圾：24 个 pytest basetemp（≈158MB）、`.ruff-install`（32MB）、`rebuild`/`tools`、backend `.ruff_cache`/`.pytest_cache`/`venustech_smoke`、var/ 顶层散落日志与一次性脚本、覆盖率产物；`var/data|demo|legacy|backups|logs` 与 `backend/.legacy-data-2026-10-27` 全部保留。
- `.gitignore` 增加本地垃圾与覆盖率产物规则；`var/logs/` 纳入白名单且 `--fix-local` 明确不删。
- 遗留：7 个空 ACL 目录 + `var/tmp/acl-blocked` 需完全权限会话 `rd /s /q`（均在 gitignored 的 var/ 内，不影响仓库）。

**测试质量基建 + 新测试**
- 后端：pin `pytest-cov==5.0.0` / `coverage==7.17.0`；覆盖率 **85.18% → 88.48%**（missed 1478→1149）；新增 **166 条**（api 错误路径 44 / core 28 / schemas 51 / service 43），全量 **1449 passed + 1 strict xfail**；3 条负向验证（改错断言必红）；`tests/README.md` 重写为 9 节规范（分层/AAA/断言/禁止真实库/覆盖率命令）；CI 加非阻断覆盖率报告。
- 前端：`@vitest/coverage-v8` + `test:coverage`；新增 **49 条** → **135 passed / 12 files**（kernel/http 92.23%、shared/composables 89.74%、offline core 100%）；CI 加非阻断覆盖率；`docs/guides/frontend.md` 新增测试与覆盖率章节。
- 覆盖率口径：前端分母为全量 `src/**/*.{ts,vue}`（views/ 按约定排除）；v8 对未执行文件不产 branch 计数，评估以 **lines** 为主。
- **CI 首跑（Linux）抓到一个真 bug 并已修**：`api/logs.py` 的路径穿越检查依赖 `resolve().is_relative_to()`，而 POSIX 上反斜杠不是分隔符 → `..\..\evil.log` 被当普通文件名，返回 404 而不是 400「非法文件名」。已改为**显式拒绝分隔符/上跳/空名**（跨平台一致）+ 保留 resolve 纵深防御。
- 测试发现 5 个真问题（只记录未修，登记 D-17~D-21）：`PATCH /auth/me` pet_position 必 500、`api/logs.py` 对 stdlib logger 调 `.opt()`、read_log 错误分支绕过信封、avatar memory/inspiration 无归属校验（IDOR）、SSE 未带 `X-API-Token`。

**启动脚本真修（D-11 后续）**
- 根因：`Start-Process` 为控制台子进程新建窗口时，在 stdin/stdout 被重定向（CI / 管道 / 隐藏窗口 / 远程 shell）的环境会**死锁** → 后端永远起不来（表现为"卡在 [1/3] 无子进程"）。
- 修法：子进程 stdout/stderr 显式重定向到 `var/logs/<时间>-<服务>.{out,err}.log`；端口轮询替代固定 sleep；停止后等待端口释放；新增 **`-Verify`**（真启动 → 端口 + `/api/v1/health` → 自动停止 → 退出码 0/1）；非交互不等待回车、不开浏览器。
- 实测：dev / demo / mobile 三模式 `-Verify` 全部 PASS；`cmd /c start-dev.bat -Verify` **exit 0，15.2s**；停止后 8765/5173/3000 全部释放；`audit_delivery.py` 仍绿。
- 新增 runbook `docs/runbooks/startup.md`（入口对照 / `-WhatIf` `-Verify` / 日志排障 / 与 CI 边界）。

### Changed — Phase 3：前端全量分层 + 交付底座（2026-10-27）

本轮把"按类型平铺"的前端彻底迁入领域包，并把启动器/lint/备份治理补齐。**后端 1284 测试、前端 86 测试、lint/format/typecheck/build 全绿。**

**P3 全量迁移：27 个领域 → `features/`**
- 142 个文件移动：`api/<d>.ts` → `features/<d>/api.ts`；`types/<d>.ts` + api 内联类型 → `features/<d>/model.ts`；`views/<Domain>/` → `features/<d>/views/`；`components/<domain>/`、`composables/use<Domain>` 同理；每个领域一个 `index.ts` 唯一出口（view 只导出懒加载入口，避免主包污染）。
- 非领域资产归位：`types/api` → `kernel/http/types`；`types/common|user` → `shared/types`；`utils/offlineQueue*` → `kernel/offline`；`useTheme`/`useAutoSave`/`useQueryAction` → `shared`；`useDevice`/`useAsync`/`useShortcuts` → `kernel`；`components/common` → `shared/components/common`；纯 UI layout → `shared/components/layout`；业务壳（DefaultLayout/TopNav/GlobalSearch/LeftInfoPanel）→ `app/layout`；NotFound → `app/views`。
- 旧路径引用 **392 → 0**；三个旧桶（api/types/composables index）删除。
- 构建结果：main chunk 87,473 → **88,647 B（+1.3%）**，各域 view 仍独立懒加载 chunk。

**P4：薄壳清理 + kernel 收口 + `kernel/http` 拆分**
- 8 个薄转发壳全部删除，`api/ composables/ stores/ constants/ directives/` 过渡目录清空；`frontend/src` 只剩 `app/features/kernel/shared/styles/test`。
- `kernel` 对上层引用归零；架构守护删除 `TRANSITIONAL_AREAS`（旧目录依赖一律 ERROR），R14 负向测试证明会变红。
- `kernel/http/index.ts`（416 行、9 类职责）拆为 `client` / `errors` / `request` / `sse` / `types` / `connectivity` + 22 行纯出口；**公开 API 与行为契约逐字不变**（10 个 value + 1 个 type，AST 对比一致）。

**ADR-0008：请求体 `null` 语义**
- 明确"显式 null = 清空、省略 = 不改"（后端 `exclude_unset=True` + 字段存在即赋值）。前端请求类型落地 34 处 `?: T | null`（含 Project/Milestone），不再用 `as any` 表达清除关联。

**D-11 启动器单一实现**
- 新增 `ops/start.ps1`（`-Mode dev|demo|mobile [-DataDir] [-WhatIf]`）与 `ops/setup.ps1`；根 4 个 `.bat` 与 `scripts/dev.ps1` 改为 ASCII 薄转发壳（原 97/120/100/86 行 → 14–17 行）。
- `-WhatIf` 三模式实测（不启动进程）；`audit_delivery.py` 守护点从 .bat 迁到 ps1，新增"转发壳契约/模式契约"，两次负向验证均变红。

**D-12 Git 历史备份治理**
- 新增 `ops/backup-git.ps1`：检测 `.git` Junction 并警告、`git bundle create --all`、`bundle verify` 校验、按数量轮转；实测 4.5MB / 107 commits 通过。备份 runbook 更新为脚本优先流程。

**D-13 lint 进 CI**
- 后端：`ruff 0.6.2`，`select = E4/E7/E9/F`（不做 format），**245 → 0**；F841 修复一律"只剥赋值、保留有副作用的调用"；F821 连锁暴露并修复了 `project_service.export()` 的一处函数内 import 隐患。CI `backend.yml` 增加 ruff 步。
- 覆盖面补齐（D-16）：`backend/scripts/**` 已纳入 ruff —— 13 条（F541 4 / F401 3 / F821 3 / F841 3）清零，门禁三处统一为 `ruff check app tests scripts`（`backend.yml` / `check_all.py` 第 15 项 / `pyproject.toml` 口径说明）。
- 前端：ESLint 9 flat + Prettier + `eslint-config-prettier`；**核心是 ADR-0007 分层边界由 `no-restricted-imports` 强制**（kernel↛shared/features、shared↛features、feature 禁止深链跨域），负向验证会变红；CI `frontend.yml` 增加 `lint` 与 `format:check`。
- 付了学费：Prettier `semi:false` 会把 Vue **多语句**内联事件处理器拆成换行（Vue 表达式解析失败 → build 红）。已把 25 处抽成 23 个命名函数，扫描器归零；约定写入 `docs/guides/frontend.md`：**模板内联 handler 必须是单次调用，多语句抽函数**。

**CI 首次真实运行（2026-10-28，重建仓库后）**
- 4 个 workflow 全部跑通：`backend-ci`（ruff + pytest 1284 + 架构守护 + 冒烟）、`frontend-ci`（lint + format + typecheck + vitest 86 + build + 2 个行为脚本）、`repo-guard`、`android-apk`。
- 实跑暴露并修复 3 个"本地永远发现不了"的 CI-only 缺陷：
  1. `backend.yml` 在 **job 级 env** 用 `${{ runner.temp }}` → runner 上下文不可用，GitHub 直接判 workflow 非法（0s 失败、无日志）→ 改为 `/tmp`；
  2. `audit_docs_links.py` 跨平台缺陷：文档里的 `ops\start.ps1` 在 Linux 被当字面文件名、`var/...`（gitignored）被当必须存在 → 归一为 `/` + 运行期路径豁免；
  3. `frontend.yml`/`android-build.yml` 固定 Node 20，而 **jsdom 30 engines 要求 ≥22.22/≥24.15**（vitest 报 `webidl.util.markAsUncloneable is not a function`）→ 统一升 Node 24，与开发机一致。

**验证入口**
- `check_all.py` 扩到 **15 项**（新增 ruff；前端 lint/format 在 CI）。CI 四工作流覆盖：后端 lint+测试+冒烟、前端 lint+format+typecheck+测试+构建、仓库守护、Android 打包。

### Changed — Phase 4：交付收尾（var 数据迁移 / styles 归位 / scripts lint / 泄漏收尾，2026-10-27）

- 运行期数据目录收敛到仓库根 `var/`（ADR-0004）：真实库 `backend/data` → `var/data`、演示库 `backend/data_demo` → `var/demo`、历史副本 `backend/data_*` → `var/legacy/<原名>`。全部为**复制后逐文件 SHA256 校验一致**（41 个文件 / 0 不一致），真实库业务行数 154 → 154 不变、`alembic_version` 0021 不变。
- `backend/app/config.py`：dev/源码运行默认数据目录改为 `<仓库根>/var/data`（**与 CWD 无关**）；保留「`var/data` 不存在而旧 `backend/data` 存在 → 回退旧目录并告警」的一次性兼容分支（迁移完成并发布一版后可删，源码注释写明删除条件）。打包（frozen）分支行为不变。
- `ops/start.ps1`：dev/mobile 默认 `var/data`、demo 默认 `var/demo`；`-DataDir` 相对路径解析基准从 `backend/` 改为**仓库根**。`scripts/dev.ps1` 兼容壳文档与 `seed_demo.py` 默认目录同步。
- 迁移前备份：`ops/backup-git.ps1` 生成 git bundle（4,406,419 B，`bundle verify` 通过）+ `var/backups/data-pre-var-migration-2026-10-27/`（17 文件逐文件 SHA256 校验，含 `.encryption_key`）。
- 旧目录不删除，原样改名为 `backend/.legacy-data-2026-10-27/`（已 gitignore；确认无误后可删）。

**工程文件归位（styles / test setup / d.ts）**
- `src/styles/{variables,element-plus,global,animations}.scss` → `src/shared/styles/`；`src/test/setup.ts` → `src/shared/test/setup.ts`；`src/styles/`、`src/test/` 删除，`src/` 顶层只剩 `app/features/kernel/shared` + 3 个生成 d.ts。
- 零变化证据：用项目 dart-sass 分别编译迁移前后，**4/4 CSS 字节完全相同**（13,319 / 1,421 / 7,347 / 2,535 B）；`main.ts` 注入顺序逐条不变；build 产物 JS `index-DKAMBqBz.js` 88,647 B、CSS `index-B4rfms-L.css` 59,251 B **哈希与大小均未变**。
- `auto-imports.d.ts` / `components.d.ts` / `env.d.ts` 保留 `src` 根（unplugin 生成产物/全局环境声明，不属于分层资产），理由写入 `shared/README.md`。

**D-16：`backend/scripts` 纳入 ruff**
- 13 条清零（F541×4 / F401×3 / F821×3 / F841×3），门禁三处统一 `ruff check app tests scripts`（`backend.yml` / `check_all.py` / `pyproject.toml`）。
- 3 条 F821 逐条核实：`seed_demo.py:441 utcnow` 是**真潜伏 bug**（completed 且无 `done_days` 时 NameError，已用 HEAD 源码+桩复现；当前数据走不到）→ 函数内补导入；`smoke_backend.py` 两处 `pathlib` 是死代码（`'pathlib' in dir()` 恒 False 且下一行覆盖）→ 删除。

**P0-2 泄漏收尾（refs 层）**
- `git-filter-repo` 清洗本地历史（移除 `backend/data*/**`、`*.db*`、`.encryption_key`；44 commits、main tree 逐字节不变）；本地 10 个陈旧分支删除 + reflog/gc → 旧 SHA 本地 `cat-file` 已失败。
- 远端 `git push --mirror --force`：只剩 `main` + 3 个干净 tag，`feature/phase2-development` 等 10 个分支删除。
- `audit_repo_secrets.py --strict` 已在 CI 与 `check_all.py` 生效（历史再出现 DB 直接红）。
- ✅ **2026-10-28 已彻底处置**：`gh repo delete` + 重建 + 推送干净历史（`main` 86fa061 + 3 tags，分支数 1）。验证：旧 commit → HTTP 422、旧 blob → HTTP 404、`git fetch` → `not our ref`、全新克隆历史扫 `*.db*`/`.encryption_key` 命中 0；star/fork 归零属预期，仓库描述保留。

### Changed — Phase 2：收口领域边界（Repository / sync / 前端分层，2026-10-27）

本轮目标：把"分层正确"升级为"边界被机器守住"。**后端测试 1229 → 1282，前端测试 86，全部通过。**

**D-06 Repository 收口（service 零直连 ORM）**
- 16 个 service 的 **156 个直连 ORM 调用点 → 0**（AST 口径）。
- 新增 7 个 repository：`growth`（State/Event/SkillStat）、`vault`、`workspace`（Root/File）、`audit`、`settings_history`、`backup`（WAL checkpoint）、`task`（FocusSession）；现有 repo 增加约 60 个**业务语义化方法**（`identity_counts` / `clear_project` / `replace_source_links` / `list_autofill_candidates` / `stats_user` …）。
- 基类新增纯 DAO 工具 `BaseRepository.nullify()`（解除引用，只 flush），避免在 service 写 UPDATE。
- 聚合服务（dashboard/report/backup/security）跨域读全部改经各域 repo，不再直接 `select(Base.metadata.tables)`。
- 新增守护 **R13**：service 出现 `select()/text()/db.execute|get|scalar|scalars|add|add_all|delete|query` 即 CI 红（`services/sync/` 为显式豁免）；8 条原子性测试 + 19 条仓储契约测试补位。

**D-07 `core/sync` 领域逻辑下沉**
- `core/sync.py`（389 行，表分级策略/密文列白名单/settings 前缀过滤/导出游标）整体迁入 `services/sync/`（`engine.py` + `adapters.py` + `__init__.py`），行为零变化；`api/sync.py` 与 2 个脚本的 import 更新。
- `core/sync_adapters.py` 并非死代码（smoke 脚本在用），随之下沉而非删除；**真正的死代码 `core/cache.py` 已删除**。
- 结果：`core/` **0 依赖 models/database**；架构守护 **R2 收紧**为 `core → {core, root(config/database)}`，禁止依赖 models 回潮。
- 新增 29 条 sync 测试（策略/快照/差分/加密列剥离/游标/公开面）。

**D-09 SettingsView 拆分（1701 → 291 行）**
- 拆出 `components/settings/` 14 个分区组件、`composables/useSettings{Config,Diagnostics,Sync}.ts`、纯逻辑 `settingsUtils.ts` 与共享样式；父组件只留骨架与协调（**-82.9%**）。
- 等价性证据：DOM 405 节点 vs 405 节点（结构/文本/class/条件 **0 差异**）、sass 规则集 99 vs 99、emit 35/35 有监听、5 个 loader 时机不变；新增 7 条纯逻辑 vitest（前端 79 → 86）。
- 代价：`SettingsView` chunk 31,979 → 38,590 B（+6.6 KB，1 个巨组件拆成 15 个模块的固有成本）。

**前端 kernel / shared / features + pet 单领域试点（ADR-0007）**
- `kernel/`：http（单点漏斗）、ui（toast/modal）、offline（队列）真实迁移；`shared/`：constants、directives 真实迁移。
- `features/pet/`：api / model / composable / component / view / `index.ts` **真实迁移，旧路径全删无壳**；6 处引用方改走 feature 入口；view 用懒加载入口，主包不受污染。
- 旧公共路径保留 **8 个薄转发壳**（`export *`、壳内零实现、标 `@deprecated P1/P4 删除`），避免 30+ 文件 import 雪崩。
- 新增守护 **R14**：kernel 反向依赖 shared/features、shared→features、跨 feature 深链 = CI 红；过渡依赖（kernel→types/utils 等 8 条）先 WARN，P3 归位后转 ERROR。`domains.json` 新增 `frontend_features` 登记。
- 验证：typecheck 0 / vitest 86 / build 成功；`PetSettingsView` chunk **14,236 B，与迁移前同大小**，主入口 +28 B。

**D-15 架构守护空转修复（本轮审计副产品，P0 隐性）**
- 发现 `layer_of_file()` 用"仓库相对路径"与 `app/` 前缀比较（永不匹配）→ 所有文件被判 `root` 跳过，**R1/R2 自 Phase 0 起实际未生效**；且 `TYPE_CHECKING` 豁免标记传入却未使用（修复前暴露 28 条 api→models 假违规）。
- 两处均已修复，并新增 **4 条负向测试 + 2 条回归测试**（R1/R2/R13/R14 各注入违规证明会变红；分层判定与 TYPE_CHECKING 豁免锁死）。
- 现状：178 个后端模块、`--strict` 0 违规；R14 仅剩 8 条已登记过渡依赖。

**数据契约收尾**
- 新增迁移 `0022`：把历史遗留的 `tasks.status='todo'`（已修复 bug 的残留数据）归一为 `pending` —— 否则响应枚举校验会 500；实测真库副本 25 行任务无损。
- `TaskOut.status/priority`、`FocusTaskOut.status` 收紧为 `Literal`；**请求侧刻意保持宽松**（priority 非法值有"回退 medium"的既有契约、status 由状态机返回业务码），已在 schema 注释写明原因。
- `ops/server` 的 `npm test` 脚本修正为 `node --test`（目录参数在 Node 24 下会误判为模块）。

### Changed — Phase 1：修正正确性（3 个 P0 + 事务 / 迁移 / 契约 / 死代码，2026-10-26）

本轮目标是"把架构纪律落到会出错的地方"。**后端测试 1215 → 1229 全绿**，新增 4 道守护。

**P0-1 访问令牌回环绕过（安全，已修）**
- 原缺陷：`server.js` 对 `127.0.0.1` 来源无条件放行；cloudflared 等隧道把公网请求转成回环连接后，`X-API-Token` 形同虚设。
- 修复：判定逻辑抽到 `ops/server/lib/security.mjs` —— 只有"回环 **且无任何代理头**（`x-forwarded-for` / `cf-connecting-ip` / `forwarded` …）"才豁免；令牌比较改 `crypto.timingSafeEqual`；响应加 `nosniff` / `Referrer-Policy` / `X-Frame-Options`。
- 令牌治理：新增 `npm run token:rotate`（旧令牌留在 `.qm-token.prev` 宽限期，删除即吊销）。
- 验证：`ops/server/test` 16 条单测（含 4 条 P0 场景）+ 端到端 curl（代理头无令牌 401 / 本机直连放行）+ CI `edge-server` job。

**P0-2 真实数据库存在于 Git 历史（已评估 + 防护，远端处置待仓库所有者执行）**
- 事实：`backend/data/app.db`（606KB）在提交 `6b5c2dd` 进入历史，仅 `origin/feature/phase2-development` 可达；**未包含 `.encryption_key`**，故加密字段仍是密文。
- 新增 `scripts/audit_repo_secrets.py`：检查当前索引 + 扫描全部 refs 的历史新增文件 + `.gitignore` 覆盖抽样；已接入 CI。
- 处置步骤（删分支 / 重建远端 / 轮换凭据 / 验证）见 `docs/runbooks/security-incident-db-leak.md`。

**P0-3 备份导入 100% 失败（已修）**
- 原缺陷：`http.post` 对 `FormData` 做 `JSON.stringify`，body 变成 `{}` 且 `Content-Type: application/json`，后端 `/backup/import` 要求 multipart → 必 422。
- 修复：`http.postForm()` 原样传 FormData、不手写 Content-Type（boundary 由运行时生成）、显式跳过离线队列（二进制体无法重放）；`backupApi.import` 切换。
- 验证：真实 HTTP server 抓原始请求，断言 `multipart/form-data; boundary=...` 与原始字节 → 11/11 PASS；另加 4 条 vitest 供 CI。

**事务上移：repo 只 flush，service 控 commit（D-04）**
- `BaseRepository.create/create_many/update/delete` 不再内部 commit → `flush()`；`api/deps.get_db` 改为请求级事务（成功 commit / 异常 rollback）。
- service 的 51 处 commit 收敛：删除 11 处破坏原子性的中间提交，补齐 15 处"发布事件前提交"（订阅者用独立 Session，未提交读不到），非请求调用方（seed / 后台任务 / 扫描线程）逐个补齐。
- 新增 `tests/test_transaction_atomicity.py` 8 条：用例第二步失败时第一步必须整体回滚、publish 时刻独立 Session 可见、repo 只 flush、get_db 兜底提交。
- 架构守护新增 **R11**：repositories 内出现 `commit()` 即失败（负向测试验证过会命中）。

**迁移基线重建（D-05）**
- `0001_initial.py` 从 `Base.metadata.create_all()` 改为**冻结显式 DDL**：49 张表 / 79 个索引，revision 与 down_revision 不变（已升级库不受影响），downgrade 显式逆序。
- 新增 `0021_schema_reconcile.py`：幂等对账——补齐审计发现的 11 个缺失索引、删除 DB 侧同列重复索引、兜底补表/列/索引；对 0011 / 0020 / 无版本手工库均验证可升级。
- 新增 `tests/test_migration_integrity.py` 6 条：全新库三方对账（ORM metadata / 实际 DB / 迁移链）、0001 无 bulk DDL、链线性单 head、0011→head、部分升级库、0021 幂等。
- 架构守护新增 **R12**：0001 出现 `create_all`/`drop_all` 即失败。
- 验证：7 个真实数据目录**副本**升级成功，业务行数 0 变化（`data` 154 行不变）。

**前端契约对齐（D-08）**
- 13 处漂移全部修正（task 的 `estimated_minutes`/`acceptance_criteria`、document 的 `tags`/`project_id`、ProjectMemory/Review 的 `identity_id`、`timestamp` 单位秒、review `type` 可选等），后端 `schemas/*.py` 为唯一真值。

**前端死代码清理（D-10）**
- 删除 15 个文件 / 1625 行（含被 `TopNav` 取代的 `AppHeader`/`AppSidebar`、死 store、6 个死 composable、死桶导出及其传递性死亡组件）。
- 每个候选都有零引用证据（静态 import 全量解析 + 标签名双查 + `components.d.ts` + 懒加载 + 旧 dist 交叉验证）；`npm run typecheck` 连续 5 轮 exit 0。

**验证入口**
- `check_all.py` 扩到 **14 项**（新增仓库敏感文件守护），`--strict` 保持"缺依赖=失败"。
- CI：`repo-guard` 增加敏感文件历史扫描；新增 `edge-server` job 跑统一服务测试。

### Changed — 架构重整：把"靠自觉"换成"靠机器"（2026-10-26）

本轮**不动业务功能**，只重做架构的表达、边界与工程底座。背景是三位审计员对
644 个文件做的只读审计（报告：`.arch-audit/reports/{backend,frontend,ops-docs}.md`）。

**新增权威文档与机器契约**

- `ARCHITECTURE.md`（仓库根）：全项目架构唯一权威——一条请求的 15 跳、五层依赖规则、
  8 个领域的边界、目录契约、新增模块 12 步、债务清单与演进路线。
- `docs/architecture/domains.json`：领域/模块的机器可读注册表（8 领域 × 48 模块）。
- `scripts/audit_architecture.py`：AST 解析真实 import 图的架构守护，10 条规则
  （分层方向 / core 隔离 / 命名 / 路由与模型注册 / 领域归属 / 根目录契约 / 前端边界），
  替代原先只有 5 条文本断言的 `test_architecture.py`（后者改为调用它，单一规则来源）。
- `scripts/architecture_baseline.json`：债务棘轮——已知违规降级为 WARN，新增违规立即失败。
- `scripts/audit_docs_links.py`：文档链接与内联路径全量守护（归档区/CHANGELOG 冻结不校验）。
- `docs/architecture/ADR/0001–0006`：分层模块化单体、core 最底层、架构即代码、
  运行期数据、版本/依赖单一来源、文档 IA 六项决策记录。

**结构修复**

- `core` 不再反向依赖业务层：`core/event_handlers.py`、`core/growth_handlers.py`
  上移到组合根 `app/bootstrap/`。审计前 `core → services/repositories` 是真实违规，
  且旧守护测试全绿（抓不到）。
- 根目录从 14 个游离文件收敛到 12 个（仅 4 个用户启动器 + 元文件 + 契约文档）：
  统一服务 `server.js` + `package.json` → `ops/server/`；`push-branches.bat` → `ops/`。
  `server.js` 已用 HTTP 实测：静态 200 / 代理 502 JSON / 令牌路径不变。
- 后端测试入口 `tests/test_architecture.py` 改为调用架构守护（不再维护第二套规则）。

**文档 IA 重组（58 个文件移动、零内容删除）**

- `docs/` 从"按写作时间堆叠"改为五分区：`architecture/`（现行+legacy+ADR）、
  `product/`（需求/PRD v1 归档/v2 现行/UI）、`guides/`、`process/archive/`、`design/`、`assets/`。
- 新建 `docs/README.md`：唯一入口，10 秒导航 + 现行/archived 显式标注。
- 5 组多版本文档收敛，21 个带日期的过程记录归档（保留可追溯性）。
- 链接守护全量通过（现行 32 个 md 零失效）。

**工程底座**

- `VERSION` 成为版本唯一事实来源；`scripts/check_versions.py` 校验 5 处并支持 `--sync`
  （修复 0.1.0 / 0.7.0 / 1.0 三处版本分裂）。
- 依赖单一来源：`requirements.txt`（运行时）+ 新增 `requirements-dev.txt`（测试/工具）；
  `pyproject.toml` 明确"仅工具配置"，版本与 `VERSION` 对齐；修复 `uv.lock` 空壳导致的
  "按文档装不出依赖"。
- `backend/.env.example` 重写：覆盖 `Settings` 全部 12 个字段，删除幽灵变量
  `VENUSTECH_AI_API_KEY`，安全默认（`DEMO_SEED=false`、CORS 不用 `*`）。
- 数据目录解析改为**与启动 CWD 无关**（默认恒为 `backend/data`），杜绝从仓库根启动
  生成第二份库；新增 `var/` 约定与 `docs/runbooks/backup.md`（密钥与库必须成对备份）。
- CI 从 1 个工作流（仅 Android 打包）扩到 4 个：`backend.yml`、`frontend.yml`、
  `repo-guard.yml`，把 12 项守护全部纳入 CI（此前 CI 覆盖率 0%）。
- `check_all.py` 新增 `--strict`（缺依赖=失败，杜绝"跳过即通过"的假绿）与文档链接项（13 项）。

### Fixed — 单调日历依赖导致的"每周一必红"测试（2026-10-26）

`test_dashboard_production.py::test_streak_calculates_consecutive_days` 断言
"本周至少 2 天打卡"，但打卡日插入的是"今天 + 昨天"——周一运行时昨天属于上一周，
本周只有 1 格为 True，测试必然失败。改为按 `weekday()` 推导期望值，全年任意一天都确定。
（实测：2026-10-26 恰为周一，红的正是它。）

### Security — 本轮审计发现、待你决策的 P0（尚未修复）

- **令牌回环绕过**：`ops/server/server.js` 对 `127.0.0.1` 无条件放行；若用 cloudflared
  隧道该端口，公网请求源地址即回环 → `X-API-Token` 形同虚设。
- **旧分支含真实用户库**：`origin/feature/phase2-development` 树中存在
  `backend/data/app.db`（606KB，公开可拉取）。需删除分支并按需清洗历史（不可逆，待确认）。
- **备份导入 100% 失败**：前端用 `JSON.stringify` 发送 `FormData`，后端要求 multipart → 422。


### Fixed — 密钥轮换此前是「假轮换」，可致 API Key 永久丢失（2026-10-11）

**这是本轮最重要的一条**：`SecurityService.rotate_key()` 声称轮换三张表，
实测只有 `settings` 真的被重加密。探针（`tests/test_zz_probe_security.py`，跑完即删）
给出的硬证据：

| 探针观测 | 含义 |
|---|---|
| `rotate_key` 返回 `{'rotated': 1, 'tables': ['vault_items','users','settings']}` | 声称三表已轮换 |
| `users.api_key_encrypted` 密文**未变化** | **从未真正轮换** |
| `vault_items.secret_encrypted` 密文**未变化** | 不归本密钥管，永远轮不到 |
| `settings` 密文变化 | 只有这一项真的轮换了 |

1. **`users.api_key_encrypted` 带前缀，导致整串无法解密**
   `encrypt_secret()` 落库的是 `"fernet:" + <Fernet token>`（`app/core/security.py`），
   而旧代码拿**整串**去 `mgr.decrypt()` → 必然 `InvalidToken` → 被 `except` 静默 `continue`。
   后果不是当场报错，而是该列只能靠密钥环兜底；密钥环只留 `KEEP_PREVIOUS=5` 代，
   实测**第 4 次轮换后 API Key 永久解不开**（`解密失败：密钥不匹配或数据已损坏`）
   —— 正是这段代码注释原本警告的失败模式。
   修法：读时剥 `fernet:` 前缀、写回时原样还原。
2. **`vault_items.secret_encrypted` 本不该登记**
   它的密文由**保险箱主密码**派生的独立 Fernet 加密（`vault_service._require_fernet`），
   与全局密钥无关，`mgr.decrypt` 必然失败 → 每次都静默跳过，**却在返回值里谎报「已轮换」**。
   已从 `_CIPHER_COLUMNS` 移除（它的轮换在 `VaultService.change_password` 里）。
   登记判据已写明：**只有由全局 `EncryptionManager` 加出来的列才登记**。
3. **轮换后全局单例不刷新 → API Key 当场失效**
   修好 ①② 后，轮换开始**真的重写密文**，随即暴露出下一个环节：
   `rotate_key` 用的是局部 `EncryptionManager`，而 `decrypt_secret()` 走的是
   `main.py` 启动时建的**长驻单例**，其 `_fernet` 只在进程启动读一次磁盘。
   症状极具误导性：提示「密钥轮换成功」，但 API Key 当场失效，**重启服务才恢复**
   （由 `smoke_backend.py` 的往返断言先测出）。修法：新增
   `EncryptionManager.reload()`，轮换提交成功后刷新已存在的单例。
4. **返回值不再谎报**：改为按表统计**真的解开并重写**的行数
   （`{"rotated": N, "tables": [...], "details": {...}}`），
   而不是回一张静态清单。前端不消费该结构，无兼容风险。
5. **`api/security.py` 改用项目异常体系**：原先用裸 `HTTPException`，会绕过统一信封，
   前端（`http.ts` 只读 `errBody.message`）只能显示 `HTTP 503: Service Unavailable`。
   它是**全仓唯一**这样写的 API 文件，已统一为 `ServerException` / `ValidationException`。

### Fixed — `EncryptionManager` 的两处静默错误与三处死代码（2026-10-11）

- **`decrypt_file()` 绕过历史密钥回退**：旧实现直接 `self._fernet.decrypt(...)`，
  于是同一份密文 `decrypt()` 能解（会依次试 previous）、`decrypt_file()` 却抛
  `InvalidToken` —— 两条路径行为不一致。改为统一走 `self.decrypt()`。
- **`decrypt_file()` 在无密钥时把密文当明文写出**：旧写法 `self._fernet.decrypt(x) if self._fernet else x`，
  `_fernet` 为空（cryptography 缺失）时会把**密文原样写进目标文件**，静默产出垃圾。
  现由 `decrypt()` 明确抛 `RuntimeError`。
- 删除三处死代码：`__init__` 里对同一路径的**重复赋值**、`_previous_fernet`（单数）
  的赋值逻辑（**全仓无任何读取方**，`decrypt()` 只用复数 `_previous_fernets`）、
  `rotate_key` 里的 `for f in [self._fernet]: pass` 空循环。
  注：`decrypt_file` / `encrypt_file` 全仓**无生产调用方**，修它们零风险。

### Added — 安全模块测试覆盖（2026-10-11）

后端 pytest **1126 → 1219 条**（+93，50 → **52 个文件**）：

| 文件 | 用例 | 守什么 |
|------|------|--------|
| `tests/test_encryption_production.py` | 33 | `EncryptionManager`：密钥派生 / 随机 salt / 密钥环多代回退 / 轮换后旧密文可解 / `reload()` / 单例入口 |
| `tests/test_security_production.py` | 42 | **`rotate_key` 真的重加密**（核回归：连续轮换超代数后仍可解）/ 注册表一致性（扫描模型里所有 `*encrypted*` 列，漏登记即失败）/ DPAPI 与损坏值跳过不阻断 / 失败整体回滚 / `require_unlocked` 门禁 / 审计白名单与修剪 |
| `tests/test_security_api.py` | 18 | 信封契约 / 未解锁 409 / 解密坏 token → 400 且信封完整 / 后端不可用 → 500 |

- 注册表守护带**非空断言**：扫描函数返回空集时不得平凡通过（否则等于永真）。

### Added — 前端单元测试体系（vitest + jsdom，2026-10-11）

**前端不再「零单元测试」**：新增 `frontend/vitest.config.ts` + `src/test/setup.ts`，
4 个 spec / **75 条用例**（实测 4 passed / 75 passed），并纳入一键入口
（`check_all.py` 第 12 项，11 项 → **12 项**）。

| 套件 | 用例 | 守什么 |
|------|------|--------|
| `src/utils/__tests__/reportHtml.spec.ts` | 29 | 人生报告单文件 HTML：零外链 / 零脚本 / 全量转义（XSS）/ 三轴渲染 / 体积格式化 / 下载行为 |
| `src/composables/__tests__/useTheme.spec.ts` | 22 | data-theme 映射表（4 包 × 明暗，逐行钉死）/ 冷启动读存储 / 跟随系统 / 循环切换 |
| `src/constants/__tests__/constants.spec.ts` | 12 | 常量与类型的一致性（THEME_PACKS ↔ ThemePack）/ 状态与优先级映射 / 存储键与路由 |
| `src/composables/__tests__/useQueryAction.spec.ts` | 12 | `?action=` 消费与清参 / 同页重复触发 / 未知 action 不动 URL / 异常不吞 |

- 新增 npm 脚本 `npm run test`（单次）/ `npm run test:watch`
- 新增 devDependencies：`vitest@^3` / `@vue/test-utils@^2` / `jsdom`

### Fixed — 前端单元测试暴露的 3 处缺陷（2026-10-11）

1. **`useTheme` 的 `isDark` 不响应系统明暗变化**（`composables/useTheme.ts`）
   `isDark = computed(() => resolveMode(config.value.mode) === 'dark')`，而 `resolveMode`
   直接读 `media.matches` —— 依赖里只有 `config`，**系统切换时 computed 不会重算**。
   症状：`mode=system` 下用户切换 OS 主题，`data-theme` 变了（监听器里 `apply` 了），
   但组件读到的 `isDark` 仍是旧值 → 月亮/太阳图标与依赖明暗的文案不跟着变。
   修法：把系统明暗收进 `const systemDark = ref(media.matches)`，`resolveMode` 读 ref，
   监听器里先更新 ref 再 `apply`。已写成回归用例（`第3组` 两条）。
2. **`THEME_PACKS` 漏了第 4 套主题**（`constants/index.ts`）
   常量里只有 cream / guofeng / abyss，而 `ThemePack` 联合类型、`useTheme.cyclePack`
   顺序、`SettingsView.vue` 的主题选择器**都是 4 套**（缺 `epic` 史诗典藏）。
   因为该常量当时无消费方，漏项不报错也没人发现 —— 现补 `epic` 并由
   `constants.spec.ts` 第 1 组钉死「常量必须与类型一一对应」。
3. **`useQueryAction` 的处理器抛错会变成未捕获的 Promise rejection**
   （`composables/useQueryAction.ts`）`consume` 是 async，调用处是 `void consume(v)`，
   处理器抛错 → rejected promise，Vue 的 errorHandler 接不住（watch 回调返回 undefined），
   只在控制台留一条无上下文的报错。修法：捕获 + `console.error` 记录，
   **保留 `action` 参数**（用户可重试），而不是既没打开弹窗又清掉了参数。

### Added — 测试覆盖第五轮：experience / report（2026-10-11）

**规模：45 文件 / 1012 用例 → 49 文件 / 1126 用例**（新增 114 条，全量实测 1126 passed / 0 failed）

- **新增 `experience`**（S6-4 经历视图：日记 / 复盘 / 分身记忆 / 项目记忆四源归并）：
  Service 44 + API 20 = **64 条**
  - 归一语义：日记取 `diary_date`、复盘取 `review_date`、两种记忆取 `created_at`；
    `None → created_at` 的兜底分支单独成测（`_as_datetime` 三个分支）
  - 跨源降序（而非按源分块拼接）、内存分页（切片只影响 items，`total` 始终全量）、
    身份过滤（`identity_id` 优先于 `identity_unassigned`）、`source_counts` 是**过滤后**计数
  - **只读铁律被测试守住**：调用前后四张源表行数不变 + `sqlite_master` 表集合不变
    （不存在 `experiences` 之类的新表）
  - 单源上限 `_PER_SOURCE_CAP=500` 钉成契约（含「上限按源而非全局」）
- **新增 `report`**（S6-5 人生报告：身份 × 成长 × 档案 三轴 + 近期经历）：
  Service 35 + API 15 = **50 条**
  - 身份轴六项计数全部**写后查库交叉验证**（与 `SELECT count(*)` 对拍），
    含归档身份（`is_archived=True` 而非被丢弃）、软删除身份排除、未归类桶
  - 成长轴：award 后 level/exp 同步、技能树计数为 0 的分类被过滤、
    分类被移除时名称退化为 id（历史计数不丢弃）
  - 档案轴：`workspace.enabled` 默认 false → **不读磁盘、roots 为空**；开启后列出根
  - 近期经历：上限 10 条、降序、`identity_name` 解析为身份名（未归类为 `null`）
  - **如实钉住一个反直觉事实**：报告自称「只读聚合」，但首次生成会经
    `GrowthService.get_or_create_state` **写入一行 `growth_states` 并 `commit()`**
    —— 已写成用例（不是 bug，但接进别的事务前必须知道）
- `tests/factories.py` 新增 9 个工厂：identity / diary / review / avatar_memory /
  project_memory / sop / prompt / skill / workspace_root，以及四源复合夹具
  `seed_four_sources(day_offset=...)`（`reviews` 上有 `(user_id,type,review_date)`
  唯一约束，同日同类型会撞 —— 工厂用参数错开日期）

### Fixed — 第五轮修复的生产缺陷（2026-10-11，1 处）

`api/experience.py`：`page` / `page_size` 是**裸 int 参数，无任何范围约束**。
实测 `page=0` → `start = (0-1)*30 = -30` → Python 负索引切片 `rows[-30:0]` = 空列表 →
**HTTP 200 但 `items` 为空**（`total` 却 > 0），前端表现为「明明有数却一条都不显示」；
`page_size=0` / 负数同理，`page_size=100000` 则一路拉满 4×500 条做内存归并。

修法：`Query(1, ge=1)` / `Query(30, ge=1, le=500)`，与既有约定对齐
（`api/events.py` 的 `limit`、`api/growth.py` 的 `limit`、`api/logs.py` 的 `tail`
都是 `Query(..., ge=, le=)`）。非法值现在统一映射为 **400 / code 1001**。
已核对前端实际传值（`ExperienceView.vue`：`page` 从 1 起、`PAGE_SIZE=50`）
与内部调用方（`ReportService._recent_experience` 直接调 Service，不走 HTTP），
确认不打断任何现有路径。

### Added — 真机端到端探针 + 日志格式守护（2026-10-11 第四轮）

**规模：44 文件 / 1006 用例 → 45 文件 / 1012 用例**（全量 44.6s）

- **新增真机端到端探针 `backend/scripts/probe_backend_live.py`（65 项断言）**：
  打**真实 uvicorn 服务 + 真实 SQLite 库**，验证「全新库 → 20 个迁移 → 种子 → 接口真可用」。
  与 `tests/`（进程内 TestClient）及 `scripts/smoke_backend.py`（TestClient 冒烟）互补，
  守的是**用户路径** —— 对应铁律「完成 = 双击 → 服务真的起来 → 关键接口非空」。
  实测：全新库就绪 21.4s · 20 个迁移全部成功 · 库文件 0.79MB · **65 项断言全绿**
- **新增 `scripts/audit_log_format.py`**（纳入 `check_all.py` 第 11 项，基线 0）：
  扫描 loguru 不生效的 `%s` / `exc_info=` 写法；已用植入坏样本反向验证会报警
- **新增 `tests/test_logging_contract.py`（6 条）**：把 loguru 的实际行为钉成契约
  （`%s` 参数丢失 / `{}` 正确 / `exc_info` 不进堆栈 / `opt(exception=True)` 进堆栈）
- `scripts/check_all.py` 从 10 项扩到 **11 项**

### Fixed — 日志写法系统性失真（2026-10-11 第四轮 · 真机探针发现，16 文件 / 50 处）

后端日志后端是 **loguru**（占位符 `{}`），但项目里有 50 处写成 printf 风格
`%s` / `%d` / `%.Nf`，或标准库 logging 的 `exc_info=`。实测（loguru 直接实验，非推断）：

| 写法 | 实际输出 | 参数/堆栈 |
|------|----------|-----------|
| `logger.info("A %s", 1)` | `A %s` | **丢失** |
| `logger.info("B {}", 1)` | `B 1` | 正确 |
| `logger.warning("D", exc_info=True)` | 无堆栈 | **不生效** |

真机 uvicorn 启动日志为证（修复前 → 修复后）：
`插件路由已挂载: %s` → `插件路由已挂载: aihot`；
`成长体系订阅者已注册（%d 个事件）` → `（14 个事件）`。

修法：`%s|%d|%.Nf` → `{}|{:.Nf}`；`exc_info=` → `logger.opt(exception=True)` 前缀。
影响：`main.py` / `database.py` / `core/{plugin_manager,event_bus,event_handlers,growth_handlers}.py` /
`api/{health,logs}.py` / `services/{dashboard,pet,growth,settings,workspace,backup}.py` /
`services/ai/ai_service.py` / `services/rules/domain_engine.py`。

> 这类失真**不会让任何测试变红**，也不影响功能，只让排查问题时看不到参数值 ——
> 故必须落成脚本守护，否则一定会被再犯。

### Added — 测试覆盖第三轮：panel / pet（2026-10-11）

**规模：40 文件 / 873 用例 → 44 文件 / 1006 用例**（全量 36.8s）

- **新增 `panel`**（快速待办 / 系统提醒 / 左侧面板聚合）：Service 41 + API 24 = 65 条
- **新增 `pet`**（桌宠配置 / 形象 / 四维陪伴数值 / 状态感知引擎）：Service 43 + API 20 = 63 条
- **`resource` 补 5 条**：`content_type` 白名单与契约回归
- 质量审计：44 文件 / 954 函数 / 2731 断言，**0 违规**

### Fixed — 第三轮修复的生产缺陷（2026-10-11，共 6 处）

1. `resource_service` + `models/resource.py`：收集箱 `content_type` 无白名单，
   模型注释写 `url` 而前端与种子数据用 `link` → 一旦参与筛选/渲染分支即**静默不匹配**。
   统一为 `text/link/image/file` 并加白名单（非法值 400）
2. `panel_service`：`update_todo` / `update_reminder` 显式传 `null` 直接写 `NOT NULL` 列
   → `IntegrityError` 未捕获 → **500**（实证：`NOT NULL constraint failed: quick_todos.title`）。
   加 `_reject_null` 守卫 → 400
3. `panel_service`：`reminder.type` / `repeat` 有注释枚举（meeting/study/health/custom、
   none/daily/weekly）但无校验 → 写错值不报错、前端渲染分支静默落到默认。
   加白名单（create + update 双侧）
4. `pet_service` + `api/pet.py`：`update_avatar` 收裸 `dict` 无白名单 → **mass-assignment**，
   客户端可改 `user_id`（**把形象送给别人**；探针实证 `user_id` 真被改写）
5. `pet_service`：形象四入口（update / delete / activate / `update_config.current_avatar_id`）
   零归属校验 → **IDOR**（探针实证：他人形象被成功删除）。
   加 `_owned_avatar → 404`，API 层改用显式 `UpdatePetAvatarRequest`
6. `pet_service`：`set_active_avatar` 在配置不存在时跳过写 `current_avatar_id`
   → 与 `avatar.is_active=True` 不一致。改为「不存在则创建」

### Added — 后端测试体系分级升级（2026-10-11）

**规模：3 文件 / 103 用例 → 40 文件 / 873 用例**（全量约 32s，两次复跑无抖动）

- **分层基础设施**：`conftest.py` 两层隔离（Service 层函数级事务回滚 /
  API 层动态清表）+ `factories.py` 数据工厂；新增 `tests/README.md`（规范）
  与 `tests/ROADMAP.md`（推进路线图）
- **覆盖铺开**：P0 核心业务 340 条 · P1 系统支撑 149 条 · P2 领域功能 181 条 ·
  P3 安全面 179 条（vault 主密码生命周期/密文形态/动作白名单 · resource IDOR 契约）
- **接入一键入口**：`scripts/check_all.py` 从 9 项扩到 **10 项**（新增后端 pytest 全量）
- **新增质量守护** `scripts/audit_test_quality.py`：静态扫描 5 类「缺陷存在时依然全绿」
  的写法（永真断言 / 无断言 / 宽泛 raises / 吞异常 / 空函数体），基线 0；
  已用植入坏用例的样本反向验证确实会报警

### Fixed — 测试暴露的生产缺陷（2026-10-11，共 12 处）

**第一轮（asset / workflow）**

1. `workflow_service` 生成任务 `status="todo"`（非法状态）→ 任何流转报 3001，**任务永久卡死**
2. `workflow_service` 标签/模板去重未带 `user_id` → 他人同名数据导致本用户**静默不创建**
3. `asset_service` 详情/更新/删除/使用**只校验存在性** → IDOR
4. `asset_service` / `workflow_service` PATCH 裸 dict 无差别 `setattr` → mass-assignment
5. `asset_service` `project_id` 仅靠外键兜底 → 不存在 id 触发 500，他人 id 被静默接受
6. `api/asset.py` `rating` 查询参数无范围约束

**第二轮（vault / resource）**

7. `resource_service` 构造函数**不收 `user_id`**，11 个单条操作零归属校验 → IDOR
8. `resource_service` `update_template` / `update_domain` 收裸 dict → mass-assignment
9. `resource_service` 非法 action 抛裸 `ValueError` → 500（应为 400）
10. `resource_service` 无 status 白名单 → 写入永不生效的值既不报错也不出现（**静默失败**）
11. `api/resource.py` + `schemas`：`batch-process` 参数绑定与前端封装契约不符
    → 按封装接线即恒定 400（页面尚无调用点，未在生产暴露）
12. `vault_service` `_session_keys` 在模块内被定义两次 → 死代码

### Fixed — 测试套件抖动根因（2026-10-11）

- `journal_mode=WAL` 曾被放进 SQLAlchemy connect 事件（每连接协商一次）→ 与连接池
  竞争导致「单跑过、全套挂、换新 Session 立刻好」的随机锁死。
  **修复**：引擎从 NullPool 改为小连接池（pool_size=5），WAL 移到启动时
  `run_maintenance()` 设一次。**效果：套件 238s → 15s 且不再抖动**
- `clean_db` 夹具用普通 Session 执行 `PRAGMA foreign_keys=OFF/ON` → PRAGMA 在事务内
  **静默无效**，OFF 残留在池连接上 → 级联删除失效。
  **修复**：改用 AUTOCOMMIT 连接，并在归还池前恢复 `foreign_keys=ON`

### 已知限制（已被测试钉死，非缺陷）

- PATCH 传 `null` 不能把字段置空（需传空串）；支持置空属接口语义变更
- SOP 版本历史取默认 100 条上限（未分页）
- 收集箱 `content_type` 无白名单，前端取值 `link` 与模型注释 `url` 拼写不一致
  （当前能正常存取；一旦该字段参与筛选或渲染分支即成静默不匹配）

### Added — 模块化深度开发 · mod-tools 收口（2026-09-19）

**P0 全部完成（6/6）**
- **工作区搜索防抖 + 分页**（P0-1）：搜索框 400ms 防抖（原来每次按键都发请求）；
  改为「加载更多」追加分页（PAGE_SIZE=50），显示「已显示 X / Y」与「已显示全部」；
  切根/改条件重置到第 1 页，与分页状态的追加语义严格分开
- **保险箱移动端表单单列**（P0-2）：<768px 下 `.vault__form-row` 由 1fr 1fr 塌缩单列
- **保险箱「更换主密码」入口**（P0-3）：头部按钮 + 三段密码弹窗；
  前端做长度 / 两次一致 / 新旧不同三重校验（主密码不可找回，必须拦住手误）；
  后端 `change_master_password` 本就完整（校验旧密码 → 全量重加密 → 换 salt/verifier）
- **语音实时上屏**（P0-5）：Web Speech 通道开启 `interimResults` +
  `continuous`，边说边出字；未定稿文字以弱化样式单独展示（不混入正式文本）；
  再按麦克风可停止；`no-speech`/`aborted` 不再误报「识别失败」；
  20s 兜底自动停止；卸载时释放麦克风实例

**P1 全部完成（6/6）**
- 保险箱凭据筛选（名称/用户名/网址 + 分类 + 身份），命中计数与无命中空态
- AI 资讯手动刷新按钮 + 移动端下拉刷新（阻尼 0.45、阈值 56px、仅顶部起手）
- 助理建议条目可单条移除
- **工作区扫描异步化**：`POST /scan` 立即返回 scanning 态并起后台线程；
  新增 `GET /scan-progress`（阶段 / 已发现数 / 僵尸态识别）；
  后台线程自建 Session（请求 Session 已随请求关闭）；前端轮询并在按钮上显示进度
- **SSH 连通性测试**：`POST /vault/items/{id}/test-connection`，
  仅 TCP 三次握手探测，host/port **只从凭据读取**（不接受请求体，避免成为端口扫描原语），
  3s 超时，结果写审计日志

**新增守护：设计引用存在性审计**（`frontend/scripts/audit-tokens.py`）
- 本轮实测发现 18 个「被引用但未定义」的 CSS 令牌（约 50 处引用受影响，
  `--danger` 单名被 11 个文件使用）——CSS 变量解析失败会**静默失效**，
  不报错、只是样式不生效
- 处置：在 `variables.scss` 增加 **LEGACY ALIAS** 兼容层（18 个名字一一映射到
  规范令牌；写成 `var(<既有令牌>)` 引用，自动跟随 4 套主题明暗切换），
  标注为待收敛项；未定义令牌基线钉在 0，新增即失败
- 同类问题扩展到**图标名**：实测 7 处引用不存在的图标（渲染为空 → 按钮变裸文字），
  补齐 bookmark/download/upload/list/graph 五个图标，并把 `loading` 改为既有的 `spin`
- 该审计已纳入 `check_all`（现为 **6 项**：架构守护 / 冒烟 236 / 版本一致性 /
  设计引用 / 类型检查 / 离线队列 15）

**验证**：后端冒烟 228 → **236 通过 0 失败**（+8 断言）；
`check_all` 六项全绿；颜色审计 171 未增；前端构建成功并已 `cap sync android`。

**已知未做**：P2 五项（FTS5 全文索引 / 自动上锁计时器 / 资讯收藏 /
多轮对话与冲突检测 / 离线队列冲突策略）——均为 PRD 标注的远期项。


### Added — 模块化深度开发 · mod-tools / F4.3 离线队列（2026-09-19）

**离线队列基础设施（弱网记待办不再丢）**
- `utils/offlineQueueCore.ts`：纯逻辑核心（FIFO 重放 / 失败重试计数 /
  上限停止 / 重试全部 / 清空失败 / 并发保护），存储与发送接口注入，
  可脱离浏览器单测
- `utils/offlineQueueIdb.ts`：IndexedDB 持久化（库
  `venustech_offline_queue` / 表 `queue` / 自增主键），App 重启不丢
- `stores/offlineQueue.ts`：Pinia store + online/offline 监听 + 事件广播
- `api/http.ts`：写操作拦截——离线或网络失败（含服务端不可达）时入队，
  抛 `OfflineQueuedError`（消息即"已离线，操作已加入同步队列"）；
  用注册钩子接入 store，避免 http ↔ store 循环依赖
- `components/layout/OfflineQueueIndicator.vue`：右上角数字角标
  （>99 显示 99+，失败转草莓红，同步中转 spinner）+ 底部抽屉面板
  （条目列表 / 重试全部 / 清空失败）
- 状态语义明确并写入注释：pending / retrying（>0 且 <3）/ failed（>=3）

**验证**：新增 `frontend/scripts/test-offline-queue.ts` **15 条行为测试**
（esbuild 转译 + node 执行），并纳入 `check_all` 第 5 步；
check_all 五项全绿（架构守护 / 冒烟 228 / 版本一致性 / 类型检查 / 队列测试）。

**已知边界**：冲突策略为"最后写入胜出"（PRD 列为 P2）；超时后重放可能重复，
真幂等需服务端 `X-Idempotency-Key`（后续）。


### Added — 模块化深度开发 · mod-platform（2026-09-18）

**P0 安全债（四条真实缺陷）**
- **密钥轮换不再丢数据**：`SecurityService.rotate_key` 先解密全部密文
  → 换 key → 用新密钥重加密写回；失败整体回滚。覆盖 vault_items 与
  settings 中的密文（原实现只换 key_file，历史密文全部作废）
- **加解密端点门禁**：`/security/encrypt|decrypt|key/rotate` 要求保险箱
  已解锁（此前任何能触达 API 的调用都可批量解密用户密钥）
- **同步删除传导**：`diff(propagate_deletes=)` 默认关闭；本地有而远端无
  → 落墓碑软删（保留 deleted_at）。对端未给出某张表时绝不删（防裁剪包
  误删本地数据）
- **禁止明文降级**：加密后端三级 —— DPAPI → Fernet（真加密）→ 仅 dev
  的 plain 占位 → 生产拒绝写入

**P0 回归修复（自查发现）**
- `init_encryption` 全项目无调用点 → `get_encryption()` 恒为 None，
  Fernet 回退形同虚设、生产保存 API Key 直接抛错。已在 lifespan 启动时
  统一初始化
- `decrypt_secret` 支持 `fernet:` 前缀，保留 `plain:` 历史兼容读取

**P1 基础设施**
- **插件权限真正执行**（F3.1）：白名单 network/db_read/files；未知权限拒绝
  加载（fail-closed）；exec/db_write/subprocess 声明即拒绝；
  `has_permission()` 运行时校验
- **同步冲突预览**（F2.4）：`SyncEngine.preview()` + `POST /sync/preview`
  —— 只算不改库，导入前可见 total/by_op/by_table/samples
- **安全审计日志**（F5.4）：新增 `audit_logs` 表（迁移 0019，幂等守卫）+
  14 种动作白名单 + 加解密/轮换埋点（成败均记）+ `GET /security/audit`；
  `audit()` 自身永不抛异常
- **插件错误隔离**（F3.4）：`safe_call()` 异常全捕获留痕 + 可超时
  （initialize 10s / shutdown 5s）；超时用非阻塞关闭避免 join 线程

**验证**：后端冒烟 150 → **168 通过 0 失败**（+18 断言）；架构守护与
vue-tsc 全绿。

**已知未做（按需再启）**：同步增量（F2.1，数据量小无痛点）、字段级
合并（O5）、配置双写统一（O4）、规则引擎可配置（O6）、备份自动化
（O7）、插件前端注册（O8）、设置搜索与变更历史（O9）

### Added — 三期 S6-3b/S6-6：同步引擎 / AI HOT 插件（2026-09-16）

**S6-3b diff-sync 引擎**（4f18dd3）
- `core/sync.py`：canon / snapshot / diff（LWW + 只增不删）/ apply；
  **SYNC_POLICY 四级表分级**（full / derived-skip / encrypted-only /
  filtered）第一天内置 —— workspace_files 不同步、vault 只同步密文
  材料、settings 排除设备键
- `/sync/export`（本地 JSON 包）/ `/sync/import`（包绑定 user_id）
- 验收（二期 W4 基准全落断言）：双库往返一致、二次 apply 零操作
- 诚实边界：无真正冲突解决，`resolve_conflict()` 预留

**S6-6 AI HOT 插件**（4c869d5）—— 插件架构第一次真实检验
- 加载器接活：内置插件随仓库分发（`app/plugins_builtin/`）+ 用户
  插件目录；`get_router()` 约定挂载 `/api/v1/plugins/{id}`；失败隔离
- AI HOT 信息源（aihot.virxact.com 匿名只读）：精选/热点/日报，
  base URL 硬编码防 SSRF、参数全白名单、离线降级读缓存
- `/aihot` 资讯页 + Dashboard 快速入口

### Added — 三期 S6-4/S6-5/C/D：经历视图 / 人生报告 / 工作区 / 保险箱（2026-09-16）

**S6-4 经历视图**（088eaa7 / 24d7938）
- `GET /experience` 四源（日记/复盘/分身记忆/项目记忆）按身份聚合 —— **不建经历表**
- `/experience` 时间线页：日期分组 + 来源标签 + 身份色点

**C 工作区**（300ca40 / 41b7ea8；设计修正见三期规划 §5.0）
- **可选功能 + 引导部署**：默认关闭零预设（workspace.enabled），目录结构由
  引导向导建立 —— 登记现有文件夹，或**按用户自己的身份生成目录骨架**
  （迁移组织原则，不迁移路径）
- 噪声过滤扫描（规则存 settings 可改；只存元数据不复制内容）、一键开终端
  （路径白名单唯一动作，resolve + is_relative_to 双重校验）
- 0016 迁移（workspace_roots / workspace_files）

**S6-5 人生报告**（12b253a / d15a455）
- `GET /report` 三轴聚合（身份×成长×档案）+ 近期经历
- `/report` 预览 + 单文件 HTML 导出（内联样式零依赖，数据归用户可存档带走）

**D 保险箱**（8ab58ab / 519b55b）
- **D0 安全修正**：`encryption.py` 移除硬编码全局 salt（随机 salt 显式传参，
  PBKDF2 200k，cryptography 升硬依赖）；顺带修 InvalidToken 未导入
- 主密码不落盘（随机 salt + 校验器，无哈希可爆破）；解锁态仅存进程内存
  （重启自动上锁）；凭据 secret 只存 Fernet token，明文唯一出口要求解锁态；
  换主密码全量重加密；凭据可挂身份
- 0017 迁移（vault_config / vault_items）

### Added — 三期 B：身份层（2026-09-16）

**横切分类轴**（总路线波次一，提交 f22c6b5 / 3a924b6 / c450cfa）
- 新增 `identities` 表 + 8 张业务表可空 `identity_id`（0015 迁移，幂等守卫）：
  tasks / projects / documents / diaries / reviews / avatar_memories / project_memories / inbox_items
- 身份 CRUD 五端点：上限 12 个、slug 唯一不可改、color_token 白名单（只收设计令牌名）、软删除（悬空引用读作「未归类」）
- 任务全链路支持身份：创建/编辑挂身份、列表按身份过滤 / 只看未归类（list 与 count 共用同一过滤器）
- 前端：身份管理页（/identities）+ `useIdentity` 全局组合式 + 任务列表身份筛选与新建/编辑选择
- 设计约束：identity_id **有意不加外键约束**（SQLite 重建表风险），归属校验收敛在服务层

### Added — A 计划：把已有能力接出来（2026-09-16）

**成长体系可视化**（补 W2 欠账）
- 新增 `views/Growth/GrowthView.vue`（路由 `/growth`）：等级进度 + EXP 流水 + 22 类技能树 + 升级规则说明
- 顶栏等级徽章由静态 `<div>` 改为可点击 `<button>`，跳转成长页
- 背景：S6-2 的 EXP / 等级 / 技能树自动归类早已跑通，但用户**看不到**，只有顶栏一个静态徽章

**系统与诊断面板**（四个后端模块终于有界面）
- 加密状态 / 日志 / 事件总线 / 插件四个模块路由一直存在且可用，前端却既无封装也无入口
- 新增 `api/system.ts` + 设置页「系统与诊断」面板，仅做接入，未新增后端能力

**用户配置 API**（`settings` 表从死表变为可用）
- 新增完整四层链路：`repositories/settings_repo.py` → `services/settings_service.py` → `api/settings.py`（GET / PUT `/api/v1/settings`）
- 支持 upsert（重复写入不撞 `(user_id, key)` 唯一约束）、键白名单（拒绝未登记键）、默认值合并
- `BaseSwitch` 新增 `change` 事件：此前只发 `update:modelValue`，消费方无法区分「用户点了」与「程序赋值」

### Fixed — start-demo.bat 起不来后端（2026-09-19）

- 现象：双击 `start-demo.bat` 窗口一闪而过并退出，报
  `ModuleNotFoundError: No module named 'app'`，前端自然看不到任何演示数据
- 根因：脚本在**仓库根目录**执行 `uvicorn app.main:app`，而 `app` 包只在 `backend\` 下；
  uvicorn 以 CWD 为 import 根，必然找不到
- 修复：后端改用 `start /D "%~dp0backend"` 启动（与 `start-dev.bat` 一致）；
  首次运行自动执行 `seed_demo.py --reset --yes`；同时拉起前端并打开浏览器；
  8765 / 5173 占用由「提示」升级为「拦截退出」
- 实测：identities 10 / projects 12 / tasks 57 / reviews 35，复习卡片有数据

### Fixed — 2026-09-16

**P1 · 设置页 4 个通知开关是假的**
- 现象：任务 / 复盘 / 系统 / 提示音四个开关只改前端 `ref()`，刷新即回默认值
- 根因：后端 `settings` 表（PRD §15.11）自一期建好后，没有 repository、没有 service、没有路由，从未被任何代码读写
- 修复：开关改为 `onMounted` 拉取、切换即落库，连点 300ms 内的切换合并为一次 PUT
- 验证：冒烟新增 5 条断言（58 → **63**），覆盖默认值 / 写入 / upsert 幂等 / 白名单拒绝 / 持久化重读

### 进行中
- 强AI能力扩展（任务自动拆解 / RAG知识问答 / 长文写作助手）
- 本地模型推理接入（Ollama / LM Studio）
- Electron 桌面端打包
- 插件生态深化

### Fixed — 调试与性能优化（2026-09-15）

**P0 · 全新数据库迁移崩溃**（新装用户无法启动）
- 根因：`0001_initial.py` 用 `Base.metadata.create_all()` 建的是"当前全部模型"（实测 39 张表），使 0009–0011 撞已存在的表
- 修复：为 `0009_workflow` / `0010_avatar` / `0011_pet` 补上与 0008 一致的幂等守卫（`_table_exists` / `_index_exists`）
- 验证：迁移 0001→0011 全程通过，冒烟测试 28/28 恢复全绿

**P0 · 架构守护测试长期失效**
- 根因：本机 venv 无 pytest（考校报告 E-01），`tests/test_architecture.py` 从未执行，已累积 **7 个文件违规**直接 import `app.models`
- 修复：7 个 api 文件（asset/avatar/learning/life/pet/resource/workflow）的模型导入移入 `if TYPE_CHECKING:`（测试内置的正式出口）；为 `test_architecture.py` 增加免 pytest 运行入口
- 验证：架构守护 2/5 → **5/5 全通过**

**P1 · 首页「今日执行」统计口径错误**
- 根因：`total = len(all_tasks)`（全部任务）、分组 count 亦不分日期，与同屏 `today_stats` 口径矛盾；且查询无 ORDER BY，取前 5 条为任意顺序，逾期任务可能被挤掉
- 修复：明确「今日要动手」口径（进行中/等待天然计入；待办仅今日到期或已逾期）；`total` = 各分组之和（自洽）；新增排序「已逾期 → 今日到期 → 无期限 → 未来到期」
- 验证：新增 4 条回归断言（修复前会失败）

### Performance — 2026-09-15
- **首页 SQL 27 → 19 条（-30%），服务层耗时 8.03 → 5.06 ms（-37%）**：把 10 处 `list_x(page=1, page_size=1)["total"]`（内部为 SELECT+COUNT 两条 SQL 并 hydrated 1 行）改为直连 Repository 的 `COUNT`；`len(list_domains())` 全量加载改为 `count()`
- `StringListType` 显式声明 `cache_ok = True`：SQLAlchemy 判定用 `__class__.__dict__`（type_api.py:1290）**不认继承**，导致含 `documents.tags` 的语句被判无缓存键并触发 SAWarning。消除告警并恢复语句缓存路径（诚实说明：简单查询上 A/B 未测出可测量提升，属正确性/卫生性修复）
- 索引实测无需优化：11 个关键查询全部走索引，34 张表有索引，无索引 5 张均为单行配置表

### Fixed — 遗留项清零 + 静默失效功能（2026-09-15 第二轮）

**四个「静默失效」的功能**（功能看似存在、实则永不生效且零日志）

| 编号 | 问题 | 实测 | 修复 |
|------|------|------|------|
| S-1 | 桌宠状态感知整体失效：① `list(status="todo")` 但合法状态只有 pending/in_progress/waiting/completed → `todo_count` 恒 0，「专注中」与待办气泡永不触发；② `getattr(mood,"mood")` 但 `MoodLog` 只有 `score` → 心情恒为「平静」 | 修后 todo_count=3 ✓ / 心情随 score 变化 ✓ | 任务感知改 `count_due_today_open()`；心情改按 `score(1-5)` 经 `MOOD_SCORE_MAP` 映射 |
| S-2 | 健康检查双重失效：`conn.execute("SELECT 1")` 传裸字符串在 SQLAlchemy 2.0 抛 `ObjectNotExecutableError` 被吞 → 库可连却报未连接；`settings.database_url` 属性不存在（实为 `db_url`）→ 库大小恒 0 MB | `connected` False→True ✓ / `size_mb` 0→0.62 MB ✓ | `text("SELECT 1")`；改用 `settings.db_path` |
| S-3 | AI Key 校验把所有异常吞成 `valid=False`，网络故障被报成「Key 无效」，用户会反复重填正确的 Key | — | 区分 401/403 与其他失败，记日志并回传原因；`ApiVerifyResult` 新增 `reason`（可加性） |
| S-4 | AI 客户端在「已配 Key 但解密失败」时静默退回 Mock，与"从未配置"无法区分 | — | 补 warning/exception 日志 |

**其他修复**
- `dashboard_service` 4 处 `except: pass` 静默降级为 `status="planned"` → 补 `logger.warning(exc_info=True)`。此前**模块真实报错会伪装成「功能未开发」，会在二期开发中掩盖 bug**；另补 `pet_service` 2 处、`plugin_manager`、`logs`、`health` 降级日志
- `/logs/clear` 部分文件清空失败由静默 skip 改为返回 `failed` 列表
- `0008_new_modules` 硬编码日志 `"... 15 tables created"` 改为按实际建表数输出（**实测全新库上建 0 张**，该假数字是 B-1 长期不可见的帮凶）
- **R-02 快速入口直达新建**：三个"新建"入口原先只跳列表页（点了"新建"却没新建）。现带 `?action=new`，新增通用 composable `useQueryAction` 由列表页消费后直接打开新建弹窗并清理参数

### Added — 二期限流伏笔与工具（2026-09-15）
- `app/migration_helpers.py`：迁移共享幂等守卫（`table_exists`/`index_exists`/`column_exists`/`create_index_if_missing`/`add_column_if_missing`）+ `migrations/script.py.mako` 模板默认引入并写明原因 → **B-1 复发防护**
- `scripts/check_all.py`：一键跑架构守护 + 后端冒烟 + 前端类型检查，**零第三方依赖**（本机 venv 无 pytest）→ 解决「测试写了却没跑」的根因（B-2）
- `backend/scripts/audit_sync_readiness.py`：逐表审计 `updated_at`/`deleted_at`。**基线：39 张表仅 7 张就绪，32 张需在 S6-3 前补齐**
- `scripts/audit_hardcoded_colors.py`：设计令牌合规审计 + `--max` 棘轮。**基线：171 处 / 16 文件 / 59 种色值**（其中仅 `#fff` 有对应令牌，其余 58 种不在令牌体系内，需设计决策）
- `scripts/dev.ps1` 新增 `-DataDir` 参数：分支可隔离数据库，避免新迁移污染主库

### Changed — 2026-09-15
- **`backend/data/app.db` 移出版本控制**（`git rm --cached`）。此前切分支会连数据库一起切、有丢数据风险；全新库现由「迁移 + 种子」可靠重建，这也让 B-1 类问题不再被掩盖
- 迁移幂等守卫统一收敛到 `app/migration_helpers.py`（原 7 个文件各自重复定义，且存在内联 / `IF NOT EXISTS` / 命名函数三种写法）
- `CONTRIBUTING.md`：新增「新迁移必须幂等」铁律、免 pytest 验证路径、设计令牌债务说明

### Added — 规划（2026-09-15）
- **新增二期阶段六：外部交付物内核融合**（PRD v2.0 §3 / §3.1），七项任务 S6-1~S6-7
  - S6-1 领域知识库 + 学习计划生成引擎（P0）—— 迁移 13 领域 / 52 能力单元 / 90 条带达标标准的任务
  - S6-2 成长体系：经验值 / 等级 / 技能树（P0-P1）—— 经 `event_bus` 订阅挂载，不改现有模块代码
  - S6-3 同步抽象层 + 本地适配器（P0）—— 为三期云同步铺路，本期不接云
  - S6-4 结构化经历 + 能力溯源（P1）—— 须先完成 Diary/Review/AvatarMemory/ProjectMemory 概念归并
  - S6-5 单文件 HTML 报告导出引擎（P2）
  - S6-6 AI HOT 信息源插件（P2）
  - S6-7 形象合成机制（P3，已降级）
- 归档两份评估文档：`docs/management/三交付物融合方案-2026-09-15.md`、`docs/management/地球Online内核融入效果评估-2026-09-15.md`

## [0.7.0] - 2026-09-07

### Added — 二期开发（4新模块 + 3大进化）

**二期PRD与架构**
- 完成二期PRD（1948行，约40页）：产品总纲 / 4大新模块 / 现有模块进化 / API设计 / 15张新表 / 非功能需求 / 插件生态 / 8个里程碑
- 二期架构四轮优化：分层架构补全（schemas/repositories/services）、TTL内存缓存、前端useDataCache、vite细粒度manualChunks、代码整洁
- 事件总线从18种扩展到28种事件类型

**一期考校维护**
- 考校评分85/100，修复5个问题：首页卡片拖拽ID重复、拖拽排序不生效、待开发模块灰度不生效、"提交成果"按钮无实际功能、后端config版本号未同步
- 产出《一期模块考校报告-2026-09-06.md》

**M7 资源中心（P0）**
- 收集箱CRUD + 处理流程（归档/删除/转任务/转文档）+ 批量处理
- 模板库CRUD + {{变量}}替换引擎 + 使用计数
- 领域库CRUD + 排序
- 后端16个API端点，前端三Tab页面

**M8 学习成长（P0）**
- SM-2间隔重复算法（EF更新公式、间隔序列1→6→15→38→95天）
- 3D翻卡复习交互 + 今日复习队列
- 学习计划CRUD + 学习时长统计 + 时间趋势
- 后端12个API端点，前端四Tab页面

**M9 生活记录（P0）**
- 习惯打卡（幂等 + 连续天数计算 + 月历视图）
- 心情记录（5档评分 + 分布统计 + 7天趋势）
- 四维日记（工作/学习/生活/成长）
- 后端15个API端点，前端三Tab页面

**M10 长期资产库（P0）**
- SOP流程（自动版本管理 + 版本历史）
- Prompt模板（四段式 + 变量替换 + 评分）
- Skill技能库CRUD
- 项目记忆CRUD
- 后端24个API端点，前端四Tab页面

**工作流模板系统（P1）**
- 3套预设工作流：数学学习 / 项目开发 / 小说写作
- 每套包含：模块组合 / 文件夹结构 / 标签体系 / 任务模板 / 文档模板 / SOP / 自动化规则
- 一键应用引擎：自动创建标签（领域库）+ 导入文档模板 + 创建初始任务 + 记录应用历史
- 后端8个API端点，前端工作流中心页面

**第二分身进化（P1）**
- 长期记忆系统：4类记忆（用户画像/知识记忆/事件记忆/关系记忆）+ 可信度标注 + 用户确认机制 + 统计面板
- 五档自动化：L1完全手动 / L2建议不执行 / L3低风险自动 / L4大部分自动 / L5完全自主
- 灵感工作流：模板化生成（4领域×4方向）→ 选择方向 → 自动生成详细提示词 → 执行 → 反馈优化
- 模型配置：云端（DeepSeek/OpenAI）+ 本地（Ollama/LM Studio）预留接口
- 人格设定：名称 / 设定词 / 回复长度 / 语言风格 / 创造力参数
- 后端16个API端点，前端第二分身设置页（三Tab）

**桌宠形象进化（P1）**
- Marvis式状态感知引擎：时间感知（7个时间段）+ 任务感知（待办提醒）+ 心情感知（读取最近心情）
- 本地TTS语音：浏览器SpeechSynthesis API + 语速/音调/音量调节 + 5种说话场景
- 自定义形象管理：多套形象切换 + 简单/进阶模式 + 形象卡片网格
- 显示设置：大小/透明度/置顶/自启/拖拽/点击互动/右键菜单
- 后端10个API端点，前端桌宠设置页（四Tab）

### Changed
- 首页4个新模块卡片从占位数据改为真实数据库数据，status从planned改为ready
- 快速入口新增工作流/第二分身/桌宠设置3个入口，收集箱从planned改为ready
- 首页快速入口从5个扩展到8个
- 后端数据库连接优化：NullPool + WAL + busy_timeout=5000 + cache_size=20MB

### Fixed
- 首页模块显示"待开发"但实际已开发完成的体验问题
- 收集箱快速入口跳转路径错误
- 心情均分无数据时显示0.0而非"暂无记录"

### 数据模型扩展
- 新增10张表：inbox_items / templates / domains / study_plans / flashcards / study_time_logs / habits / habit_checkins / mood_logs / diaries / sops / sop_versions / prompt_templates / skills / project_memories / workflows / workflow_applications / avatar_memories / avatar_inspirations / avatar_configs / pet_configs / pet_avatars
- 迁移版本：0008 → 0011

## [0.2.0] - 2026-09-06

### Added — 9 模块深度开发完成（分支合并至 main）

- **M01 首页 Dashboard**：本周进度环（SVG 环形图）、连续打卡徽章（火焰+天数）、卡片拖拽排序（HTML5 拖拽 + localStorage 持久化）
- **M02 任务 Task**：任务模板系统（5 内置模板 + 自定义保存）、任务依赖关系（前置任务 ID 列表 + 阻塞状态计算）
- **M03 知识 Document**：双向链接、文档导出补全、模板系统、版本 diff、文档关系图谱（后端 /documents/graph/data API + 前端 SVG 力导向图）
- **M04 第二分身 Conversation**：8 内置提示词模板 + 搜索 + / 快捷触发、6 套预设人设切换、多模型切换（DeepSeek/GPT/Claude/Ollama）、用户画像沉淀（4 类特质标签 + 模拟文档分析）、主动提醒系统（定时检查即将到期任务 + 桌宠事件触发提醒气泡）
- **M05 复盘 Review**：热力日历（月度打卡心情着色）、情绪趋势（近 14 天心情/精力双折线 SVG）、复盘模板系统（日/周/月/项目 4 类型）、复盘导出 Markdown（单条/批量）、年度复盘报告（年度数据聚合 + 里程碑 + 高频标签 + Markdown 导出）
- **M06 项目 Project**：项目详情页（672 行 5 Tab）、进度统计、里程碑 CRUD、归档/恢复、项目模板、项目内快速添加、项目时间线（timeline() 聚合）、项目导出（export() 返回 JSON + 前端 JSZip 打包）
- **M07 桌宠 Pet**：动作系统从 6 扩展到 12 种、桌宠/人形双形态切换（带旋转动画）、右键菜单（8 动作 + 形态切换）、双击快速切换、二次元人形 SVG、配置持久化、四维度状态系统（亲密度/饱食度/心情/精力随时间衰减）、互动系统（喂食/抚摸/玩耍/休息）、状态条实时显示、自定义形象配置（5 套预设 + 主色/辅色/眼色可配置）
- **M08 设置 Settings**：史诗典藏主题（亮色传说 + 暗色暗夜双模式）、四套主题完整对齐、桌宠设置面板（开关/默认形态/互动/透明度）、通知设置（任务/复盘/系统/提示音）、数据目录显示与打开、高级设置（动画开关/字体缩放 80-130%/性能模式/自动保存）、快捷键参考面板（8 组）、数据清理（缓存/临时文件/旧备份）、关于页增强（可展开更新日志 v0.1.70-v0.2.0）
- **M09 基础设施 Infrastructure**：健康检查增强（系统信息/数据库状态/磁盘使用/路径）、事件总线增强（异步事件 / 18 种事件类型 / 历史 500 条 / 统计 API）、events API（统计/历史/类型/清空/测试）、system/info 端点、插件系统基础架构（PluginManager 发现/加载/启用禁用/热重载 + plugin.json 元数据规范 + PluginContext 注入 API）、加密存储模块（Fernet AES-128-CBC + HMAC + PBKDF2 密钥派生 + 文件加密解密 + 密钥轮换 + 缺库优雅降级）、plugins API、security API、日志查看 API（日志文件列表/内容读取支持 tail 行数和级别过滤/清空/路径遍历安全防护）

### Changed
- UI 组件画廊 V3.0：四套主题（奶油糖果/国风雅集/深渊档案/史诗典藏）深度对齐，每套 52 组件
- 史诗典藏主题改为明亮传说史诗感，暗色仅作为暗夜模式
- 首页布局严格对齐参考 UI：顶部水平导航 + 主页面板跳转子页面，主页面板固定不下拉

### Fixed
- 合并后 SCSS 嵌套语法错误（ConversationView/ReviewView/SettingsView/ProjectDetailView/DesktopPet 多处 &__ 选择器在顶层使用）
- HTML 重复 class 属性（SettingsView/DesktopPet）
- DocumentEditor 类型错误（wikiResults 缺少 project_id 字段）
- 首页模块跳转问题：收集箱 404、待开发模块跳转到不相关页面、项目卡片应跳详情页

## [0.1.0] - 2026-09-04

### Added — 一期工程 100%（评估见 docs/management/一期工程进度评估-2026-09-04.md）

- **设计沉淀**：PRD v1.0 / 需求分析 / 技术架构 v2.0（后端/前端各多轮优化）/ UI 设计规范 / 交互设计 / UI 组件画廊（95 组件，三套主题变体）
- **后端骨架**：FastAPI + SQLAlchemy 2.0 + SQLite(WAL/StaticPool) + Alembic（迁移 0001-0004）+ pydantic-settings + loguru + AES 加密
  - 分层 pi → services → repositories → models，统一响应/异常/日志；14 张表（用户/任务/子任务/文档/版本/反链/文件夹/对话/消息/复盘/待办/提醒/通知/设置/项目）
  - 事件总线 + 订阅者（文档保存→AI 摘要/标签，任务完成→通知）
  - AI 服务抽象（DeepSeek httpx 客户端，指数退避重试）+ Mock 降级
  - 全模块路由：auth/task/document/folder/conversation/review/dashboard/backup/panel/notification/project
  - 演示种子（大量：任务/文档/复盘/对话/待办/提醒/通知）
- **前端工程**：Vue 3 + TS 严格 + Vite + Pinia + Router(Hash) + Element Plus 按需
  - 三栏布局（左信息面板 + 顶导航 + 主内容）；16 基础组件 + 7 布局组件 + 桌宠组件
  - 9 API 模块 + 14 composables + 8 视图（Dashboard/Task/Document/Conversation/Review/Project/Settings）
  - 全局搜索(⌘K)/命令面板/快捷键/通知(30s 轮询)/主题(三套)/备份/API Key 配置
- **功能模块**：任务（列表/看板/子任务/状态机/今日最重要）、知识（文件夹/编辑器/自动保存/标签/搜索/AI 摘要）、第二分身（SSE/5 思维模式/引用文档/灵感/本地降级）、复盘（自动填充/评分/AI 反思/转任务）、项目管理（/projects）
- **桌宠**：SVG 二次元形象、6 动作、拖拽、气泡、任务完成庆祝联动
- **工程化**：后端 pytest（架构守护 + 冒烟，12 项通过）、前端 vue-tsc 零错误、生产构建成功、一键启动脚本（bat + ps1）

### Changed
- 项目迁移至 D:\YanYuas\PersonalDevelopmentPortfolio\VenustechSystem，对接 GitHub 远程 origin
- 补齐 README（项目简介/技术栈/目录/快速开始/文档索引）
- 清理仓库根目录散落的开发修复脚本与误生成文件

### Fixed
- Windows 日志中文乱码（stdout/stderr UTF-8 reconfigure）
- Alembic path_separator 警告
- 迁移后 README/CHANGELOG 骨架化（本次补全）