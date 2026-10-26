# M03 Document 知识文档深度开发PRD

> 分支：`feature/document-deep` | 优先级：P0 | 预计工时：4天

## 一、模块定位

知识文档是启明星系统的"第二大脑"，承担个人知识库的存储、组织、检索与创作。支持文件夹层级管理、Markdown富文本编辑、标签体系、全文搜索。

**核心目标**：让用户的知识有序沉淀，随时可查可用

## 二、当前实现状态

### 已实现
- 文档资源管理器（D03）：文件夹树 + 文档列表
- 文档卡（D01）：标题、摘要、标签、字数、更新时间
- 文档编辑器（D04）：基础Markdown编辑
- 标签输入器（D05）：添加/删除标签
- 基础CRUD：创建、编辑、删除文档
- 文件夹基础管理

### 未实现/待完善
- 文件夹跳转（当前点击文件夹无响应）
- Markdown编辑器增强（工具栏、预览、快捷键）
- 全文搜索（当前仅标题搜索）
- 文档版本历史
- 文档导出（MD/PDF/HTML）
- 双向链接（[[]]语法）
- 文档关系图谱
- 模板系统
- 附件管理
- 阅读模式

## 三、深度开发功能清单

### P0 必须完成

#### F01 文件夹跳转与层级管理
- **需求**：点击文件夹进入该文件夹，显示子文件夹和文档；支持面包屑导航
- **实现**：
  - 文件夹树点击展开/折叠
  - 文档列表按当前文件夹筛选
  - 面包屑导航：根目录 / 文件夹1 / 子文件夹
  - 支持新建/重命名/删除文件夹
  - 拖拽文档到文件夹移动
- **数据模型**：folders表已有parent_id，需完善查询逻辑
- **验收**：文件夹层级可正常跳转，面包屑可回溯

#### F02 Markdown编辑器增强
- **需求**：提供完整的Markdown编辑体验，含工具栏、实时预览、快捷键
- **实现**：
  - 工具栏：加粗、斜体、标题、列表、链接、图片、代码块、引用
  - 编辑/预览双栏切换
  - 快捷键：Ctrl+B/I/K等
  - 自动保存（30秒防抖）
  - 字数统计
  - 光标位置记忆
- **技术**：CodeMirror 6 或 Milkdown
- **验收**：所有Markdown语法可正常编辑和预览

#### F03 全文搜索
- **需求**：支持搜索文档标题和内容，高亮匹配关键词
- **实现**：
  - 搜索框输入即时搜索（防抖300ms）
  - 搜索结果：标题 + 内容片段（关键词高亮）
  - 按文件夹/标签筛选搜索结果
  - 搜索历史记录
  - 快捷键：Ctrl+F聚焦搜索
- **技术**：SQLite FTS5全文搜索
- **验收**：输入关键词可搜到包含该词的文档，内容片段高亮显示

#### F04 文档版本历史
- **需求**：保存文档每次编辑的版本，可查看和恢复历史版本
- **实现**：
  - 每次保存自动创建版本快照
  - 版本列表：时间、字数、变更摘要
  - 版本对比：高亮增删内容
  - 一键恢复到历史版本
  - 版本保留策略：最近30天，或最多50个版本
- **数据模型**：`document_versions`表

### P1 高质量打磨

