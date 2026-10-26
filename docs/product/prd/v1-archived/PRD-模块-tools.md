# PRD-模块-tools：工具箱模块（mod-tools）深度优化需求文档

> 所属系统：Venustech System（启明星）
> 模块：工具箱维度（mod-tools）—— 工作区管理 + 加密保险箱 + AI 资讯热榜 + AI 行程助理
> 文档版本：v1.0（模块化深度优化阶段）
> 日期：2026-09-18
> 读者：前端开发、后端开发、测试、产品
> 技术栈：Vue3 + TS 严格 + Vite + Pinia + SCSS（无 UI 框架）；FastAPI + SQLAlchemy 2.0 + SQLite(WAL) + Alembic
> 移动端：Capacitor 7 + Android 壳，375px 宽度适配
> 设计令牌唯一来源：`frontend/src/styles/variables.scss`（本文所有颜色/间距/圆角均引用令牌名，不写 hex）

---

## 1. 模块定位与目标

### 1.1 模块定位

工具箱是启明星个人操作系统的「辅助工具集合层」，位于六维导航体系中的工具维度。它不承担主流程闭环（那是首页/执行/知识/人生/资产/伙伴六维的职责），而是为日常工作流提供四把「顺手的螺丝刀」：把磁盘上的真实文件夹纳入索引、把敏感凭据加密存好、把 AI 圈的热点资讯聚合到一屏、把口语化的待办快速结构化。

模块由四个子模块构成：

| 子模块 | 前端视图 | 后端入口 | 核心职责 |
|--------|----------|----------|----------|
| 工作区 | `WorkspaceView.vue` + `WorkspaceSetupView.vue` | `/workspace` | 多根目录登记、文件索引检索、噪声过滤扫描、白名单开终端 |
| 保险箱 | `VaultView.vue` | `/vault` | 主密码加密、凭据 CRUD、按需解密、SSH 密钥白名单动作 |
| AI 资讯 | `AiHotView.vue` | `/plugins/aihot`（内置插件） | 24h/7d 动态、热点榜、日报聚合、离线降级缓存 |
| AI 助理 | `AssistantView.vue` | `/assistant` | 语音/文字双通道输入、DeepSeek 结构化解析、确认后落库 |

### 1.2 模块目标

1. **数据主权**：工作区只索引路径与大小，绝不读取或复制文件内容；保险箱明文永不落盘、永不进日志。
2. **零预设引导**：工作区默认关闭、零内置路径，通过四步引导向导让新用户自己建立目录骨架（登记现有文件夹或按身份生成）。
3. **离线可用**：AI 资讯上游不可达时自动降级读缓存；移动端弱网/离线时写操作进入本地队列，联网后自动同步。
4. **移动优先**：AI 助理以手机端为首要场景（375px），语音双通道（原生 STT + Web Speech API）覆盖 Capacitor 壳与浏览器两端。
5. **安全红线不退**：终端动作只允许「打开目录」与「ssh -i 固定模板」两类白名单操作，动态字段全部过正则白名单，杜绝命令注入面。
6. **主题无感**：所有新增视觉元素只使用设计令牌，在奶油糖果 / 国风雅集 / 深渊档案 / 史诗典藏四套主题下无需额外适配。

### 1.3 非目标（本期不做）

- 不做工作区文件内容读取、编辑或预览（只索引元数据）。
- 不做保险箱跨设备云端同步（密文同步留待总路线 SYNC_POLICY 引擎落地时在表分级登记）。
- 不做 AI 资讯的评论、收藏、订阅推送（本期只读聚合展示）。
- 不做 AI 助理的多轮对话、记忆持久化、复杂日程冲突检测（本期只做「口语 → 结构化建议 → 确认落库」单跳）。
- 不替换 DeepSeek 为其他大模型（Key 加密落库，模型名可配置但渠道固定）。

---

## 2. 现状盘点（基于代码确认）

> 以下功能均已在代码中实现，盘点用于界定「已完成」与「待优化」边界，不重复设计。

### 2.1 工作区主视图（`WorkspaceView.vue`）

| 编号 | 已实现功能 | 代码依据 |
|------|------------|----------|
| A1 | 根列表横向 chip 切换，激活态 `is-active`（`--primary` 边框 + `--primary-soft` 底） | `ws__root.is-active` |
| A2 | 根概况：标签名 + 文件数（`scan_status==='ok'` 显示「N 项」否则「未扫描」） | `ws__root-meta` |
| A3 | 选中根详情卡片：完整路径（`--font-mono` 省略）+ 身份色点 + 身份名 | `ws__card-head` / `ws__identity-dot` |
| A4 | 文件名搜索框（`@update:model-value` 即触发，无显式防抖） | `ws__ops` BaseInput |
| A5 | 操作行：刷新 / 重新扫描 / 打开终端 / 移除（danger） | `ws__ops` 四枚 BaseButton |
| A6 | 统计行：索引 N 项 · 总大小（B/KB/MB 格式化）· 上次扫描时间 · 搜索命中数 | `ws__stats` / `formatSize` |
| A7 | 扫描错误态红色提示（`--straw-ink`）：显示 `scan_error` 前 500 字符 | `ws__error` |
| A8 | 文件列表：图标（folder/doc）+ 文件名 + 相对路径（`--font-mono` 省略）+ 大小 | `ws__list` / `ws__file` |
| A9 | 双击条目在父目录开终端（唯一白名单动作，后端 `resolve()` 校验） | `openFileRoot` / `openTerminal` |
| A10 | 空状态引导：未启用或无根时 BaseEmpty 引导去 `/workspace/setup` | `v-else-if="!enabled \|\| roots.length === 0"` |
| A11 | 加载态：根列表 `BaseSkeleton variant="list" :rows="4"`，文件列表 `:rows="5"` | `v-if="loading"` / `v-if="filesLoading"` |

### 2.2 工作区引导向导（`WorkspaceSetupView.vue`）

| 编号 | 已实现功能 | 代码依据 |
|------|------------|----------|
| B1 | 四步步骤指示器（圆形数字 chip，`is-active`/`is-done` 两态） | `wsetup__step` × 4 |
| B2 | 步骤①欢迎页：文件夹图标 40px + 数据主权承诺（`--mint-soft` 底提示条） | `wsetup__welcome` / `wsetup__promise` |
| B3 | 步骤②启用：单按钮启用，写入 `settings["workspace.enabled"]="true"` | `enable()` → `workspaceApi.setEnabled(true)` |
| B4 | 步骤③路径 A：登记现有文件夹（绝对路径 + 可选备注名），3 列网格行 | `wsetup__row` grid `2fr 1fr auto` |
| B5 | 步骤③路径 B：按身份生成目录骨架（选已登记根 → 为每个活跃身份建同名文件夹） | `buildSkeleton()` / `build_identity_skeleton` |
| B6 | 骨架结果展示：已创建列表（✅）+ 已存在跳过列表（↩️） | `wsetup__skeleton-result` |
| B7 | 步骤④首次扫描：每根独立「扫描/重新扫描」按钮，显示已索引项数与总大小 | `scan()` 循环 |
| B8 | 完成门槛：`canFinish = roots.length > 0`，无任何根时「完成」按钮 disabled | `canFinish` computed |
| B9 | 已启用用户进入时自动跳到步骤③（跳过欢迎与启用） | `if (status.enabled) step.value = 3` |

### 2.3 工作区后端服务（`workspace_service.py`）

