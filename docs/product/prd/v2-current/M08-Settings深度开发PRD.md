# M08 Settings 设置深度开发PRD

> 分支：`feature/settings-deep` | 优先级：P1 | 预计工时：3天

## 一、模块定位

设置是启明星系统的"控制中心"，管理所有系统配置：AI模型、主题外观、数据管理、用户信息、快捷键等。是用户个性化定制系统的入口。

**核心目标**：让系统配置清晰易用，让个性化触手可及

## 二、当前实现状态

### 已实现
- 设置导航分组（H01）：基础分组导航
- AI模型配置（H02）：API Key配置
- 开关设置项（H03）：基础开关
- 数据导出导入（H04）：基础导出
- 内置主题切换器（H05）：四套主题切换
- 本地用户配置

### 未实现/待完善
- 完整的设置分组（通用/外观/AI/数据/快捷键/关于）
- AI模型完整配置（多提供商、多模型、测试连接）
- 主题自定义（颜色、字体、圆角）
- 数据管理（备份列表、恢复、清理）
- 快捷键配置
- 用户信息编辑
- 系统信息展示
- 检查更新
- 隐私与安全设置
- 实验室功能

## 三、深度开发功能清单

### P0 必须完成

#### F01 设置分组完善
- **需求**：设置页按功能分组，清晰导航
- **实现**：
  - 左侧导航分组：
    - 通用：语言、启动项、默认页面
    - 外观：主题、字体、缩放、动画
    - AI：模型配置、人设、隐私
    - 数据：备份、导出、清理、存储位置
    - 快捷键：全局快捷键配置
    - 关于：版本、更新、开源许可
  - 右侧显示对应设置项
  - 设置项即时生效（无需保存按钮）
  - 设置变更Toast提示
- **验收**：所有设置分组可正常切换

#### F02 AI模型完整配置
- **需求**：支持多AI提供商配置，可测试连接
- **实现**：
  - 提供商列表：DeepSeek、OpenAI、Claude、Gemini、本地(Ollama)
  - 每个提供商：API Key、Base URL、默认模型
  - 模型选择下拉框（自动获取可用模型）
  - "测试连接"按钮
  - 默认模型设置
  - API Key加密存储
  - 无Key时的引导配置
- **数据模型**：`ai_providers`表（与M04共用）
- **验收**：配置后可正常对话，测试连接有效

#### F03 四套主题切换完善
- **需求**：四套内置主题可流畅切换，配置持久化
- **实现**：
  - 主题预览卡片（四套主题缩略图）
  - 点击切换主题，即时生效
  - 主题配置本地存储
  - 跟随系统（亮色/暗色自动切换）
  - 主题切换动画
- **依赖**：四套CSS变量已就绪
- **验收**：四套主题可正常切换，刷新后保持

#### F04 数据管理完善
- **需求**：完整的数据备份、恢复、导出、清理功能
- **实现**：
  - 备份列表：显示所有备份（时间、大小）
  - 手动备份按钮
  - 自动备份设置（每日/每周/关闭）
  - 从备份恢复（二次确认）
  - 数据导出（全量/按模块）
  - 数据导入（从备份文件）
  - 缓存清理
  - 存储位置显示
- **依赖**：M09 Infrastructure备份系统
- **验收**：备份/恢复/导出/导入功能正常

### P1 高质量打磨

#### F05 主题自定义
- **需求**：用户可自定义主题颜色、字体、圆角
- **实现**：
  - 主色选择器
  - 背景色选择
  - 字体选择（内置字体+系统字体）
  - 圆角调节（小圆角/中圆角/大圆角）
  - 自定义主题保存
  - 重置为默认
- **技术**：CSS变量动态修改

#### F06 快捷键配置
- **需求**：用户可查看和修改全局快捷键
- **实现**：
  - 快捷键列表：功能 + 当前快捷键
  - 点击修改：按下新快捷键
  - 冲突检测
  - 恢复默认
  - 快捷键说明
- **数据模型**：`shortcut_configs`表

#### F07 用户信息编辑
- **需求**：用户可编辑个人信息
- **实现**：
  - 用户名
  - 头像（上传/默认头像）
  - 个人简介
  - 第二分身称呼用户的方式
  - 信息用于首页问候和AI对话

