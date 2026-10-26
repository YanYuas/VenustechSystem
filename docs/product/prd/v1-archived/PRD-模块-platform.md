# PRD · mod-platform 系统底座模块

> 模块代号：mod-platform
> 模块名称：系统底座（Platform Foundation）
> 所属系统：Venustech System · 启明星
> 文档版本：v1.0
> 日期：2026-09-18
> 状态：模块化深度优化阶段 · 待评审
> 读者：后端工程师、前端工程师、架构评审

---

## 一、模块定位与目标

### 1.1 一句话定位

mod-platform 是启明星系统的**跨模块基础设施层**，承载设置管理、同步引擎、插件框架、规则引擎、安全加密、事件总线、备份恢复与构建部署八类横切能力。**任何跨模块改动先落这里，再向业务模块下发**——它是六维导航（首页/执行/知识/人生/资产/伙伴）之下的"地基"，不直接对用户产出业务价值，但所有业务模块的可靠性、可扩展性、安全性都由它兜底。

### 1.2 模块边界

| 方向 | 范围 | 不包含 |
|------|------|--------|
| 前端视图 | `frontend/src/views/Settings/SettingsView.vue` 设置页 | 业务模块各自的视图 |
| 后端核心 | `core/sync.py` `core/plugin_manager.py` `core/encryption.py` `core/security.py` `core/event_bus.py` | 业务 service |
| 后端 API | `api/settings.py` `api/sync.py` `api/plugins.py` `api/security.py` `api/backup.py` | 业务 API 路由 |
| 规则引擎 | `services/rules/`（domain_engine / domain_lib / skill_cats） | AI 对话与摘要服务 |
| 设计令牌 | `frontend/src/styles/variables.scss` | 组件内部样式 |
| 导航定义 | `frontend/src/constants/dimensions.ts` | 具体业务路由页 |

### 1.3 核心目标

1. **可靠性**：同步引擎从"能导出"升级为"可信赖的多端数据一致性"，备份恢复可验证、可自动调度。
2. **扩展性**：插件框架从"能加载 py 文件"升级为"有权限边界、有生命周期、可挂载前后端"的正式扩展点。
3. **安全性**：加密密钥管理、敏感信息存储、审计日志形成闭环，消除 `plain:` 降级路径的安全债。
4. **可配置性**：规则引擎从硬编码常量升级为"内置库 + 用户自定义层"双层结构，不重启即可生效。
5. **可观测性**：事件总线、同步任务、插件加载、安全操作四类后台行为在设置页有可见面板，不再"黑盒运行"。

### 1.4 非目标（本期不做）

- 不实现真正的云端同步服务端（仅抽象云适配器契约，服务端属四期）。
- 不实现插件市场分发与签名校验（仅本地插件目录扫描）。
- 不实现多用户协作与权限体系（当前为单用户本地优先架构）。
- 不重写业务模块的 UI，仅在设置页暴露已存在的后端能力。

---

## 二、现状盘点（基于代码确认）

### 2.1 已实现功能清单

#### 2.1.1 同步引擎（`core/sync.py`）

| 能力 | 现状 | 代码位置 |
|------|------|----------|
| 同步流水线 | canon → snapshot → diff → apply 四阶段 | `SyncEngine.snapshot/diff/apply` |
| 表分级策略 | `SyncPolicy` 四档：full / derived-skip / encrypted-only / filtered | `SYNC_POLICY` 注册表 |
| 派生表跳过 | `workspace_files` 标记 derived-skip，不进同步包 | `SYNC_POLICY["workspace_files"]` |
| 加密列白名单 | `vault_items` / `vault_config` 只同步密文材料列，明文 `notes` 剥除 | `ENCRYPTED_ONLY_COLUMNS` |
| 设备配置过滤 | `settings` 表中 `workspace.*` 前缀键整行不跨机同步 | `SETTINGS_EXCLUDED_PREFIXES` |
| 冲突解决 | LWW（`updated_at` 大者胜，相同本地胜），`resolve_conflict()` 预留接口 | `_newer / resolve_conflict` |
| 同步方向 | **只增不删**：远端没有的行不动本地；三态（remote-only 插入 / both 远端新更新 / both 本地新跳过） | `diff()` |
| 本地适配器 | 导出 JSON 同步包到目录，文件名 `qimingxing-sync-{stamp}.json` | `export_to / load_package` |
| 包校验 | `version == SYNC_PACKAGE_VERSION(=1)`、文件 ≤ 50MB、`user_id` 匹配 | `load_package / import_` |
| 应用事务 | upsert = 删旧行 + 插新行，单事务 commit | `apply()` |
| API | `GET /policy` `GET /packages`（倒序前 20） `POST /export` `POST /import` | `api/sync.py` |

**已知诚实边界（代码注释原文）**：算法本质是 LWW + 只增不删，**无真正的冲突解决**；远端删除不会传导到本地；每次全量 snapshot，无增量。

#### 2.1.2 插件框架（`core/plugin_manager.py`）

| 能力 | 现状 |
|------|------|
| 元数据 | `plugin.json` 声明 id/name/version/author/description/enabled/entry_point/permissions/metadata |
| 发现 | 扫描 `{data_dir}/plugins/` 下含 `plugin.json` 的子目录 |
| 加载 | `importlib.util.spec_from_file_location` 动态加载 entry_point（默认 `main.py`） |
| 生命周期 | 加载后调 `module.initialize(context)`；卸载前调 `module.shutdown()`（失败仅 warning 不阻断） |
| 上下文注入 | `PluginContext` 注入 event_bus / config / data_dir / logger |
| 路由挂载 | 插件模块约定 `get_router()` 返回 `APIRouter`，宿主收集后挂载 |
| 启停 | `set_enabled(id, bool)` 联动 load/unload |
| 状态 | `get_status()` 返回 total/enabled/loaded 计数与插件列表 |
| API | `GET /plugins` `POST /{id}/enable|disable|reload` `POST /discover` |

**已知缺口**：`permissions` 字段被读取但**未被强制执行**；无沙箱；插件异常仅 logger.exception，不隔离；无前端注册机制；无插件级日志通道。

#### 2.1.3 加密安全（`core/encryption.py` + `core/security.py`）

| 能力 | 现状 |
|------|------|
| 算法 | Fernet = AES-128-CBC + HMAC-SHA256 |
| 密钥派生 | PBKDF2-HMAC-SHA256，200,000 迭代，随机 16 字节 salt |
| 密钥文件 | `.encryption_key` 与 `.encryption_key.salt`，`os.chmod 0o600`（Windows 静默忽略） |
| 数据接口 | `encrypt / decrypt / encrypt_json / decrypt_json / encrypt_file / decrypt_file` |
| 密钥轮换 | `rotate_key()` **当前仅替换 key_file，不重加密已有密文**（已知缺口） |
| API Key 保护 | `security.py` 用 Windows DPAPI 加密；未装 pywin32 时降级为 `plain:` + base64 占位 |
| API | `GET /security/status` `POST /security/encrypt|decrypt` `POST /security/key/rotate` |

**已知安全债**：`plain:` 降级仅注释 `TODO(D07)`，未强制；`/security/encrypt` 与 `/security/decrypt` 路由未挂 `get_current_user` 鉴权；`rotate_key()` 不重加密历史数据，调用后旧密文全部不可解。

#### 2.1.4 事件总线（`core/event_bus.py`）

