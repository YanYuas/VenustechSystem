# 分支开发指南

> 版本：v1.0 · 日期：2026-09-15
> 适用：启明星系统（VenustechSystem）本地开发
> 结论：**能开分支、能回退、也能实时观测效果** —— 但有 3 个坑必须先填，其中 1 个有丢数据风险。

---

## 一、结论速览

| 问题 | 答案 |
|------|------|
| 能不能开分支开发以便回退？ | **能。** 仓库已有 `feature/*` 惯例（现存 11 个 feature 分支） |
| 分支上能观测实时效果吗？ | **能，和主分支完全一样。** 不需要任何"分支预览环境" |
| 有坑吗？ | **有 3 个。** 其中 `app.db` 被 git 跟踪会导致切分支时数据被覆盖，必须先处理 |

---

## 二、为什么分支上能观测实时效果

**原理**：Git 分支只是一个指向某个提交的指针。执行 `git checkout feature/xxx` 之后，你的**工作目录里就是那个分支的代码**。

而开发服务器跑的就是工作目录，所以：

```
git checkout -b feature/eo-kernel-fusion
        ↓
工作目录 = 分支代码
        ↓
python -m uvicorn app.main:app --reload   → 后端 8765（改动自动重载）
npm run dev                               → 前端 5173（Vite HMR 热更新）
```

**行为与在 main 上开发完全一致**：改 Vue 组件 → 浏览器即时热更新；改 Python → uvicorn 自动重载。所见即所得。

> 这也是本地优先应用的优势：它是**跑在你自己机器上**的，不像 Web 服务需要部署一套"分支预览环境"。切分支 = 换代码，仅此而已。

---

## 三、必须先处理的 3 个坑

### 坑 1（严重 · 有丢数据风险）· `app.db` 被 git 跟踪

**现状**：运行期数据已收敛到 `var/`（gitignored）；`var/data/app.db` **不在版本控制里**。

**会造成什么**：

| 场景 | 后果 |
|------|------|
| `git checkout feature/x` | 数据库被替换成 **feature/x 提交时的快照**，你当前的数据消失 |
| 本地有未提交的数据改动时切分支 | git 可能**拒绝切换**；若强制则**覆盖本地数据** |
| 在分支里录入的测试数据 | 会跟着提交进入版本历史，污染仓库 |

**这条最危险的地方**是它**静默**：你以为只是"切了代码"，实际上数据也跟着换了。

**修法**（一次性，之后永久生效）：

```bash
# 1) 让 git 不再跟踪数据库文件（--cached 只动索引，不动你本地文件，数据安全）
# 历史命令（当时库还在 backend/data 下）；现在无需执行，库已不在索引里
git rm --cached <当时的数据库路径>

# 2) .gitignore 已追加：backend/data/ · backend/data_test/ · data-*/ · .workbuddy/
#    （本次已改好，无需手动操作）

# 3) 提交
git commit -m "chore: 数据库移出版本控制，避免切换分支时覆盖本地数据"
```

**修好后的效果**：`app.db` 变成**未跟踪文件**，而 `git checkout` **不会碰未跟踪文件** ——

> 切分支时代码变、数据不变。**这正是你想要的。**

---

### 坑 2 · Alembic 版本戳跨分支冲突

**现状**：后端每次启动都会自动跑迁移（`backend/app/main.py:43` → `run_migrations()`）。

**问题链**：
1. 分支新增迁移 `0012_xxx.py`，启动后自动应用 → 数据库里 `alembic_version` 表记为 `0012`
2. 切回 `main` → main 分支里**没有 0012 这个文件**
3. 启动后端 → Alembic 报 `Can't locate revision identified by '0012'`，**后端起不来**

**修法（推荐）：给分支一个独立的数据目录**

启明星的 `config.py:49` 支持用环境变量覆盖数据目录：

```python
data_dir: Path = _default_data_dir()   # 默认 ./data（相对后端工作目录）
# 环境变量前缀 VENUSTECH_ → VENUSTECH_DATA_DIR
# db_path = data_dir / "app.db"
```

所以只要在启动后端时指定：

```powershell
# PowerShell（当前终端会话有效）
$env:VENUSTECH_DATA_DIR = "./data-fusion"
cd backend
python -m uvicorn app.main:app --reload --port 8765
```

分支就会使用 `backend/data-fusion/` 下的 `app.db`，**与主库彻底隔离**：

- 分支随便跑迁移，主库不受影响
- 切回 main，主库的 `alembic_version` 还是 `0011`，后端正常启动
- 分支开发时录入的测试数据也不会污染你的真实数据

> `.gitignore` 已加入 `data-*/`，所以这类目录不会被误提交。

