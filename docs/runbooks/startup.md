# 启动与自检 runbook（dev / demo / mobile / setup）

- 适用范围：本机开发、演示演示、局域网/手机访问、首次安装。
- 唯一实现：`ops/start.ps1`（启动）、`ops/setup.ps1`（安装）。
  根目录 4 个 `.bat` 与 `scripts/dev.ps1` **只是薄转发壳**（3–17 行），不再复刻逻辑。
- 相关守护：`python scripts/audit_delivery.py`（单一实现 / 转发壳契约 / ASCII / BOM / 冒烟水分）。

## 1. 入口对照

| 入口 | 等价命令 | 做什么 | 数据目录 |
|---|---|---|---|
| `start-dev.bat` | `ops\start.ps1 -Mode dev` | 后端 `--reload` :8765 + 前端 Vite :5173 + 浏览器 | `var\data` |
| `start-demo.bat` | `ops\start.ps1 -Mode demo` | 同上，演示库；缺库自动 seed | `var\demo` |
| `start-mobile.bat` | `ops\start.ps1 -Mode mobile` | 后端仅回环 :8765 + 边缘服务 :3000 + 令牌 | `var\data` |
| `setup.bat` | `ops\setup.ps1` | venv / 依赖 / node_modules 安装 | — |
| `scripts/dev.ps1` | `ops\start.ps1 -Mode dev` | 兼容旧文档的转发壳 | 同上 |

常用参数：

```powershell
# 只预演：打印将执行的命令/数据目录，不启动任何进程
ops\start.ps1 -Mode demo -WhatIf

# 真自检：启动 → 等端口 + /api/v1/health → 自动停止 → 退出码 0/1
ops\start.ps1 -Mode dev -Verify

# 分支隔离：数据目录相对仓库根（2026-10-27 起）
ops\start.ps1 -Mode dev -DataDir .\var\data-feature-x
```

## 2. `-Verify` 行为（推荐用于"改完启动脚本身"或升级前排障）

1. 正常执行前置检查（venv / 依赖 / node_modules / 端口 / dist）。
2. `Start-Process` 拉起服务，**stdout/stderr 重定向到 `var\logs\<时间>-<服务>.out.log|.err.log`**。
3. 用 `Wait-UntilListening` 轮询端口（不再固定 sleep），后端额外 `GET http://127.0.0.1:8765/api/v1/health` 判断健康。
4. 输出 `[VERIFY] PASS/FAIL`，`taskkill /T /F` 结束整棵进程树，并等端口释放。
5. 退出码：**0 全部通过；1 任一失败**（失败时先看 `var\logs` 下对应服务的 `.err.log`）。

实测（2026-10-28，Windows 10，Node 24 / Python 3.11）：

| 模式 | 结果 | 说明 |
|---|---|---|
| dev | ✅ PASS | backend :8765 health 200 + frontend :5173；停止后端口全部释放 |
| demo | ✅ PASS | 使用 `var\demo`，真实库未被触碰 |
| mobile | ✅ PASS | backend 回环 + edge server :3000 |
| `cmd /c start-dev.bat -Verify` | ✅ exit 0，15.2s | 用户双击路径同样通过 |

## 3. 日志与排障

- 子进程日志：`var\logs\<时间>-<服务>.out.log` / `.err.log`（`var/` 已 gitignore）。
- **`ModuleNotFoundError: No module named 'app'`**：不要把 `uvicorn app.main:app` 放在仓库根裸跑；
  uvicorn 以 CWD 为 import 根，必须 `cd backend` 或用启动脚本（脚本已把 cwd 设到 `backend`）。
- **端口被占用**：`Get-NetTCPConnection -LocalPort 8765 -State Listen` 找到 PID，
  `taskkill /T /F /PID <pid>`；`-Verify` 失败通常也会在日志里留下 EADDRINUSE。
- **前端白屏/404**：dev 需要 `frontend\node_modules`；mobile 需要 `frontend\dist\index.html`（缺失会自动 build）。
- **手机连不上**：确认在同一 WiFi / Tailscale；访问 `http://<PC-IP>:3000`，首次需在设置里填访问令牌
  （`start-mobile.bat` 窗口会打印，来源 `.qm-token`；重配用 `node ops/server/rotate-token.mjs`）。
- **demo 没数据**：删除 `var\demo\app.db` 后重新 `start-demo.bat`（会自动 seed），不要动 `var\data`。
- 非交互环境（CI/管道/远程 shell）：脚本不会等待回车、不会开浏览器；用 `-Verify` 做确定性自检。

## 4. 与 CI 的边界