| 能力 | 现状 |
|------|------|
| 事件常量 | 32 个命名事件（task/document/review/inspiration/project/conversation/pet/backup/system + 二期 12 个） |
| 同步订阅 | `subscribe(event, handler)` 直接调用 |
| 异步订阅 | `subscribe_async(event, coro)` 入事件循环 `create_task`；无 loop 时降级 `asyncio.run` |
| 历史 | `deque(maxlen=500)` 内存环形缓冲，`EventRecord` 记录 handlers 调用数与成败 |
| 统计 | 按事件聚合 count/success/failed；列出活跃订阅数 |
| API | 前端通过 `systemApi.eventStats()` 消费（设置页"事件总线"面板） |

**已知缺口**：类属性可变状态（多实例共享但无锁）；历史仅内存，重启丢失；无死信队列；单个 handler 抛异常只 log，不影响后续 handler（已正确），但统计粒度是"整事件成败"，无法定位单个 handler。

#### 2.1.5 设置管理（`api/settings.py` + 前端 SettingsView）

| 能力 | 现状 |
|------|------|
| 后端 | `GET /api/v1/settings` 读全部（含默认值）；`PUT /api/v1/settings` 批量写 |
| 通知设置 | 前端 4 开关（task/review/system/sound），300ms 连点合并为一次 PUT |
| 昵称 | 800ms 防抖 PATCH |
| 外观 | 4 主题包（cream/guofeng/abyss/epic）× 3 模式（light/dark/system） |
| AI 配置 | API Key 验证后保存；自动化等级 L1–L5 |
| 高级设置 | 动画/字体缩放 80–130%/性能模式/自动保存，存 localStorage |
| 桌宠 | enabled/form/interaction/opacity，存 localStorage |

#### 2.1.6 备份恢复（`api/backup.py`）

| 能力 | 现状 |
|------|------|
| 导出 | `POST /backup/export` 返回路径 |
| 导入 | `POST /backup/import` 接收 zip（≤100MB），同步函数（线程池）避免阻塞事件循环 |
| 统计 | `GET /data/stats` 返回 documents/tasks/tags/conversations 计数 |
| 前端 | 导出 toast 路径；导入后提示"重启生效" |

#### 2.1.7 规则引擎（`services/rules/`）

| 能力 | 现状 |
|------|------|
| 领域库 | 13 领域 / 52 能力单元 / 90 条带达标标准的任务，frozen dataclass 常量 |
| 技能分类 | 22 分类 / 164 关键词（`skill_cats.py`） |
| 计划生成 | `generate_study_plan(goal, total_days, minutes_per_day)` 纯函数，离线可用 |
| 日/周模式 | ≤45 天按天排；>45 天按周排（每周 5 任务） |
| 移植对齐 | `js_round` 对齐 JS Math.round；正则 `count=1` 对齐 JS replace 无 g 标志 |
| 时长归一 | `parse_duration_minutes` 把"约 3 小时"等文本解析为分钟整数 |
| 验证任务 | 末尾强制追加一条"真实成品记录"作为技能点亮凭证 |

**已知缺口**：全部硬编码在 `.py` 常量，用户不可扩展、不可热更新；无调试面板；无自定义规则入口。

### 2.2 设计令牌现状（`variables.scss`）

四套 UI 主题各含亮/暗变体，共 8 套 `[data-theme]`：

| 主题包 | data-theme 值 | 主色语义 |
|--------|---------------|----------|
| 奶油糖果 | `""`(cream 亮) / `dark`(可可夜) | `--primary` 启明粉 |
| 国风雅集 | `guofeng` / `guofeng-dark` | `--primary` 朱砂红 |
| 深渊档案 | `abyss`(默认暗) / `abyss-light`(碧涛) | `--primary` 磷火青 |
| 史诗典藏 | `epic` / `epic-dark` | `--primary` 星尘金 |

令牌分七类：基础色 / 语义衍生 ink / 功能派生 soft / 字体 / 字号阶梯（xs–2xl）/ 圆角（sm–xl + pill）/ 投影 / 间距（space-1..10）/ 缓动（ease-spring、ease-soft）/ 控件尺寸基线。

---

## 三、深度优化方向（P0/P1/P2 优先级分级）

### 3.1 优先级定义

| 级别 | 含义 | 上线门槛 |
|------|------|----------|
| P0 | 阻塞性 / 安全债 / 数据可靠性 | 本迭代必须完成，否则不发版 |
| P1 | 核心体验缺口，用户可感知 | 本迭代尽量完成，可带降级 |
| P2 | 增强与打磨，不阻塞主流程 | 排入下个迭代 |

### 3.2 优化方向总表

| 编号 | 方向 | 优先级 | 对应功能点 | 现状痛点 |
|------|------|--------|-----------|----------|
| O1 | 安全加固：强制 DPAPI、鉴权补全、审计日志 | **P0** | F5.1–F5.4 | `plain:` 降级在裸奔；encrypt/decrypt 无鉴权；rotate_key 丢数据 |
| O2 | 同步引擎可靠性：增量、删除传导、冲突预览 | **P0** | F2.1–F2.4 | 只增不删导致远端删除永不生效；全量 snapshot 慢；无预览直接 apply |
| O3 | 插件权限与错误隔离 | **P0** | F3.1 / F3.4 | permissions 读了不 enforce；插件抛异常拖垮宿主 |
| O4 | 跨模块基础设施：事件可观测、配置统一、构建 | **P1** | F1.1–F1.4 | 事件统计只展示不告警；localStorage 与 settings 表双写不一致 |
| O5 | 同步冲突解决升级为字段级合并 | **P1** | F2.2 | 行级 LWW 会整行覆盖，丢失其他字段更新 |
| O6 | 规则引擎可配置：用户自定义领域 | **P1** | F4.1–F4.3 | 长尾技能只能走 generic_units 四阶段模板 |
| O7 | 备份自动化与完整性校验 | **P1** | F7.1–F7.2 | 无自动备份；导入不校验 zip 完整性 |
| O8 | 插件前端注册与市场雏形 | **P2** | F3.3 | 插件只能加后端路由，无法注入前端 UI |
| O9 | 设置页搜索与变更历史 | **P2** | F6.1–F6.2 | 设置项增多后无查找；无回滚 |
| O10 | 云适配器契约定稿 | **P2** | F2.5 | 预留接口但未冻结契约 |

---

## 四、功能需求详细拆解

### F1 跨模块基础设施优化

#### F1.1 设计令牌统一治理

**功能描述**：以 `frontend/src/styles/variables.scss` 为唯一视觉来源，建立"令牌使用零 hex 硬编码"的硬约束。新增业务模块时，所有颜色、圆角、阴影、动效必须引用既有令牌，不得在组件内写 hex 值。

**规则与边界**：
- 允许的令牌分类：基础色（`--bg-*` `--text-*` `--line`）、语义色（`--primary` `--mint` `--butter` `--sky` `--lilac` `--strawberry` `--gold` 及其 `-ink` `-soft` 衍生）、几何（`--radius-*` `--shadow-*`）、间距（`--space-*`）、动效（`--ease-*`）、字体（`--font-*` `--text-*`）。
- 禁止：组件 `.vue` / `.scss` 内 grep `#[0-9a-fA-F]{3,6}` 非零命中（SettingsView 现状中 `&.theme-cream` 等预览渐变属一次性视觉稿，需迁移为令牌组合或接受例外登记）。
- 新增令牌需在本 PRD 附录登记用途，不得私自在组件文件内 `:root` 覆盖。

