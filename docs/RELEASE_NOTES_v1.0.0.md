# 启明星系统 v1.0.0 发行说明

> **版本**：1.0.0 ｜ **发布日期**：2026-11-01 ｜ **首个公开发行版本**
> 变更全量清单见 [CHANGELOG](../CHANGELOG.md)；架构与债务清单见 [ARCHITECTURE](../ARCHITECTURE.md)；许可证见 [LICENSE](../LICENSE)（MIT）。
> 文档总索引：[docs/README.md](README.md)。

启明星系统是一个**本地优先**的个人成长 / 知识管理 / 生活记录桌面系统：Windows 上一键启动，
数据全部落在本机 SQLite；Web 前端 + 可选的手机浏览器访问（统一服务令牌鉴权）+ Android 壳。

---

## 一、1.0.0 亮点

- **数据自有、本地优先**：全部业务数据存本机 `var/data/app.db`，不上云、不需要账号体系；
  备份/恢复为一等能力（原子替换 + 失败自动回滚，见 `docs/runbooks/backup.md`）。
- **8 大领域、33 个 API 模块**：platform（认证/设置/安全/备份/同步/事件/健康/日志/通知/规则/插件）、
  execution（任务/项目/工作流/工作区）、knowledge（文档/学习/资源/经验/复盘）、growth（成长/身份/习惯/心情/日记）、
  assistant（对话/助手/面板/AI）、companion（桌宠/形象）、asset（SOP/Prompt/Skill/项目记忆/保险箱）、
  insight（首页聚合/报告）。领域地图与机器可读定义见 [ARCHITECTURE §5](../ARCHITECTURE.md) 与
  [domains.json](architecture/domains.json)。
- **AI 第二分身**：对话（SSE 流式）、5 种思维模式、引用文档/灵感；DeepSeek HTTP 客户端 + **Mock 降级**
  （未配置 API Key 也可用）。
- **桌宠陪伴**：SVG 形象、动作/拖拽/气泡/任务完成庆祝联动；Phase 12–14 把定时器、动作顺序、
  卸载清理全部收口（组件级测试钉死）。
- **多端使用**：Windows 一键启动（dev / demo / mobile 三模式，`-Verify` 真自检）、
  手机浏览器经统一服务访问（令牌鉴权 + `/api` 代理 + 路径穿越防护）、Android Capacitor 壳（CI 构建 debug APK）。
- **四套主题 × 明暗**：cream / guofeng / abyss / epic（`data-theme` 驱动，组件不写死颜色，由设计令牌审计守护）。

## 二、技术架构一页摘要

- **分层**：`api → services → repositories → models`，`core` 为基础设施且**单向依赖**；
  AST 守护 R1–R14 机器强制（`scripts/audit_architecture.py --strict`），新增模块必须先在
  [domains.json](architecture/domains.json) 登记领域。
- **事务边界**：repositories 只 `flush()`，`commit()` 权在 service / `get_db`（守护 R11）；
  跨模块解耦走 `core/event_bus`（同步 + 异步投递，失败可观测、无运行 loop 时同步兜底）。
- **单一启动器**：`ops/start.ps1` 是唯一实现（根目录 `.bat` 只是薄转发壳）；
  `-WhatIf` 只预演、`-Verify` 真启动 → 等端口 + `/api/v1/health` → `taskkill` 自动停止 → 退出码 0/1；
  支持 `-DataDir` 分支隔离数据。
- **迁移完整性**：Alembic 显式 DDL 基线（49 表 / 79 索引）冻结，后续迁移必须幂等；
  `tests/test_migration_integrity.py` 对「全新库 / ORM metadata / 真实 DB」三方对账。
- **安全**：修复历史 IDOR（D-20）、加密单例与密钥轮换真实化、备份恢复原子替换（D-46）、
  统一服务令牌鉴权 + 路径穿越防护、敏感文件/本地数据仓库守护。
- **工程门禁**：`scripts/check_all.py` 16 项一键校验；5 个 CI workflow
  （backend / frontend / repo-guard / android-apk / windows-startup，其中后两个分别跑 Android 构建与
  Windows 启动冒烟）。

## 三、质量数据（1.0.0 发布时）

| 指标 | 数值 |
|---|---|
| 后端测试 | **1965 passed**；语句覆盖率 **98.94%**（CI 阈值 98%，低于即红） |
| 前端测试 | **515 passed**；lines **82.2%**（阈值 lines 81 / branches 88 / functions 48 / statements 81） |
| 代码质量 | ruff 0.17.3（E4/E7/E9/F）· ESLint（含分层边界）+ Prettier · vue-tsc 零错误 · vite build 成功 |
| CI | 5 个 workflow，main 全绿；覆盖率 XML/JSON 作为 artifact 保留 7 天 |
| 本地一键门禁 | `python scripts/check_all.py --strict` 16 项全绿 |

