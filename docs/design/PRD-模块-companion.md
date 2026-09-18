# 启明星系统 PRD —— 伙伴模块（mod-companion）深度优化

> 模块名：伙伴（companion）· 六维导航之一
> Slogan：方向启明，人生推演
> 文档版本：v1.0（模块化深度优化版）
> 日期：2026-09-18
> 状态：现状盘点完成，深度优化方向待排期
> 读者：前端 / 后端开发、评委、项目经理
> 关联代码：
> - 前端视图：`frontend/src/views/Conversation/ConversationView.vue`、`frontend/src/views/Pet/PetSettingsView.vue`、`frontend/src/views/Avatar/AvatarSettingsView.vue`
> - 桌宠主组件：`frontend/src/components/pet/DesktopPet.vue`
> - 前端逻辑：`frontend/src/composables/useConversation.ts`
> - 后端 API：`backend/app/api/conversation.py`、`pet.py`、`avatar.py`
> - 后端服务：`backend/app/services/conversation_service.py`、`pet_service.py`、`avatar_service.py`
> - 后端模型：`backend/app/models/conversation.py`、`pet.py`、`avatar.py`
> - Schema：`backend/app/schemas/conversation.py`、`pet.py`、`avatar.py`
> - AI 服务：`backend/app/services/ai/`（`client.py`、`ai_service.py`、`prompt_builder.py`）

---

## 1. 模块定位与目标

### 1.1 一句话定位

伙伴模块是启明星系统的**核心差异化亮点**——「第二分身」。它不是一个冰冷的聊天框，而是一个**住在用户电脑里、了解用户、会主动服务、有二次元形象的 AI 伙伴**。模块由三条线组成：

| 子线 | 载体 | 解决的问题 |
|------|------|-----------|
| AI 对话 | `ConversationView.vue` | 多轮对话、RAG 引用、思维模式、主动服务 |
| 桌宠 | `DesktopPet.vue` + `PetSettingsView.vue` | 帧动画、悬浮、拖拽、状态感知、语音、四维陪伴数值 |
| Avatar 形象 | `AvatarSettingsView.vue` | 五档自动化、长期记忆、灵感工作流、形象切换 |

### 1.2 模块在六维导航中的位置

六维导航：首页（dashboard）、执行（execution）、知识（knowledge）、人生（life）、资产（asset）、**伙伴（companion）**。

伙伴模块与其他五维的关系：

- **向上游读取**：从「知识」拉取文档做 RAG 引用；从「执行」读取今日到期未完成任务做任务感知；从「人生」读取最近心情记录做心情感知。
- **向下游写入**：长期记忆沉淀用户画像；灵感可一键转任务/转文档；对话中可建议新建任务。
- **全局陪伴**：`DesktopPet.vue` 是唯一跨页面常驻的组件，通过 `PET_ACTION_EVENT` 自定义事件与各模块解耦通信（如任务完成时派发 `celebrate` 动作）。

### 1.3 本次深度优化的三大方向

来自《模块划分方案》，本次 PRD 围绕以下三个方向展开功能拆解：

1. **对话体验优化**：流式输出、打断、上下文管理（现状已有 SSE 与 AbortController，但上下文窗口固定 20 条、无摘要压缩、无对话标题自动生成）。
2. **记忆系统深化**：长期记忆可视化、记忆检索注入对话、记忆遗忘（现状记忆已落库但未注入对话上下文、无衰减/遗忘机制、无检索）。
3. **形象合成**：桌宠 ↔ 人形切换、自定义形象上传（现状双击切换形态已实现但仅内置 SVG，`image_url` 上传仅支持 URL 字符串，未支持本地文件）。

### 1.4 本次优化目标（可验收）

- 对话流式打断、上下文压缩、对话标题自动生成三项落地，长对话不爆上下文。
- 长期记忆在每次对话时按相关性注入 system prompt，分身真正"记得"用户。
- 记忆具备时间衰减与人工遗忘，避免记忆无限膨胀。
- 桌宠 ↔ 人形切换有明确动效与持久化，自定义形象支持本地上传图片。
- 所有新增功能在 375px 移动端宽度下可用（Capacitor 7 + Android 壳）。

---

## 2. 现状盘点（基于代码确认）

> 以下功能清单**逐项来自实际代码**，非凭空设计。每条标注代码出处，便于开发对照。

### 2.1 AI 对话线（ConversationView + conversation_service）

| 已实现功能 | 代码出处 | 说明 |
|-----------|---------|------|
| 会话 CRUD | `conversation.py` router | GET/POST/DELETE `/conversations`，消息列表 GET `/conversations/{id}/messages` |
| SSE 流式对话 | `conversation.py` `send_message` | `StreamingResponse(media_type="text/event-stream")`，事件类型 `content/done/error` |
| 流式打断 | `useConversation.ts` `stopStreaming` | `AbortController.abort()` 中止 fetch，规则模式用 `ruleCancelled` 标志中止打字机 |
| 本地消息先渲染 | `useConversation.ts` `sendMessage` | 用户消息先 push 到 `messages.value`，流式期间立即可见，失败不丢输入 |
| 无 Key 降级 | `useConversation.ts` `buildLocalReply` | 无 API Key 时走规则关键词回复；学习类意图走 S6-1 领域规则引擎 `learningApi.generatePlan` |
| 规则模式打字机 | `useConversation.ts` | 每 3 字符一帧，15ms 间隔，可被 `stopStreaming` 中断 |
| 五种思维模式 | `conversation_service.py` `MODE_CONFIG` | normal(0.7)/deep(0.2)/creative(0.9)/critical(0.4)/brainstorm(1.0)，各带 system hint |
| 文档引用 | `ConversationView.vue` `selectedDocs` | 最多 3 篇，以 system 消息注入，单文档截断 2000 字符 |
| 历史窗口 | `conversation_service.py` `MAX_HISTORY_MESSAGES=20` | 固定取最近 20 条 |
| Token 估算 | `conversation_service.py` `_estimate_tokens` | 中文 1 字≈1.5 token，英文 1 词≈1.3 token |
| 错误占位 | `conversation_service.py` stream_messages | AI 异常时保存 `[AI 服务异常] xxx` 占位助手消息 |
| 提示词模板 | `ConversationView.vue` `builtinTemplates` | 8 个内置模板 + 自定义模板（localStorage），空输入按 `/` 唤起 |
| 人设切换 | `ConversationView.vue` `personas` | 6 个内置人设（贴心助手/智慧导师/知心朋友/犀利批评家/创意伙伴/理性分析师），localStorage 持久化 |
| 模型切换 | `ConversationView.vue` `availableModels` | 5 个模型（DeepSeek V3/R1、GPT-4o、Claude 3.5、Ollama 本地），localStorage 持久化 |
| 用户画像 | `ConversationView.vue` `userTraits` | 4 类特质（interest/skill/style/value），confidence 百分比，localStorage 持久化 |
| 主动提醒 | `ConversationView.vue` `checkReminders` | 轮询 `/tasks?due_soon=true`，派发 `venustech-pet-action` 事件，间隔 localStorage 持久化 |
| AI 辅助接口 | `conversation.py` ai_router | `/ai/summarize`、`/ai/suggest-tags`、`/ai/inspiration`、`/ai/reflection-questions` |
| LLM 客户端 | `ai/client.py` | DeepSeekClient（httpx 零 openai 依赖，网络错误重试 2 次指数退避 1s→2s）、MockLLMClient |
| Key 校验 | `ai/ai_service.py` `verify_api` | 区分 401/403（Key 无效）与网络/5xx 错误，不再一律吞成"Key 无效" |

### 2.2 桌宠线（DesktopPet + PetSettingsView + pet_service）

| 已实现功能 | 代码出处 | 说明 |
|-----------|---------|------|
| 12 种动作 | `DesktopPet.vue` `PetAction` | idle/happy/thinking/working/celebrate/sleep/wave/dance/read/run/shy/surprised |
| 每动作气泡文案 | `DesktopPet.vue` `MESSAGES` | 每种动作 4 条随机文案，气泡显示 3 秒 |
| 点击互动 | `DesktopPet.vue` `onClick` | 单击随机 happy/thinking/celebrate 2 秒；拖拽位移后吞掉 click 防误触 |
| 拖拽 | `DesktopPet.vue` `onDragMove` | rAF 合帧，`translate3d` 定位，`will-change: transform`，`dragMoved` 防误触 |
| 双击切换形态 | `DesktopPet.vue` `toggleForm` | pet ↔ human 双 SVG，300ms 过渡，localStorage 持久化 |
| 右键菜单 | `DesktopPet.vue` `onContextMenu` | Teleport 到 body，8 动作 + 喂食/玩耍/休息 + 亲密度/心情进度条 |
| 事件驱动动作 | `DesktopPet.vue` `onPetAction` | 监听 `PET_ACTION_EVENT`，任务完成等业务事件触发 celebrate |
| 庆祝纸屑 | `DesktopPet.vue` `pet__confetti` | 8 片纸屑，`hsl(i*45,80%,60%)`，1s 下落 |
| 显示设置 | `PetSettingsView.vue` display tab | enabled/size(80/120/160)/opacity(0.3-1)/always_on_top/auto_start/draggable/click_interaction/right_click_menu/show_bubble/bubble_duration(2-15s) |
| 状态感知 | `pet_service.py` `get_current_state` | 8 时段 + 今日到期未完成任务数 + 最近心情 score 映射 |
| 时段动作 | `pet_service.py` `TIME_STATES` | 6-9 伸懒腰/9-12 认真工作/12-14 吃饭/14-18 思考/18-19 放松/19-23 阅读/23-6 睡觉 |
| TTS | `PetSettingsView.vue` `testTTS` | 浏览器 `speechSynthesis`，rate/pitch/volume/speak_scene 五场景 |
| 四维陪伴数值 | `pet_service.py` `get_stats`/`update_stats` | intimacy/satiety/mood/energy 0-100，惰性衰减，增量更新，60s 轮询 |
| 互动 | `DesktopPet.vue` pet/feed/play/rest | 抚摸+2亲密度+3心情；喂食+25饱食（≥95 拒绝）；玩耍-10能量（<20 拒绝）；休息+30能量 |
| 心情标签 | `DesktopPet.vue` `getMoodLabel` | ≥80 超开心/≥60 不错/≥40 一般/≥20 低落/否则需要陪伴 |
| 形象 CRUD | `pet.py` router | `/pet/avatars` CRUD + `/activate`，无形象自动建默认"启明星" |
| 形象模式 | `models/pet.py` `PetAvatar` | simple（静态+eye/mouth_position）/advanced（action_frames JSON） |