**验收标准**：
- [ ] 全库 `frontend/src/**/*.vue` 与 `frontend/src/**/*.scss` 中，除 `variables.scss` 与例外登记文件外，`#[0-9a-fA-F]{6}` 正则 grep 零命中
- [ ] 四套主题包切换时，设置页所有卡片、按钮、开关、滑块、toast 颜色同步切换，无肉眼可见的"主题漏色"
- [ ] 暗模式（`dark` / `guofeng-dark` / `abyss` / `epic-dark`）下，文字对比度满足 WCAG AA（正文对比度 ≥ 4.5:1）
- [ ] 新增令牌需在本 PRD 附录 A 登记，PR 模板含"是否新增令牌"勾选

**交互细节**：
- 主题包切换时，整页颜色过渡 200ms `var(--ease-soft)`，避免硬切闪烁
- 主题卡片选中态：边框 `2px solid var(--primary)` + `box-shadow: var(--glow)`，过渡 200ms
- 主题预览色块高 48px、圆角 `var(--radius-sm)`，4 列 grid，gap `var(--space-3)`

**状态全覆盖**：
- 默认态：4 张主题卡片按当前 pack 高亮
- 加载态：主题切换瞬间全局 100ms 淡入
- 错误态：`[data-theme]` 未命中时回退 `:root` 奶油日，并在 console 打 warning，不白屏

---

#### F1.2 事件总线可观测性升级

**功能描述**：在现有 `EventBus` 内存历史（deque 500）与统计基础上，补充：①失败 handler 定位；②阈值告警；③事件订阅关系可视化。设置页"事件总线"面板从"只读计数"升级为"可诊断"。

**规则与边界**：
- 历史窗口保持 500 条内存，不落盘（避免 SQLite 膨胀）
- 单事件失败率 > 30%（滑动窗口 1 分钟）时，前端事件面板该事件行标 `--strawberry` 色
- 订阅关系：启动时 dump `event → [handler 模块名]` 清单到 `GET /system/events/subscriptions`

**验收标准**：
- [ ] 单条事件历史记录中能区分"哪个 handler 失败"，而非仅整事件成败
- [ ] `get_stats()` 返回 `by_event[event].failed_handlers: list[str]`
- [ ] 设置页事件面板按 count 降序排列，失败数 > 0 的行左侧 3px `--strawberry` 色条
- [ ] 连续 5 次 publish 同一事件全部失败时，toast 提示"事件 {event} 持续失败，请检查插件或服务"
- [ ] 清空历史按钮（已有）保留，二次确认后清 deque，不影响订阅

**交互细节**：
- 事件行 hover 时背景 `var(--primary-soft)`，左移 2px
- 点击某事件行展开最近 10 条 EventRecord 时间线（200ms 展开动画）
- 失败数徽标：圆角 `var(--radius-pill)`、背景 `--straw-soft`、文字 `--straw-ink`、字号 `--text-xs`

**状态全覆盖**：
- 默认态：按 count 降序列表，最多显示 30 行
- 空状态：暂无事件记录（系统刚启动）
- 加载态：面板展开时 200ms 骨架行（3 行 shimmer）
- 错误态：`GET /system/events/stats` 失败时显示"事件统计不可用"+ 重试按钮

---

#### F1.3 配置中心统一

**功能描述**：现状存在三类配置存储——后端 `settings` 表（通知）、`localStorage`（桌宠/高级设置）、`user_config` 接口（昵称/Key/自动化等级）。本期将"应跨机同步"的配置统一收敛到后端 `settings` 表，仅保留"设备相关"键在 localStorage（由 `SYNC_POLICY.FILTERED` 排除）。

**规则与边界**：
- 收敛清单：动画开关、字体缩放、性能模式、自动保存、桌宠 enabled/form/interaction/opacity —— 这些是**用户偏好**，应跨机同步
- 保留 localStorage：`workspace.*` 前缀（窗口坐标、设备分辨率、本地路径），由 `SETTINGS_EXCLUDED_PREFIXES` 过滤
- 迁移策略：首次启动检测到 localStorage 旧键，一次性写入 settings 表，随后 localStorage 仅作缓存

**验收标准**：
- [ ] 上表 8 项偏好读写均走 `GET/PUT /api/v1/settings`
- [ ] `workspace.*` 键不进入同步包（导出后 grep JSON 无 `workspace.` 前缀）
- [ ] 旧 localStorage 键在首次启动时自动迁移，迁移后 toast 一次"已同步你的偏好"
- [ ] 切换设备后导入同步包，8 项偏好与源机一致

**交互细节**：
- 滑块（字体缩放 80–130%、步长 5、灵感概率 0–100）拖动时不连续请求，松手 300ms 后 PUT
- 开关切换立即 PUT（不等防抖），失败时回滚 UI 状态并 toast `--strawberry` 色

**状态全覆盖**：
- 默认态：从 settings 表读取后渲染
- 空状态：新用户首次进入，8 项均为代码默认值
- 加载态：`GET /settings` 未返回时，开关显示 skeleton 条（高 `--row-h` 的 60%）
- 错误态：PUT 失败时该开关回到旧值，toast"保存失败，已还原"

---

#### F1.4 构建与部署流程优化

**功能描述**：固化前端 Vite 构建 + 后端 FastAPI 打包 + Capacitor 7 Android 壳的三段流水线，输出可复现的构建命令与产物清单。

**规则与边界**：
- 前端：`npm run build` 产出 `dist/`，Capacitor 同步到 `android/app/src/main/assets/public`
- 后端：`pip install -e .` + Alembic 迁移，数据目录由 `config.data_dir` 决定
- Android 壳：Capacitor 7 仅包 WebView，不内嵌 Python 后端（后端跑在用户电脑，App 壳通过 `apiBase` 连接）
- 产物哈希：每次构建输出 `build-manifest.json`（前端 hash、后端 git commit、schema version）

**验收标准**：
- [ ] `npm run build` 产物首屏 JS gzip ≤ 200KB（dev 除外）
- [ ] 后端启动时执行 `alembic upgrade head` 幂等，不重复执行报错
- [ ] Capacitor 同步后 Android 壳可独立启动，未配置 apiBase 时显示"连接电脑服务"引导页
- [ ] `build-manifest.json` 包含 `frontend_hash / backend_commit / schema_version / built_at` 四字段

**交互细节**：
- 构建失败时 CI 日志高亮报错行，本地 `npm run build` 失败在终端红色输出
- Android 启动页（splash）保持 500ms 后淡入主 WebView，避免白屏闪烁

**状态全覆盖**：
- 默认态：正常构建产物
- 失败态：构建命令非零退出，产物目录不生成半成品
- 版本不一致态：`schema_version` 与代码预期不符时，启动 banner 警告"数据库结构过旧，请迁移"

---

### F2 同步引擎可靠性提升

#### F2.1 增量同步与断点续传

**功能描述**：现状 `snapshot()` 每次全量扫描所有可同步表。本期引入 `synced_at` 水位线，只导出自上次同步后 `updated_at > watermark` 的行；同步包支持分段（单包 > 10MB 时分片），导入支持断点续传。

**规则与边界**：
- 水位线存储：`sync_state` 表（见第六章数据模型），每用户每方向（push/pull）一条
- 分片：导出端按 10MB 切分 `qimingxing-sync-{stamp}.part-N.json`，含 `manifest.json` 记录总分片数
- 断点续传：导入端记录已完成分片序号，中断后从下一片继续
- 删除传导：新增 `tombstone` 列表（`{table, id, deleted_at}`），远端软删除行会在导入时标记本地 `deleted_at`，不再"只增不删"

**验收标准**：
- [ ] 连续两次导出，第二次导出包体积 ≤ 第一次的 10%（无变化时）
- [ ] 单包 > 10MB 时自动分片，`manifest.json` 含 `parts: N, size_each: ~10MB`
- [ ] 导入中断（模拟 kill 进程）后重新导入，已应用分片不重复执行
- [ ] 远端软删除一行后，本地导入该行 `deleted_at` 被置位（不物理删除）
- [ ] `SYNC_POLICY` 注册表不变；`derived-skip` 表仍不进包

