# 启明星系统 v1.1.0 发行说明

> **版本**：1.1.0 ｜ **发布日期**：2026-11-01 ｜ 类型：工程栈升级（无用户可见功能变更）
> 全量变更：[CHANGELOG](../CHANGELOG.md) ｜ 架构与债务：[ARCHITECTURE](../ARCHITECTURE.md) ｜ 许可：[LICENSE](../LICENSE)（MIT）

## 这个版本做了什么

**前端构建栈 Vite 5 → 8**（D-57），并同步升级 Vitest 3 → 5：

| 组件 | 版本 |
|---|---|
| vite | **8.3.5**（Rolldown + oxc + lightningcss 构建内核） |
| @vitejs/plugin-vue | **6.0.10** |
| vitest / @vitest/coverage-v8 | **5.0.5** |
| @types/node | **24.19.2** |
| esbuild | **0.28.2**（显式依赖：vite 8 不再随附，行为测试与本地门禁仍直接使用） |

配置迁移：分包改用 rolldown `codeSplitting.groups`；压缩改 `minify:'oxc'`（保留 drop console/debugger）；`strictPort: true` 让 5173 被占用时显式失败（配合启动脚本 `-Verify`）。

## 结果

- 578 个前端测试全绿（39 files）；构建产物 **1021.0 KB（−0.76%）**、CSS **239.9 KB（−1.0%）**；类型检查 / lint / format 全绿；
- **覆盖率口径 v2**：coverage 层换 AST-aware remapper（`ast-v8-to-istanbul`），同一测试集下统计粒度变化（隔离实验证明与 vite 版本无关）。双口径记录：v1 84.79% → v2 **71.01%** lines；阈值按规则显式重校准为 `{lines:70, branches:64, functions:49, statements:69}`，详见 [frontend.md §九](guides/frontend.md)。
- CI/启动链路：Node 24 已满足 vite 8 要求；`../.github/workflows/frontend.yml` / `../.github/workflows/windows-startup.yml` 注释与文档同步（含 esbuild 显式依赖警示、Vite 8 dev 观察点）。

## 升级说明（1.0.1 → 1.1.0）

- **必须重建前端依赖**：`cd frontend && rm -rf node_modules && npm ci`（不要用 `npm install`/`--legacy-peer-deps` 掩盖 peer 冲突）。
- 后端无变更，无数据库迁移；数据目录/启动方式不变。
- 视觉/浏览器回归未在本地自动化验证（Rolldown/lightningcss 可能影响极少数 CSS 边界）；如发现样式异常请提 issue 并附主题/页面。
- 已知限制：D-66（主密钥模式历史密钥语义）；Android 安装包暂未对外发行。

## 相关文档

- [README](../README.md) · [CHANGELOG](../CHANGELOG.md) · [ARCHITECTURE](../ARCHITECTURE.md)
- [开发规范](guides/development.md) · [前端规范（§九 覆盖率口径）](guides/frontend.md)
- 上一个版本：[v1.0.1](RELEASE_NOTES_v1.0.1.md) ｜ [v1.0.0](RELEASE_NOTES_v1.0.0.md)（首发）