### 2.3 Avatar 形象线（AvatarSettingsView + avatar_service）

| 已实现功能 | 代码出处 | 说明 |
|-----------|---------|------|
| 五档自动化 | `AvatarSettingsView.vue` `automationLevels` | L1 完全手动 / L2 建议不执行 / L3 低风险自动 / L4 大部分自动 / L5 完全自主，默认 L2 |
| 模型配置 | `AvatarSettingsView.vue` config tab | cloud(deepseek/openai/custom) + local(ollama/lmstudio)，含 url/name |
| 人格设定 | `AvatarSettingsView.vue` | persona_name(默认启明星)/persona_setting/reply_length(short/medium/long)/language_style(casual/professional/cute)/creativity(0-1 默认 0.7) |
| 长期记忆 | `avatar_service.py` | CRUD + verify + stats，4 类（profile/knowledge/event/relation），importance 1-5，confidence 0-1 |
| 记忆统计 | `AvatarSettingsView.vue` memory tab | 5 张统计卡（4 类 + verified），按类型筛选 |
| 灵感工作流 | `avatar_service.py` | 模板化生成（4 领域×4 模板），batch_id，select 生成 prompt 模板，execute/feedback/discard |
| 灵感状态机 | `models/avatar.py` `AvatarInspiration.status` | generated/selected/executing/completed/discarded |
| 事件总线 | `avatar_service.py` | inspiration.generated / inspiration.executed / avatar.memory.updated |

### 2.4 现状缺口（本次要补的）

| 缺口 | 现状 | 影响 |
|------|------|------|
| 上下文不压缩 | 固定取最近 20 条消息，不做摘要 | 长对话早期信息被挤出窗口，分身"健忘" |
| 对话标题不自生成 | 创建时写死"新对话" | 会话列表一堆"新对话"无法区分 |
| 记忆不注入对话 | 记忆表已落库但 `_build_context` 完全不读 | 记忆系统是死的，分身不记得用户画像 |
| 记忆无检索 | 无向量/关键词检索接口 | 无法按当前对话相关性取记忆 |
| 记忆无遗忘 | 只有 CRUD，无时间衰减/重要度衰减 | 记忆无限膨胀，噪声越来越多 |
| 形象仅 URL 字符串 | `image_url` 是手填 URL，无文件上传 | 用户无法上传自己的图 |
| 人形无合成 | human 形态是内置 SVG，不可换 | "形象合成"只停留在切换，不支持自定义人形 |
| 打断体验不完整 | 已能 abort，但无"继续/重写"按钮 | 打断后用户只能重发 |
| 移动端侧栏缺失 | 767px 以下 `__sidebar display:none` | 手机端看不到历史会话，无法切换 |

---

## 3. 深度优化方向（P0/P1/P2 优先级分级）

### 3.1 优先级定义

| 优先级 | 定义 | 本次排期 |
|--------|------|---------|
| P0 | 核心体验阻断，不做模块就不成立 | 本期必须交付 |
| P1 | 差异化亮点，显著提升"懂你"感知 | 本期尽力交付，可分期 |
| P2 | 远期愿景，依赖更强基础设施（向量库/本地模型/图像合成） | 本期只做接口预留 |

### 3.2 P0（本期必做）

| 编号 | 方向 | 功能点 | 对应章节 |
|------|------|--------|---------|
| P0-1 | 对话体验 | 流式打断后"继续/重写"操作 | F1.2 |
| P0-2 | 对话体验 | 对话标题自动生成（首条消息后异步生成） | F1.1 |
| P0-3 | 对话体验 | 上下文窗口压缩（超长历史摘要化） | F1.3 |
| P0-4 | 记忆深化 | 长期记忆按相关性注入对话 system prompt | F2.3 |
| P0-5 | 桌宠 | 桌宠 ↔ 人形切换动效与状态持久化完善 | F3.6 |
| P0-6 | 形象 | 自定义形象本地上传（图片文件而非 URL） | F4.2 |

### 3.3 P1（本期尽量做）

| 编号 | 方向 | 功能点 | 对应章节 |
|------|------|--------|---------|
| P1-1 | 记忆深化 | 记忆时间衰减与手动遗忘 | F2.4 |
| P1-2 | 记忆深化 | 记忆关键词检索接口 | F2.3 |
| P1-3 | 对话体验 | 对话分支/重生成单条回复 | F1.2 |
| P1-4 | 形象合成 | 人形形象自定义换装（配色/发型上传） | F4.2 |
| P1-5 | 主动服务 | 到期任务主动气泡提醒已有，补"勿扰时段" | F1.8 |
| P1-6 | 桌宠 | 四维数值过低时的主动关怀气泡 | F3.5 |

### 3.4 P2（远期预留接口）

| 编号 | 方向 | 功能点 | 对应章节 |
|------|------|--------|---------|
| P2-1 | 记忆深化 | 向量检索（embedding）替代关键词检索 | F2.3 |
| P2-2 | 形象合成 | AI 生成形象图（文生图） | F4.2 |
| P2-3 | 多分身 | 多人格并存与一键切换（现 6 人设仅前端 localStorage） | F6.3 |
| P2-4 | 语音 | 多音色 TTS 选择（现仅浏览器默认 voice） | F3.3 |
| P2-5 | 本地模型 | Ollama 真实接入（现仅前端列表占位） | F6.2 |

---

## 4. 功能需求详细拆解

> 编号规则：`F<线>.<序>`。每个功能点含：功能描述、验收标准（checkbox）、交互细节（含动画时长/偏移量数值）、状态全覆盖（默认/空/加载/错误）。

### F1 对话体验

#### F1.1 会话列表与标题管理

- 左侧 240px 会话列表，按 `updated_at` 倒序，显示标题 + 紧凑时间（`MM-DD HH:mm`）。
- 新建会话默认标题"新对话"；**用户发出第一条消息后，后端异步用 AI 生成 ≤12 字标题**（复用 `/ai/summarize` 同款非流式调用，temperature 0.3）。
- 悬停会话项显示删除按钮（`AppIcon name="trash"`，12px），删除前 `useModal.confirm` 二次确认，文案含会话标题。
- 支持重命名：双击标题进入编辑态，Enter 保存 / Esc 取消。

**验收标准**：
- [ ] 会话列表按 `updated_at` 倒序，空列表显示"暂无对话"
- [ ] 首条消息发送成功后 ≤5s 内标题从"新对话"变为 AI 生成的 ≤12 字标题
- [ ] AI 标题生成失败时保留"新对话"，不报错、不阻断对话
- [ ] 删除会话二次确认弹窗显示会话标题，确认后列表移除且当前会话清空
- [ ] 双击标题可重命名，Enter 保存、Esc 取消
- [ ] 当前会话项背景为 `--primary-soft`，文字色 `--primary`

**交互细节**：
- 会话项 padding 为 `var(--space-2) var(--space-3)`，hover 背景 `--bg-inset`，过渡 0.2s `--ease-soft`
- 标题单行省略（`white-space: nowrap; overflow: hidden; text-overflow: ellipsis`）
- 时间字号 `--text-xs`，色 `--text-low`
- 标题自动生成期间，列表项标题前显示 12px 转圈 icon，生成完切换为文字（200ms 淡入）
- 重命名输入框宽度撑满项，失焦或 Enter 提交

**状态全覆盖**：
- 默认态：会话列表正常展示，当前项高亮
- 空状态：无会话时居中显示"暂无对话"，字号 `--text-sm`，色 `--text-low`，padding `var(--space-6)`
- 加载态：列表区 5 行骨架屏（高度 `--row-h`，背景 `--bg-inset`， shimmer 动画 1.2s）
- 错误态：列表加载失败显示"加载失败，点击重试"，点击重新拉取；http 层已 toast 提示

#### F1.2 SSE 流式对话与打断