**交互细节**：
- 设置页"导出同步包"按钮在数据量 > 5MB 时显示预计耗时提示（"约 3 秒"）
- 导入进度条：0–100%，每 5% 更新一次，已应用行数计数
- 导出完成 toast 显示文件大小（KB/MB 自适应）

**状态全覆盖**：
- 默认态：上次同步时间显示为"今天 14:30"或"3 天前"
- 空状态：从未同步过时显示"尚未同步"
- 加载态：导出中按钮 loading 态，禁用重复点击
- 错误态：目录不可写时 toast"导出失败：目录不可写"；版本不兼容时 toast"同步包版本过旧，请导出新包"

---

#### F2.2 冲突解决升级为字段级合并

**功能描述**：现状 `_newer` 行级 LWW 会整行覆盖。本期升级为字段级：同 ID 行双方都改了不同字段时，取各方最新字段合并；仅当同一字段双方都改时，才对该字段 LWW。

**规则与边界**：
- 字段级 merge 输入：local_row / remote_row / 双方各自的 `field_updated_at`（需新增列或在 sync 包内携带 per-field 时间戳）
- 本期为兼容旧包：sync 包 version 升到 2，v1 包降级为行级 LWW 并提示
- 合并结果不可确定性时（同字段同时改且时间戳相同），保留本地值并记入冲突日志

**验收标准**：
- [ ] A 机改 `title`、B 机改 `description`，合并后两处修改都保留
- [ ] A、B 同时改 `title` 且时间戳相同，本地胜，写入 `conflict_log` 表
- [ ] v1 同步包（无 per-field 时间戳）导入时回退行级 LWW，不报错
- [ ] `SYNC_PACKAGE_VERSION` 升至 2，`load_package` 接受 1 与 2

**交互细节**：
- 导入完成 toast 增加"合并 N 处 / 冲突 M 处"
- 冲突条目在设置页"同步历史"中可查看（P1 面板，见 F2.3）

**状态全覆盖**：
- 默认态：无冲突时正常合并
- 冲突态：导入完成后 toast 黄色"有 M 处字段冲突已保留本地版"
- 错误态：合并代码抛异常时整体回滚事务（apply 已是单事务，回滚不脏库）

---

#### F2.3 同步冲突预览

**功能描述**：导入同步包前，先 dry-run 展示将要应用的 ops 列表（插入/更新/冲突各几条），用户确认后再 apply。

**规则与边界**：
- 新增 `POST /sync/preview` 接口：返回 ops 摘要 + 前 20 条明细（表名、ID、op 类型、字段 diff）
- 用户在前端抽屉中勾选"我已知悉"后，前端再调 `POST /sync/import`
- 预览结果 60 秒内有效，过期需重新预览

**验收标准**：
- [ ] 预览接口返回 `{ops_count, insert_count, update_count, conflict_count, samples: [..20]}`
- [ ] 明细行显示：表名（中文友好，如"任务"）、ID 前 8 位、op 标签（`--mint` 插入 / `--sky` 更新 / `--butter` 冲突）
- [ ] 用户未确认前不写库
- [ ] 超大包（ops > 500）预览仅展示摘要 + 前 20 条，其余折叠

**交互细节**：
- 预览抽屉从右侧滑入，宽 480px，300ms `var(--ease-spring)`
- op 标签为 `var(--radius-pill)` 小胶囊，字号 `--text-xs`
- 底部固定操作栏："取消"（secondary）+ "应用 N 处变更"（primary）

**状态全覆盖**：
- 默认态：摘要 + 样本列表
- 空态：ops=0 时显示"没有需要应用的变化"，按钮置灰
- 加载态：预览中 skeleton 3 行
- 错误态：同步包损坏时 toast 红色，不展开抽屉

---

#### F2.4 同步包加密

**功能描述**：现状导出的 JSON 同步包是明文，包含任务、日记、复盘等全部用户数据。本期用 `EncryptionManager` 对同步包整体加密，导出时要求用户设置同步密码（与主密钥独立）。

**规则与边界**：
- 导出：`POST /sync/export` 新增可选 `password` 字段；传了则用 Fernet 加密 payload 后写入 `.enc` 文件
- 导入：`POST /sync/import` 检测到 `.enc` 后缀时要求 password，解密失败报"密码错误"
- 密码不存储、不落盘；用户需自行保管
- v1 明文包仍可导入（向后兼容），但导出默认加密

**验收标准**：
- [ ] 加密后的同步包用文本编辑器打开不可见明文任务内容
- [ ] 错误密码导入返回 400"密码错误或包已损坏"
- [ ] 正确密码导入后数据与导出时一致
- [ ] 未传 password 时导出明文包，但前端提示"建议设置密码"

**交互细节**：
- 设置密码弹窗：两次输入（密码 + 确认），强度条（弱/中/强，基于长度与字符集）
- 导入加密包时弹出密码输入框，3 次失败锁定 60 秒（防暴力）

**状态全覆盖**：
- 默认态：明文导出可用
- 加密态：导出后 toast"已加密，请妥善保管同步密码"
- 错误态：密码错误提示；包损坏提示"文件不完整或版本不符"

---

#### F2.5 云适配器契约（预留）

**功能描述**：定义云适配器接口协议，本期不实现服务端，但本地适配器与未来云适配器实现同一契约，保证引擎零改动切换。

**规则与边界**：
- 契约：`class SyncAdapter(Protocol): def export(self, payload) -> str / def fetch(self) -> dict`
- 本地文件适配器已实现；未来 WebDAV / S3 / 官方云均实现该 Protocol
- 配置项 `sync.adapter = "local" | "webdav" | "official"`，存在 settings 表

**验收标准**：
- [ ] `SyncAdapter` 为 `typing.Protocol`，本地适配器显式声明实现
- [ ] 切换 adapter 配置后，`SyncEngine` 实例化逻辑不变
- [ ] 未实现的 adapter 配置值启动时报错"不支持的同步适配器"

---

### F3 插件框架扩展性

#### F3.1 插件权限声明与沙箱边界

**功能描述**：现状 `plugin.json` 的 `permissions` 字段被读取但未 enforce。本期定义权限清单与运行时校验，插件请求越权能力时被拒绝。

**规则与边界**：
- 权限清单（v1）：
  - `event:subscribe` 订阅事件总线
  - `event:publish` 发布事件
  - `route:mount` 挂载后端路由
  - `fs:data_dir:read` 读 data_dir
  - `fs:data_dir:write` 写 data_dir
  - `net:outbound` 出站网络请求
- 插件 `initialize(context)` 收到的 `PluginContext` 按权限裁剪：未声明 `fs:data_dir:write` 时 `data_dir` 只读包装
- 权限不足时插件 `initialize` 抛 `PermissionError`，加载标记 failed

**验收标准**：
- [ ] 未声明 `route:mount` 的插件调用 `context.mount_router()` 时抛 `PermissionError`
- [ ] 设置页插件详情展示已声明权限列表（中文友好，如"挂载路由 / 读写数据目录"）
- [ ] 插件加载失败时，`get_status()` 中该插件 `loaded: false, error: str`
- [ ] 新权限加入时需在本 PRD 登记，插件 `plugin.json` 不在清单内的权限被忽略并 warning

**交互细节**：
- 插件列表中，failed 插件行左侧 3px `--strawberry` 色条
- 点击插件名展开详情抽屉：名称、版本、作者、描述、权限清单、加载错误（如有）

