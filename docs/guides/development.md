# 启明星系统 · 开发规范

> 最后更新：2026-09-27

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
- 运行期数据存 `backend/data_*/`，已被 `.gitignore` 排除

### 3.4 测试

- pytest，测试放 `backend/tests/`
- 当前 4 个测试文件，覆盖率待提升

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
| 环境初始化（仅首次） | `setup.bat` ＝ `ops\setup.ps1` | — | — |
| 开发 | `start-dev.bat` ＝ `ops\start.ps1 -Mode dev` | 8765(--reload) + 5173 | `backend\data` |
| 演示（丰富示例数据） | `start-demo.bat` ＝ `-Mode demo` | 8765 + 5173 | `backend\data_demo`（缺库自动 seed） |
| 手机 / 局域网 | `start-mobile.bat` ＝ `-Mode mobile` | 8765(回环) + **3000**(对外) | `backend\data` |

```powershell
# 三种模式都可以先"预演"：只打印将要执行的命令 / 环境变量，不启动进程
powershell -ExecutionPolicy Bypass -File ops\start.ps1 -Mode dev    -WhatIf
powershell -ExecutionPolicy Bypass -File ops\start.ps1 -Mode demo   -WhatIf
powershell -ExecutionPolicy Bypass -File ops\start.ps1 -Mode mobile -WhatIf

# 分支开发：数据目录隔离（相对 backend\，会被转成绝对 Windows 路径）
powershell -ExecutionPolicy Bypass -File ops\start.ps1 -Mode dev -DataDir .\data-fusion

# 兼容旧入口（等价于 -Mode dev [-DataDir]，仅供既有文档/肌肉记忆使用）
powershell -ExecutionPolicy Bypass -File scripts\dev.ps1 -DataDir .\data-fusion
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

## 9. 常见问题

### Q: Git 报 `index.lock` 错误？
A: `.git/` 是目录联接，需到目标目录删除锁文件：
```powershell
Remove-Item "C:\Users\21722\qimingxing-git-repo\*.lock" -Force
```

### Q: 后端启动报 `ModuleNotFoundError: app`？
A: `app` 包只在 `backend\` 下，而 uvicorn 以 **CWD** 为 import 根 —— 所以必须让 CWD=`backend\`。
   用一键启动器即可（`ops\start.ps1` 已固定后端 CWD，并统一用 `backend\.venv` 的解释器）；
   手动排障时请 `cd backend` 后再跑 `.venv\Scripts\python.exe -m uvicorn app.main:app ...`，
   **不要**在仓库根直接跑 `python -m uvicorn app.main:app`。

### Q: 移动端离线队列如何工作？
A: 弱网时请求写入本地 IndexedDB，网络恢复后自动重放。见 `frontend/src/kernel/offline/`（offlineQueue / offlineQueueCore / offlineQueueIdb）。

### Q: 如何添加新主题？
A: 在 `frontend/src/styles/` 中新增主题变量文件，在 `data-theme` 中注册，无需修改组件代码。

### Q: 数据存在哪里？
A: 运行期数据存 `backend/data_*/`（SQLite），已被 `.gitignore` 排除。切换分支不会覆盖本地数据库。