启动脚本是 **Windows-only**（`Get-NetTCPConnection` / `taskkill` / `.venv\Scripts`），
ubuntu runner 不跑它 —— 组件级由 `.github/workflows/backend.yml` /
`.github/workflows/frontend.yml` 覆盖（ruff / pytest / typecheck / vitest / build）。
**脚本本身**由 `.github/workflows/windows-startup.yml` 在 Windows runner 上守（见 §5）。

本机改完启动逻辑后，最低验证要求：

```powershell
ops\start.ps1 -Mode dev -WhatIf        # 计划正确
ops\start.ps1 -Mode dev -Verify        # 真启动 + 健康检查 + 清理
python scripts\audit_delivery.py       # 转发壳/唯一实现/ASCII/BOM 契约
```

## 5. CI 冒烟（Windows runner）

`windows-startup` workflow 是**启动脚本本身的回归测试**：在 `windows-latest` 上真实启动
dev 模式（后端 :8765 + 前端 :5173）→ 等端口 + `GET /api/v1/health` → `taskkill` 停止 →
退出码 0/1。脚本坏掉时 CI 直接变红，不再依赖"有人记得本机跑一次 `-Verify`"。

**触发条件**

- 手动：Actions → `windows-startup` → Run workflow（`workflow_dispatch`）；
- 自动：push 到 `main` 且改动命中 `ops/**`、`scripts/**`、`backend/**`、`frontend/**`
  或该 workflow 文件本身（`paths` 过滤 —— Windows 分钟约为 Linux 的 2×，不开 PR 触发）。

**跑什么（8 步）**

| # | 步骤 | 说明 |
|---|---|---|
| 1 | `actions/checkout@v4` | — |
| 2 | `actions/setup-python@v5`（3.11，cache pip） | 缓存键含 `backend/requirements*.txt` |
| 3 | `actions/setup-node@v4`（24，cache npm） | 缓存键含 `frontend/package-lock.json` |
| 4 | `python -m pip install -r backend/requirements-dev.txt` | **装到 PATH python（CI 无 venv）** |
| 5 | `npm ci`（cwd=`frontend`） | 满足 `Assert-FrontendDeps` 对 `frontend/node_modules` 的硬检查 |
| 6 | `python scripts/audit_delivery.py` | 先跑秒级的启动器契约（单一实现 / 薄转发壳 / ASCII / BOM / 冒烟水分） |
| 7 | `pwsh -NoProfile -ExecutionPolicy Bypass -File ops/start.ps1 -Mode dev -Verify` | 真启动 + 健康检查 + 自动停止 |
| 8 | `actions/upload-artifact@v4`（`if: failure()`） | 上传 `var/logs/**` → artifact `windows-startup-logs`（保留 7 天） |

**CI 没有 `backend/.venv`，dev 为什么能跑**：`ops/start.ps1` 的 `Resolve-Python 'dev'` 在 venv
缺失时会打印 `[WARN] project venv not found` 并**回退到 PATH 上的 `python`**；`demo` / `mobile`
分支则硬要求 venv（直接 `[ERROR] project venv not found`）。所以 CI 固定用 `-Mode dev`，
依赖由第 4 步装进同一个 PATH python。三条前置硬检查在 CI 的满足方式：

| 检查 | CI 里怎么满足 |
|---|---|
| 解释器（`Resolve-Python 'dev'`） | setup-python 提供 PATH `python` → 走 venv 缺失回退分支 |
| 后端依赖（`Test-BackendDeps` 探针 `import uvicorn, fastapi`） | 第 4 步 pip 安装成功 |
| 前端依赖（`Assert-FrontendDeps` 查 `frontend/node_modules`） | 第 5 步 `npm ci` |

**失败怎么看**

1. Actions 运行页底部 **Artifacts → `windows-startup-logs`** 下载；
2. 看 `var/logs/<时间>-backend-FastAPI.err.log`（uvicorn / 迁移 / 依赖问题）与
   `<时间>-frontend-Vite.err.log`（npm / vite 问题）；
3. 常见原因：依赖漏装（第 4/5 步）、`--reload` 下 app import 失败（日志里 `ModuleNotFoundError`）、
   端口被占用（runner 上罕见，日志里 `EADDRINUSE`）。

**注意**

- **首次真实结果只能在 push 后看到**：本机无法复现 runner 的"无 `backend/.venv` + 全新
  `frontend/node_modules`"环境；本机等价验证用 §2 的 `-Verify` 与 §4 的三条命令。
- 本 workflow 只覆盖 **dev**；demo / mobile 仍靠本机 `-Verify`（§2 实测表）覆盖，暂不进 CI。