**状态全覆盖**：
- 默认态：插件正常加载，开关可切换
- 禁用态：开关 off，不加载，灰色
- 失败态：开关 on 但加载失败，行显示"加载失败：{error}"，提供"重试"按钮
- 空态：plugins 目录为空时显示"暂无插件 —— 把插件文件夹放进 plugins 目录"

---

#### F3.2 插件生命周期钩子规范

**功能描述**：固化插件生命周期约定，宿主在关键节点调用插件钩子，插件可选择性实现。

**规则与边界**：
| 钩子 | 调用时机 | 必须 | 说明 |
|------|----------|------|------|
| `initialize(context)` | 加载成功后 | 是 | 注入 PluginContext |
| `shutdown()` | 卸载/禁用前 | 否 | 清理资源 |
| `on_enable()` | 被启用后 | 否 | 恢复运行态 |
| `on_disable()` | 被禁用前 | 否 | 暂停定时器/连接 |
| `health_check()` | 宿主周期探测（30s） | 否 | 返回 `{healthy: bool, detail: str}` |

- 钩子抛异常不阻断宿主，仅 logger.warning 并记录
- `on_disable` 失败不阻止禁用（资源泄漏由 shutdown 兜底）

**验收标准**：
- [ ] 上述 5 个钩子在 `plugin_manager.py` 中均有调用点
- [ ] 插件不实现可选钩子不报错（`hasattr` 检查）
- [ ] `health_check` 连续 3 次失败时，设置页插件状态变红，并提示"插件可能卡死"

**交互细节**：
- 健康检查失败的插件行，状态点从 `--mint` 灰化为 `--strawberry`，600ms 过渡

**状态全覆盖**：
- 健康态：绿点
- 不健康态：红点 + tooltip 显示 detail
- 未实现钩子：灰点"未上报"

---

#### F3.3 插件前端注册机制（P2）

**功能描述**：允许插件向前端注入 UI 扩展点（导航 tab、设置页区块、右键菜单项）。本期定义注册协议，不做市场。

**规则与边界**：
- 插件在 `plugin.json` 中声明 `frontend: {"nav_tabs": [...], "settings_sections": [...]}`
- 后端启动时聚合所有插件的前端声明，通过 `GET /plugins/manifest` 下发
- 前端启动时拉取 manifest，动态注册路由与设置页区块
- 插件前端包需打包为 ESM 单文件，放插件目录 `frontend/index.js`

**验收标准**：
- [ ] `GET /plugins/manifest` 返回聚合后的前端声明
- [ ] 无插件时 manifest 为空对象，前端不报错
- [ ] 插件前端 JS 加载失败时仅该扩展点不渲染，不白屏

**交互细节**：
- 动态注册的导航 tab 与内置 tab 视觉一致（复用 `DimensionTab` 结构）
- 加载失败的扩展点在设置页显示"插件 XX 的前端模块加载失败"，不阻断其他区块

---

#### F3.4 插件错误隔离

**功能描述**：插件代码抛异常、死循环、内存泄漏时不拖垮宿主。本期为每个插件加载建立隔离边界。

**规则与边界**：
- 插件 `initialize` 超时（5 秒）视为加载失败，不继续调用
- 插件订阅的事件 handler 抛异常时，仅该 handler 失败，其他 handler 继续（现状已满足）
- 插件路由 `/plugins/{pid}/*` 统一前缀，插件抛 HTTP 异常时由宿主 exception handler 包装为 500，不泄露堆栈
- 不做真沙箱进程隔离（Python 单进程限制），靠约定与日志兜底

**验收标准**：
- [ ] `initialize` 阻塞 > 5s 时，`load()` 返回 False 并记录 timeout
- [ ] 插件路由抛异常，响应体不含本地路径、变量名等敏感信息
- [ ] 插件日志写入独立文件 `logs/plugin-{pid}.log`，便于排查

---

### F4 规则引擎可配置性

#### F4.1 领域库热加载与用户扩展层

**功能描述**：现状 `DOMAIN_LIB` 是 Python 常量，改一个领域要改代码重启。本期引入用户扩展层：`data_dir/rules/domains/*.json`，启动时加载并与内置库合并，运行中可热重载。

**规则与边界**：
- 内置库（13 领域）只读，用户不可改
- 用户扩展 JSON schema：`{key, name, patterns[], verify_task, units[{name, tasks[{task, duration, acceptance, repeatable}]}]}`
- 合并顺序：内置库优先匹配（`match_domain` 先遍历内置，再遍历用户扩展）
- 热重载：`POST /rules/reload` 重新扫描用户目录，无需重启

**验收标准**：
- [ ] 用户在 `domains/` 放一个合法 JSON 后，`list_domains()` 返回 14+ 领域
- [ ] 不合法 JSON 被跳过，logger.warning 指出文件名与原因
- [ ] 用户领域的 patterns 与内置领域冲突时，内置优先，日志提示
- [ ] 热重载接口 200 返回新领域数量

**交互细节**：
- 设置页"规则引擎"区块显示内置领域数与用户扩展数
- 用户扩展行右侧"编辑/删除"按钮（打开文件管理器，不在应用内编辑）

**状态全覆盖**：
- 默认态：仅内置库
- 扩展态：显示用户领域标签
- 错误态：JSON 解析失败显示"文件 X 格式错误，已跳过"

---

#### F4.2 自定义技能分类扩展

**功能描述**：`skill_cats.py` 22 分类硬编码。本期同样允许用户在 `data_dir/rules/skill_cats/*.json` 追加分类。

**验收标准**：
- [ ] 用户追加分类后，技能自动归类命中新分类
- [ ] 内置 22 分类不可删除、不可覆盖
- [ ] 重复 id 的用户分类被忽略并 warning

---

#### F4.3 规则引擎调试面板

**功能描述**：设置页新增"规则引擎"折叠区，提供目标输入框，实时预览 `match_domain` 命中结果与 `generate_study_plan` 前 5 条计划。

**规则与边界**：
- 输入框 placeholder："例如：我想学雅思，30 天"
- 实时预览：输入停止 400ms 后调用 `POST /rules/preview`
- 仅调试，不落库

**验收标准**：
- [ ] 输入"我想学 Python"命中 `programming` 领域，显示领域名与匹配的 pattern
- [ ] 输入"随便学点啥"走 generic_units 兜底，显示"未命中领域库，使用通用拆解"
- [ ] 预览结果展示前 5 条 PlanItem（Day N 标题 + 任务 + 时长）

**交互细节**：
- 预览结果淡入 200ms
- 命中领域名用 `--primary-ink` 色；未命中用 `--butter-ink` 色提示兜底

**状态全覆盖**：
- 默认态：空输入，占位提示
- 命中态：绿色标签显示领域名
- 兜底态：黄色标签显示"通用拆解"
- 错误态：生成异常显示"计划生成失败"，不影响主流程

---

### F5 安全加固

#### F5.1 加密密钥管理升级

**功能描述**：修复现状 `rotate_key()` 只换 key_file、不重加密历史数据的缺陷。本期实现真正的密钥轮换：用旧密钥解密所有用新密钥加密。

**规则与边界**：
- 轮换流程：
  1. 生成新 key（或基于新密码派生）
  2. 遍历所有加密存储位置（vault_items.secret_encrypted、加密文件、settings 中加密值）
  3. 旧 key 解密 → 新 key 加密 → 写回
  4. 全部成功后替换 key_file；任一步失败则回滚 key_file，保留旧数据
- 旧 key 立即失效（现状已满足，补"重加密"这一步）

