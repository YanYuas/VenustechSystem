# 贡献指南

感谢参与启明星系统（Venustech System）开发。请遵循以下约定，保证代码一致与可持续。

## 分层架构（严格单向依赖）

```
api → services → repositories → models
           ↘ core（统一响应/异常/日志/加密/事件总线）
```

- **api**：参数校验 + 响应封装，不碰 models、不直接建 Session
- **services**：业务逻辑，不依赖 FastAPI
- **repositories**：纯数据存取
- 架构守护测试强制（`backend/tests/test_architecture.py`）

## 代码规范

- **后端**：PEP8；分层纪律；统一 `AppException`；Schema 字段 snake_case 且与前端类型一致；Prompt 集中 `PromptBuilder`
- **前端**：Vue3 `<script setup lang="ts">` + Composition API；TS 严格模式禁 `any`；原生 fetch（禁 axios）；组件经 common/ 基础件，hex 色值仅 token 处
- **Windows**：源码 UTF-8；.bat 存 ASCII/GBK（cmd 按系统代码页解析）；脚本输出 utf-8

## 验证（提交前必须过）

```bash
# 后端
cd backend && python scripts/smoke_backend.py   # 端到端断言全绿
# （可选）python -m pytest                        # 单元 + 架构守护

# 前端
cd frontend && npm run typecheck                  # vue-tsc 零错误
cd frontend && npm run build                      # 生产构建成功
```

## 数据库变更

改模型后生成 Alembic 迁移（`alembic revision --autogenerate`），启动自动 `upgrade head`，勿手改表。

## 提交规范（Conventional Commits）

```
feat(scope): 描述      # 新功能
fix(scope): 描述       # 修复
docs(scope): 描述      # 文档
refactor(scope): 描述  # 重构（不改行为）
chore(scope): 描述     # 杂项/清理
```

scope 用 backend / frontend / docs / scripts 等。提交前确认工作区仅含本次意图变更，勿夹带无关文件（如本地数据、构建产物、测试库）。

## 数据与产物（勿提交）

`backend/data/`、`backend/data_test/`、`frontend/dist/`、`node_modules/`、`*.log` 等已在 `.gitignore`。
