# 启明星系统 v1.0.1 发行说明

> **版本**：1.0.1 ｜ **发布日期**：2026-11-01 ｜ 类型：补丁版本（含 v1.0.0 后的依赖升级与债务清理）
> 全量变更：[CHANGELOG](../CHANGELOG.md) ｜ 架构与债务：[ARCHITECTURE](../ARCHITECTURE.md) ｜ 许可：[LICENSE](../LICENSE)（MIT）

## 这个版本修了什么

### 两个真实缺陷
- **项目时间线 / 项目导出 500（D-65，P2）**：只要项目关联过复盘记录，打开项目详情时间线或导出就会 `AttributeError`；现改为从复盘 `data` JSON 派生标题/导出正文，恢复正常。
- **文档图谱样式失效（D-64）**：`DocumentGraph.vue` 样式块缺 `lang="scss"`，嵌套选择器被浏览器忽略 → loading / 空态样式此前未生效；已补齐（Vite 8 升级调研时发现）。

### 安全与可靠性（P2）
- **加密密钥轮换原子化（D-58）**：salt / key / keyring 三处写入改为「临时文件 + fsync + `os.replace`」；任一步失败**整体回滚**、内存密钥不切换、原异常上抛，消除「新 key 已落盘但密钥环没写」导致旧密文不可解的风险。

### 依赖升级（自上版本后合入）
- **SQLAlchemy 2.1.6 / Alembic 1.20.1**（D-56）：5 个隐式 float 列显式 `Float`，迁移完整性三方对账（ORM/DDL/PRAGMA）一致。

### 体验小修（P3）
- toast 最多同时 50 条（超出淘汰最旧）+ 相同内容不重复堆叠；
- 输入框内不再触发 `Ctrl+Shift+N`；`Ctrl+]`/`Ctrl+S` 不再误吃 Shift 组合；
- 弹窗同一实例可重复关闭；重复任务无匹配星期时输出 debug 日志；
- SQLite 日期适配器显式注册，消除 Python 3.12+ 弃用告警。

## 质量数据

| 项 | 数值 |
|---|---|
| 后端测试 | **2026 passed**（0 failed / 0 skipped） |
| 后端覆盖率 | **99.75%**（阈值 99%） |
| 前端测试 | **578 passed / 39 files** |
| 前端覆盖率 | lines **84.79%** / branches 89.95% / functions 52.85%（阈值 {83,89,51,83}） |
| CI | backend / frontend / repo-guard / windows-startup / android-apk 全绿 |

## 升级说明（1.0.0 → 1.0.1）

- 无需新的数据库迁移变更；启动时自动执行既有迁移与维护。
- 升级前建议先在「设置 → 数据 → 导出备份」导出一份备份。
- 依赖变化：SQLAlchemy 2.1.6 / alembic 1.20.1（随本版本进入发行）。
- 已知限制：Vite 8 升级单独立项（D-57，spike 结论「可升级、需先重校准覆盖率口径」）；主密钥模式历史密钥语义（D-66）；单用户模型、无云同步。

## 相关文档

- [README](../README.md) · [CHANGELOG](../CHANGELOG.md) · [ARCHITECTURE](../ARCHITECTURE.md)
- [启动与自检 runbook](runbooks/startup.md) · [备份恢复 runbook](runbooks/backup.md)
- 上一个版本：[v1.0.0](RELEASE_NOTES_v1.0.0.md)