## 四、快速开始

### Windows（推荐）

1. 首次准备：安装 **Python 3.11+** 与 **Node 24.x**（前端 CI 实测版本；jsdom 要求 ≥22.22.2），
   然后双击 `setup.bat`（创建 `backend/.venv`、装后端依赖、`npm ci`）。
2. 日常启动：
   - 开发：`start-dev.bat`（后端 :8765 + 前端 :5173）
   - 演示数据：`start-demo.bat`（独立库 `var/demo`，不碰真实库）
   - 手机访问：`start-mobile.bat`（回环后端 + 边缘服务 :3000 + 访问令牌）
3. 自检（改完启动脚本或排障时）：`ops/start.ps1 -Mode dev -Verify` —— 退出码 0 表示
   "服务真起来 / 健康检查通过 / 已自动停止"。
4. 数据与日志：数据库 `var/data/`，服务日志 `var/logs/`；备份与恢复见
   [启动与自检 runbook](runbooks/startup.md) 与 [备份 runbook](runbooks/backup.md)。

### 手动路径（排障用，不推荐日常）

```powershell
# 后端（必须用项目 venv；uvicorn 以 CWD 为 import 根 → 先 cd backend）
cd backend
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8765 --reload

# 前端
cd frontend
npm run dev
```

API 文档（FastAPI OpenAPI，version=1.0.0）：`http://127.0.0.1:8765/docs`。

## 五、已知限制

- **D-56（P3）SQLAlchemy 2.1 暂缓**：2.1 把隐式 `float` 注解映射从 `Float` 改为 `Double`，
  会与冻结迁移 DDL 漂移并被迁移完整性门禁拦下。当前锁定 `SQLAlchemy==2.0.52`；
  升级前需给 5 个列显式 `Float` 并跑迁移完整性回归（详见 ARCHITECTURE §10）。
- **D-57（P3）vite 8 迁移**：vite 5 → 8 是 major（Node 版本 / 插件兼容 / 构建产物回归），
  需专门迁移任务；当前保持 vite 5.x。
- **云同步未实现**：本地优先，只有本地同步适配器；多设备同步不在 1.0.0 范围。
- **Android 仅 debug APK**：CI 构建未签名调试包；无应用商店签名正式包。
  `build.gradle` 的 `versionCode` 仍为 1，对外发 APK 前需人工递增。
- **单机单用户**：无多租户/角色权限体系；统一服务为"访问令牌"级鉴权。
- 其它架构债务与历史决策见 [ARCHITECTURE §10](../ARCHITECTURE.md)：D-01~D-55 均已有结论/已修，
  当前仅 D-56 / D-57 未修。

## 六、升级说明（0.7.0 → 1.0.0）

1. **先备份**：按 [备份 runbook](runbooks/backup.md) 导出数据库与加密密钥目录（升级前必做）。
2. **直接替换代码后启动**：启动时会自动执行 Alembic `upgrade head`，无需手工迁移；
   数据目录约定不变（`var/data`、`var/demo`、`var/legacy`），切换版本不会覆盖本地库。
3. **版本代码变更点**（本次已全部同步为 1.0.0）：
   - 根 `VERSION`（唯一事实来源）、后端 `settings.version` 与 OpenAPI version、
     `backend/pyproject.toml`、`frontend/package.json` + `frontend/package-lock.json`、
     `ops/server/package.json`、Android `build.gradle` 的 `versionName`；
   - 备份清单的 `app_version` 从 0.7.0 变为 1.0.0。
4. **旧备份兼容**：0.7.0 的备份仍可导入；跨 **MAJOR** 版本时导入会提示"版本不一致"
   （按设计只是警告、不阻断，确认数据无误后继续使用）。
5. **依赖要求变化**：后端 pytest 9.2.0 / ruff 0.17.3（本地旧 venv 建议重装
   `backend/requirements-dev.txt` 对齐）；前端 Node 24（CI 口径）。
6. **API 兼容**：路径仍为 `/api/v1/*`；前后端同版本升级（本项目本地一体部署，不承诺跨版本 API 兼容）。

## 七、相关文档

| 主题 | 入口 |
|---|---|
| 启动 / 自检 / 排障 | [runbooks/startup.md](runbooks/startup.md) |
| 备份与恢复 | [runbooks/backup.md](runbooks/backup.md) |
| 开发规范 / PR 流程 / 发布流程 | [guides/development.md](guides/development.md)（§2.1 PR、§10 发布） |
| 架构总纲与债务（§10）/ 路线（§11） | [ARCHITECTURE.md](../ARCHITECTURE.md) |
| 文档总索引 | [docs/README.md](README.md) |
