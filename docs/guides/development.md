# 启明星系统 · 开发规范

> 最后更新：2026-10-31

## 1. 分支策略

```
main              ← 主分支，始终保持可运行
  └─ feat/xxx     ← 功能分支
  └─ fix/xxx      ← 修复分支
  └─ mod/xxx      ← 模块开发分支（历史遗留，不再新建）
```

**规则**：
- 小改动可直接在 main 提交
- 大功能开 `feat/<模块>-<功能>` 分支，如 `feat/document-offline`
- Bug 修复开 `fix/<模块>-<问题>` 分支
- 分支完成后合并到 main，删除功能分支
- **不再新建 `mod-*` 分支**（历史遗留，已全部合并待清理）

**重要**：`.git/` 是目录联接，指向 `C:\Users\21722\qimingxing-git-repo`。如遇 `index.lock` 错误，需到目标目录删除锁文件：
```powershell
Remove-Item "C:\Users\21722\qimingxing-git-repo\*.lock" -Force
```

## 2. 提交规范

**格式**：`<类型>(<范围>): <简短描述>`

| 类型 | 用途 | 示例 |
|------|------|------|
| `feat` | 新功能 | `feat(task): 离线队列基础设施` |
| `fix` | 修复 bug | `fix(api): 后端不可达时离线队列失效` |
| `refactor` | 重构 | `refactor(services): 拆分 conversation_service` |
| `style` | 代码格式 | `style: 统一 ESLint 缩进` |
| `docs` | 文档 | `docs: 更新板块结构文档` |
| `chore` | 构建/工具/依赖 | `chore: 升级 Vue 到 3.5` |
| `test` | 测试 | `test: 补充认证边界用例` |
| `clean` | 清理 | `clean: 删除误提交的编译文件` |
| `merge` | 合并 | `merge: mod-tools -> main` |

**要求**：
- 描述用中文，简洁明了
- 一次提交只做一件事
- 涉及文件移动用 `git mv` 保持历史

### 2.1 PR 流程与协作治理（模板 / CODEOWNERS / Dependabot）

- **什么时候走 PR**：跨模块/多文件改动、依赖升级、外部贡献、需要留审查记录的改动。§1 的
  「小改动可直接在 main 提交」仍适用于单点修复；但**改 CI、迁移、启动器、依赖**建议一律走 PR。
- **PR 模板**：[`.github/pull_request_template.md`](../../.github/pull_request_template.md) —— 打开 PR 时自动带出，
  必须如实填写「影响面 / **已验证项** / 回滚方案 / 关联 issue」。已验证项的「全绿」口径与 §8 一致：
  `check_all --strict`（含 ruff / pytest / 架构守护 / 文档链接等）、前端
  `lint + format:check + typecheck + test + build`；勾不了就写原因（如「本机无 Node，build 由 CI 覆盖」），
  **不要空勾**。
- **CODEOWNERS**：[`.github/CODEOWNERS`](../../.github/CODEOWNERS) 为 `* @YanYuas`（单人维护）——
  所有 PR 自动请求维护者 review；强制力来自 main 分支保护里的 "Require review from Code Owners"
  （仓库设置，不是本文件能决定的）。
- **Dependabot**：[`.github/dependabot.yml`](../../.github/dependabot.yml) 每周一 09:00（Asia/Shanghai）
  检查 4 处依赖：`backend/`（pip）、`frontend/`（npm）、`ops/server/`（npm）、GitHub Actions。
  **分组策略**：同生态内按「一起升级更安全」分组（pytest 生态 / FastAPI 栈 / DB 栈 /
  前端构建-测试-lint 工具链 / Capacitor），且只有 **minor + patch** 归组；**major 升级单独开 PR**，
  强制人工评估破坏性变更。Dependabot PR 的合并口径同普通 PR：至少跑对应门禁
  （后端 ruff + pytest，前端 lint + test + build，或直接 `check_all --strict`）。