#### F05 双向链接
- **需求**：支持[[文档名]]语法创建双向链接，点击可跳转
- **实现**：
  - 编辑器中[[触发文档选择器
  - 链接文档显示反向链接列表
  - 未创建文档的链接显示为灰色，点击可创建
  - 链接自动更新（文档重命名时）
- **技术**：Markdown解析 + 链接索引表

#### F06 文档导出
- **需求**：支持导出为Markdown、PDF、HTML格式
- **实现**：
  - 单文档导出
  - 文件夹批量导出（ZIP）
  - 导出时保留图片和附件
  - PDF导出支持自定义样式
- **技术**：前端html2pdf，后端pandoc（可选）

#### F07 模板系统
- **需求**：内置常用文档模板，支持自定义模板
- **实现**：
  - 内置模板：会议纪要、读书笔记、项目计划、日报/周报
  - 自定义模板：将文档保存为模板
  - 新建文档时选择模板
  - 模板变量：{{日期}}、{{标题}}等自动替换

#### F08 阅读模式
- **需求**：专注阅读视图，隐藏编辑工具栏
- **实现**：
  - 一键切换阅读/编辑模式
  - 阅读模式：居中排版、舒适行宽、优雅字体
  - 支持目录导航（根据标题生成）
  - 阅读进度条

### P2 二期预研

#### F09 文档关系图谱
- 可视化展示文档间的链接关系
- 力导向图，节点可拖拽

#### F10 附件管理
- 文档中插入图片/文件
- 附件本地存储，支持预览

#### F11 AI文档助手
- AI总结文档内容
- AI生成文档大纲
- AI润色/续写

## 四、技术实现要点

### 前端
- `DocumentExplorerView.vue`重构：文件夹树 + 文档列表 + 面包屑
- `DocumentEditor.vue`重构：CodeMirror 6 + 工具栏 + 预览
- 新增组件：`FolderTree.vue`、`Breadcrumb.vue`、`MarkdownToolbar.vue`、`VersionHistory.vue`、`DocSearchPanel.vue`、`BackLinkPanel.vue`
- `useDocument` composable扩展：全文搜索、版本管理、导出

### 后端
- `document_service.py`扩展：
  - 全文搜索（FTS5）
  - 版本快照管理
  - 双向链接索引
  - 导出功能
- `folder_service.py`扩展：层级查询、移动文档
- 新增模型：`DocumentVersion`、`DocumentLink`
- 新增迁移：0008_document_versions.py、0009_doc_links.py

### 性能
- 大文档（>10万字）虚拟滚动
- 全文搜索结果分页
- 编辑器懒加载（仅在打开文档时初始化）
- 自动保存防抖

## 五、数据模型扩展

### document_versions表
```sql
CREATE TABLE document_versions (
  id TEXT PRIMARY KEY,
  document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  content TEXT NOT NULL,
  word_count INTEGER,
  change_summary TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_versions_doc ON document_versions(document_id, created_at DESC);
```

### document_links表（双向链接）
```sql
CREATE TABLE document_links (
  id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  target_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  target_title TEXT, -- 目标文档标题（用于未创建文档）
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(source_id, target_id)
);
CREATE INDEX idx_links_source ON document_links(source_id);
CREATE INDEX idx_links_target ON document_links(target_id);
```

### documents表扩展
```sql
ALTER TABLE documents ADD COLUMN template_id TEXT;
ALTER TABLE documents ADD COLUMN is_template BOOLEAN DEFAULT 0;
```

## 六、API接口设计

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/documents` | 文档列表（按文件夹/标签筛选） |
| POST | `/api/v1/documents` | 创建文档 |
| GET | `/api/v1/documents/{id}` | 文档详情 |
| PUT | `/api/v1/documents/{id}` | 更新文档 |
| DELETE | `/api/v1/documents/{id}` | 删除文档 |
| GET | `/api/v1/documents/search?q=` | 全文搜索 |
| GET | `/api/v1/documents/{id}/versions` | 版本列表 |
| GET | `/api/v1/documents/{id}/versions/{vid}` | 版本详情 |
| POST | `/api/v1/documents/{id}/versions/{vid}/restore` | 恢复版本 |
| GET | `/api/v1/documents/{id}/backlinks` | 反向链接 |
| GET | `/api/v1/documents/{id}/export?format=` | 导出文档 |
| GET | `/api/v1/folders` | 文件夹树 |
| POST | `/api/v1/folders` | 创建文件夹 |
| PUT | `/api/v1/folders/{id}` | 更新文件夹 |
| DELETE | `/api/v1/folders/{id}` | 删除文件夹 |
| POST | `/api/v1/documents/move` | 移动文档到文件夹 |

## 七、验收标准

1. 文件夹层级可正常跳转，面包屑可回溯
2. Markdown编辑器支持所有常用语法和工具栏
3. 全文搜索可搜到文档内容，关键词高亮
4. 文档版本自动保存，可查看和恢复历史版本
5. 双向链接可正常创建和跳转
6. 文档导出为MD/PDF/HTML格式正确
7. 模板系统可正常使用
8. 阅读模式排版舒适
9. 大文档编辑无明显卡顿
10. 四套主题下编辑器显示正常

## 八、风险与依赖

- **依赖**：M09 Infrastructure（全文搜索索引、导出服务）
- **风险**：CodeMirror 6学习曲线较陡，可能需要额外时间
- **兼容性**：FTS5在旧版SQLite中可能不支持，需检测
- **数据迁移**：版本历史可能占用大量存储空间，需清理策略