| 编号 | 已实现能力 | 代码依据 |
|------|------------|----------|
| C1 | 开关持久化：`settings["workspace.enabled"]`，默认 false | `is_enabled()` / `set_enabled()` |
| C2 | 路径校验：必须绝对路径 + `resolve()` + 拒绝文件系统根（`p.parent == p`）+ 必须存在且为目录 | `_validate_root_path` |
| C3 | 同用户同路径唯一约束（`uq_workspace_roots_user_path`） | `register_root` 查重 |
| C4 | 噪声剪枝：黑名单目录不进入子树（`workspace.noise_dirs`），黑名单扩展名跳过（`workspace.noise_exts`） | `_walk` / `_noise_set` |
| C5 | 扫描全量替换：单事务先 DELETE 再 INSERT，失败即回滚 | `scan_root` |
| C6 | 索引字段：rel_path（POSIX 风格）、name、ext（小写含点）、is_dir、size、mtime、从根继承 identity_id | `WorkspaceFile` 模型 |
| C7 | 身份骨架：文件夹名过 `_UNSAFE_FS_CHARS` 正则清洗（`\/:*?"<>|` 替换为 `-`），已存在跳过 | `build_identity_skeleton` |
| C8 | 开终端白名单：`resolve()` 后必须落在任一 `enabled=True` 的根内，否则抛「安全白名单拦截」 | `_ensure_inside_enabled_roots` |
| C9 | 终端类型：`cmd`（默认）/ `wt` / `powershell`，Windows 下 `DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP` | `open_terminal` |
| C10 | 文件检索：`name.contains(search)` LIKE + `ext == ext.lower()` + 计数下推 SQL（`func.count`）+ 分页 | `list_files` |
| C11 | 软删除：`deleted_at` 字段，`_owned_root` 校验归属与未删除 | `SoftDeleteMixin` / `_owned_root` |

### 2.4 保险箱视图与后端（`VaultView.vue` / `vault_service.py`）

| 编号 | 已实现功能 | 代码依据 |
|------|------------|----------|
| D1 | 三态状态机：未初始化（设主密码）→ 已初始化未解锁 → 已解锁（CRUD） | `status.configured` / `status.unlocked` |
| D2 | 主密码要求 ≥8 位，两次输入一致性校验，不落盘、不存哈希 | `onSetup` / `setup` |
| D3 | 解锁校验：PBKDF2(随机 salt) 派生 Fernet 密钥 → 解密已知常量校验器 | `unlock` / `_VERIFIER_PLAINTEXT` |
| D4 | 解锁态存进程内存 `_session_keys`（dict[user_id, bytes]），服务重启即自动上锁 | `_session_keys` |
| D5 | 明出口唯一：`GET /items/{id}/secret` 按需解密，列表接口 `with_secret=False` | `reveal_secret` / `list_items` |
| D6 | 凭据分类：`login`（账号）/ `note`（笔记） | `category` Literal |
| D7 | 凭据字段：name / category / username / url / secret_encrypted / notes / identity_id | `VaultItem` 模型 |
| D8 | SSH 动作白名单模板：`ssh -i "{key_path}" [user@]host [-p port]`，动态字段过正则 | `_validate_action` / `run_action` |
| D9 | SSH 字段正则：host `^[A-Za-z0-9._-]{1,253}$`，user `^[A-Za-z0-9._@-]{1,64}$`，port `^\d{1,5}$` 且 1-65535 | `_SAFE_HOST` / `_SAFE_USER` / `_SAFE_PORT` |
| D10 | 密钥文件必须真实存在（`key_path.is_file()`），否则报错 | `run_action` |
| D11 | 更换主密码：原密码校验通过后，用新密钥重加密全部凭据密文（原地轮换） | `change_master_password` |
| D12 | 明文查看切换：点击眼睛图标调 `revealSecret`，再点隐藏；编辑时自动解密填充 secret 字段 | `toggleReveal` / `openEdit` |
| D13 | 身份色点 + 分类胶囊标签 + 身份名标签 | `vault__dot` / `vault__cat` |
| D14 | 删除二次确认弹窗（modal.confirm） | `onDelete` |

### 2.5 AI 资讯插件与视图（`plugins_builtin/aihot/main.py` / `AiHotView.vue`）

| 编号 | 已实现功能 | 代码依据 |
|------|------------|----------|
| E1 | 四个 Tab：今天（24h）/ 最近 7 天 / 热点 / 日报 | `TABS` 数组 |
| E2 | 上游硬编码 `BASE_URL = "https://aihot.virxact.com/api/v1"`，防配置注入 SSRF | `BASE_URL` 常量 |
| E3 | 匿名只读 GET，无 Key；window 白名单 `{24h, 7d}`，category 正则 `^[a-z0-9_-]{1,40}$` | `_ALLOWED_WINDOWS` / `_SAFE_CATEGORY` |
| E4 | 离线降级：上游失败 → 读内存缓存 → 读磁盘缓存文件（`plugins/aihot/{name}.json`）→ 诚实报错 | `_fetch` / `_load_cache` |
| E5 | 降级横幅：`--butter-soft` 底提示「展示的是最近一次成功同步的缓存内容」 | `aihot__degraded` |
| E6 | 日报 404 回退：latest 404 → 检索最近 7 天索引 → 取实际日期再请求一次 | `daily()` 回退逻辑 |
| E7 | 列表项：序号（热点 Tab 显示）+ 标题 + 分类 `BaseTag semantic="lilac"` + 摘要（2 行截断 `-webkit-line-clamp: 2`）+ 日期 | `aihot__item` |
| E8 | 点击条目新窗口打开原链接（`window.open(url, '_blank', 'noopener')`） | `openLink` |
| E9 | 日报纯文本 `<pre>` 展示，`white-space: pre-wrap` + `word-break: break-word` | `aihot__daily` |
| E10 | 空状态：日报无内容与列表无内容分别有不同 BaseEmpty 文案 | `v-else-if="tab === 'daily' && !dailyText"` |

### 2.6 AI 助理视图与后端（`AssistantView.vue` / `assistant_service.py`）

| 编号 | 已实现功能 | 代码依据 |
|------|------------|----------|
| F1 | 语音双通道：Capacitor 原生 STT（`@capacitor-community/speech-recognition`）/ 浏览器 Web Speech API | `isNative` computed / `startNativeVoice` / `startWebVoice` |
| F2 | 原生 STT 动态 import（PWA 构建永不加载原生插件分包），20s 超时兜底 | `await import(...)` / `setTimeout(20000)` |
| F3 | 识别语言 `zh-CN`，partialResults 实时拼接，listeningState=stopped 自动收尾 | `startListening({language:'zh-CN', partialResults:true})` |
| F4 | 麦克风大按钮：96px 高，`2px dashed --primary` 边框，`--primary-soft` 底，listening 时 `assistant-pulse` 1.2s 呼吸动画 | `assistant__mic` / `@keyframes assistant-pulse` |
| F5 | 解析：DeepSeek JSON Mode（`response_format: json_object`, temperature 0.2, max_tokens 1500, timeout 20s） | `_deepseek_parse` |
| F6 | 无 Key 降级：本地正则规则解析（标点/连接词切条 + 时间词提取 + 优先级词） | `local_parse` / `_deadline_from_text` |
| F7 | 建议条目结构：kind（task/reminder/note）+ title（12 字内）+ deadline（ISO）+ people + location + priority + notes | `Suggestion` interface |
| F8 | 确认后落库：task/reminder → TaskService，note → ResourceService（收集箱），单批上限 30 条 | `apply` / `len(items) > 30` |
| F9 | 待办分组：逾期（danger）/ 今天（primary）/ 之后（default），自动跳过 completed | `groups` computed / `GROUP_META` |
| F10 | 完成勾选：✓ 圆形按钮，26px，hover 变 `--mint-ink` + `--mint` 边框 | `assistant__done` |
| F11 | 来源标签：DeepSeek（mint）/ 简化解析（default）/ 待命（无来源） | `BaseTag :semantic` |
| F12 | Key 加密落库：`encryption` 文件密钥加密，永不回显、不进日志 | `configure` / `_key` |
| F13 | 澄清问题区：`--butter-soft` 底，展示 AI 不确定的点（最多 5 条） | `assistant__clarify` |
| F14 | 移动端优先：max-width 560px，padding-bottom 含 `env(safe-area-inset-bottom)` | `.assistant` 样式 |