- **Issue 模板**：[`.github/ISSUE_TEMPLATE/`](../../.github/ISSUE_TEMPLATE) 含 bug / feature 两个模板
  （自动带出复现步骤 / 环境 / 验收标准），新建 issue 时选择即可。

## 3. 后端规范（FastAPI + Python）

### 3.1 分层架构

```
backend/app/
├── api/              ← 路由层（HTTP 端点，34 个模块）
├── services/         ← 业务逻辑层（34 个服务）
├── repositories/     ← 数据访问层（31 个仓储）
├── models/           ← SQLAlchemy ORM 模型（26 个）
├── schemas/          ← Pydantic 请求/响应模式（23 个）
├── core/             ← 配置/数据库/中间件（14 个）
├── plugins_builtin/  ← 内置插件（2 个）
└── config.py / database.py / main.py
```

**依赖方向**：api → services → repositories → models
**禁止**：跨层反向依赖、循环依赖

### 3.2 命名规范

- 路由文件：snake_case，如 `document.py`
- 服务类：`<模块>Service`，如 `DocumentService`
- 模型类：PascalCase，如 `Document`
- Pydantic 模式：`<动作>Request` / `<动作>Response` / `<实体>Create` / `<实体>Update`

### 3.3 数据库

- 使用 SQLAlchemy 2.0 async 语法
- 迁移用 Alembic（`backend/migrations/`，23 个版本）
- 模型继承 `Base`（`models/base.py`）
- 运行期数据统一存仓库根 `var/`（真实库 `var/data`、演示库 `var/demo`、历史副本 `var/legacy`），已被 `.gitignore` 排除

### 3.4 测试

- pytest，测试放 `backend/tests/`（当前 60 个测试文件；最新条数以 `pytest --collect-only -q` 为准）
- **测试规范唯一入口**：[`backend/tests/README.md`](../../backend/tests/README.md)（分层/命名/AAA/夹具/null 语义/覆盖率/慢测试登记）
- 覆盖率（本地与 CI 同一条命令；CI 另有阈值棘轮 `--cov-fail-under`，覆盖率回退会拦合并）：

```bash
cd backend
python -m pytest tests -q --cov=app --cov-report=term-missing
```

- **CI 覆盖率报告可作为 artifact 下载**（Actions 运行页底部 Artifacts 区，保留 **7 天**）：
  `backend-coverage`（`coverage.xml`，Cobertura 格式）与 `frontend-coverage`
  （`frontend/coverage/` 目录，含 `coverage-summary.json` 便于做趋势）。
  artifact 上传是 `if: always()` —— **上传失败只会丢报告，不影响测试/门禁结论**
  （结论看 pytest / vitest 退出码与覆盖率阈值步骤）。

## 4. 前端规范（Vue 3 + TypeScript）

### 4.1 目录结构

```
frontend/src/
├── components/
│   ├── common/        ← 通用组件（20 个，跨模块复用）
│   ├── layout/        ← 布局组件（15 个）
│   └── <module>/      ← 模块专用组件（document/pet/task）
├── views/             ← 页面视图（23 个目录，按模块分）
├── api/               ← API 服务层（30 个模块，类型化请求）
├── composables/       ← 组合式函数（24 个）
├── stores/            ← Pinia 状态管理（2 个）
├── types/             ← TypeScript 类型定义（22 个）
├── styles/            ← 主题样式（4 套）
├── constants/         ← 常量（2 个）
├── directives/        ← 自定义指令（1 个）
├── utils/             ← 工具函数（4 个）
└── app/               ← 应用级模块（4 个）
```

### 4.2 组件规范

- **通用组件**放 `components/common/`，跨模块复用
- **布局组件**放 `components/layout/`
- **模块专用组件**放 `components/<module>/`
- 组件名用 PascalCase，文件名与组件名一致
- 使用 `<script setup lang="ts">` 语法
- 组件自动导入（unplugin-vue-components），无需手动 import