**验收标准**：
- [ ] 轮换后，轮换前用旧 key 加密的密文可被新 key 解密（因为已重加密）
- [ ] 重加密过程中断（模拟 kill），重启后旧数据仍可解（key_file 未换）
- [ ] 重加密期间不允许其他写操作（进程内锁）
- [ ] 设置页"轮换密钥"按钮增加二次确认："轮换后旧备份文件将无法解密，请先导出备份"

**交互细节**：
- 重加密进度条：按记录数百分比，禁用其他安全操作
- 完成后 toast"密钥已轮换，N 条数据已重加密"

**状态全覆盖**：
- 默认态：密钥正常
- 轮换中：进度条 + 禁用按钮
- 失败态：toast 红色"轮换失败，已回滚"
- 未初始化态：加密不可用时按钮置灰

---

#### F5.2 安全审计日志

**功能描述**：对安全敏感操作持久化审计日志，设置页"安全审计"面板可查看。

**规则与边界**：
- 审计事件：
  - `security.key.rotated` 密钥轮换
  - `security.vault.unlocked` 保险箱解锁
  - `security.vault.locked` 保险箱锁定
  - `security.encrypt.success / security.decrypt.success / security.decrypt.failed`
  - `security.plugin.enabled / security.plugin.disabled`
  - `settings.sensitive_changed` API Key 等敏感设置变更
- 存储：`audit_log` 表（见第六章），不落文件
- 保留：默认保留 90 天，可在设置中清理
- 每条记录：`timestamp / event / actor / detail / ip_or_device`

**验收标准**：
- [ ] 上述 7 类事件均有记录
- [ ] 审计日志不可通过 API 删除单条，只能"清空全部"
- [ ] 设置页审计面板按时间倒序，分页每页 50 条
- [ ] 解密失败记录 detail 含失败原因（不包含密文本身）

**交互细节**：
- 失败事件行左侧 3px `--strawberry` 色条
- 事件名用 `--font-mono`，时间用 `--text-xs` `--text-low`
- 过滤下拉：全部 / 成功 / 失败

**状态全覆盖**：
- 默认态：按时间倒序列表
- 空态："暂无审计记录"
- 加载态：5 行骨架
- 错误态：查询失败显示重试

---

#### F5.3 敏感 API 鉴权补全

**功能描述**：现状 `/security/encrypt`、`/security/decrypt`、`/security/key/rotate` 未挂 `get_current_user`。本期补全，并增加频率限制。

**规则与边界**：
- 三个路由全部 Depends `get_current_user`
- 解密接口频率限制：每分钟 30 次（防暴力调用）
- encrypt/decrypt 接口仅用于业务模块内部调用，前端设置页不直接暴露裸 encrypt/decrypt 表单

**验收标准**：
- [ ] 无 token 调用 `/security/encrypt` 返回 401
- [ ] 超过 30 次/分钟返回 429
- [ ] 设置页不再直接调用裸 encrypt/decrypt（仅 status 与 key/rotate）

---

#### F5.4 DPAPI 强制与降级告警

**功能描述**：现状未装 pywin32 时降级为 `plain:` + base64，注释标 `TODO(D07)`。本期：非 Windows 平台或 DPAPI 不可用时，启动 banner 明确告警"API Key 以非加密方式存储，请勿在共享设备使用"。

**规则与边界**：
- Windows 上未装 pywin32：启动时 warning，设置页"安全"区块显示黄色警告条
- 非 Windows（macOS/Linux）：使用 keyring 或文件权限降级，不再用 base64
- `plain:` 前缀的密文在设置页标记"弱加密"，一键升级按钮（重新加密为 DPAPI/keyring）

**验收标准**：
- [ ] DPAPI 不可用时，启动日志含明确 warning
- [ ] 设置页安全面板显示"当前 API Key 保护方式：弱加密（base64）"
- [ ] "升级"按钮点击后，所有 `plain:` 密文重新加密为 `dpapi:` 或 keyring
- [ ] 升级后无 `plain:` 前缀残留

---

### F6 设置管理（前端体验）

#### F6.1 设置项搜索

**功能描述**：设置页卡片已达 10 张（外观/AI/第二分身/桌宠/通知/高级/快捷键/数据清理/数据管理/系统与诊断/关于）。本期顶部增加搜索框，输入关键字过滤可见卡片与卡片内字段。

**规则与边界**：
- 搜索范围：卡片标题 + 卡片内所有 label 文字
- 搜索匹配：包含即命中，大小写不敏感
- 空搜索时展示全部卡片

**验收标准**：
- [ ] 输入"主题"仅显示"外观"卡片
- [ ] 输入"备份"显示"数据管理"卡片
- [ ] 无命中时显示"没有找到相关设置"

**交互细节**：
- 搜索框高 `--control-h`，圆角 `--radius-pill`，右侧清除按钮
- 过滤时卡片淡出 150ms 再淡入，不跳动布局
- 快捷键 Ctrl+, 聚焦搜索框（设置页内）

**状态全覆盖**：
- 默认态：空搜索，全部卡片
- 过滤态：仅命中卡片
- 空结果态：居中提示 + 清除搜索按钮
- 加载态：不影响（纯前端过滤）

---

#### F6.2 设置变更历史

**功能描述**：记录用户设置变更，支持查看与回滚到某版本。

**规则与边界**：
- 每次 PUT /settings 写入一条 `settings_history` 记录（时间、变更 key、旧值、新值）
- 保留最近 200 条
- 回滚：选择某条记录，将该 key 恢复为旧值（单 key 回滚，不批量）

**验收标准**：
- [ ] 修改通知开关后，历史中出现一条记录
- [ ] 点击"恢复"后该设置回到旧值
- [ ] 敏感值（api_key）在历史中脱敏显示为 `sk-***`

**交互细节**：
- 历史列表时间用相对时间，hover 显示绝对时间
- 恢复按钮二次确认

---

### F7 备份与恢复

#### F7.1 自动备份策略

**功能描述**：现状备份需用户手动点"导出备份"。本期增加自动备份：按日/按周/按月三档，保留最近 N 份。

**规则与边界**：
- 配置项：`backup.auto_enabled`（默认关）、`backup.interval`（daily/weekly/monthly）、`backup.keep`（默认 5）
- 触发时机：应用启动时检查距上次备份时间，超过间隔则自动导出
- 备份路径：`{data_dir}/backups/`，文件名 `venustech-backup-{stamp}.zip`
- 超出 keep 数量时自动删除最旧备份

**验收标准**：
- [ ] 开启日备份后，次日启动自动生成一份 zip
- [ ] keep=5 时，第 6 份备份生成后自动删除最旧
- [ ] 自动备份失败不阻断启动，仅 warning

**交互细节**：
- 设置页"数据管理"卡片新增自动备份开关与下拉
- 最近一次备份时间显示在卡片内
- 手动导出按钮与自动备份共用导出逻辑

**状态全覆盖**：
- 默认态：自动备份关闭
- 开启态：显示间隔与保留份数
- 失败态：自动备份失败 toast 黄色提示，不阻塞

---

#### F7.2 备份完整性校验

**功能描述**：导入 zip 前校验完整性（magic number、CRC、文件清单），避免损坏备份导致覆盖。

**规则与边界**：
- 导出时在 zip 内写入 `MANIFEST.json`（文件清单 + SHA256 + 导出时间 + user_id）
- 导入时先读 MANIFEST，校验每个文件 SHA256，任一不匹配则拒绝导入
- 校验失败返回"备份文件不完整或已损坏"

**验收标准**：
- [ ] 手动修改 zip 内任一文件后导入，被拒绝
- [ ] 正常备份导入成功
- [ ] 跨用户备份（MANIFEST.user_id 不匹配）拒绝

