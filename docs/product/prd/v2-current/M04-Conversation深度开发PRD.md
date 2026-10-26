# M04 Conversation 第二分身深度开发PRD

> 分支：`feature/conversation-deep` | 优先级：P1 | 预计工时：5天

## 一、模块定位

第二分身是启明星系统的核心差异化功能，定位为"用户的第二大脑"。它沉淀用户的文档、习惯、思维方式，可模仿用户思维处理事务，全程本地运行保护隐私。弱AI（本地模型）负责日常事务，强AI（用户自带API）负责复杂任务。

**核心目标**：成为用户真正的数字分身，而非普通聊天机器人

## 二、当前实现状态

### 已实现
- 对话消息流（E01）：用户/AI消息展示
- 消息输入框（E02）：文本输入 + 发送
- 引用文档卡片（E03）：AI回复中引用的文档
- 分身状态指示（E05）：在线/思考中状态
- 无API Key降级：前端本地规则模式回复
- 基础对话历史保存

### 未实现/待完善
- 对话会话管理（新建/切换/删除会话）
- 提示词模板系统
- 文档引用与知识库检索
- 第二分身人设配置（性格、语气、背景设定）
- 本地模型接入（Ollama/LM Studio）
- 多模型切换（DeepSeek/OpenAI/Claude等）
- 思维模仿与用户画像沉淀
- 主动提醒与建议
- 对话导出
- 语音输入/输出

## 三、深度开发功能清单

### P0 必须完成

#### F01 对话会话管理
- **需求**：支持多个对话会话，可新建/切换/删除/重命名
- **实现**：
  - 左侧会话列表：显示会话标题、时间、消息数
  - 新建会话按钮
  - 点击切换会话
  - 右键菜单：重命名、删除
  - 会话搜索
- **数据模型**：conversations表（已有），需完善前端会话列表UI
- **验收**：可创建多个会话，切换时内容正确加载

#### F02 提示词模板系统
- **需求**：内置常用提示词模板，用户可快速调用
- **实现**：
  - 内置模板：总结文档、头脑风暴、翻译、润色、代码解释等
  - 自定义模板：用户可保存常用提示词
  - 输入框中"/"触发模板选择器
  - 模板支持变量：{{文档名}}、{{选中文字}}等
- **数据模型**：`prompt_templates`表

#### F03 文档引用与知识库检索
- **需求**：对话中可引用本地文档，AI基于文档内容回答
- **实现**：
  - 输入框中"@"触发文档选择器
  - 引用文档显示为卡片，可点击查看
  - AI回复中标注引用来源
  - RAG检索：基于用户文档库回答问题
  - 引用文档可一键跳转查看
- **技术**：本地向量检索（SQLite vec0 或 simple embedding）
- **验收**：@文档后AI回答基于该文档内容，标注引用来源

#### F04 第二分身人设配置
- **需求**：用户可配置第二分身的人设、性格、语气
- **实现**：
  - 预设人设：助手、导师、朋友、批评家、异性分身等
  - 自定义人设：姓名、性别、性格、背景故事、说话风格
  - 人设词自动注入系统提示词
  - 多套人设可切换
- **数据模型**：`persona_configs`表
- **验收**：切换人设后AI回复风格明显变化

### P1 高质量打磨

#### F05 本地模型接入
- **需求**：支持接入本地大模型（Ollama/LM Studio），全程离线运行
- **实现**：
  - 配置本地模型API地址（默认http://localhost:11434）
  - 自动检测可用模型
  - 模型选择下拉框
  - 流式输出支持
  - 本地模型运行状态指示
- **技术**：OpenAI兼容API格式

#### F06 多模型切换
- **需求**：支持多种AI模型，用户可按需切换
- **实现**：
  - 支持提供商：DeepSeek、OpenAI、Claude、Gemini、本地模型
  - 每个提供商配置API Key和Base URL
  - 对话中可切换模型（新消息生效）
  - 模型能力标签（强/弱、速度、成本）
  - 默认模型设置
- **数据模型**：`ai_providers`表

#### F07 用户画像沉淀
- **需求**：第二分身自动分析用户文档，沉淀用户画像
- **实现**：
  - 定期分析用户文档，提取兴趣、专业领域、写作风格
  - 用户画像面板：展示沉淀的特质标签
  - 画像用于AI回复时的个性化
  - 用户可编辑/删除画像标签
  - 全程本地处理，不上传
- **技术**：本地NLP分析 + 关键词提取

#### F08 主动提醒与建议
- **需求**：第二分身可主动提醒用户待办、给出建议
- **实现**：
  - 基于任务到期提醒
  - 基于文档内容给出学习建议
  - 桌宠气泡展示主动消息
  - 提醒频率可配置
  - 可关闭主动模式

### P2 二期预研

#### F09 思维模仿与生成
- 基于用户历史文档模仿用户思维
- 生成用户风格的文本
- "如果是我会怎么想"功能

