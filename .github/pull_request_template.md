<!--
PR 标题用 Conventional Commits：`<类型>(<范围>): <描述>`
  例：`fix(backend): token 过期未返回 401 而是 500`
类型/范围规则见 docs/guides/development.md §2；分支规则见 §1（小改动可直接 main，本模板用于需要评审/跨模块/依赖升级的改动）。
填写要求：**已验证项必须真跑过再勾**，勾不了的写明原因，不要空勾。
-->

## 变更摘要

<!-- 一句话说清「改了什么、为什么」。多件不相关的事请拆成多个 PR（CONTRIBUTING.md §5 一次提交只做一件事） -->

-

## 影响面

- [ ] 后端 `backend/**`（api / services / repositories / models / core / migrations）
- [ ] 前端 `frontend/**`（views / components / composables / kernel / shared / styles）
- [ ] CI / 工程脚本（`.github/workflows/**`、`scripts/**`、`ops/**`）
- [ ] 文档（`docs/**`、`README.md`、`CONTRIBUTING.md`、`CHANGELOG.md`）
- [ ] 依赖升级（Dependabot 自动 PR 或手动升级）

## 已验证项

<!-- 对应 CONTRIBUTING.md §3「提交前必须过」；本地真跑过再勾 -->

- [ ] `python scripts/check_all.py --strict` —— 一键入口全绿（与 CI 同款命令）
- [ ] 后端：`cd backend && python -m ruff check app tests scripts`
- [ ] 后端：`cd backend && python -m pytest tests -q`
- [ ] 前端：`cd frontend && npm run lint && npm run format:check && npm run typecheck && npm test && npm run build`
- [ ] 涉及启动器 / 后端启动链路时：`ops/start.ps1 -Mode dev -Verify`（或等 `windows-startup` CI 跑完）
- [ ] 涉及分层 / 新增模块时：`python scripts/audit_architecture.py --strict`，且已在 `docs/architecture/domains.json` 登记领域
- [ ] 涉及文档时：`python scripts/audit_docs_links.py --all`
- [ ] 数据库变更：新增迁移（不手改表），`backend/tests/test_migration_integrity.py` 通过
- [ ] 已更新 `CHANGELOG.md`（用户可见的 feat/fix 必须写；纯内部重构可写「无用户可见变更」）

## 回滚方案

<!-- 出问题时怎么退：revert 哪个 commit / 迁移是否需要回退或补偿 / 数据是否需要清理 -->

-

## 关联 issue / 背景

<!-- 例：Closes #12；或贴需求/审计报告链接 -->

## 给 reviewer 的提示（可选）

<!-- 重点看哪里、哪些是有意的取舍、已知风险与未覆盖项 -->