### 2.7 现状缺口（待本期补齐）

| 编号 | 缺口 | 影响 |
|------|------|------|
| G1 | 工作区搜索框无防抖，每次按键都发请求（`@update:model-value` 直调 `loadFiles`） | 大根目录下按键即请求，浪费且可能卡顿 |
| G2 | 工作区无分页加载，`page_size=50` 固定，无滚动加载或翻页 UI | 文件多了看不到第 51 条之后 |
| G3 | 工作区移动端（375px）根 chip 横向换行尚可，但操作行 5 枚按钮会挤压换行 | 手机端操作行拥挤 |
| G4 | 保险箱移动端新增/编辑表单为 2 列网格（`grid-template-columns: 1fr 1fr`），375px 下输入框过窄 | 手机端表单难用 |
| G5 | 保险箱无「更换主密码」前端入口（后端 API 已存在 `POST /change-password`，前端未接） | 用户想改主密码无入口 |
| G6 | 保险箱无搜索/筛选，凭据多了无法快速定位 | 凭据超过 20 条后难找 |
| G7 | AI 资讯 Tab 在 375px 下 4 个 pill 按钮可能换行或挤压 | 手机端 Tab 切换不美观 |
| G8 | AI 资讯无下拉刷新 / 手动刷新按钮，只能切 Tab 重新请求 | 想看最新内容必须切 Tab |
| G9 | 助理语音识别 Web Speech 通道 `interimResults=false`（只取最终结果），原生通道才有 partialResults | 浏览器端看不到实时识别文字，体验割裂 |
| G10 | 助理无离线队列：离线时 parse/apply 直接报错，不排队 | 地铁/电梯弱网时无法快速记待办 |
| G11 | 助理建议条目不可删除（只能取消勾选），AI 拆错的条目不想要只能不勾 | 多拆出的条目无法从建议区移除 |
| G12 | 工作区扫描为同步阻塞调用，大目录（>10000 项）时前端长时间 loading | 大根目录扫描体验差，且无进度反馈 |
| G13 | 保险箱 SSH 动作无主机/端口测试连通性，配置错了点了才报错 | 调试 SSH 配置反复试错 |
| G14 | 无离线操作队列基础设施（跨四个子模块的写操作排队与同步机制） | 移动端离线体验整体缺失 |

---

## 3. 深度优化方向（P0/P1/P2 优先级分级）

### 3.1 P0（本期必须交付，阻塞核心体验）

> 状态（2026-09-19 收口）：**6/6 完成** ✅

| 编号 | 方向 | 涉及子模块 | 对应缺口 | 状态 |
|------|------|------------|----------|------|
| P0-1 | 工作区搜索防抖 + 分页加载 | 工作区 | G1 / G2 | ✅ 400ms 防抖 + 「加载更多」追加分页（PAGE_SIZE=50） |
| P0-2 | 保险箱移动端表单适配（单列堆叠） | 保险箱 | G4 | ✅ <768px 表单栅格塌缩单列 |
| P0-3 | 保险箱「更换主密码」前端入口 | 保险箱 | G5 | ✅ 头部按钮 + 三段密码弹窗（长度/一致性/同值校验） |
| P0-4 | 移动端整体 375px 适配打磨（四个子模块） | 全部 | G3 / G4 / G7 | ✅ 四子模块静态排查无固定超宽；触摸目标 ≥32px |
| P0-5 | 语音识别率优化：Web Speech 通道开启 interimResults 实时上屏 | AI 助理 | G9 | ✅ interim+continuous、幽灵字上屏、可停止、no-speech 不再误报 |
| P0-6 | 离线队列基础设施（写操作本地排队 + 联网自动同步） | 全部写操作 | G10 / G14 | ✅ 核心 15 条行为测试全绿，已纳入 check_all |

### 3.2 P1（本期尽量交付，体验增量明显）

> 状态（2026-09-19 收口）：**6/6 完成** ✅

| 编号 | 方向 | 涉及子模块 | 对应缺口 | 状态 |
|------|------|------------|----------|------|
| P1-1 | 保险箱凭据搜索/筛选（按名称/分类/身份） | 保险箱 | G6 | ✅ 三条件派生筛选 + 命中计数 + 空态 |
| P1-2 | AI 资讯手动刷新按钮 + 下拉刷新 | AI 资讯 | G8 | ✅ 按钮 + 触摸下拉（阻尼 0.45 / 阈值 56px） |
| P1-3 | 助理建议条目可删除（× 按钮） | AI 助理 | G11 | ✅ 单条移除，不再只能取消勾选占位 |
| P1-4 | 工作区扫描异步化 + 进度反馈 | 工作区 | G12 | ✅ 后台线程 + scan-progress 轮询 + 僵尸态识别 |
| P1-5 | 保险箱 SSH 配置连通性测试按钮 | 保险箱 | G13 | ✅ TCP 探测（host 只取凭据值）+ 审计留痕 |
| P1-6 | AI 资讯移动端 Tab 横滑容器 | AI 资讯 | G7 | ✅ 已在 §5.3 移动端适配中落地（实测确认） |

### 3.3 P2（远期规划，本期仅设计预留）

| 编号 | 方向 | 涉及子模块 | 说明 |
|------|------|------------|------|
| P2-1 | 工作区文件内容全文索引（FTS5） | 工作区 | 本期只索引元数据，内容检索留待后续 |
| P2-2 | 保险箱自动上锁计时器（解锁后 N 分钟无操作自动锁） | 保险箱 | 安全增强，需用户可配置 |
| P2-3 | AI 资讯收藏/稍后读 | AI 资讯 | 需新增数据表 |
| P2-4 | 助理多轮对话与日程冲突检测 | AI 助理 | 需对话历史表 + 冲突算法 |
| P2-5 | 离线队列冲突解决策略（以最后写入为准 / 手动选择） | 全部 | 队列基础设施稳定后再加 |

---

## 4. 功能需求详细拆解

### 4.1 工作区（F1.x）

##### F1.1 搜索防抖与即时反馈

- 将搜索框 `@update:model-value` 直调 `loadFiles` 改为 300ms 防抖，防抖期间输入框右侧显示「输入中…」微提示。
- 防抖触发后发请求，请求期间文件列表区域保留旧数据并叠加半透明 loading 遮罩（`--overlay` 20% 透明度），而非整体骨架屏闪烁。