- 发送消息走 `POST /conversations/{id}/messages`，后端 SSE 逐块下发 `data: {type: content|done|error, content?, tokens?, error?}`。
- 前端先本地插入用户消息（id 前缀 `local-user-`），再流式渲染助手回复，光标 `▋` 闪烁 1s `step-end infinite`。
- **流式中发送按钮变为红色"停止"**（`variant="danger"`），点击调 `stopStreaming()`：`AbortController.abort()` + 规则模式 `ruleCancelled = true`。
- **打断后新增操作**（P0-1）：流式被中止时，助手消息气泡下方出现两个小按钮——「继续生成」「重写」。「继续生成」把已生成内容作为前缀，把用户原始消息重发一次；「重写」丢弃已生成内容，重新发送用户消息。

**验收标准**：
- [ ] 用户消息本地立即可见，助手回复逐字流式出现，带闪烁光标
- [ ] 流式中输入框右侧按钮变为 `--strawberry` 色"停止"，点击后 300ms 内流停止
- [ ] 流停止后助手气泡下方出现「继续生成」「重写」两个 pill 按钮
- [ ] 「继续生成」以已生成内容为前缀继续流式，不重复已输出文字
- [ ] 「重写」清空当前助手气泡，重新调用接口
- [ ] SSE 事件 `type:error` 时 toast 显示错误内容，不写入占位消息（现状是写 `[AI 服务异常]` 占位，P0 改为气泡内错误提示 + 重试按钮）
- [ ] 组件卸载时（路由切换）自动 abort，不残留流

**交互细节**：
- 用户气泡：右对齐，背景 `--primary`，文字 `--on-primary`，右下圆角 `--radius-sm`，max-width 75%
- 助手气泡：左对齐，背景 `--bg-inset`，文字 `--text-hi`，左下圆角 `--radius-sm`，max-width 75%
- 流式光标 `▋` 色 `--primary`，闪烁动画 `blink 1s step-end infinite`
- 消息进场：opacity 0→1 + translateY 8px→0，200ms `--ease-soft`
- 「继续生成」「重写」按钮出现在助手气泡底部，opacity 0→1 150ms，字号 `--text-xs`，hover 背景 `--primary-soft`
- 消息区自动滚到底部：用户手动上滚时暂停自动跟随（距底部 < 80px 才跟随）

**状态全覆盖**：
- 默认态：消息流正常，输入框可输入，发送按钮 `--primary`
- 空状态：无会话时居中显示"和第二分身聊聊吧～"，附引导"输入 / 唤起模板，或先配置 API Key"
- 加载态（流式中）：助手气泡带光标逐字出现；发送按钮禁用并变红"停止"
- 错误态：SSE error 事件 → 气泡内显示"生成失败：{error}" + 「重试」按钮；网络中断 → 保留已生成内容为 fallback 消息并 toast

#### F1.3 上下文窗口管理（P0-3）

- 现状 `MAX_HISTORY_MESSAGES = 20` 固定取最近 20 条。优化为：
  1. 当历史消息 token 估算总和超过阈值（约 6000 token）时，把**最早的、超出窗口的消息**打包成一段"历史摘要"注入 system，而非直接丢弃。
  2. 摘要由 `PromptBuilder` 新增 `compact_prompt(earlier_messages)` 生成，非流式调用，temperature 0.2。
  3. 摘要结果缓存到 `Conversation` 新字段 `compact_summary`（见第 6 章），下次对话直接复用，避免每次重新摘要。
- 引用文档仍注入 system，单文档截断 2000 字符（现状不变）。

**验收标准**：
- [ ] 历史 ≤20 条时行为与现状一致，不触发摘要
- [ ] 历史超过阈值时，最早消息被摘要替换为一段 ≤500 字的"此前对话摘要"system 消息
- [ ] 同一对话第二次发送时复用 `compact_summary`，不重复调用摘要接口
- [ ] 摘要失败时降级为直接截断（现状行为），不报错
- [ ] system prompt 顺序：persona → mode hint → compact summary → 引用文档 → 近期历史 → 当前消息

**交互细节**：
- 摘要对用户透明，不打断流式体验；仅在开发者控制台日志记录"触发上下文压缩"
- 压缩触发阈值在后端常量，前端不感知

**状态全覆盖**：
- 默认态：正常上下文构建
- 加载态：摘要生成期间用户消息先正常流式，摘要异步完成后下次生效
- 错误态：摘要失败降级截断，后端日志 warning

#### F1.4 思维模式切换

- 输入栏上方 5 个 pill 按钮：标准 / 深度 / 创意 / 批判 / 头脑风暴，对应 icon：chat/target/spark/warning/idea。
- 后端 `MODE_CONFIG` 已配置 temperature 与 hint，前端只负责传 `mode` 字段。
- 选中态：背景 `--primary-soft`，文字 `--primary`，边框 `--primary`；未选中：背景 `--bg-inset`，文字 `--text-mid`。

**验收标准**：
- [ ] 5 种模式切换后，下次发送请求 `mode` 字段正确传递
- [ ] deep 模式 temperature 0.2，brainstorm 1.0，与后端 `MODE_CONFIG` 一致
- [ ] 非法 mode 值后端回退 normal

**交互细节**：
- pill 按钮 padding `4px 10px`，圆角 `--radius-pill`，字号 `--text-xs`，gap 4px
- 选中态切换过渡 0.2s
- 移动端 767px 以下按钮 padding 缩为 `4px 8px`，字号 `--text-xs`（11px），自动换行

**状态全覆盖**：
- 默认态：normal 选中
- 禁用态：流式中切换模式不影响当前流，下次生效

#### F1.5 文档引用（RAG 雏形）

- 输入栏「引用」按钮，点击打开 Modal 选择文档，最多 3 篇。
- 选中的文档以 pill 形式显示在输入框上方，可单独 × 移除。
- 后端把引用文档内容截断 2000 字符后注入 system（现状）。

**验收标准**：
- [ ] 最多选 3 篇，选满后其余文档 checkbox 禁用
- [ ] 发送消息后引用标签清空（现状 `selectedDocs.value = []`）
- [ ] 引用文档内容以 system 消息注入，不污染用户消息
- [ ] 文档不属于当前用户时不注入（现状 `doc.user_id == self.user.id` 校验）

**交互细节**：
- 引用按钮选中后变为 `--lilac-soft` 背景 + `--lilac-ink` 文字 + `--lilac` 边框
- 引用 pill：背景 `--lilac-soft`，文字 `--lilac-ink`，padding `3px 8px`，× 按钮字号 13px
- Modal 内文档列表 max-height 40vh，滚动加载
- 选择列表空时显示"暂无文档可引用"

**状态全覆盖**：
- 默认态：未选引用，按钮无高亮
- 空状态：文档列表为空时 Modal 内显示引导"先去知识模块创建文档"
- 加载态：文档列表"加载中…"
- 错误态：加载失败静默（现状），按钮仍可点

#### F1.6 提示词模板系统

- 输入框为空时按 `/` 唤起模板选择 Modal。
- 8 个内置模板：总结文档/头脑风暴/翻译润色/文本润色/代码解释/复盘分析/制定计划/寻求建议。
- 支持自定义模板：名称 + 分类 + 内容，localStorage 持久化（key `venustech_ai_templates`）。
- 应用模板时把模板内容**前置**拼接到当前输入框（不覆盖已输入内容）。

**验收标准**：
- [ ] 空输入按 `/` 唤起模板 Modal，有内容时不唤起
- [ ] 模板搜索框实时过滤名称与分类
- [ ] 自定义模板可增删，刷新后保留
- [ ] 应用模板后 toast"已应用模板「{name}」"
- [ ] 内置模板不可删除，自定义模板右上角 × 可删

**交互细节**：
- 模板网格 2 列，gap 8px，max-height 320px 滚动
- 模板项 padding 12px，hover 边框 `--primary` + 背景 `--primary-soft`，150ms
- 图标容器 32×32，背景 `--primary-soft`，圆角 8px
- 自定义模板删除按钮 hover 背景 `--strawberry` 白字
- 新建表单展开在 Modal 顶部，字段：名称输入 / 分类下拉（自定义/工作/学习/写作/创意/其他）/ 内容 textarea 3 行

**状态全覆盖**：
- 默认态：模板 Modal 打开
- 空状态：搜索无结果显示"没有匹配的模板"
- 加载态：无（localStorage 同步读取）
- 错误态：名称或内容为空时 toast.warning"请填写模板名称和内容"

#### F1.7 人设与模型切换

- 顶部 persona-bar 三个按钮：人设 / 模型 / 画像。
- 人设 6 个内置（现状），模型 5 个（现状），均 localStorage 持久化。
- **P2 预留**：人设与模型未来应落库（现仅前端 localStorage，清缓存即丢失），本期不改存储，仅补 UI 一致性。

**验收标准**：
- [ ] 切换人设后 toast"已切换人设为「{name}」"，刷新后保持
- [ ] 模型列表分两组：强 AI（云端）/ 本地模型（离线）
- [ ] 每个模型卡片显示成本/速度标签
- [ ] 选中项右侧 `AppIcon name="check"`，色 `--primary`