---

## 五、移动端适配需求（375px 宽度）

### 5.1 适配原则

- 移动端通过 Capacitor 7 壳访问同源 Web 页面，宽度基准 375px（iPhone SE）
- 设置页 `max-width: 720px` 在 375px 下占满宽度，左右 padding 从 `--space-5`(20px) 降为 `--space-4`(16px)
- 所有卡片纵向堆叠，grid 从 4 列降为 2 列（主题包、数据统计）

### 5.2 关键适配点

| 组件 | 桌面端 | 移动端 375px |
|------|--------|--------------|
| 主题包 grid | 4 列 | 2 列，预览色块高 40px |
| 数据统计 grid | 4 列 | 2 列，数字字号 `--text-lg` 替代 `--text-xl` |
| 操作按钮行 | 横向 flex 不换行 | 纵向堆叠或允许换行，按钮全宽 |
| 抽屉（同步预览/插件详情） | 右侧 480px | 底部弹出 bottom-sheet，高度 70vh |
| 日志内容 `<pre>` | max-height 280px 滚动 | 高度 240px，字号 11px 不变 |
| 快捷键 kbd | min-width 100px | 自适应宽度，允许换行 |
| 搜索框 | 顶部居中 max 480px | 通栏 |
| 底部操作栏（预览抽屉） | 固定底部 | 贴底 + safe-area-inset-bottom 34px |

### 5.3 触控与手势

- 所有可点击区域最小高 `--control-h`(40px)，桌面端按钮不缩到 `--control-h-sm`(32px) 以下
- 开关、滑块触控热区扩大 8px（伪元素 padding 扩展，不影响视觉尺寸）
- 抽屉下拉关闭：bottom-sheet 支持向下拖动 100px 触发关闭，跟随手指 200ms 回弹动画
- 刷新手势：事件面板、日志列表支持下拉刷新（移动端），桌面端保留刷新按钮

### 5.4 移动端状态差异

- 服务器地址/访问令牌区块：移动端默认折叠（App 壳才需要），桌面端展开
- 备份导入：移动端调起系统文件选择器，不展示"已选择：xxx.zip"长文件名（截断显示）
- 键盘弹出：输入框聚焦时页面不自动滚动到视口中心，仅滚动到可见即可（避免遮挡按钮）

---

## 六、数据模型与 API 补充

### 6.1 新增数据表

#### 6.1.1 `sync_state`（同步水位线）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID PK | |
| user_id | String INDEX | 所属用户 |
| direction | Enum | push / pull |
| watermark | DateTime | 上次成功同步的最大 updated_at |
| last_package_version | Int | 上次同步包版本 |
| updated_at | DateTime | |

#### 6.1.2 `conflict_log`（冲突记录）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID PK | |
| user_id | String INDEX | |
| table | String | 表名 |
| row_id | String | 行 ID |
| field | String | 冲突字段 |
| local_value | Text | 本地值（脱敏） |
| remote_value | Text | 远端值（脱敏） |
| resolved_as | Enum | local / remote / merged |
| created_at | DateTime | |

#### 6.1.3 `audit_log`（安全审计）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID PK | |
| user_id | String INDEX | |
| event | String INDEX | 审计事件名 |
| detail | Text | JSON 详情（不含敏感值原文） |
| actor | String | 操作来源（web / app / desktop） |
| created_at | DateTime | |

#### 6.1.4 `settings_history`（设置变更历史）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID PK | |
| user_id | String INDEX | |
| key | String | 配置键 |
| old_value | Text | 旧值（敏感键脱敏） |
| new_value | Text | 新值（敏感键脱敏） |
| created_at | DateTime | |

### 6.2 新增/变更 API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/sync/preview` | 导入前 dry-run 预览 |
| POST | `/api/v1/sync/export` | 增加可选 `password` 字段（加密导出） |
| POST | `/api/v1/sync/import` | 增加可选 `password` 字段；支持分片目录 |
| GET | `/api/v1/system/events/subscriptions` | 事件订阅关系 |
| GET | `/api/v1/audit/logs?limit=&offset=` | 审计日志分页 |
| POST | `/api/v1/audit/clear` | 清空审计日志（二次确认） |
| GET | `/api/v1/rules/domains` | 内置 + 用户领域合并清单 |
| POST | `/api/v1/rules/preview` | 调试面板实时预览 |
| POST | `/api/v1/rules/reload` | 热重载用户规则 |
| GET | `/api/v1/plugins/manifest` | 插件前端注册聚合 |
| GET/PUT | `/api/v1/settings/history` | 变更历史与回滚 |
| POST | `/api/v1/backup/auto` | 配置自动备份策略 |

### 6.3 既有 API 变更

- `POST /security/encrypt` `/decrypt` `/key/rotate`：补 `Depends(get_current_user)`
- `GET /sync/policy`：返回值不变，但前端据此渲染分级说明
- `GET /plugins`：返回结构增加 `error` 字段（加载失败原因）

---

## 七、用户故事

### 故事一：多端数据同步（学生 · 桌面 + Android 壳）

> **作为** 一名学生，我在台式机上记录了今天的任务与日记，希望在 Android 手机上看到同样的数据。
>
> **触发**：用户在桌面端设置页点"导出同步包"，设置密码后得到一个加密 JSON 文件；通过网盘/AirDrop 传到手机；在手机端设置页"同步包列表"选择该文件，输入密码。
>
> **期望**：导入前看到预览（"将插入 12 条任务、更新 3 条日记"），确认后 3 秒完成；手机端任务列表立即出现今天的任务；手机端删除一条任务后，下次回桌面端导入时该任务也被标记删除。
>
> **验收**：F2.1 增量、F2.3 预览、F2.4 加密、F2.2 字段合并全部可用。

### 故事二：密钥泄露应急（开发者）

> **作为** 一名开发者，我怀疑我的主密钥可能泄露，需要立即轮换。
>
> **触发**：设置页 → 系统与诊断 → 加密存储 → 轮换密钥。
>
> **期望**：点击后二次确认"轮换前请先导出备份"；确认后进度条显示"N 条数据已重加密"；完成后旧备份文件用旧密钥无法打开（因为数据已用新密钥重加密）；审计日志留下一条 `security.key.rotated` 记录。
>
> **验收**：F5.1 真轮换、F5.2 审计、F7.1 自动备份配合。

### 故事三：安装第三方插件（高级用户）

> **作为** 一名高级用户，我从社区下载了一个"番茄钟"插件，想在启明星里用。
>
> **触发**：把插件文件夹（含 `plugin.json` 与 `main.py`）放进 `{data_dir}/plugins/pomodoro/`，在设置页"插件"区块点"扫描插件"。
>
> **期望**：扫描后出现"番茄钟 v1.0.0"；点开详情看到它声明的权限（"订阅事件 / 挂载路由 / 读写数据目录"）；打开开关后插件加载，通知栏出现番茄钟通知；禁用开关后插件卸载，定时器停止；插件代码有 bug 时不影响其他功能，设置页显示"加载失败：xxx"。
>
> **验收**：F3.1 权限、F3.2 生命周期、F3.4 错误隔离。

### 故事四：自定义学习领域（自由职业者）

> **作为** 一名自由职业者，我想学"Blender 建模"，但内置 13 个领域没有这个方向。
>
> **触发**：在 `{data_dir}/rules/domains/blender.json` 写入自己的领域定义（patterns 匹配 blender/建模/C4D，units 写 4 个能力单元）；在设置页"规则引擎"点"热重载"。
>
> **期望**：在 AI 助理处输入"我想学 Blender，30 天"，系统命中用户自定义领域，生成的计划来自 Blender.json 而非通用四阶段模板；调试面板输入同样目标能实时预览命中结果。
>
> **验收**：F4.1 热加载、F4.3 调试面板。