**验收标准**：
- [ ] 连续输入「project」「proj」「pro」时，300ms 内只发最后一次请求（DevTools Network 面板确认）
- [ ] 防抖期间搜索框右侧显示小圆点 + 「输入中…」文字（`--text-low` 色，`--text-xs` 字号）
- [ ] 请求进行中旧文件列表不消失，遮罩透明度 20%，200ms 淡入
- [ ] 请求完成后遮罩 200ms 淡出，新数据替换旧数据
- [ ] 空搜索词（trim 后为空）时不发请求，直接清空文件列表

**交互细节**：
- 防抖计时器：300ms，使用 `setTimeout` 管理，组件卸载时 `clearTimeout`
- 遮罩层级：文件列表容器 `position: relative`，遮罩 `position: absolute; inset: 0; background: var(--overlay); z-index: 1`
- 搜索框聚焦时 `box-shadow: var(--focus-ring)`（沿用现有 BaseInput focus 态）

**状态全覆盖**：
- 默认态：搜索框为空，文件列表展示当前根全量前 50 条
- 输入态：防抖中，旧数据保留 + 「输入中…」微提示
- 加载态：请求发出，半透明遮罩覆盖列表
- 空结果态：搜索无命中，BaseEmpty「没有匹配的条目」（沿用现有）
- 错误态：请求失败时 toast 提示（http 层已有），列表保留旧数据

##### F1.2 文件列表分页加载

- 后端已支持 `page` / `page_size` 参数（默认 50），前端补充「加载更多」按钮 + 滚动到底自动加载。
- 每页固定 50 条，累计加载；底部显示「已加载 N / 共 M 条」。

**验收标准**：
- [ ] 首次加载请求 `page=1&page_size=50`
- [ ] 当 `items.length < total` 时，列表底部显示「加载更多」按钮（`--secondary` 变体）
- [ ] 点击「加载更多」后请求下一页，新数据追加到列表末尾（不替换）
- [ ] 加载中按钮文字变为「加载中…」并 disabled
- [ ] 全部加载完后按钮变为「已加载全部 M 条」disabled 态（`--text-low` 色）
- [ ] 切换根目录或新搜索词触发时，页码重置为 1，列表清空后重新加载

**交互细节**：
- 「加载更多」按钮居中，宽度 160px，高度 `--control-h-sm`（32px）
- 追加数据时有 150ms 淡入动画（新条目 `opacity: 0 → 1`）
- 滚动到底自动加载：使用 IntersectionObserver 监听底部哨兵元素，rootMargin 0px
- 哨兵元素高度 1px，仅在 `hasMore` 时渲染

**状态全覆盖**：
- 默认态：首屏加载中显示骨架屏 5 行
- 有更多态：底部「加载更多」按钮可点击
- 加载更多态：按钮 disabled + 「加载中…」+ 小型 spinner
- 全部加载态：底部文字「已加载全部 N 条」灰色
- 空态：total=0 时不渲染哨兵与按钮，显示 BaseEmpty

##### F1.3 异步扫描与进度反馈

- 将扫描从同步阻塞调用改为：前端点击「重新扫描」后立即返回一个 `scan_id`，轮询查询扫描状态（running / ok / error）。
- 扫描进行中按钮变为「扫描中…」并显示已索引项数实时增长（每 2 秒轮询一次）。

**验收标准**：
- [ ] 点击「扫描」后按钮立即变为 disabled + 「扫描中…」
- [ ] 扫描期间按钮旁实时显示「已索引 N 项」（N 每 2 秒更新）
- [ ] 扫描完成后 toast「扫描完成」+ 文件数，按钮恢复为「重新扫描」
- [ ] 扫描失败时按钮恢复，红色提示条显示错误信息（沿用现有 `scan_error` 展示）
- [ ] 扫描期间切换到其他根再切回来，扫描状态不中断（后端任务独立于前端路由）

**交互细节**：
- 轮询间隔 2000ms，最长轮询 120 秒（超时后停止轮询，按钮恢复，提示「扫描可能仍在后台进行」）
- 扫描中按钮右侧显示 8px 旋转 spinner（`--primary-ink` 色）
- 进度文字格式：`已索引 1,234 项`（千分位格式化）

**状态全覆盖**：
- 默认态：按钮「重新扫描」`--secondary` 变体
- 扫描中态：按钮 disabled + spinner + 实时计数
- 完成态：按钮恢复 + toast + 文件列表自动刷新
- 错误态：按钮恢复 + 红色错误条 + toast 警告
- 超时态：按钮恢复 + toast 提示「扫描超时，请稍后查看」

##### F1.4 移动端操作行适配（375px）

- 工作区详情卡片的操作行（搜索框 + 刷新 + 重新扫描 + 打开终端 + 移除）在 375px 下重新排列：搜索框独占一行，4 枚按钮 2×2 网格排列。

**验收标准**：
- [ ] 视口宽度 ≤ 480px 时，搜索框独占一行（宽度 100%）
- [ ] 4 枚操作按钮变为 2 列网格，每行 2 枚，间距 `--space-2`（8px）
- [ ] 按钮文字缩写：「刷新」→「刷新」（不变）、「重新扫描」→「重扫」、「打开终端」→「终端」、「移除」→「移除」
- [ ] 桌面端（>480px）保持现有单行排列不变

**交互细节**：
- 使用 CSS 媒体查询 `@media (max-width: 480px)` 覆盖 `.ws__ops` 的 flex 方向为 column
- 按钮网格 `display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-2)`
- 按钮高度统一 `--control-h-sm`（32px），字号 `--text-sm`（12px）

**状态全覆盖**：
- 桌面态：单行排列，搜索框 flex:1 占据剩余空间
- 移动态：搜索框独占行 + 按钮 2×2 网格

---

### 4.2 保险箱（F2.x）

##### F2.1 移动端表单单列堆叠（375px）

- 新增/编辑凭据的 BaseModal 表单在 375px 下从双列网格改为单列堆叠，输入框全宽。
- SSH 动作条件区（action_user / action_port）同样单列。

**验收标准**：
- [ ] 视口宽度 ≤ 480px 时，`.vault__form-row` 的 `grid-template-columns` 从 `1fr 1fr` 变为 `1fr`
- [ ] 名称输入框、分类选择、用户名、网址、密码、备注、身份选择、动作类型、主机、用户名、端口全部纵向堆叠
- [ ] 每行间距 `--space-3`（12px）
- [ ] 桌面端保持双列网格不变

**交互细节**：
- 媒体查询 `@media (max-width: 480px)` 覆盖 `.vault__form-row`
- 输入框高度统一 `--control-h`（40px），保证移动端手指可点（最小触摸目标 40×40px）
- Modal 在移动端宽度为 `100vw - 32px`（左右各 16px 边距），最大高度 `85vh`，内部可滚动

**状态全覆盖**：
- 默认态：桌面双列 / 移动单列
- 编辑态：打开编辑时 secret 字段自动解密填充（沿用现有）
- 保存态：确认按钮 loading，防止重复提交

##### F2.2 更换主密码前端入口

- 后端已存在 `POST /api/v1/vault/change-password`（旧密码 + 新密码，重加密全部凭据），前端在保险箱头部「上锁」按钮旁补充「改密码」入口。
- 弹出 Modal：旧密码 + 新密码（≥8 位）+ 确认新密码，校验一致性后提交。