**交互细节**：
- 人设按钮：emoji 头像 20px + 名称 600 + 描述 `--text-xs` `--text-low`，hover 边框 `--primary`
- 模型 Modal 宽 520px，分组标题 `--text-low` 12px
- 模型卡片左侧 emoji 24px，右侧信息 + 成本/速度 tag（背景 `--bg-panel`，圆角 4px）
- 移动端隐藏人设描述，仅显示名称

**状态全覆盖**：
- 默认态：显示当前人设与模型
- 空状态：无
- 加载态：无
- 错误态：无（纯前端切换）

#### F1.8 主动服务与勿扰时段（P1-5）

- 现状：`ConversationView.vue` 每 `reminderInterval` 分钟轮询 `/tasks?due_soon=true`，有待办时派发 `venustech-pet-action` 事件让桌宠气泡提醒。
- **新增勿扰时段**：在 reminder 设置中增加「勿扰时段」（默认 23:00-08:00），该时段内不派发提醒事件。
- 提醒文案：`有 {n} 个任务即将到期~`（现状）。

**验收标准**：
- [ ] 开启提醒后，到达轮询间隔且有待办时桌宠出现气泡
- [ ] 当前时间在勿扰时段内时不派发事件，桌宠不打扰
- [ ] 提醒开关与间隔 localStorage 持久化（key `venustech_reminder_settings`）
- [ ] 页面卸载时清除定时器

**交互细节**：
- 提醒开关为 checkbox，间隔 range 滑块（单位分钟，现状固定 30，本期扩展 5-120 步进 5）
- 勿扰时段为两个 time 输入（开始/结束）
- 桌宠气泡出现时动作切为 `thinking`，气泡文案来自事件 detail

**状态全覆盖**：
- 默认态：提醒开启，30 分钟间隔
- 关闭态：checkbox 关闭后定时器清除
- 加载态：无（本地轮询）
- 错误态：轮询失败静默 catch（现状），不影响主对话

---

### F2 记忆系统

#### F2.1 长期记忆 CRUD 与确认

- AvatarSettingsView 长期记忆 Tab，四类记忆：profile（用户画像）/knowledge（知识记忆）/event（事件记忆）/relation（关系记忆）。
- 每条记忆字段：类型色标 + 标题 + 内容 + 分类 tag + 来源 + 可信度% + 重要度 1-5 星 + 确认按钮 + 删除按钮。
- 「确认」按钮 toggle `is_verified`：未确认时普通按钮，确认后变为 `--mint` 色实心按钮"✓ 已确认"。

**验收标准**：
- [ ] 新增记忆表单：类型下拉 + 分类输入 + 重要度 1-5 + 标题（必填）+ 内容
- [ ] 标题为空时 toast.warning"请填写标题"
- [ ] 确认按钮 toggle 后列表刷新，按钮样式切换
- [ ] 删除记忆有后端删除，无二次确认（与现状一致，建议补确认）
- [ ] 记忆类型色标：profile 蓝 / knowledge 绿 / event 橙 / relation 灰（现状 hex 已在前端映射，改用令牌 `--sky-soft` / `--mint-soft` / `--butter-soft` / `--bg-hover`）

**交互细节**：
- 记忆卡片 padding `var(--space-3)`，头部行 gap 8px，flex-wrap
- 类型 pill：背景色 + 20% 透明，文字色同色系深 ink 色
- 重要度显示为 `⭐{importance}`，色 `--text-mid`，字号 `--text-xs`
- 确认按钮：未确认 border 1px `--line`；已确认背景 `--mint` 白字
- 卡片 hover 左侧出现 3px `--primary` 竖条（新增）

**状态全覆盖**：
- 默认态：记忆列表正常展示
- 空状态：居中 🧠 图标 48px + "还没有记忆，添加第一条记忆吧"
- 加载态：居中"加载中..."
- 错误态：toast.error"加载记忆失败"/"创建失败"/"删除失败"

#### F2.2 记忆统计与可视化

- 顶部 5 张统计卡：4 类记忆数 + 已确认数。
- 每卡：icon 24px + 数字 `--text-xl` 700 色 `--primary` + 标签 `--text-xs` `--text-mid`。
- 下方筛选按钮组：全部 / 👤 用户画像 / 📚 知识记忆 / 📅 事件记忆 / 🔗 关系记忆。

**验收标准**：
- [ ] 统计数字与列表数据一致
- [ ] 点击筛选按钮按类型重新拉取（page=1, page_size=50）
- [ ] 选中筛选按钮背景 `--primary-soft`，文字 `--primary`，边框 `--primary`

**交互细节**：
- 统计卡 grid 自适应 `minmax(120px, 1fr)`，gap `var(--space-2)`
- 筛选按钮 padding `6px 12px`，圆角 `--radius-pill`，字号 `--text-xs`

**状态全覆盖**：
- 默认态：5 张统计卡正常
- 空数据态：所有数字为 0
- 加载态：数字骨架屏
- 错误态：toast.error 提示

#### F2.3 记忆检索注入对话（P0-4 / P1-2）

- **现状缺口**：记忆表已落库，但 `conversation_service._build_context` 完全不读记忆。本期补上。
- **P0-4 最小实现**：每次对话构建上下文时，查询当前用户 `is_verified=true` 且 `importance>=4` 的记忆，取最近 10 条，拼成一段"关于用户你记得：..."的 system 消息注入。
- **P1-2 检索升级**：新增关键词检索接口 `POST /avatar/memories/search?query=xxx`，按标题/内容 LIKE 匹配，返回 top 5。对话时先用用户当前消息做 query 检索，再注入。
- **P2-1 远期**：embedding 向量检索，本期仅在 service 留 TODO 注释。

**验收标准**：
- [ ] 每次对话 system prompt 中包含已确认高重要度记忆摘要（≤800 字）
- [ ] 未确认的记忆不注入（避免 AI 把猜测当事实）
- [ ] 记忆数为 0 时不注入该段，不报错
- [ ] P1 检索接口：输入 query 返回相关记忆 top 5，按 importance desc + created_at desc 排序
- [ ] 注入的记忆段标注来源（如"用户于 X 确认的画像"），让 AI 知道这是事实而非猜测

**交互细节**：
- 此功能对用户透明，不增加 UI
- 对话消息气泡内不展示注入的记忆（避免干扰阅读）
- 开发者控制台日志打印"注入 N 条记忆"便于调试

**状态全覆盖**：
- 默认态：正常注入
- 空记忆态：不注入，对话正常进行
- 错误态：记忆查询失败时 catch 后继续对话（降级为无记忆上下文），日志 warning
- 超限态：注入记忆总字数超 800 时截断尾部

#### F2.4 记忆遗忘与衰减（P1-1）

- **现状缺口**：记忆只增不减。
- **新增规则**：
  1. 记忆 `created_at` 超过 180 天且 `importance<=2` 且 `is_verified=false` 时，前端记忆列表中该项置灰（opacity 0.5），并出现「归档」按钮。
  2. 归档后记忆不删除，但不再注入对话上下文（查询时排除 `archived=true`）。
  3. 用户可手动「遗忘」某条记忆：二次确认后软删除（现状 `SoftDeleteMixin` 已支持）。
- 后端 `AvatarMemory` 新增 `archived: bool = False` 字段（见第 6 章）。

**验收标准**：
- [ ] 超期低重要度未确认记忆在列表中置灰并出现「归档」按钮
- [ ] 归档后该记忆不再出现在对话注入中
- [ ] 归档记忆仍可在「已归档」筛选中查看
- [ ] 手动遗忘有二次确认，确认后软删除
- [ ] 已确认记忆永不自动归档（保护用户确认过的事实）

**交互细节**：
- 置灰卡片 opacity 0.5，300ms 过渡
- 「归档」按钮为 ghost 样式，hover 背景 `--butter-soft`
- 「遗忘」按钮为 `--strawberry` 描边，点击后 Modal 确认"遗忘后该记忆将不再被分身读取，确定？"
- 归档/遗忘后列表刷新，统计数同步更新

**状态全覆盖**：
- 默认态：正常记忆高亮
- 待归档态：置灰 + 归档按钮
- 已归档态：移到「已归档」分组，默认折叠
- 错误态：toast.error"操作失败"

#### F2.5 用户画像沉淀（深化）

- 现状 `ConversationView.vue` 的 `userTraits` 完全 localStorage，"分析我的文档"是 2 秒 setTimeout 假数据。
- **P1 深化**：把画像特质迁移到 `AvatarMemory`（`memory_type=profile`），复用记忆 CRUD。
- 「分析我的文档」按钮改为真实调用：后端遍历用户最近 30 篇文档，用 LLM 提取特质，批量写入 `avatar_memories`（source="文档分析"）。

**验收标准**：
- [ ] 画像面板读取的数据来自 `GET /avatar/memories?memory_type=profile`，而非 localStorage
- [ ] 「分析我的文档」按钮点击后真实调用后端，loading 期间按钮转圈
- [ ] 分析完成后 toast"画像分析完成，新增 N 个特质标签"
- [ ] 旧 localStorage 数据首次加载时自动迁移一次到后端（幂等）

