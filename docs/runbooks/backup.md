# 备份与恢复 Runbook

> 适用：本地单机部署（`ops/server/server.js` + FastAPI + SQLite）。
> 目标：换机、误删、升级失败时，能在 10 分钟内恢复到可用状态。

## 1. 必须备份的三样东西

| 对象 | 位置 | 丢失后果 |
|---|---|---|
| 数据库 | `$VENUSTECH_DATA_DIR/app.db`（默认 `backend/data/app.db`） | 全部业务数据丢失 |
| 加密主密钥 | `$VENUSTECH_DATA_DIR/.encryption_key` | 已加密字段（AI Key、保险箱凭据）**永久不可解**，换钥也无法恢复 |
| 前端产物 + 服务代码 | `frontend/dist`、`ops/server/` | 可重新构建/检出，非关键 |

> ⚠️ **只备份 `app.db` 不备份 `.encryption_key`，等于备份了一半。**
> 两者必须成对保存，且存放在加密介质上。

## 2. 手动备份（推荐，一分钟）

1. 停止后端进程（避免 WAL 未 checkpoint）。
2. 复制整个数据目录到一个带日期的文件夹：

```powershell
$data = "D:\YanYuas\PersonalDevelopmentPortfolio\VenustechSystem\backend\data"
$dest = "D:\Backups\qimingxing-$(Get-Date -Format yyyyMMdd-HHmm)"
New-Item -ItemType Directory -Path $dest -Force | Out-Null
Copy-Item "$data\app.db*" $dest
Copy-Item "$data\.encryption_key" $dest
```

3. 校验：`$dest` 里应有 `app.db`、`.encryption_key`；启动后端确认数据完整。

## 3. 应用内备份 / 恢复

- 入口：设置页「备份与恢复」（`backend/app/api/backup.py`）。
- 备份：生成 JSON 快照（`services/backup_service.py`），可选自动备份间隔。
- 恢复：**导入接口要求 `multipart/form-data`**。
  > ✅ 2026-10-26 已修复：前端改用 `http.postForm`（现位于 `@/kernel/http`）发送 multipart，
  > 备份导入不再 422（见 CHANGELOG Phase 1）。导入仍是**覆盖式**操作 —— 先按第 2 节做文件级备份。

## 4. 恢复步骤

1. 停止后端。
2. 把备份的 `app.db` 与 `.encryption_key` 放回 `$VENUSTECH_DATA_DIR`。
3. 启动后端：`start-dev.bat`（薄转发壳 → `ops\start.ps1 -Mode dev`；会自动跑迁移，Alembic 幂等）。
4. 验证：首页有数据；设置页能解密已存的 AI Key（说明密钥正确）。

## 5. 换机迁移清单

- [ ] 复制数据目录（含 `.encryption_key`）
- [ ] `setup.bat` 安装依赖
- [ ] 若用手机访问：旧机的 `.qm-token` **不要**沿用，让新机重新生成后在手机端重填
- [ ] 确认 `.git` 是否随项目目录备份（见 ADR/ARCHITECTURE D-12：`.git` 可能是外置 Junction）

## 6. Git 历史备份（容易被忽略的一层）

**坑**：本机 `.git` 是指向工作区外的 Junction（`C:\Users\21722\qimingxing-git-repo`）。
直接复制 `D:\...\VenustechSystem` 目录**不会**备份提交历史 —— 换机后历史全丢，
只剩工作区文件。

可靠做法：用仓库自带脚本（已封装 bundle 创建 + 校验 + 轮转）：

```powershell
# 预演：只打印计划，不写文件
pwsh -ExecutionPolicy Bypass -File ops\backup-git.ps1 -WhatIf

# 实际执行（默认写到 var/backups，只保留最近 5 个）
pwsh -ExecutionPolicy Bypass -File ops\backup-git.ps1

# 指定长期位置（推荐放到移动硬盘/网盘同步目录）
pwsh -ExecutionPolicy Bypass -File ops\backup-git.ps1 -Destination D:\Backups\venustech -Keep 10
```

脚本会：检测 `.git` 是否 Junction 并警告、`git bundle create --all`、`git bundle verify`
（校验失败即退出 1，避免"假备份"）、按数量轮转。

恢复（在空目录里）：

```powershell
git clone "D:\Backups\venustech\venustech-YYYYMMDD-HHmmss.bundle" VenustechSystem-restored
```

> 建议：**数据备份（app.db + .encryption_key）与历史备份（bundle）分开做**，两者都不能由对方替代。
> `var/backups/` 已被 gitignore，bundle 不会进仓库 —— **必须复制到仓库外**才算真正备份。
> 建议每周一次（或每次大改前），并把"最近一次 bundle 位置"记在密码管理器里。
> 长期方案（需停机窗口）：把 `.git` 迁回仓库内，让"复制项目目录"也能带走历史。