**验收标准**：
- [ ] 保险箱已解锁状态下，头部操作区显示「改密码」按钮（`--secondary` 变体，icon="key"）
- [ ] 点击弹出 Modal，标题「更换主密码」
- [ ] 三个密码输入框均为 `type="password"`，有显示/隐藏切换眼睛图标
- [ ] 新密码长度 <8 时前端拦截提示「新主密码至少 8 位」
- [ ] 两次新密码不一致时前端拦截提示「两次输入不一致」
- [ ] 提交成功后 toast「主密码已更换，全部凭据已重加密」
- [ ] 提交失败（旧密码错误）时 toast 显示后端错误信息，密码框清空

**交互细节**：
- 「改密码」按钮与「上锁」按钮并排，间距 `--space-2`（8px）
- Modal 表单纵向排列，每个输入框高度 `--control-h`（40px）
- 显示/隐藏密码：眼睛图标按钮，点击切换 `type="password"` ↔ `type="text"`，图标 `eye` ↔ `eye-off`
- 提交按钮 `--primary` 变体，宽度 100%，loading 时显示「更换中…」

**状态全覆盖**：
- 默认态：已解锁时显示「改密码」按钮
- 未解锁态：不显示「改密码」按钮（保险箱上锁态无法改密码）
- 校验错误态：输入框下方红色文字提示（`--straw-ink`）
- 提交态：按钮 loading + disabled
- 成功态：toast + Modal 关闭
- 失败态：toast 错误 + 表单保留（不清空旧密码，清空新密码）

##### F2.3 凭据搜索与筛选

- 在凭据列表上方补充搜索框 + 分类筛选 Tab（全部 / 账号 / 笔记）+ 身份筛选下拉。
- 搜索在前端对已加载凭据列表做客户端过滤（名称 / 用户名 / 网址模糊匹配）。

**验收标准**：
- [ ] 已解锁状态下，凭据列表卡片顶部显示搜索框（placeholder「搜索凭据名称、用户名或网址…」）
- [ ] 搜索框下方显示三个分类筛选 pill：全部 / 账号 / 笔记，默认「全部」
- [ ] 身份筛选下拉：「全部身份」+ 每个身份一项（显示身份名）
- [ ] 搜索 + 分类 + 身份三个条件为 AND 关系
- [ ] 过滤后列表实时更新，底部显示「共 N 条」
- [ ] 无匹配时显示 BaseEmpty「没有匹配的凭据」

**交互细节**：
- 搜索框高度 `--control-h-sm`（32px），宽度 flex:1
- 分类 pill 按钮样式沿用 AI 资讯 Tab 风格（圆角 pill，激活态 `--primary` 底 + `--on-primary` 文字）
- 身份筛选使用 BaseSelect 组件
- 客户端过滤：`items.value.filter(it => ...)`，无防抖（本地过滤，即时响应）
- 375px 下搜索框独占一行，分类 pill 横滑排列（`overflow-x: auto; flex-shrink: 0`）

**状态全覆盖**：
- 默认态：搜索空 + 分类全部 + 身份全部，展示全量凭据
- 过滤态：按条件过滤，列表实时收缩
- 空过滤态：无匹配时 BaseEmpty
- 加载态：凭据列表加载时搜索区禁用（opacity 50% + pointer-events: none）

##### F2.4 SSH 连通性测试按钮

- 在 SSH 凭据编辑 Modal 中，当 `action_type === 'ssh'` 时，表单底部补充「测试连接」按钮。
- 点击后后端尝试 `ssh -o BatchMode=yes -o ConnectTimeout=5 -i "{key_path}" user@host -p port exit`，返回成功/失败。

**验收标准**：
- [ ] SSH 凭据编辑 Modal 中，`action_type` 选择「SSH 连接」时表单底部显示「测试连接」按钮
- [ ] 点击后按钮变为 loading + 「测试中…」，超时 10 秒
- [ ] 连接成功：按钮下方显示绿色提示「连接成功（耗时 N ms）」（`--mint-soft` 底 + `--mint-ink` 文字）
- [ ] 连接失败：按钮下方显示红色提示「连接失败：{错误原因}」（`--straw-soft` 底 + `--straw-ink` 文字）
- [ ] 未填主机名时前端拦截，提示「请先填写主机名」
- [ ] 测试连接不修改凭据数据，仅为诊断

**交互细节**：
- 「测试连接」按钮 `--secondary` 变体，宽度 100%，高度 `--control-h-sm`
- 结果提示区域高度自适应，150ms 淡入
- 后端新增 `POST /api/v1/vault/items/{id}/test-action`（要求解锁态，不持久化测试结果）
- 测试使用 `BatchMode=yes` 避免交互式密码提示挂住后端进程

**状态全覆盖**：
- 默认态：显示「测试连接」按钮
- 测试态：按钮 loading + 「测试中…」
- 成功态：绿色提示条
- 失败态：红色提示条 + 错误原因
- 未配置态：主机名为空时按钮 disabled

---

### 4.3 AI 资讯（F3.x）

##### F3.1 手动刷新与下拉刷新

- 在 AI 资讯头部标题右侧补充一枚刷新图标按钮（icon="reload"），点击后重新请求当前 Tab 数据。
- 移动端支持下拉刷新：列表顶部下拉超过 60px 触发刷新（沿用 Capacitor 原生下拉刷新或自定义触摸实现）。

**验收标准**：
- [ ] 头部「AI 资讯」标题右侧显示刷新图标按钮（32×32px，透明背景，hover 变 `--bg-inset`）
- [ ] 点击刷新按钮后，按钮变为旋转动画（360° 旋转 0.6s），列表区叠加半透明 loading
- [ ] 刷新完成后按钮停止旋转，toast 不提示（静默刷新）
- [ ] 移动端下拉超过 60px 触发刷新，刷新期间按钮同步旋转
- [ ] 刷新失败时 toast 显示错误（http 层已有），按钮恢复

**交互细节**：
- 刷新按钮旋转动画：`@keyframes spin { to { transform: rotate(360deg) } }`，0.6s linear infinite
- 下拉刷新阈值 60px，超过时提示文字「松开刷新」，未超过时提示「下拉刷新」
- 下拉刷新使用 Touch 事件实现：`touchstart` 记录起始 Y，`touchmove` 计算位移，`touchend` 判断是否超过阈值
- 桌面端不实现下拉刷新（仅按钮刷新）

**状态全覆盖**：
- 默认态：静止图标按钮
- 刷新态：图标旋转 + 列表半透明遮罩
- 下拉态（移动）：跟随手指位移显示提示文字
- 错误态：toast + 按钮恢复

##### F3.2 移动端 Tab 横滑容器

- 375px 下 4 个 Tab pill（今天 / 最近 7 天 / 热点 / 日报）改为横向可滚动容器，避免挤压换行。

**验收标准**：
- [ ] 视口宽度 ≤ 480px 时，`.aihot__tabs` 变为 `overflow-x: auto; flex-wrap: nowrap`
- [ ] Tab pill 不换行，可左右滑动查看全部
- [ ] 激活 Tab 自动滚动到可视区域（`scrollIntoView({ inline: 'center', behavior: 'smooth' })`）
- [ ] 滚动条隐藏（`scrollbar-width: none` + `::-webkit-scrollbar { display: none }`）
- [ ] 桌面端（>480px）保持现有 flex-wrap 排列不变