**交互细节**：
- 特质 pill 按 category 着色：interest 蓝 / skill 绿 / style 紫 / value 金（沿用现状）
- 每个 pill 显示 confidence 百分比，hover 显示来源
- 删除特质 = 删除对应 memory 记录

**状态全覆盖**：
- 默认态：展示已有特质
- 空状态：无特质时提示"点击分析我的文档，让分身更了解你"
- 加载态：分析中按钮 loading + 禁用
- 错误态：toast.error"分析失败"，不影响已有特质展示

---

### F3 桌宠

#### F3.1 帧动画与动作系统

- 现状 12 种动作由 CSS keyframes 实现（非真实帧图）：idle-bounce 2s / happy-jump 0.5s / working-shake 0.3s / celebrate-spin 0.6s / dance-move 0.4s 等。
- `PetAvatar.mode=advanced` 时 `action_frames` JSON 预留了多帧动作 URL（现状未消费）。
- **本期**：保持 CSS 动画为默认实现；advanced 模式形象若有 `action_frames`，前端按帧序列播放（`idle: [url1,url2,...]`，每帧 200ms 切换）。

**验收标准**：
- [ ] 12 种动作均有对应 CSS 动画，切换动作时 300ms 内生效
- [ ] idle 动作每 8 秒有 30% 概率弹出随机气泡（现状）
- [ ] advanced 模式形象按 `action_frames` 逐帧播放，帧率可配置（默认 200ms/帧）
- [ ] 动作切换后经过 duration 自动回到 idle（现状 `actionTimer`）

**交互细节**：
- 动画时长汇总：
  - idle-bounce：2s ease-in-out infinite，translateY 0↔-5px
  - happy-jump：0.5s，translateY 0↔-10px + rotate ±5deg
  - working-shake：0.3s，translateX ±2px
  - celebrate-spin：0.6s，rotate 0→360 + scale 1→1.2
  - confetti：8 片，每片延迟 `i*0.05s`，1s 下落，最终 translate 至 `(i-4)*20px`
  - wave-arm：0.5s，右臂 rotate -30deg
- hover 时 `__body` scale(1.05)，0.3s `--ease-spring`
- 庆祝纸屑颜色 `hsl(i*45, 80%, 60%)`

**状态全覆盖**：
- 默认态：idle 动作循环
- 动作态：触发动作后播放 duration 再回 idle
- 禁用态：`enabled=false` 时桌宠整体隐藏
- 错误态：advanced 帧图加载失败回退 CSS 动画

#### F3.2 拖拽与悬浮

- 桌宠 `position: fixed`，`transform: translate3d(x, y, 0)` 定位，`will-change: transform`。
- mousedown 开始拖拽，mousemove 经 rAF 合帧（现状 `pendingPos` + `requestAnimationFrame`）。
- `dragging=true` 时 cursor: grabbing，否则 grab。
- 拖拽结束 emit `move` 事件，父组件持久化 `position_x/position_y`（后端 PetConfig 已有字段）。

**验收标准**：
- [ ] 拖拽流畅，mousemove 不阻塞主线程（rAF 合帧）
- [ ] 拖拽位移 > 3px 后吞掉紧跟的 click，不误触发抚摸
- [ ] 拖拽结束位置保存到后端 `position_x/position_y`
- [ ] 重启应用后桌宠出上次保存位置
- [ ] `draggable=false` 时 mousedown 不启动拖拽
- [ ] 拖拽时桌宠不被屏幕边缘卡住（限制在可视区内）

**交互细节**：
- 拖拽偏移量：`dragOffset = { x: e.clientX - pos.x, y: e.clientY - pos.y }`
- rAF 合帧：mousemove 频率可达 125Hz，逐事件写 ref 会多余重渲染，故用 `pendingPos` 缓存
- 边缘约束：x 范围 [0, innerWidth - 100]，y 范围 [0, innerHeight - 140]
- 拖拽中阴影加深 `--shadow-raise`，松手恢复 `--shadow-card`

**状态全覆盖**：
- 默认态：静止在原位，grab 光标
- 拖拽态：grabbing 光标 + scale(1.05)
- 禁用态：draggable=false 时光标 default，不可拖
- 错误态：位置保存失败时本地仍可拖动，下次回退旧位置

#### F3.3 气泡与 TTS 语音

- 气泡：桌宠上方 `bottom: 100%; margin-bottom: 8px`，`translateX(-50%)`，含小三角。
- 气泡显示时长由 `bubble_duration` 配置（默认 5s，范围 2-15s）。
- TTS：浏览器 `speechSynthesis`，rate/pitch/volume 可配，`speak_scene` 五档（never/remind/interact/celebrate/always）。
- **P2 远期**：多音色选择（现仅浏览器默认 voice）。

**验收标准**：
- [ ] 气泡出现/消失动画 0.3s `--ease-spring`，opacity + translateY 8px
- [ ] 气泡显示时长 = `bubble_duration` 秒，到时自动消失
- [ ] TTS 开启后，按 speak_scene 决定何时朗读：
  - never：不读
  - remind：仅到期任务提醒时读
  - interact：互动时读
  - celebrate：庆祝时读
  - always：所有气泡都读
- [ ] TTS 测试按钮可播放示例文本"你好，我是启明星，你的桌面伙伴！"
- [ ] 浏览器不支持 speechSynthesis 时 toast.error"当前浏览器不支持语音合成"

**交互细节**：
- 气泡 padding `8px 14px`，圆角 `--radius-md`，字号 `--text-sm`，背景 `--bg-raised`，阴影 `--shadow-raise`
- 气泡三角：6px 透明边 + 6px 顶色 `--bg-raised`
- TTS utterance 参数：rate = `config.tts_rate`（0.5-2.0 默认 1.0），pitch 0.5-2.0，volume 0-1 默认 0.8
- 新气泡出现时若旧气泡未消失，直接替换文本（不叠加）

**状态全覆盖**：
- 默认态：无气泡
- 显示态：气泡出现，TTS 同步朗读
- 关闭态：`show_bubble=false` 时不显示气泡，TTS 仍可朗读
- 错误态：TTS 不支持时按钮 disabled

#### F3.4 状态感知引擎

- 后端 `get_current_state` 综合三源：时间（8 时段）+ 任务（今日到期未完成数）+ 心情（最近 MoodLog.score）。
- 任务感知：work/afternoon 时段且 `todo_count>0` 时动作切为 `focused`，气泡"还有 N 个任务待完成，加油！"
- 心情感知：score 5/4→happy，3→neutral，2→anxious，1→sad，各带对应气泡。

**验收标准**：
- [ ] 不同时段返回正确 time_state 与默认动作（对照 TIME_STATES 表）
- [ ] 工作日 9-12 点且有待办时，动作变 focused
- [ ] 最近心情 score 为 1 时气泡变为"别难过，我陪着你"
- [ ] 任务/心情查询失败时降级为无待办/平静（现状 try/except），不阻断状态返回
- [ ] 状态感知可在设置中开关（`state_awareness_enabled`）

**交互细节**：
- 状态预览卡片 4 格：时间状态 / 当前动作 / 心情状态 / 待办任务数
- 每格：icon 24px + 标签 `--text-xs` + 值 `--text-sm` 600
- 气泡预览条：`--primary-soft` 背景 + `--primary` 文字，含 💬 icon
- 时间段动作网格：7 个时段卡片，time-range 色 `--text-mid`，time-action 色 `--text-hi` 600

**状态全覆盖**：
- 默认态：正常返回状态
- 关闭态：`state_awareness_enabled=false` 时不做任务/心情叠加，只返回时间状态
- 加载态：状态接口 loading 时"加载中..."
- 错误态：接口失败时静默，桌宠沿用上次动作

#### F3.5 四维陪伴数值与互动

- 四维：intimacy 亲密度 / satiety 饱食度 / mood 心情 / energy 精力，均 0-100，默认 60。
- 后端惰性衰减：读取时按 `stats_updated_at` 与现在时间差现算（`apply_stat_decay`），不在后台写库。
- 互动：抚摸 / 喂食 / 玩耍 / 休息，均提交**增量**（非绝对值），后端先衰减再叠加。
- **P1-6 主动关怀**：任一维度 < 20 时，桌宠每 30 分钟主动气泡提醒一次（如"我有点饿了..."）。

**验收标准**：
- [ ] 抚摸：intimacy +2，mood +3，动作 happy 1.5s
- [ ] 喂食：satiety +25，mood +5；satiety≥95 时气泡"人家吃饱啦~"不叠加
- [ ] 玩耍：mood +10，energy -10，intimacy +3；energy<20 时拒绝并动作 sleep
- [ ] 休息：energy +30，mood +5，动作 sleep 3s
- [ ] 数值上下限收敛在 0-100（后端负责，前端不 clamp）
- [ ] 60 秒轮询一次 `GET /pet/stats`，后端惰性衰减后返回
- [ ] 互动接口失败时仍播放动作/气泡，不让互动"毫无响应"
- [ ] P1-6：维度 <20 时每 30 分钟主动气泡一次

**交互细节**：
- 右键菜单底部两行进度条：亲密度（`#FF6B9D`）/心情（`#FFD93D`）
- 进度条高 6px，圆角 3px，宽度过渡 0.3s
- 心情文案映射：≥80 超开心 / ≥60 心情不错 / ≥40 一般般 / ≥20 有点低落 / <20 需要陪伴
- 互动按钮右侧显示当前百分比（如"喂食 60%"）