### 故事五：安全审计回溯（企业用户）

> **作为** 一名重视数据安全的用户，我想知道上周谁（哪个设备）改过我的 API Key。
>
> **触发**：设置页 → 安全 → 审计日志，过滤"敏感设置变更"。
>
> **期望**：看到一条 `settings.sensitive_changed` 记录，时间、设备来源（desktop/android）、字段名（api_key），值脱敏为 `sk-***`；点击"详情"看到旧值/新值均脱敏；3 个月前的记录因保留策略被自动清理。
>
> **验收**：F5.2 审计日志、F6.2 设置历史脱敏。

### 故事六：手机端设置调整（通勤中）

> **作为** 一名通勤用户，我在地铁上用 Android 壳想关掉"提示音"。
>
> **触发**：手机端打开设置页，宽度 375px。
>
> **期望**：主题包 2 列网格不挤；通知开关大触控热区；切换后 300ms 内自动保存；底部 bottom-sheet 风格的同步预览可下拉关闭；键盘弹出时"确认导入"按钮不被遮挡。
>
> **验收**：第五章全部移动端适配点。

---

## 八、验收标准（模块级）

### 8.1 功能完整性

- [ ] 第二章"已实现功能清单"中所有现状能力在本版本不回退（回归测试）
- [ ] 第三章 P0 方向（O1/O2/O3）100% 完成
- [ ] P1 方向（O4/O5/O6/O7）完成 ≥ 80%
- [ ] P2 方向至少启动 F2.5 与 F6.1

### 8.2 数据可靠性

- [ ] 同步导入 1000 行数据，事务失败时回滚率 100%（无半写状态）
- [ ] 密钥轮换中断后，重启应用旧数据仍可解密
- [ ] 备份导入 SHA256 校验失败时拒绝导入，不污染现有数据
- [ ] 软删除通过同步包跨端传导，不物理删库

### 8.3 安全性

- [ ] 全库 grep `plain:` 前缀，非 Windows 降级路径有明确告警
- [ ] `/security/encrypt` `/decrypt` `/key/rotate` 无 token 返回 401
- [ ] 审计日志中不出现 API Key 原文、保险箱 secret 原文
- [ ] 插件未声明权限时越权调用抛 PermissionError

### 8.4 性能与可观测

- [ ] 全量 snapshot 在 10000 行数据下 < 500ms
- [ ] 增量同步第二次导出包体积 < 首次 10%
- [ ] 事件总线单 handler 异常不影响其他 handler（现有）+ 不影响主请求（既有）
- [ ] 设置页首屏加载 < 800ms（含诊断面板懒加载）

### 8.5 移动端

- [ ] 375px 宽度下设置页无横向滚动条
- [ ] 触控热区不小于 40×40px
- [ ] 底部 bottom-sheet 下拉关闭手势可用
- [ ] Android 壳冷启动到设置页可交互 < 2s（含后端连接）

---

## 九、风险与依赖

### 9.1 技术风险

| 风险 | 影响 | 缓解 |
|------|------|------|
| 密钥轮换重加密在大数据量下耗时长 | 用户误以为卡死 | 进度条 + 后台线程 + 取消按钮（取消即放弃，不换 key） |
| 字段级 merge 需要 per-field 时间戳，老数据无此列 | 历史行无法字段级合并 | 老数据降级为行级 LWW，仅对新数据生效 |
| 插件沙箱在 Python 单进程内无法真隔离 | 插件死循环仍会卡住宿主 | P0 只做超时与异常隔离；真沙箱列 P2 外部进程方案 |
| 同步包加密后用户忘记密码 | 数据无法导入 | 导出时强提示"密码即钥匙，丢失不可恢复"；不做密码找回 |
| DPAPI 跨机器不可用 | Windows 之间也需重输 | 文档说明 DPAPI 绑定当前用户；跨机用同步密码加密通道 |

### 9.2 依赖关系

- F2.2 字段级 merge 依赖 F2.1 增量同步的 `sync_state` 表
- F5.1 真轮换依赖 F7.2 备份完整性校验（轮换前先备份）
- F3.3 前端插件注册依赖 F3.1 权限声明
- F4.1 用户领域热加载依赖 settings 表统一配置（F1.3）
- 移动端 bottom-sheet 组件需在 `components/common/` 新建，本 PRD 只提需求，组件本身归前端基础设施 PRD

### 9.3 不做与边界声明

- 本期不实现服务端云同步（仅本地文件适配器 + 契约）
- 本期不做插件签名校验与插件市场
- 本期不改业务模块（任务/文档/复盘）的任何表结构
- 本期不引入新的 UI 框架，所有新组件基于现有 BaseCard/BaseButton/BaseSwitch 自研体系
- 设计令牌不新增（除非 F1.1 评审后批准）

---

## 附录 A：令牌使用约定（摘要）

本 PRD 中所有颜色描述均引用 `frontend/src/styles/variables.scss` 中的令牌：

- 主操作 / 选中态：`--primary` + `--on-primary`
- 成功 / 在线：`--mint` + `--mint-soft` + `--mint-ink`
- 警告 / 进行中：`--butter` + `--butter-soft` + `--butter-ink`
- 信息：`--sky` + `--sky-soft` + `--sky-ink`
- 危险 / 删除 / 错误：`--strawberry` + `--straw-soft` + `--straw-ink`
- 文字三级：`--text-hi`（标题）/ `--text-mid`（正文）/ `--text-low`（辅助）
- 背景四级：`--bg-cream`（页面）/ `--bg-panel`（卡片）/ `--bg-raised`（浮层）/ `--bg-inset`（内嵌）
- 分隔线：`--line`
- 动效时长：本 PRD 出现的 150/200/300/500ms 均为建议值，最终以组件实现为准；缓动统一 `--ease-soft` 或 `--ease-spring`

---

## 附录 B：既有代码索引

| 文件 | 行数规模 | 本 PRD 引用点 |
|------|----------|---------------|
| `backend/app/core/sync.py` | 248 | F2 全部 |
| `backend/app/core/plugin_manager.py` | 220 | F3 全部 |
| `backend/app/core/encryption.py` | 177 | F5.1 / F2.4 |
| `backend/app/core/security.py` | 37 | F5.4 |
| `backend/app/core/event_bus.py` | 177 | F1.2 |
| `backend/app/api/settings.py` | 41 | F1.3 / F6 |
| `backend/app/api/sync.py` | 82 | F2 全部 |
| `backend/app/api/plugins.py` | 46 | F3 全部 |
| `backend/app/api/security.py` | 62 | F5.3 |
| `backend/app/api/backup.py` | 47 | F7 全部 |
| `backend/app/services/rules/domain_engine.py` | 639 | F4 全部 |
| `backend/app/services/rules/domain_lib.py` | ~840 | F4.1 内置库 |
| `backend/app/services/rules/skill_cats.py` | 155 | F4.2 |
| `frontend/src/views/Settings/SettingsView.vue` | 1339 | F6 / 移动端 |
| `frontend/src/styles/variables.scss` | 524 | F1.1 / 全文令牌 |
| `frontend/src/constants/dimensions.ts` | 138 | 导航归属（/settings 属 companion 维度） |

---

> 本文档为 mod-platform 模块深度优化阶段的 PRD，所有功能描述均基于仓库现有代码确认。
> 评审通过后，按 P0 → P1 → P2 顺序进入迭代排期。