### 4.3 主题规范

- 三套主题：奶油糖果（默认）、国风雅集、深空档案
- 颜色、字号、间距一律引用 CSS 变量
- 禁止硬编码色值/字号/间距
- 主题切换通过 `data-theme` 属性

### 4.4 移动端规范

- 使用 Capacitor 打包 Android
- 弱网场景使用离线队列（`composables/` 中的 useOfflineQueue）
- 移动端交互使用 ActionSheet 替代桌面端弹窗
- 表格支持横向滚动，栅格支持塌缩

## 5. API 设计规范

- RESTful 风格，版本前缀 `/api/v1/`
- 列表接口统一分页参数：`page`, `page_size`
- 响应统一格式：`{ code, message, data }`
- 错误用 HTTP 状态码 + 业务错误码
- 接口文档自动生成（Swagger UI：`http://localhost:8765/docs`）

## 6. 配置管理

| 环境 | 配置文件 | 说明 |
|------|----------|------|
| 开发 | `backend/.env`（不入库） | 本地开发配置 |
| 模板 | `backend/.env.example` | 配置项模板 |
| 前端开发 | `frontend/.env.development` | 前端开发环境 |
| 前端生产 | `frontend/.env.production` | 前端生产环境 |

- `.env` 不入库，敏感信息（API Key/密钥）只放 `.env`
- `.qm-token` 是本地令牌，已被 `.gitignore` 排除
- 新增配置项必须同步更新 `.env.example`

## 7. 启动方式（单一实现：`ops/start.ps1`）

**D-11 之后的模型**：根目录 4 个 `.bat` 与 `scripts/dev.ps1` 都只是**薄转发壳**，
真正的启动逻辑只存在于 [`ops/start.ps1`](../../ops/start.ps1)（安装逻辑在 `ops/setup.ps1`）。
不要再往任何 `.bat` 里加逻辑 —— `scripts/audit_delivery.py` 会把实现细节写回转发壳判红。

| 场景 | 命令（任选其一） | 端口 | 数据目录 |
|---|---|---|---|
| 环境初始化（仅首次） | `setup.bat` ＝ `ops/setup.ps1` | — | — |
| 开发 | `start-dev.bat` ＝ `ops/start.ps1 -Mode dev` | 8765(--reload) + 5173 | `var\data` |
| 演示（丰富示例数据） | `start-demo.bat` ＝ `-Mode demo` | 8765 + 5173 | `var\demo`（缺库自动 seed） |
| 手机 / 局域网 | `start-mobile.bat` ＝ `-Mode mobile` | 8765(回环) + **3000**(对外) | `var\data` |

```powershell
# 三种模式都可以先"预演"：只打印将要执行的命令 / 环境变量，不启动进程
powershell -ExecutionPolicy Bypass -File ops/start.ps1 -Mode dev    -WhatIf
powershell -ExecutionPolicy Bypass -File ops/start.ps1 -Mode demo   -WhatIf
powershell -ExecutionPolicy Bypass -File ops/start.ps1 -Mode mobile -WhatIf

# 分支开发：数据目录隔离（相对仓库根，会被转成绝对 Windows 路径）
powershell -ExecutionPolicy Bypass -File ops/start.ps1 -Mode dev -DataDir .\var\data-branch

# 兼容旧入口（等价于 -Mode dev [-DataDir]，仅供既有文档/肌肉记忆使用）
powershell -ExecutionPolicy Bypass -File scripts/dev.ps1 -DataDir .\var\data-branch
```

> 启动器会做这些校验（都只在这一处实现）：项目 venv 是否存在、能否 `import uvicorn/fastapi`、
> `frontend\node_modules`、端口占用（dev 仅提示 / demo 直接拦下）、`frontend\dist` 是否需要构建。
> 后端进程的 CWD 固定为 `backend\`（`app` 包只在那里），所以从任何目录调用都不会
> `ModuleNotFoundError: No module named 'app'`。

### 手动启动（不推荐，仅排障用）

```bash
# 后端（必须用项目 venv；PATH 上的 python 通常缺依赖）
cd backend
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8765 --reload