**状态全覆盖**：
- 默认态：四维数值正常显示
- 衰减态：长时间未打开后数值下降，气泡反映低落状态
- 边界态：饱食≥95 拒绝喂食，精力<20 拒绝玩耍
- 错误态：stats 接口失败保留上次数值，静默

#### F3.6 形态切换（桌宠 ↔ 人形）（P0-5）

- 现状：双击桌宠切换 pet/human 双 SVG，300ms 过渡，localStorage 持久化（key `venustech_pet_form`）。
- **P0-5 完善**：
  1. 切换时播放 wave 动作 1.5s（现状已有）。
  2. 切换中 `switching=true` 时 opacity 0 + scale(0.5) + rotate(180deg)，300ms。
  3. 形态状态应落库到 `PetConfig`（现仅 localStorage，清缓存丢失）。
  4. 人形尺寸：桌宠宽 100px，人形宽 90px、body 高 140px。

**验收标准**：
- [ ] 双击桌宠在 pet/human 间切换，300ms 动效
- [ ] 切换时 wave 动作播放 1.5s
- [ ] 形态选择落库，重启应用后保持
- [ ] 右键菜单「切换形态」按钮同样触发
- [ ] 人形状态下 hover 仍 scale(1.05)

**交互细节**：
- 切换过渡：opacity 1→0→1，scale 1→0.5→1，rotate 0→180deg→0，0.3s ease
- 人形 SVG viewBox `0 0 120 160`，桌宠 `0 0 120 140`
- 人形状态 `.pet.is-human`：width 90px，body height 140px

**状态全覆盖**：
- 默认态：pet 形态
- 切换中态：opacity 0 + scale 0.5 + rotate 180
- 人形态：显示人形 SVG
- 错误态：持久化失败时本地仍可切换，下次回退

---

### F4 形象管理

#### F4.1 形象 CRUD 与切换

- PetSettingsView 形象管理 Tab，grid 卡片展示所有形象。
- 每卡：预览区 120px 高 + 名称 + 描述 + 类型 tag（内置/自定义）+ 模式 tag（简单/进阶）+ 操作（使用/删除）。
- 无形象时后端自动创建默认"启明星"builtin simple。

**验收标准**：
- [ ] 形象列表按 sort_order 排列
- [ ] 「使用」按钮调用 `/pet/avatars/{id}/activate`，当前形象卡片显示"当前使用"badge
- [ ] 仅 custom 形象显示删除按钮，builtin 不可删
- [ ] 删除形象后列表刷新，若删除的是当前形象则回退默认
- [ ] 创建形象：名称（必填≤50）+ 描述 + 图片URL + 模式选择

**交互细节**：
- 卡片 grid `repeat(auto-fill, minmax(220px, 1fr))`，gap `var(--space-3)`
- 当前形象卡片 border 2px `--primary`
- badge 绝对定位 top 6px right 6px，`--primary` 背景白字 pill
- 预览区背景 `--bg-hover`，无图时居中 emoji 🐱 48px
- 「使用」按钮 primary sm，「删除」按钮 danger sm

**状态全覆盖**：
- 默认态：形象卡片网格
- 空状态：无形象时自动创建默认（后端），前端不显示空态
- 加载态："加载中..."
- 错误态：toast.error"加载形象失败"/"切换失败"/"删除失败"

#### F4.2 自定义形象上传（P0-6 / P1-4）

- **现状缺口**：`image_url` 是手填 URL 字符串，用户无法上传本地图。
- **P0-6**：
  1. 上传表单增加文件选择器（`<input type="file" accept="image/*">`），选择后上传到后端静态目录。
  2. 后端新增 `POST /pet/avatars/upload`，接收 multipart 文件，校验类型（png/jpg/webp/gif）与大小（≤2MB），返回可访问 URL。
  3. 创建形象时 `image_url` 自动填为上传返回的 URL。
- **P1-4 人形换装**：上传的图片若为人形立绘，可在 human 形态下替换内置人形 SVG（图片模式）。

**验收标准**：
- [ ] 可选择本地图片文件上传，≤2MB，格式 png/jpg/webp/gif
- [ ] 上传失败（类型不符/超大小）时明确报错，不创建形象
- [ ] 上传成功后 image_url 自动填入表单，预览区实时显示
- [ ] 自定义形象可在桌宠（pet 形态）或人形（human 形态）下使用
- [ ] 删除自定义形象时其图片文件一并清理（或标记待清理）

**交互细节**：
- 文件选择器：点击预览区虚线框唤起，框内提示"点击上传形象图"
- 上传中预览区显示 loading 转圈
- 上传成功预览区以 `background-size: contain` 居中显示
- 图片过大时压缩到最长边 512px（前端 canvas 压缩）
- 上传按钮 hover 边框 `--primary`

**状态全覆盖**：
- 默认态：表单空，预览占位
- 上传中态：预览区 loading + 按钮禁用
- 成功态：预览区显示图片，表单自动填 URL
- 错误态：toast.error 具体原因（"图片超过 2MB" / "不支持的格式"）

#### F4.3 形象模式（simple / advanced 帧动画）

- simple 模式：静态图 + 表情位置（eye_position / mouth_position JSON）。
- advanced 模式：多帧动作（action_frames JSON，如 `{idle: [url1,url2], work: [...]}`）。
- 本期 advanced 模式帧图播放接入 F3.1。

**验收标准**：
- [ ] simple 模式形象以静态图显示
- [ ] advanced 模式形象按 action_frames 逐帧播放 idle
- [ ] 每种动作（idle/work/sleep）可配置独立帧序列
- [ ] 帧序列缺失时回退 idle 帧

**交互细节**：
- 模式选择在创建表单下拉：简单模式（静态+表情）/ 进阶模式（多帧动作）
- advanced 模式展开后显示帧序列编辑器（每动作一组 URL 输入）
- 帧切换 200ms/帧

**状态全覆盖**：
- 默认态：simple 静态显示
- 帧动画态：advanced 循环播放
- 缺帧态：回退 idle
- 错误态：帧图加载失败显示占位

---

### F5 灵感工作流

#### F5.1 灵感生成

- AvatarSettingsView 灵感 Tab，顶部生成区：领域下拉（学习/开发/写作/通用/全部）+ 数量下拉（3/5/10）+ 生成按钮。
- 后端当前模板化生成（`INSPIRATION_TEMPLATES` 4 领域×4 模板），同批 `batch_id` 关联。
- **远期**：接入 LLM 基于长期记忆与最近活动生成（现 `inspiration_prompt` 已在 ai_service 预留）。

**验收标准**：
- [ ] 点击生成后按钮 loading"生成中..."，禁用
- [ ] 生成结果 prepend 到列表顶部，toast"生成 N 个灵感"
- [ ] 同批灵感 batch_id 相同
- [ ] 数量参数后端 1-10 约束（schema `count: ge=1, le=10`）
- [ ] 无灵感时空状态"点击上方按钮生成第一批灵感"

**交互细节**：
- 生成按钮 min-width 140px，loading 时禁用 opacity 0.5
- 灵感卡片 grid `repeat(auto-fill, minmax(280px, 1fr))`，gap `var(--space-3)`
- 状态 pill：generated 蓝 / selected 橙 / completed 绿 / discarded 灰
- 预估价值 tag 右上

**状态全覆盖**：
- 默认态：生成区 + 空列表
- 生成中态：按钮 loading
- 成功态：新卡片 prepend，淡入 200ms
- 错误态：toast.error"生成失败"

#### F5.2 灵感选择与提示词

- 点击灵感卡片「选择方向」→ 后端 `select_inspiration` 生成详细 prompt（现 `_build_prompt` 模板：角色设定+任务+背景+约束+输出格式）。
- 选中后卡片变为 selected 状态，顶部展开选中详情卡：标题 + 描述 + 领域 + 预估价值 + prompt 代码框 + 复制按钮。

**验收标准**：
- [ ] 选择后 status 变 selected，prompt 字段填充
- [ ] prompt 代码框 max-height 200px 滚动，`white-space: pre-wrap`
- [ ] 复制按钮调 `navigator.clipboard.writeText`，toast"提示词已复制"
- [ ] 同一时刻只展开一个选中详情卡

**交互细节**：
- 选中卡 border 2px `--primary`
- prompt 框背景 `--bg-hover`，圆角 `--radius-md`，padding `var(--space-3)`
- 复制按钮 sm primary，点击后变"已复制"1.5s 恢复

**状态全覆盖**：
- 默认态：灵感列表
- 选中态：详情卡展开
- 空 prompt 态：不显示 prompt 框
- 错误态：toast.error"操作失败"

#### F5.3 灵感执行与反馈

- 选中灵感可「执行灵感」→ status 变 completed，result 保存。
- 反馈：「有用」👍 / 「无用」👎，写入 feedback 字段。
- 未选中灵感可「丢弃」→ status 变 discarded，卡片 opacity 0.5。

**验收标准**：
- [ ] 执行后卡片左边框 3px `--mint` 绿
- [ ] 丢弃后卡片 opacity 0.5，操作按钮隐藏
- [ ] 反馈后卡片底部显示"反馈: 👍 有用 / 👎 无用"
- [ ] 执行/丢弃/反馈后列表刷新

