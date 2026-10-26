# ADR-0004 运行期数据与密钥：收敛 `var/`，配置单一入口

- 状态：**部分采纳**（约定与解析规则已落地；物理迁移待执行）
- 相关：[ARCHITECTURE.md](../../../ARCHITECTURE.md) §7；`backend/app/config.py`、`backend/.env.example`

## 背景

2026-10 审计实测：仓库内散落 **9 个运行期数据目录、29 个文件、20.92MB**：

| 目录 | 来源 | 问题 |
|---|---|---|
| `backend/data` | 真实库（1.41MB） | 正常，但与下述混放 |
| `backend/data_demo` | 演示数据（17.52MB） | 巨大，误提交风险 |
| `backend/data_hc` / `data_pet` / `data_tt` | 全仓零引用 | 孤儿，来源不可考 |
| `backend/data_tpl` / `data_tpl2` | 空目录 | 遗留 |
| `backend/data_smoke` / `data_smoke3` | 测试残留 | 遗留 |

同时：

- `config.py` 默认数据目录是 `Path("./data")`（**相对当前工作目录**）。从仓库根启动会创建
  仓库根 `data/`，用户看到"数据消失"，且该目录**没被 gitignore 覆盖**。
- `.encryption_key` 与 `app.db` 放在一起，Windows 上 `os.chmod(600)` 不生效；密钥若丢失，
  加密字段（API Key、保险箱凭据）不可恢复。
- 配置模板 `.env.example` 只写了 4 个变量，`Settings` 实际有 12 个，其中还包含一个
  代码里不存在的幽灵变量 `VENUSTECH_AI_API_KEY`（`extra="ignore"` 静默丢弃）。

## 决策

1. **数据目录解析与 CWD 无关**：默认 `backend/data`（按 `config.py` 位置解析），
   可用 `VENUSTECH_DATA_DIR` 覆盖（演示库/分支隔离/测试都走它）。
2. **约定仓库内运行期数据统一放 `var/`**，且 `var/` 整体 gitignore；
   `backend/data*` 作为历史路径保留忽略规则，避免旧数据被误提交。
3. **配置唯一入口**：`backend/app/config.py:Settings`；`.env.example` 必须覆盖全部字段，
   安全默认（`DEMO_SEED=false`、CORS 不用 `*`），且不得包含幽灵变量。
4. **密钥备份契约**：备份 `app.db` 必须同时备份 `.encryption_key`；写入
   `docs/runbooks/backup.md`（规划）。
5. **物理迁移不在本轮执行**：迁移需停服、备份、改 4 个启动脚本，风险高且不可在沙箱内验证；
   给出 runbook 后由人工执行。

## 后果

- ✅ 从任何工作目录启动都指向同一个数据库，杜绝"幽灵第二份库"。
- ✅ 配置模板与代码对齐，不再"配了不生效"。
- ⚠️ `var/` 目前只是约定 + gitignore；`backend/data*` 实际目录仍在，Phase 1 由 runbook 迁移。
- ⚠️ Windows 下密钥文件权限无法靠 chmod 收紧，需依赖 NTFS ACL 或整盘加密（记录在案）。

## 替代方案

- 把默认数据目录改成系统标准位置（`%APPDATA%`）：对"本地优先"的源码运行模式反而增加困惑，
  且会让现有用户数据"搬家失联"。仅在打包（frozen）模式保留该分支。