# 前端
cd frontend
npm run dev  # → http://localhost:5173

# 统一服务（可选；生产/移动端先 npm run build）
node ops/server/server.js  # → http://localhost:3000
```

## 8. 代码质量检查

项目内置多个审计脚本，提交前建议运行：

```bash
# 全量检查
python scripts/check_all.py

# 后端 lint（ruff 0.6.2；口径见 backend/pyproject.toml 的 [tool.ruff.lint]：
# 只启用 E4/E7/E9/F 正确性规则 —— 未定义名 / 未使用导入与变量 / 重定义 / 语法错误；
# 不跑 ruff format，线长 E501 显式忽略，避免纯风格重排淹没业务 diff）
cd backend && python -m ruff check app tests

# 交付物审计
python scripts/audit_delivery.py

# 硬编码颜色审计
python scripts/audit_hardcoded_colors.py

# 版本检查
python scripts/check_versions.py
```

### 本地目录卫生（var/ 与本地垃圾）

`git status` 永远是干净的 —— 因为 `.gitignore` 把 `var/`、`backend/*cache` 全忽略了。
代价是：**垃圾会悄悄堆到几个 GB**（2026-10-28 实测 var/ 下 24 个 pytest basetemp ≈160MB、
`.ruff-install` 32MB）。所以目录也有一条可执行规则：

```bash
# 检查：tracked 泄漏 / .gitignore 契约 / 根目录与 var/ 白名单
python scripts/audit_workspace_hygiene.py

# 清理：只删"明确废弃"的本地垃圾（pytest basetemp、ruff/pytest 缓存、
# var/rebuild、var/tools、var/junk、backend/venustech_smoke 等）
python scripts/audit_workspace_hygiene.py --fix-local

# CI / 干净克隆：只查 tracked 泄漏 + ignore 契约（没有本地数据可查）
python scripts/audit_workspace_hygiene.py --ci
```

**什么时候跑 `--fix-local`**：跑完大规模 pytest / check_all 之后、切分支前、
发现磁盘占用异常时。它**绝不删除** `var/data`、`var/demo`、`var/legacy`、`var/backups`、
`backend/.legacy-data-*`（数据回滚兜底，只打印"确认后可手动删"）。

**var/ 顶层白名单**：`data/ demo/ legacy/ backups/ logs/ tmp/`（+ `.gitkeep`）。
新东西要么放进这几个目录（临时文件进 `var/tmp/`），要么就别放在 `var/`。
其中 `var/logs/` 是启动器/服务日志目录：白名单内、`--fix-local` **不删**，需要时手动清旧日志。

**测试覆盖率产物**（`backend/.coverage*`、`frontend/coverage/`、`htmlcov/`）属测试产物，
`.gitignore` 已覆盖；本地跑完 coverage 后 `--fix-local` 会一并清掉（可安全删除）。

> Windows 提示：若 `--fix-local` 报 `🔒 无法访问`，说明该目录由**别的沙箱会话**创建
> （ACL 只授予了创建者），本会话连 `rd /s` / `takeown` 都会被拒绝。脚本会打印
> 一条 `rd /s /q "..."` 命令，到「完全权限」会话执行即可；CI 与干净克隆不会遇到。

## 9. 常见问题

### Q: Git 报 `index.lock` 错误？
A: `.git/` 是目录联接，需到目标目录删除锁文件：
```powershell
Remove-Item "C:\Users\21722\qimingxing-git-repo\*.lock" -Force
```

### Q: 后端启动报 `ModuleNotFoundError: app`？
A: `app` 包只在 `backend\` 下，而 uvicorn 以 **CWD** 为 import 根 —— 所以必须让 CWD=`backend\`。
   用一键启动器即可（`ops/start.ps1` 已固定后端 CWD，并统一用 `backend\.venv` 的解释器）；
   手动排障时请 `cd backend` 后再跑 `.venv\Scripts\python.exe -m uvicorn app.main:app ...`，
   **不要**在仓库根直接跑 `python -m uvicorn app.main:app`。

### Q: 移动端离线队列如何工作？
A: 弱网时请求写入本地 IndexedDB，网络恢复后自动重放。见 `frontend/src/kernel/offline/`（offlineQueue / offlineQueueCore / offlineQueueIdb）。

### Q: 如何添加新主题？
A: 在 `frontend/src/styles/` 中新增主题变量文件，在 `data-theme` 中注册，无需修改组件代码。

### Q: 数据存在哪里？
A: 运行期数据统一存仓库根 `var/`（SQLite）：真实库 `var/data/app.db`、演示库 `var/demo/`、历史副本 `var/legacy/`，全部已被 `.gitignore` 排除；切换分支不会覆盖本地数据库。旧的 `backend/data*` 已迁走并改名保留在 `backend/.legacy-data-2026-10-27/`。

## 10. 发布流程（Release）

**版本规则（SemVer）**：`MAJOR.MINOR.PATCH` —— MAJOR 不兼容变更（数据/接口/启动方式）、MINOR 向后兼容的新功能、PATCH 向后兼容的修复。事实来源**唯一**是仓库根 `VERSION`，其它位置一律由脚本同步，**禁止手改**。

**tag 命名**：只允许 annotated tag `vX.Y.Z`（如 `v1.0.0`）。不用 `v1.0`、`1.0.0`、`release-1.0` 等形式；已发布 tag **不可移动/删除**（要改内容就发新的 PATCH 版本）。

**发布清单（按序）**：

```powershell
# 1) 版本 bump：只改 VERSION，再同步（--sync 幂等，可重复跑）
#    自动同步：backend/app/config.py、backend/pyproject.toml、frontend/package.json、
#              ops/server/package.json、frontend/android/app/build.gradle 的 versionName
#    需手工同步（脚本不覆盖）：frontend/package-lock.json 的两个根 version 字段、
#              文档中的「当前版本」引用（README / ARCHITECTURE 头部；历史文档与 CHANGELOG 历史段不改）
python scripts/check_versions.py --sync
python scripts/check_versions.py          # 必须 exit 0

# 2) 全量门禁（不绿不发布）
python scripts/check_all.py --strict      # 16 项
# 并确认 main 上 5 个 workflow 全绿：backend / frontend / repo-guard / android / windows-startup

# 3) CHANGELOG：把 [Unreleased] 归入 ## [X.Y.Z] - YYYY-MM-DD（Keep a Changelog 格式，不丢历史），
#    补 docs/RELEASE_NOTES_v1.0.0.md 这类按版本命名的发布说明

# 4) 提交 + tag + 推送（维护者执行；本仓库 .git 是目录联接，须在有权限的会话操作）
git add -A
git commit -m "release: v1.0.0"
git tag -a v1.0.0 -m "Qimingxing v1.0.0"
git push origin main
git push origin v1.0.0

# 5) GitHub Release：基于 tag v1.0.0 创建，正文取自发布说明
gh release create v1.0.0 --title "v1.0.0" --notes-file docs/RELEASE_NOTES_v1.0.0.md
```

**规则**：
- 发布后 `[Unreleased]` 留空占位，后续改动继续写在 Unreleased；
- Android：`versionName` 随版本同步，`versionCode` 是**整数发布序号**，每次对外发 APK 必须人工 +1（`check_versions.py` 只提示、不代改）；
- 依赖升级（Dependabot）不单独发版：随下一个版本发布并在 CHANGELOG 记录；
- 发布前确认 `LICENSE`、备份/恢复 runbook、安全说明就绪（v1.0.0 首发已具备：根目录 MIT `LICENSE`）。