**交互细节**：
- Tab pill 最小宽度 64px，`flex-shrink: 0`
- 激活 Tab 切换后 200ms 平滑滚动居中
- 使用 CSS 媒体查询 `@media (max-width: 480px)` 覆盖

**状态全覆盖**：
- 桌面态：4 个 pill 横向排列，不滚动
- 移动态：4 个 pill 横滑，激活项居中

---

### 4.4 AI 助理（F4.x）

##### F4.1 语音识别率优化：Web Speech 实时上屏

- 将 Web Speech API 通道的 `interimResults` 从 `false` 改为 `true`，实时识别文字追加到 transcript。
- 原生通道已有 partialResults，保持不变；两条通道体验对齐。

**验收标准**：
- [ ] 浏览器端（非 Capacitor）点击麦克风后，说话过程中实时识别文字逐字追加到 transcript 文本框
- [ ] 最终结果到达时，临时文字替换为最终文字（去重）
- [ ] 原生 Capacitor 通道行为不变（已有 partialResults）
- [ ] 识别错误时可直接在文本框手动编辑修正
- [ ] 连续说话超 20 秒时自动停止（沿用现有原生通道 20s 兜底，Web 通道同样加 20s 超时）

**交互细节**：
- Web 通道 `rec.interimResults = true`
- `onresult` 回调中区分 `isFinal`：最终结果追加到 transcript，临时结果单独显示在麦克风按钮下方灰色文字（`--text-low`，`--text-xs`）
- 临时文字 500ms 未更新时自动替换为最新临时结果
- 20s 超时：Web 通道同样 `setTimeout(20000)` 后 `rec.stop()`
- 麦克风按钮下方实时显示临时识别文字，高度 24px，超出省略

**状态全覆盖**：
- 待命态：麦克风按钮显示「按一下，说事情」
- 识别态：按钮呼吸动画 + 下方实时临时文字
- 最终态：临时文字替换为最终文字，追加到文本框
- 错误态：toast「语音识别失败，请用文本输入」+ 按钮恢复
- 超时态：20s 自动停止 + 交出已识别文字

##### F4.2 建议条目可删除

- 在 AI 建议列表每条右侧补充一枚 × 删除按钮，点击后从建议区移除该条。
- 删除不影响已落库数据（建议尚未落库，删除只是不勾选）。

**验收标准**：
- [ ] 每条建议右侧（时间显示旁）显示一枚 × 小按钮（16×16px，`--text-low` 色，hover 变 `--straw-ink`）
- [ ] 点击 × 后该条从建议列表移除，列表剩余条目上移（150ms 高度过渡）
- [ ] 删除后「全部加入待办」按钮文字更新为「加入 N 条」（N = 当前未删除且勾选的条数）
- [ ] 删除为纯前端操作，不发请求
- [ ] 全部删除后建议卡片自动收起（v-if suggestions.length 自然失效）

**交互细节**：
- × 按钮位置：时间文字右侧，间距 `--space-1`（4px）
- 删除动画：`max-height: 0; opacity: 0` 过渡 200ms 后从数组移除
- 删除后重新计算 `picked` 数量，按钮文字实时更新

**状态全覆盖**：
- 默认态：建议条目右侧显示 × 按钮
- 删除态：条目淡出 + 上移
- 全删态：建议卡片消失

##### F4.3 离线队列基础设施

- 新增前端离线队列 Store（Pinia），拦截四个子模块的写操作 POST/PATCH/DELETE 请求。
- 检测网络状态：`navigator.onLine` + `window.addEventListener('online'/'offline')`。
- 离线时写操作不发请求，而是存入 IndexedDB 队列（持久化，App 重启不丢）。
- 联网后自动按 FIFO 顺序重放队列，成功的出队，失败的保留并提示。

**验收标准**：
- [ ] 离线状态下（DevTools 切换 Offline），在助理页点击「全部加入待办」时，请求不发出，而是进入队列
- [ ] 队列条目包含：API 路径、方法、请求体、时间戳、重试次数
- [ ] 离线期间所有写操作（工作区登记根/扫描/移除、保险箱新增/编辑/删除凭据、助理 apply）均进入队列
- [ ] 联网后自动按 FIFO 重放，队列图标变为「同步中…」
- [ ] 重放成功的条目从队列移除
- [ ] 重放失败的条目标记为「失败」，重试次数 +1，最多重试 3 次后停止并提示
- [ ] App 重启后队列不丢失（IndexedDB 持久化）
- [ ] 队列中有待同步条目时，页面右上角显示队列角标（数字徽标）

**交互细节**：
- 队列角标：圆形 16px，`--primary` 底 + `--on-primary` 文字，显示待同步条数
- 点击角标展开队列面板（底部抽屉），列出所有待同步条目（API 路径 + 时间 + 状态）
- 队列面板支持手动「重试全部」和「清空失败」操作
- 网络状态监听：`window.addEventListener('online', flushQueue)` / `window.addEventListener('offline', ...)`
- IndexedDB 库名 `venustech_offline_queue`，表名 `queue`，主键 `id`（自增）
- 重放间隔：每条间隔 500ms（避免瞬间洪峰）
- 冲突策略（P2 预留）：本期简单处理为「最后写入胜出」，不做手动选择

**状态全覆盖**：
- 在线空闲态：无角标，写操作正常发请求
- 离线态：角标显示待同步数，写操作进入队列，toast「已离线，操作将在联网后同步」
- 同步中态：角标变为 spinner 旋转，队列面板显示逐条同步进度
- 同步完成态：角标消失，toast「N 条操作已同步」
- 同步失败态：失败条目红色标记，角标显示失败数，队列面板可手动重试

---

## 5. 移动端适配需求（375px 宽度）

### 5.1 全局规范

| 项目 | 规范 |
|------|------|
| 视口基准 | 375px（iPhone SE 标准），媒体查询断点 480px |
| 页面左右边距 | `--space-4`（16px），替代桌面端 `--space-6`（24px） |
| 卡片间距 | `--space-3`（12px），替代桌面端 `--space-4`（16px） |
| 最小触摸目标 | 44×44px（Apple HIG），按钮高度不低于 `--control-h`（40px） |
| 底部安全区 | `padding-bottom: max(var(--space-6), env(safe-area-inset-bottom))` |
| 横向滚动 | 所有横向排列的 chip/Tab 在 375px 下改为 `overflow-x: auto` + 隐藏滚动条 |
| 文字截断 | 文件名/路径/凭据名超出单行省略（`text-overflow: ellipsis`），不换行 |

### 5.2 各子模块移动端专项

#### 工作区（WorkspaceView）

- 根 chip 列表：375px 下保持横向换行（现有 flex-wrap 已支持），每个 chip 最小高度 36px，文字 `--text-sm`
- 操作行：F1.4 已定义为 2×2 网格
- 文件列表行高：从现有 6px padding 增至 12px padding（提升触摸命中率）
- 双击打开终端：移动端无双击概念，改为单击条目展开操作菜单（底部 ActionSheet），含「在父目录打开终端」与「复制路径」两项
- 搜索框：高度 `--control-h`（40px），占位文字 `--text-sm`

#### 保险箱（VaultView）

- 凭据列表行：375px 下操作按钮组（SSH/眼睛/编辑/删除）从横向排列改为更紧凑的图标按钮（每个 32×32px），间距 `--space-1`
- 表单：F2.1 已定义为单列堆叠
- 明出口切换：点击眼睛图标后明文显示区域字号 `--text-sm`（12px），`word-break: break-all`
- 上锁/新增/改密码按钮：375px 下头部按钮区纵向排列，按钮宽度 100%