**交互细节**：
- 按钮组 gap 6px，wrap 换行
- completed 卡片左边框 `--mint`，discarded 全卡 opacity 0.5
- 反馈文案字号 `--text-xs` `--text-mid`，margin-top 8px

**状态全覆盖**：
- 默认态：generated 状态新卡片
- 执行中态：按钮 loading
- 已完成态：绿边 + 反馈
- 已丢弃态：灰化

---

### F6 分身配置

#### F6.1 五档自动化

- 5 档卡片：L1 完全手动 / L2 建议不执行（默认）/ L3 低风险自动 / L4 大部分自动 / L5 完全自主。
- 每档：badge + 名称 + 描述，选中态 border 2px `--primary` + 背景 `--primary-soft`。
- 档位语义（后端 `operation_overrides` 可单项覆盖）：
  - L1：只在被问时回答，不主动操作
  - L2：主动提建议，需用户确认后执行
  - L3：自动打标签/摘要/整理，高风险需确认
  - L4：大部分操作自动，删除/覆盖/发送确认
  - L5：全自动，用户只看结果

**验收标准**：
- [ ] 点击档位卡片选中，选中态样式正确
- [ ] 保存后 `automation_level` 落库，刷新保持
- [ ] 默认 L2
- [ ] 档位切换不影响已配置的 operation_overrides

**交互细节**：
- 档位卡 grid `repeat(auto-fit, minmax(160px, 1fr))`，gap `var(--space-2)`
- badge 为 pill `--primary` 白字，字号 `--text-sm` 700
- hover border `--primary`，200ms
- 档位名称 600，描述 `--text-xs` `--text-mid` 1.4 行高

**状态全覆盖**：
- 默认态：当前档位高亮
- 切换态：点击即时高亮，保存后落库
- 错误态：toast.error"保存失败"

#### F6.2 模型配置

- 云端模型：开关 + provider 下拉（deepseek/openai/custom）+ 模型名输入。
- 本地模型：开关 + provider（ollama/lmstudio）+ 服务地址 + 模型名。
- **P2-5**：本地模型真实接入（现仅前端列表占位）。

**验收标准**：
- [ ] 关闭云端模型时隐藏 provider/name 字段
- [ ] 开启时显示字段并可编辑
- [ ] 本地模型配置校验 URL 格式
- [ ] 保存后落库 `cloud_model_*` / `local_model_*` 字段

**交互细节**：
- checkbox 行：label + 输入，gap `var(--space-3)`
- provider 下拉 flex 1 min-width 120px
- 错误态：toast.error

**状态全覆盖**：
- 默认态：按开关显示/隐藏字段
- 关闭态：字段隐藏
- 错误态：toast.error

#### F6.3 人格设定

- 字段：分身名称（默认"启明星"）+ 角色设定词 textarea + 回复长度（short/medium/long）+ 语言风格（casual/professional/cute）+ 创造力滑块 0-1（默认 0.7）。
- 人格设定词注入对话 system prompt（现 `PromptBuilder.system_persona` 固定文案，本期改为读取 `config.persona_setting` 拼接）。

**验收标准**：
- [ ] 分身名称保存后对话顶部 persona-bar 显示该名称
- [ ] persona_setting 注入对话 system，覆盖默认人设
- [ ] 创造力滑块步长 0.1，实时显示数值
- [ ] 回复长度/语言风格下拉正确传值

**交互细节**：
- textarea rows 4，resize vertical
- 创造力滑块右侧实时显示数值
- 下拉框与输入框同高 `--control-h`

**状态全覆盖**：
- 默认态：默认值填充
- 编辑态：可修改
- 错误态：toast.error

---

## 5. 移动端适配需求（375px 宽度）

> 移动端通过 Capacitor 7 套壳 Android 运行，前端代码复用。以下按 375px 宽度设计。

### 5.1 对话页移动端

| 现状（`@media max-width:767px`） | 本期补充 |
|----------------------------------|---------|
| 会话侧栏 `display:none` | 改为抽屉：顶部加汉堡按钮，点击从左滑出会话列表（宽 280px，遮罩 `--overlay`） |
| 消息气泡 max-width 85% | 保持，字号 14px |
| persona-bar 换行 | 保持，隐藏人设描述，仅显示名称 |
| 模式按钮 padding 4px 8px 字号 11px | 保持 |
| 输入栏 padding 缩减 | 保持，输入框 min-height 40px |

**移动端交互细节**：
- 会话抽屉：左滑入，translateX(-100%)→0，250ms `--ease-soft`；点击遮罩关闭
- 抽屉打开时底层内容不滚动（body overflow hidden）
- 发送按钮在流式中占满右侧，红色"停止"
- 输入框上方模式行可横向滚动（`overflow-x: auto`），不换行挤高
- 引用文档 Modal 在移动端占满底部，圆角顶部 `--radius-lg`
- 模板/人设/模型选择 Modal 宽度 100vw，安全区 padding-bottom 24px

### 5.2 桌宠设置页移动端

- Tab 导航 `tab-nav` 改为横向可滚动（`overflow-x: auto`，`scrollbar-width: none`），不换行。
- 配置区 `form-row` 在 375px 下纵向堆叠（align-items stretch）。
- 形象 grid 从 `minmax(220px,1fr)` 改为单列（`grid-template-columns: 1fr`）。
- 状态预览 4 格从 `minmax(140px,1fr)` 改为 2×2 网格。

### 5.3 Avatar 形象页移动端

- Tab 导航同上横向滚动。
- 记忆统计 5 张卡改为 2×3 网格（最后一张占满）。
- 灵感 grid 改为单列。
- 五档自动化 L1-L5 改为纵向列表（非 grid）。
- 表单输入框高度 ≥44px（符合移动端触控最小热区）。

### 5.4 触控与手势

- 所有可点元素最小热区 44×44px（触控规范）。
- 桌宠在移动端不悬浮（Capacitor 壳内无桌面悬浮能力），改为内嵌在伙伴 Tab 顶部展示区。
- 双击切换形态在移动端改为长按 500ms 触发（移动端双击易误触）。
- 右键菜单在移动端改为长按唤出底部 ActionSheet。
- 输入框弹出时页面自动上推（Capacitor keyboard plugin 配合）。

### 5.5 移动端状态全覆盖补充

- 网络中断（移动端常见）：对话发送失败时保留用户消息与已流式内容，toast"网络中断，已保留草稿"。
- 后台切回：App 从后台回到前台时自动刷新会话列表与桌宠状态（`resume` 事件）。
- 低电量：TTS 自动降级为不朗读（节省电量）。

---

## 6. 数据模型与 API 补充

> 以下为本次深度优化需要**新增**的字段与接口。现有模型见第 2 章，此处只列增量。

### 6.1 Conversation 模型新增字段

| 字段 | 类型 | 默认 | 说明 |
|------|------|------|------|
| compact_summary | Text | None | 上下文压缩后的历史摘要（F1.3） |
| auto_title | String(50) | None | AI 自动生成的短标题（F1.1） |

- 迁移：Alembic 新增两个 nullable 列，旧数据默认 NULL 不影响。

### 6.2 AvatarMemory 模型新增字段

| 字段 | 类型 | 默认 | 说明 |
|------|------|------|------|
| archived | Boolean | False | 是否已归档（F2.4 遗忘） |
| last_used_at | DateTime | None | 最近被对话引用时间（用于记忆活跃度，P1 远期） |

### 6.3 PetConfig 模型新增字段

| 字段 | 类型 | 默认 | 说明 |
|------|------|------|------|
| pet_form | String(10) | "pet" | 形态持久化（F3.6），替代 localStorage |
| dnd_start | String(5) | "23:00" | 勿扰时段开始（F1.8） |
| dnd_end | String(5) | "08:00" | 勿扰时段结束 |

### 6.4 新增 API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/conversations/{id}/auto-title` | 异步生成会话短标题（F1.1） |
| POST | `/avatar/memories/search` | 关键词检索记忆，query + top_k，返回相关记忆（F2.3） |
| POST | `/avatar/memories/{id}/archive` | 归档/取消归档记忆（F2.4） |
| POST | `/pet/avatars/upload` | 上传形象图片，multipart，返回 URL（F4.2） |
| PATCH | `/pet/config/pet-form` | 更新形态（F3.6），或并入现有 PATCH `/pet/config` |

### 6.5 既有 API 变更

- `POST /conversations/{id}/messages` 后端 `_build_context` 增加记忆注入步骤（F2.3），返回结构不变。
- `PATCH /avatar/config` 已支持全量字段，人格设定 `persona_setting` 接入 `PromptBuilder.system_persona` 拼接。

---

## 7. 用户故事

### 故事一：深夜赶论文的学生

> 晚上 23:30，小陈在写课程论文。桌宠在屏幕角落做着"阅读"动作，气泡偶尔冒"夜深了，早点休息哦"。他卡住了，点桌宠一下，分身弹出"让我想想..."。他在对话页把刚写的文献综述作为引用文档（3 篇以内），切到"深度"思维模式，问"这段论证有什么漏洞？"。流式输出逐字出现，他边看边改。中途觉得方向跑偏，点"停止"，再点"重写"，分身换了个角度。完成后他把对话里的结论手动存成知识文档，分身自动建议了 3 个标签。