**替代方案**（临时用）：切回 main 前先手动降级
```bash
cd backend && python -m alembic downgrade -1
```
不如独立目录干净，容易忘。

---

### 坑 3 · `.workbuddy/` 未被忽略

**现状**：`git status` 会把 `.workbuddy/` 显示为未跟踪目录。若图省事执行 `git add -A`，会把智能体的记忆文件一起提交进仓库。

**修法**：已加入 `.gitignore`（本次已改好）。

---

## 四、推荐的完整工作流

```powershell
# ---------- 0. 前置检查 ----------
cd D:\YanYuas\PersonalDevelopmentPortfolio\VenustechSystem
git checkout main
git status                    # 期望：除了 .workbuddy/ 无其他待提交内容

# ---------- 1. 建分支（沿用项目现有 feature/* 惯例）----------
git checkout -b feature/eo-kernel-fusion

# ---------- 2. 启动（推荐：一键脚本 + 独立数据目录）----------
# 唯一实现是 ops\start.ps1；scripts\dev.ps1 只是兼容转发壳（等价写法）
powershell -ExecutionPolicy Bypass -File ops\start.ps1 -Mode dev -DataDir .\data-fusion
# 只想看它会做什么、不启动进程：
powershell -ExecutionPolicy Bypass -File ops\start.ps1 -Mode dev -DataDir .\data-fusion -WhatIf

# 或者手动分两个终端：
# 终端 A：后端（8765，--reload 自动重载；解释器必须用项目 venv）
$env:VENUSTECH_DATA_DIR = "D:\YanYuas\PersonalDevelopmentPortfolio\VenustechSystem\backend\data-fusion"
cd backend
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8765

# 终端 B：前端（5173，Vite HMR 热更新）
cd frontend
npm run dev
# 浏览器打开 http://localhost:5173  ← 实时看到分支上的改动
```

> ✅ 数据目录隔离由 `ops\start.ps1` 的 `-DataDir` 参数提供（`scripts\dev.ps1` 是兼容转发壳，
> 参数原样透传）。相对路径按 `backend\` 解析，实际注入后端的 `VENUSTECH_DATA_DIR` 一定是
> **绝对 Windows 路径**（Git-Bash 风格 `/d/...` 会丢盘符，导致后端打开另一个空库）。
> 不传该参数则沿用主库 `var/data/app.db`。
> 该参数是分支开发的安全阀 —— 分支上随便跑新增迁移，主库不受影响。

---

## 五、回退方式（四种粒度）

| 想做什么 | 命令 |
|---------|------|
| 丢弃**未提交**的改动 | `git restore .` 或 `git checkout -- .` |
| **切回主分支**（代码回到 main，数据不变） | `git checkout main` |
| 暂存当前进度但不提交，先切走 | `git stash` → 切回后 `git stash pop` |
| **彻底放弃整个分支** | `git branch -D feature/eo-kernel-fusion` |
| 保留分支但不合并 | 什么都不用做，分支独立存在，main 不受影响 |

**关键点**：只要分支没被 merge 进 main，**main 永远是干净的**。你随时可以 `git checkout main` 回到稳定状态。

---

## 六、一句话总结

**分支开发在这个项目上是完全可行且推荐的**，因为它是本地优先应用——切分支就是切代码，开发服务器照常热更新，实时效果与主分支毫无差别。

唯一的门槛曾经是真实库被纳入版本控制（当时在 `backend` 的 `data/` 下），会让"切分支"变成"切数据"。
该文件已于 2026-09-15 执行 `git rm --cached` 移出版本控制（见 `CONTRIBUTING.md` 数据与产物章节），
现在只需用 `VENUSTECH_DATA_DIR`（或 `ops\start.ps1 -DataDir`）给分支独立数据库。

---

## 附：相关代码位置（可复核）

| 事实 | 位置 |
|------|------|
| 启动自动迁移 | `backend/app/main.py:44` `run_migrations()` |
| 数据目录可覆盖 | `backend/app/config.py:56` `data_dir` |
| 数据库路径派生 | `backend/app/config.py:81-88` `db_path` / `db_url` |
| 环境变量前缀 | `backend/app/config.py:70` `env_prefix="VENUSTECH_"` |
| 启动器（唯一实现） | `ops/start.ps1` — `-Mode dev\|demo\|mobile`、`-DataDir`（→ 绝对 `VENUSTECH_DATA_DIR`）、`-WhatIf` |
| 兼容转发壳 | `scripts/dev.ps1`（等价 `-Mode dev [-DataDir]`）、根目录 `start-*.bat` |
| 前端开发环境 | `frontend/.env.development`（proxy `/api` → 8765） |
| 数据库不再被跟踪 | `git ls-files backend/data/` → 空（2026-09-15 `git rm --cached`） |
