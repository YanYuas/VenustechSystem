# M09 Infrastructure 基础设施深度开发PRD

> 分支：`feature/infrastructure-deep` | 优先级：P0 | 预计工时：4天

## 一、模块定位

基础设施是启明星系统的"地基"，包含数据备份、通知系统、全局搜索、事件总线、认证、健康检查等跨模块能力。所有业务模块都依赖基础设施提供的服务。

**核心目标**：稳定可靠、性能优良、可扩展维护

## 二、当前实现状态

### 已实现
- 备份导出导入（backup.py）：基础备份功能
- 通知系统（notification.py）：基础通知
- 全局搜索（GlobalSearch.vue）：基础搜索
- 事件总线（event_bus.py）：模块间通信
- 认证（auth.py）：本地用户
- 健康检查（health.py）
- 统一API响应格式
- 跨平台数据目录

### 未实现/待完善
- 自动备份（定时）
- 备份列表管理
- 通知中心（历史通知、已读/未读）
- 全局搜索增强（全文搜索、分组、快捷键）
- 事件总线完善（更多事件类型、事件日志）
- 数据加密（AES-256）
- 缓存系统
- 日志系统
- 错误监控
- 性能监控
- 插件系统预留

## 三、深度开发功能清单

### P0 必须完成

#### F01 自动备份系统
- **需求**：支持定时自动备份，备份列表管理
- **实现**：
  - 自动备份频率：关闭/每日/每周
  - 备份时间设置（如每日23:00）
  - 备份保留数量（如最近10个）
  - 备份列表：时间、大小、类型（自动/手动）
  - 从备份恢复
  - 备份文件加密
  - 备份完成通知
- **技术**：APScheduler定时任务 + SQLite备份
- **验收**：定时备份正常触发，备份列表正确显示

#### F02 通知中心
- **需求**：统一的通知管理，历史通知可查看
- **实现**：
  - 通知中心面板（点击铃铛打开）
  - 通知列表：标题、内容、时间、已读/未读
  - 通知类型：任务提醒、复盘提醒、系统通知、AI消息
  - 全部已读按钮
  - 单条删除/全部清除
  - 未读数量红点
  - 通知点击跳转（任务/复盘等）
- **数据模型**：notifications表（已有），需完善
- **验收**：通知正常接收和展示，已读状态正确

#### F03 全局搜索增强
- **需求**：全局搜索支持全文搜索、分组、键盘导航
- **实现**：
  - 搜索范围：任务、文档、对话、复盘、项目、操作
  - 全文搜索（文档内容）
  - 结果分组展示
  - 关键词高亮
  - 键盘导航：↑↓选择，Enter跳转，ESC关闭
  - 搜索历史
  - 快捷键：Ctrl+K / Cmd+K
- **技术**：SQLite FTS5 + 前端键盘导航
- **验收**：搜索结果准确，键盘导航流畅

#### F04 数据加密
- **需求**：用户敏感数据加密存储
- **实现**：
  - 数据库文件加密（SQLCipher或应用层加密）
  - API Key加密存储（AES-256）
  - 用户设置密码（可选）
  - 导出文件加密
  - 加密密钥本地管理（从用户密码派生）
  - 无密码模式（默认密钥）
- **技术**：cryptography库 + PBKDF2密钥派生
- **验收**：敏感数据加密存储，导出文件需密码解密

### P1 高质量打磨

#### F05 事件总线完善
- **需求**：完善的事件驱动架构，模块间解耦
- **实现**：
  - 事件类型定义：任务完成、文档创建、复盘提交、项目归档等
  - 事件订阅/发布
  - 事件日志（调试用）
  - 异步事件处理
  - 事件重试机制
  - 模块间通过事件通信，不直接调用
- **技术**：现有event_bus.py扩展

#### F06 缓存系统
- **需求**：热点数据缓存，提升响应速度
- **实现**：
  - 内存缓存（LRU）
  - 缓存键管理
  - 缓存失效策略（TTL + 主动失效）
  - 缓存统计（命中率）
  - 首页聚合数据缓存
  - 搜索结果缓存
- **技术**：cachetools或自实现LRU

#### F07 日志系统
- **需求**：完善的应用日志，便于排查问题
- **实现**：
  - 日志分级：DEBUG/INFO/WARNING/ERROR
  - 日志文件轮转（按大小/日期）
  - 日志格式：时间、级别、模块、消息
  - 前端错误日志收集
  - 日志查看器（设置页）
  - 日志导出
- **技术**：Python logging + RotatingFileHandler

#### F08 错误监控
- **需求**：捕获和展示应用错误
- **实现**：
  - 全局异常捕获
  - 错误记录（时间、类型、堆栈、用户操作）
  - 错误列表（设置页）
  - 错误统计
  - 一键导出错误日志
  - 前端错误上报

### P2 二期预研

