# Changelog

本项目所有重要变更都记录在此文件。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

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