#### F10 语音交互
- 语音输入（Whisper本地）
- 语音输出（TTS本地）
- 免手动对话模式

#### F11 插件系统
- 第二分身可调用插件（搜索、计算、画图等）
- Function Calling支持

## 四、技术实现要点

### 前端
- `ConversationView.vue`重构：左侧会话列表 + 右侧对话区
- 新增组件：`ConversationList.vue`、`MessageBubble.vue`、`PromptTemplateSelector.vue`、`DocReferencePicker.vue`、`PersonaConfigPanel.vue`、`ModelSelector.vue`、`UserProfilePanel.vue`
- `useConversation` composable扩展：会话管理、模板、引用、流式输出
- 流式输出：SSE或fetch ReadableStream

### 后端
- `conversation_service.py`扩展：
  - 会话CRUD
  - 提示词模板管理
  - RAG检索逻辑
  - 多模型调度
  - 用户画像分析
- `ai_service.py`新增：统一AI调用接口
  - 支持多提供商
  - 流式输出
  - 本地模型兼容
- 新增模型：`PromptTemplate`、`PersonaConfig`、`AIProvider`、`UserProfile`
- 新增迁移：0010_prompt_templates.py、0011_personas.py、0012_ai_providers.py

### 性能
- 对话历史分页加载（最近50条）
- 长对话滚动加载更多
- AI响应流式输出，减少等待感
- 本地模型调用超时处理

## 五、数据模型扩展

### prompt_templates表
```sql
CREATE TABLE prompt_templates (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  name TEXT NOT NULL,
  content TEXT NOT NULL,
  category TEXT DEFAULT 'custom', -- builtin/custom
  variables TEXT, -- JSON数组
  sort_order INTEGER DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### persona_configs表
```sql
CREATE TABLE persona_configs (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  name TEXT NOT NULL,
  avatar TEXT,
  gender TEXT,
  personality TEXT, -- 性格描述
  background TEXT, -- 背景故事
  speaking_style TEXT, -- 说话风格
  system_prompt TEXT, -- 生成的系统提示词
  is_active BOOLEAN DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### ai_providers表
```sql
CREATE TABLE ai_providers (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  name TEXT NOT NULL, -- DeepSeek/OpenAI/Claude/Local
  api_key TEXT,
  base_url TEXT,
  model TEXT NOT NULL,
  is_default BOOLEAN DEFAULT 0,
  enabled BOOLEAN DEFAULT 1,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### user_profiles表
```sql
CREATE TABLE user_profiles (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  trait TEXT NOT NULL, -- 特质标签
  category TEXT, -- interest/skill/style/value
  confidence REAL DEFAULT 0.5, -- 置信度
  source TEXT, -- 来源文档ID
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

## 六、API接口设计

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/conversations` | 会话列表 |
| POST | `/api/v1/conversations` | 创建会话 |
| GET | `/api/v1/conversations/{id}` | 会话详情 |
| PUT | `/api/v1/conversations/{id}` | 更新会话 |
| DELETE | `/api/v1/conversations/{id}` | 删除会话 |
| POST | `/api/v1/conversations/{id}/messages` | 发送消息（支持流式） |
| GET | `/api/v1/conversations/{id}/messages` | 消息历史 |
| GET | `/api/v1/prompt-templates` | 提示词模板列表 |
| POST | `/api/v1/prompt-templates` | 创建模板 |
| GET | `/api/v1/personas` | 人设列表 |
| POST | `/api/v1/personas` | 创建人设 |
| PUT | `/api/v1/personas/{id}/activate` | 激活人设 |
| GET | `/api/v1/ai/providers` | AI提供商列表 |
| POST | `/api/v1/ai/providers` | 添加提供商 |
| POST | `/api/v1/ai/chat` | 统一AI调用（流式） |
| GET | `/api/v1/user-profile` | 用户画像 |
| POST | `/api/v1/user-profile/analyze` | 触发画像分析 |

## 七、验收标准

1. 可创建/切换/删除多个对话会话
2. 提示词模板可正常调用，变量正确替换
3. @文档引用后AI基于文档内容回答，标注来源
4. 人设切换后AI回复风格明显变化
5. 本地模型（Ollama）可正常接入和对话
6. 多模型可切换，API Key正确使用
7. 用户画像自动沉淀，可查看和编辑
8. 主动提醒正常触发，桌宠气泡展示
9. 无API Key时降级为本地规则模式
10. 对话数据全程本地加密存储

## 八、风险与依赖

- **依赖**：M03 Document（文档引用）、M07 Pet（主动提醒气泡）、M08 Settings（AI配置）
- **风险**：本地模型质量参差不齐，需做好降级体验
- **隐私**：用户画像数据敏感，必须本地加密
- **成本**：强AI调用产生API费用，需提示用户
- **技术**：RAG检索在SQLite中实现较复杂，可能需要简化