**涉及功能**：F1.2 流式打断重写 / F1.4 深度模式 / F1.5 文档引用 / F3.4 深夜状态 / `/ai/suggest-tags`。

### 故事二：忘记任务的自由职业者

> 上午 10 点，小林打开启明星。桌宠在 9-12 点时段做"认真工作"动作。他有 3 个任务今日到期未完成，桌宠气泡"还有 3 个任务待完成，加油！"。他点击气泡，分身展开对话，主动说"你今天有 3 个任务到期，要不要我帮你拆一下优先级？"。他说"好"，分身按截止时间排了序。中午 12 点桌宠切到"吃饭休息"，他去吃饭。

**涉及功能**：F1.8 主动提醒 / F3.4 任务感知 / F3.4 时段动作。

### 故事三：想让分身记住自己的老用户

> 老周用了启明星三个月。他打开 Avatar 设置→长期记忆，看到画像 12 条、知识 8 条、事件 5 条。他点击"分析我的文档"，分身扫了他最近 30 篇笔记，新增了 3 条特质："偏好极简工具"、"对数据敏感"、"喜欢早起工作"。下次对话时，分身主动说"你之前提过喜欢早起工作，要不要现在安排晨间任务？"。他发现有一条三个月前的低重要度未确认记忆"好像喜欢猫"，置灰了，点"归档"。他不确认这条猜测，分身再也不提起。

**涉及功能**：F2.1 记忆 CRUD / F2.3 记忆注入对话 / F2.4 记忆归档遗忘 / F2.5 文档分析画像。

### 故事四：换桌宠形象的二次元用户

> 小美觉得默认桌宠看腻了。她去桌宠设置→形象管理，点"上传形象"，选了自己画的猫娘立绘（PNG，1MB），起名字"小喵"，选"进阶模式"。上传成功后预览区显示立绘。她点"使用"，桌宠瞬间换成小喵。双击桌宠切到"人形"形态，她把立绘也设为人形图片。她还在右键菜单点"跳舞"，小喵开始 dance 动画。她摸了摸小喵，亲密度 +2，小喵气泡"好好摸~"。

**涉及功能**：F4.1 形象 CRUD / F4.2 本地上传 / F3.6 形态切换 / F3.1 动作 / F3.5 互动数值。

### 故事五：手机上临时问分身

> 小陈在地铁上，打开 Capacitor 套壳的启明星 Android 应用。会话列表通过左上角汉堡按钮抽屉打开，他切到上周的"论文思路"对话。输入框弹起时页面上推，他打字"帮我列三个论文切入点"。分身流式回复。途中信号断了一下，已输出的内容保留在气泡里，toast"网络中断，已保留草稿"。连上后他点"继续生成"。

**涉及功能**：5.1 移动端抽屉 / F1.2 流式 + 保留草稿 / F1.2 继续生成。

### 故事六：被分身主动关怀的低落用户

> 老周连续加班一周没打开启明星。周五晚上打开，桌宠四维数值因惰性衰减：心情掉到 15，精力掉到 10。桌宠动作变 sleep，气泡"需要陪伴...你还好吗？"。他点桌宠"休息"，精力 +30，心情 +5，桌宠动作慢慢变回 idle。他在对话里说"这周太累了"，分身基于记忆知道他在赶项目，说"我记得你上周在做 XX 项目，要不要这周剩下的任务我帮你压一压？"。

**涉及功能**：F3.5 惰性衰减 / F3.5 主动关怀气泡（P1-6）/ F2.3 记忆注入 / F3.4 心情感知。

---

## 8. 验收标准（模块级）

### 8.1 对话体验

- [ ] 首条消息后 ≤5s 自动生成 ≤12 字会话标题，失败回退"新对话"
- [ ] SSE 流式逐字输出，带闪烁光标，发送/停止按钮切换正确
- [ ] 流式中止后出现「继续生成」「重写」按钮，二者行为正确
- [ ] 历史超阈值时自动摘要压缩，`compact_summary` 落库复用
- [ ] 5 种思维模式 temperature 与后端 `MODE_CONFIG` 一致
- [ ] 文档引用最多 3 篇，注入 system 不污染用户消息
- [ ] 无 API Key 时规则降级 + 学习意图走领域引擎，不报错
- [ ] 上下文自动滚动到底部，用户上滚时暂停跟随

### 8.2 记忆系统

- [ ] 长期记忆四类齐全，CRUD + 确认 + 归档 + 软删除可用
- [ ] 每次对话注入已确认高重要度记忆（≤800 字），未确认不注入
- [ ] 记忆关键词检索接口返回 top 5
- [ ] 超 180 天低重要度未确认记忆自动置灰归档
- [ ] 画像特质迁移到后端，分析文档真实调用 LLM
- [ ] 记忆统计数字与列表一致

### 8.3 桌宠

- [ ] 12 种 CSS 动画动作切换流畅，duration 后回 idle
- [ ] 拖拽 rAF 合帧，位置落库，边缘约束，dragMoved 防误触
- [ ] 气泡时长可配，TTS 按场景朗读，不支持时降级提示
- [ ] 状态感知综合时间/任务/心情，失败降级不崩溃
- [ ] 四维数值惰性衰减，增量互动，边界拒绝（饱/累）
- [ ] 形态切换 300ms 动效，状态落库
- [ ] 庆祝纸屑 8 片正确播放

### 8.4 形象管理

- [ ] 形象 CRUD + activate，builtin 不可删
- [ ] 本地图片上传 ≤2MB，类型校验，自动压缩预览
- [ ] simple/advanced 两种模式渲染正确
- [ ] 当前形象 badge 显示正确

### 8.5 灵感工作流

- [ ] 生成灵感 batch 关联，状态机 generated→selected→completed/discarded 正确
- [ ] 选中后生成 prompt，可复制
- [ ] 反馈（有用/无用）落库并在卡片显示

### 8.6 分身配置

- [ ] 五档自动化选择落库，默认 L2
- [ ] 云端/本地模型配置按开关显隐
- [ ] 人格设定 persona_setting 注入对话 system

### 8.7 移动端

- [ ] 375px 宽度下所有页面可用，无横向滚动
- [ ] 会话抽屉滑入滑出正常
- [ ] 触控热区 ≥44px
- [ ] 网络中断保留草稿
- [ ] 后台切回自动刷新

### 8.8 设计令牌与主题

- [ ] 本模块所有颜色使用 `variables.scss` 令牌，不出现裸 hex（除 DesktopPet.vue 中 SVG 渐变与纸屑 hsl）
- [ ] 四套主题（奶油糖果/国风雅集/深渊档案/史诗典藏）切换后本模块无视觉错乱
- [ ] 暗色主题下气泡/卡片对比度达标

---

## 9. 风险与依赖

### 9.1 技术风险

| 风险 | 影响 | 缓解 |
|------|------|------|
| 上下文摘要额外调用 LLM，增加 token 成本 | 长对话每次多一次非流式调用 | 摘要结果缓存到 `compact_summary`，同一会话只摘要一次；摘要失败降级截断 |
| 记忆注入占用 system 长度，可能挤占对话历史 | 早期对话被挤出 | 注入记忆限制 ≤800 字，importance<4 与未确认不注入 |
| 本地上传图片在 Capacitor 壳内路径差异 | Android 上文件选择行为不同 | 用 `@capacitor/camera` 或 Filesystem 插件，Android 权限单独申请 |
| 惰性衰减在跨时区/夏令时下偏差 | 数值衰减不准 | 统一用 UTC 存储，前端展示转本地时区 |
| SSE 在 Android WebView 上兼容性 | 流式中断 | 降级为非流式轮询（P1 预留） |

### 9.2 依赖

| 依赖 | 来源 | 说明 |
|------|------|------|
| 任务到期数据 | 执行模块 TaskRepository.count_due_today_open | 桌宠任务感知依赖 |
| 心情记录 | 人生模块 MoodRepository.list | 桌宠心情感知依赖 |
| 文档内容 | 知识模块 DocumentRepository.get | RAG 引用与摘要依赖 |
| LLM 客户端 | `app.services.ai.client` | DeepSeek/Mock 双实现，Key 解密失败降级 Mock |
| 事件总线 | `app.core.event_bus` | 灵感生成/执行/记忆更新事件 |
| 设计令牌 | `frontend/src/styles/variables.scss` | 唯一视觉来源，四套主题 |
| Capacitor 7 | 移动端壳 | 375px 适配基础 |

### 9.3 不在本期范围

- 多分身并存（P2，现 6 人设仅前端 localStorage）
- 向量检索 embedding（P2，现用关键词 LIKE）
- AI 文生图生成形象（P2）
- 多音色 TTS 与第三方语音服务（P2）
- Ollama/LM Studio 本地模型真实推理接入（P2，现仅配置占位）
- 云端同步与跨设备记忆合并（三期）

---

> 本文档基于一/二/三期实际代码盘点撰写，所有现状描述均可在对应代码文件中验证。深度优化方向 P0 为本期必做，P1/P2 按排期推进。