#### F08 系统信息与更新
- **需求**：展示系统信息，支持检查更新
- **实现**：
  - 版本号、构建时间
  - 技术栈信息
  - 数据目录路径
  - 检查更新按钮
  - 更新日志展示
  - 开源许可链接

### P2 二期预研

#### F09 隐私与安全
- 数据加密密码设置
- 应用锁（启动时需要密码）
- 隐私模式（不记录历史）

#### F10 实验室功能
- 实验性功能开关
- Beta功能预览
- 功能反馈入口

#### F11 多语言
- 中英文切换
- 界面国际化

## 四、技术实现要点

### 前端
- `SettingsView.vue`重构：左侧导航 + 右侧设置面板
- 新增组件：`SettingsNav.vue`、`AIConfigPanel.vue`、`ThemeSelector.vue`、`ThemeCustomizer.vue`、`DataManagementPanel.vue`、`ShortcutConfig.vue`、`UserProfilePanel.vue`、`AboutPanel.vue`
- `useTheme` composable扩展：主题切换、自定义主题
- `useSettings` composable新增：设置项管理

### 后端
- `settings_service.py`扩展：
  - 设置项CRUD
  - AI提供商管理
  - 快捷键配置
  - 用户信息
- 新增模型：`UserProfile`、`ShortcutConfig`
- 新增迁移：0017_user_profile.py、0018_shortcuts.py

### 性能
- 设置项即时保存（防抖）
- 主题切换不刷新页面
- 大文件导出时显示进度

## 五、数据模型扩展

### user_profiles表
```sql
CREATE TABLE user_profiles (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL UNIQUE,
  display_name TEXT,
  avatar TEXT,
  bio TEXT,
  ai_address_style TEXT DEFAULT '你', -- 你/您/昵称
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### shortcut_configs表
```sql
CREATE TABLE shortcut_configs (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  action TEXT NOT NULL, -- 功能标识
  keys TEXT NOT NULL, -- 快捷键组合，如 "Ctrl+K"
  enabled BOOLEAN DEFAULT 1,
  UNIQUE(user_id, action)
);
```

### settings表（通用键值对）
```sql
CREATE TABLE settings (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  key TEXT NOT NULL,
  value TEXT NOT NULL,
  UNIQUE(user_id, key)
);
```

## 六、API接口设计

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/settings` | 获取所有设置 |
| PUT | `/api/v1/settings` | 批量更新设置 |
| GET | `/api/v1/settings/{key}` | 获取单个设置 |
| PUT | `/api/v1/settings/{key}` | 更新单个设置 |
| GET | `/api/v1/ai/providers` | AI提供商列表 |
| POST | `/api/v1/ai/providers` | 添加提供商 |
| PUT | `/api/v1/ai/providers/{id}` | 更新提供商 |
| DELETE | `/api/v1/ai/providers/{id}` | 删除提供商 |
| POST | `/api/v1/ai/providers/{id}/test` | 测试连接 |
| GET | `/api/v1/user/profile` | 用户信息 |
| PUT | `/api/v1/user/profile` | 更新用户信息 |
| GET | `/api/v1/shortcuts` | 快捷键配置 |
| PUT | `/api/v1/shortcuts` | 更新快捷键 |
| GET | `/api/v1/system/info` | 系统信息 |
| POST | `/api/v1/system/check-update` | 检查更新 |

## 七、验收标准

1. 设置分组完整，所有分组可正常切换
2. AI模型配置完整，测试连接有效
3. 四套主题可流畅切换，配置持久化
4. 数据备份/恢复/导出/导入功能正常
5. 主题自定义可正常使用
6. 快捷键可查看和修改
7. 用户信息可编辑
8. 系统信息正确显示
9. 设置变更即时生效
10. 四套主题下设置页显示正常

## 八、风险与依赖

- **依赖**：M04 Conversation（AI配置）、M09 Infrastructure（备份系统）
- **风险**：API Key存储安全，需加密
- **兼容性**：自定义主题可能与组件样式冲突
- **数据迁移**：新增设置表需处理旧配置