#### AI 资讯（AiHotView）

- Tab：F3.2 已定义为横滑容器
- 列表项：375px 下摘要从 2 行截断保持不变，标题字号 `--text-md`（15px）
- 点击条目：移动端无新窗口概念，改为 `window.open` 在 Capacitor 内打开系统浏览器（`@capacitor/browser` 插件）
- 日报纯文本：375px 下行高 1.8，字号 `--text-sm`

#### AI 助理（AssistantView）

- 麦克风按钮：现有 96px 高在 375px 下保持，左右边距 `--space-4`
- 建议条目：375px 下 checkbox 增大到 24×24px，时间文字右对齐
- 待办分组：375px 下完成勾选按钮 26px 保持，标题文字 `--text-sm`
- 文本输入框：375px 下高度自适应（rows=3），宽度 100%

### 5.3 动画与性能

- 所有移动端动画时长不超过 200ms（桌面端 300ms → 移动端 200ms）
- 呼吸脉冲动画（`assistant-pulse`）在移动端保持 1.2s 周期
- 列表滚动使用 `overscroll-behavior: contain` 防止橡皮筋效果穿透
- 触摸反馈：所有可点击元素 `:active` 态 `transform: scale(0.97)`（麦克风按钮已有此效果，推广到列表项）

---

## 6. 数据模型与 API 补充

### 6.1 新增数据表

#### offline_queue（离线队列表）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | Integer（自增） | 是 | 主键，IndexedDB 自增 |
| method | String(10) | 是 | HTTP 方法：POST / PATCH / DELETE |
| path | String(500) | 是 | API 路径，如 `/api/v1/assistant/apply` |
| body | Text | 否 | 请求体（JSON 字符串） |
| created_at | DateTime | 是 | 入队时间 |
| status | String(10) | 是 | pending / syncing / failed / synced |
| retry_count | Integer | 是 | 重试次数，默认 0，上限 3 |
| error | Text | 否 | 最后一次失败原因 |

> 注：离线队列本期仅前端 IndexedDB 实现，不建后端表。后端无感知，重放时就是正常 API 调用。

### 6.2 新增 API 端点

#### POST /api/v1/vault/items/{item_id}/test-action

- **用途**：SSH 连通性测试（F2.4）
- **要求**：解锁态
- **请求体**：无（直接用已存储的 action_host / action_user / action_port / secret_encrypted 中的密钥路径）
- **响应**：
  ```json
  {
    "ok": true,
    "success": true,
    "elapsed_ms": 1234,
    "error": null
  }
  ```
- **后端实现**：`subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", "-i", key_path, target, "exit"], capture_output=True, timeout=10)`

#### GET /api/v1/workspace/roots/{root_id}/scan-status

- **用途**：异步扫描状态轮询（F1.3）
- **要求**：登录态 + 根归属校验
- **响应**：
  ```json
  {
    "root_id": "uuid",
    "scan_status": "running",
    "file_count": 1234,
    "total_size": 567890
  }
  ```
- **后端实现**：扫描改为后台线程（`threading.Thread`），状态存内存 `_scan_tasks: dict[root_id, dict]`

### 6.3 已有 API 增强

| 端点 | 增强内容 |
|------|----------|
| `GET /workspace/files` | 无新增（前端补充分页 UI，后端已支持 page/page_size） |
| `PUT /vault/change-password` | 前端接入（后端已存在） |
| `POST /assistant/apply` | 离线队列拦截（前端层，后端无改动） |

### 6.4 Schema 补充

工作区 Schema 目前内联在 `api/workspace.py` 的 Pydantic 模型中，不单独建文件。本期新增端点沿用此模式：

```python
class TestActionResponse(BaseModel):
    success: bool
    elapsed_ms: int | None = None
    error: str | None = None

class ScanStatusResponse(BaseModel):
    root_id: str
    scan_status: str  # running / ok / error
    file_count: int
    total_size: int
```

---

## 7. 用户故事

### 场景一：新用户首次配置工作区

> 小陈是启明星新用户，打开工作区模块看到空状态引导。他点击「打开引导向导」，第一步阅读了数据主权承诺，第二步点击「启用」，第三步在路径 A 输入了 `D:\YanYuas\Projects` 并登记，然后在路径 B 选择这个根，点击「生成骨架」，系统为他已有的 3 个身份各建了一个文件夹。第四步他对根做了首次扫描，索引了 2,341 个文件。完成后他回到主视图，点击根 chip 切换，搜索框输入「论文」，300ms 防抖后过滤出 12 个匹配文件。他双击一篇论文 PDF，系统在其父目录打开了终端。

**验收要点**：引导四步流程顺畅、扫描有进度、搜索防抖生效、双击开终端被后端白名单校验通过。

### 场景二：学生手机路上速记待办

> 小李在地铁上（弱网环境）打开 AI 助理，按下麦克风说：「明天下午 3 点找张老师谈开题，然后买周五回家的高铁票，别忘了取快递」。Web Speech 实时识别文字逐字上屏，他看到识别无误后点击「帮我整理成待办」。DeepSeek 解析出 3 条建议：①任务「找张老师谈开题」deadline 明天 15:00；②任务「买周五高铁票」；③备忘「取快递」。他全部勾选后点击「加入待办」。此时地铁进入隧道完全离线，操作自动进入离线队列，右上角角标显示「1」。出地铁恢复网络后，队列自动同步，toast 提示「1 条操作已同步」，他的待办列表出现了这 3 条。

**验收要点**：语音实时上屏、离线队列入队、联网自动同步、待办正确落库。

### 场景三：开发者管理 SSH 凭据

> 王工在保险箱新增一条 SSH 凭据：名称「实验室服务器」，分类「账号」，主机 `lab.example.com`，用户 `wang`，端口 `22`，密钥路径 `C:\Users\wang\.ssh\id_ed25519`。他点击「测试连接」，5 秒后显示绿色「连接成功（耗时 823ms）」。保存后他在凭据列表点击 SSH 图标，系统打开终端执行 `ssh -i "..." wang@lab.example.com -p 22`。一个月后他想改主密码，点击头部「改密码」，输入旧密码和新密码，系统用新密钥重加密了全部 8 条凭据。他担心忘记主密码，看到页面底部提示「主密码不落盘，忘记无法找回」，便把新密码记到了密码管理器里。

**验收要点**：SSH 白名单正则校验、连通性测试、改密码重加密、明出口唯一。

### 场景四：研究者每日浏览 AI 热点

> 张教授每天早上打开 AI 资讯，默认停在「今天」Tab，看到 24 小时内 20 条 AI 圈动态。他切到「热点」Tab，看到按热度排序的前 10 条，序号 1 高亮显示。他点击一条标题，新窗口打开原文章链接。某天早上上游 AI HOT 服务宕机，页面显示 `--butter-soft` 黄色横幅「展示的是最近一次成功同步的缓存内容」，他仍能看到昨天缓存的热点。他在 375px 手机上打开时，4 个 Tab 可左右滑动，下拉列表触发刷新，看到最新的动态。

**验收要点**：四 Tab 切换、离线降级横幅、点击开链接、移动端横滑 Tab + 下拉刷新。

### 场景五：用户离线时管理凭据