#### F09 性能监控
- API响应时间统计
- 前端性能指标
- 慢查询检测
- 性能仪表盘

#### F10 插件系统
- 插件加载机制
- 插件API
- 插件市场（云端）
- 插件沙箱

#### F11 云端同步
- 数据云端备份
- 多设备同步
- 冲突解决

## 四、技术实现要点

### 前端
- 新增组件：`NotificationCenter.vue`、`BackupManager.vue`、`GlobalSearch.vue`（增强）、`LogViewer.vue`、`ErrorMonitor.vue`
- 新增composables：`useBackup`、`useNotification`（增强）、`useCache`、`useLogger`
- 全局搜索：CommandPalette模式，覆盖层
- 通知中心：下拉面板 + Web Notification API

### 后端
- `backup_service.py`扩展：自动备份、备份列表、加密
- `notification_service.py`扩展：通知中心、已读管理
- `search_service.py`新增：全文搜索聚合
- `event_bus.py`扩展：更多事件、异步处理
- `cache_service.py`新增：LRU缓存
- `logging_config.py`新增：日志配置
- `error_handler.py`新增：全局错误捕获
- 新增迁移：0019_notifications_index.py、0020_backup_records.py

### 性能
- 缓存热点数据，减少DB查询
- 搜索使用FTS5，避免LIKE全表扫描
- 备份异步执行，不阻塞主进程
- 通知使用长轮询或SSE

## 五、数据模型扩展

### backup_records表
```sql
CREATE TABLE backup_records (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  file_name TEXT NOT NULL,
  file_size INTEGER NOT NULL,
  backup_type TEXT NOT NULL, -- auto/manual
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  expires_at DATETIME,
  encrypted BOOLEAN DEFAULT 0
);
CREATE INDEX idx_backups_user ON backup_records(user_id, created_at DESC);
```

### notifications表扩展
```sql
ALTER TABLE notifications ADD COLUMN is_read BOOLEAN DEFAULT 0;
ALTER TABLE notifications ADD COLUMN action_url TEXT;
ALTER TABLE notifications ADD COLUMN metadata TEXT; -- JSON
```

### event_logs表（调试用）
```sql
CREATE TABLE event_logs (
  id TEXT PRIMARY KEY,
  event_type TEXT NOT NULL,
  payload TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_events_type ON event_logs(event_type, created_at DESC);
```

### error_logs表
```sql
CREATE TABLE error_logs (
  id TEXT PRIMARY KEY,
  error_type TEXT NOT NULL,
  message TEXT NOT NULL,
  stack_trace TEXT,
  context TEXT, -- JSON: 用户操作、页面等
  source TEXT, -- frontend/backend
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_errors_created ON error_logs(created_at DESC);
```

## 六、API接口设计

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/backup/list` | 备份列表 |
| POST | `/api/v1/backup/create` | 手动备份 |
| POST | `/api/v1/backup/{id}/restore` | 从备份恢复 |
| DELETE | `/api/v1/backup/{id}` | 删除备份 |
| GET | `/api/v1/backup/settings` | 自动备份设置 |
| PUT | `/api/v1/backup/settings` | 更新自动备份设置 |
| GET | `/api/v1/notifications` | 通知列表 |
| PUT | `/api/v1/notifications/{id}/read` | 标记已读 |
| POST | `/api/v1/notifications/read-all` | 全部已读 |
| DELETE | `/api/v1/notifications/{id}` | 删除通知 |
| GET | `/api/v1/search?q=` | 全局搜索 |
| GET | `/api/v1/search/history` | 搜索历史 |
| GET | `/api/v1/events` | 事件日志（调试） |
| GET | `/api/v1/errors` | 错误日志 |
| POST | `/api/v1/errors` | 上报错误 |
| GET | `/api/v1/logs` | 应用日志 |
| GET | `/api/v1/system/health` | 健康检查 |
| GET | `/api/v1/system/stats` | 系统统计 |

## 七、验收标准

1. 自动备份按设定时间触发，备份列表正确
2. 通知中心正常接收和展示通知
3. 全局搜索支持全文搜索，键盘导航流畅
4. 敏感数据加密存储
5. 事件总线正常工作，模块间解耦
6. 缓存系统提升响应速度
7. 日志系统正常记录，可查看和导出
8. 错误监控正常捕获和展示
9. 备份恢复后数据完整
10. 所有API响应时间<500ms（本地）

## 八、风险与依赖

- **依赖**：所有业务模块（通知/搜索/备份都涉及业务数据）
- **风险**：SQLCipher可能增加依赖复杂度，可用应用层加密替代
- **性能**：自动备份可能影响性能，需在空闲时执行
- **安全**：加密密钥管理需谨慎，避免硬编码
- **兼容性**：FTS5需SQLite版本支持
- **数据迁移**：新增多表，需确保迁移顺序正确