> 赵同学在图书馆地下室（无网络）想新增一条 GitHub Token 到保险箱。他打开保险箱（已解锁态仍在内存中），点击「新增凭据」，填写名称、Token、URL，点击保存。由于离线，请求进入队列，角标显示「2」（此前还有一条待同步）。他想删除一条旧凭据，点击删除并确认，该操作也进入队列。回到楼上恢复网络后，角标旋转同步中，2 条操作依次成功，角标消失，toast 提示「2 条操作已同步」。他刷新列表，新增的 Token 和删除的旧凭据都正确反映。

**验收要点**：离线队列持久化、联网 FIFO 重放、增删操作均被队列拦截、同步后数据一致。

---

## 8. 验收标准（整体模块级）

### 8.1 功能完整性

- [ ] 工作区四步引导向导完整可用，从零配置到首次扫描全流程无阻断
- [ ] 工作区搜索防抖 300ms 生效，分页加载「加载更多」可用
- [ ] 工作区异步扫描有进度反馈，大目录（>10000 项）不阻塞前端
- [ ] 保险箱三态状态机（未初始化/锁定/解锁）流转正确
- [ ] 保险箱主密码 ≥8 位、不落盘、重启自动上锁
- [ ] 保险箱明出口唯一（仅 revealSecret 接口），列表不含密文
- [ ] 保险箱 SSH 白名单正则校验通过，命令注入测试（如 `; rm -rf /`）被拦截
- [ ] 保险箱更换主密码入口可用，重加密全部凭据后数据完整
- [ ] 保险箱凭据搜索/筛选（名称+分类+身份 AND）可用
- [ ] AI 资讯四 Tab 切换正确，离线降级横幅显示
- [ ] AI 资讯手动刷新按钮可用，移动端下拉刷新可用
- [ ] AI 助理语音双通道（原生 + Web Speech）均可识别中文
- [ ] AI 助理 Web Speech 通道实时上屏临时识别文字
- [ ] AI 助理建议条目可删除，确认后落库（task/reminder/note 分类正确）
- [ ] AI 助理待办分组（逾期/今天/之后）正确，完成勾选生效

### 8.2 移动端适配

- [ ] 375px 宽度下四个子模块无横向溢出
- [ ] 所有可点击元素最小触摸目标 40×40px
- [ ] 横向排列的 chip/Tab 在 375px 下可横滑
- [ ] 底部安全区 `env(safe-area-inset-bottom)` 适配
- [ ] 媒体查询断点 480px，桌面端样式不被覆盖

### 8.3 离线队列

- [ ] 离线时所有写操作进入 IndexedDB 队列，不发请求
- [ ] 联网后自动 FIFO 重放，成功出队，失败重试最多 3 次
- [ ] 队列角标实时反映待同步数
- [ ] App 重启后队列不丢失
- [ ] 队列面板可查看条目详情、手动重试、清空失败

### 8.4 安全红线

- [ ] 工作区开终端路径经 `resolve()` 校验，`..` 穿越被拦截
- [ ] 工作区拒绝登记文件系统根（`D:\` / `C:\`）
- [ ] 工作区噪声目录（node_modules / venv / .git）不进入索引
- [ ] 保险箱主密码不存哈希，只存 Fernet 校验器
- [ ] 保险箱 SSH 动态字段（host/user/port）全部过正则白名单
- [ ] 保险箱密钥文件路径必须真实存在，不存在时报错
- [ ] AI 资讯 BASE_URL 硬编码，不可通过配置注入指向任意主机
- [ ] AI 助理 DeepSeek Key 加密落库，前端永不回显

### 8.5 主题一致性

- [ ] 所有新增 UI 元素只使用 `variables.scss` 中的设计令牌
- [ ] 四套主题（奶油糖果/国风雅集/深渊档案/史诗典藏）下视觉正常
- [ ] 组件文件内 grep `#` 零命中（颜色全部用令牌变量）

---

## 9. 风险与依赖

### 9.1 技术风险

| 编号 | 风险 | 影响 | 缓解措施 |
|------|------|------|----------|
| R1 | Web Speech API 在不同浏览器（Chrome/Safari）行为不一致，interimResults 质量参差 | 移动端识别体验割裂 | 原生 Capacitor 通道优先（`isNative` 判断），Web 通道作为兜底；识别结果允许手动编辑 |
| R2 | 离线队列重放时遇到数据已被其他操作变更（冲突） | 重放失败或数据不一致 | 本期策略为「最后写入胜出」，冲突不做合并；队列面板展示失败条目供手动处理 |
| R3 | 异步扫描后台线程在 SQLite(WAL) 下并发写入可能锁库 | 扫描期间其他操作报 database locked | 扫描在单事务内完成（现有实现已是），WAL 模式下读写不互斥；如遇锁，重试 3 次 |
| R4 | Capacitor 7 的 `@capacitor-community/speech-recognition` 插件在部分 Android 机型权限申请失败 | 原生语音不可用 | 权限失败时降级到 Web Speech 通道或文本输入，toast 提示 |
| R5 | SSH 连通性测试在 Windows 上 `ssh` 命令不存在（未装 OpenSSH） | 测试接口报错 | 后端捕获 FileNotFoundError，返回友好提示「未检测到 ssh 命令，请安装 OpenSSH」 |
| R6 | IndexedDB 在 Capacitor WebView 中被系统清理时队列丢失 | 离线操作丢失 | 队列面板在有 pending 条目时每 30 秒 toast 提醒一次；关键操作（保险箱）离线时提示「离线模式下凭据操作建议联网后执行」 |

### 9.2 依赖项

| 编号 | 依赖 | 来源 | 说明 |
|------|------|------|------|
| D1 | `@capacitor-community/speech-recognition` | 已有依赖 | 原生语音识别，本期不新增 |
| D2 | `@capacitor/browser` | 待确认 | AI 资讯移动端打开链接如需系统浏览器，需新增此插件 |
| D3 | IndexedDB（原生浏览器 API） | 无依赖 | 离线队列存储，无需引入库 |
| D4 | `workspace.noise_dirs` / `workspace.noise_exts` 配置项 | settings 表已有 | 噪声黑名单可配置，本期不改 |
| D5 | `encryption` 文件密钥 | 已有模块 | 保险箱与助理 Key 加密共用 |
| D6 | TaskService / ResourceService | 已有模块 | 助理 apply 落库调用 |
| D7 | 身份管理（`useIdentity` / IdentityRepository） | 已有模块 | 工作区与保险箱的身份关联 |

### 9.3 非目标边界声明

- 本期不做工作区文件内容预览/编辑（只索引元数据）
- 本期不做保险箱云端同步（密文同步留待 SYNC_POLICY 引擎）
- 本期不做 AI 资讯的收藏/订阅/推送
- 本期不做 AI 助理多轮对话与日程冲突检测
- 本期不做离线队列的手动冲突合并 UI（自动最后写入胜出）
- 本期不做工作区自动定时扫描（保持手动触发）

---

> 本文档基于 `WorkspaceView.vue`、`WorkspaceSetupView.vue`、`VaultView.vue`、`AiHotView.vue`、`AssistantView.vue`、`workspace.py`、`vault.py`、`assistant.py`、`workspace_service.py`、`vault_service.py`、`assistant_service.py`、`models/workspace.py`、`models/vault.py`、`plugins_builtin/aihot/main.py`、`styles/variables.scss` 的实际代码撰写，所有现状描述均可在上述文件中追溯。
