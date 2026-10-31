---
name: Bug 报告
about: 可复现的缺陷（启动失败 / 接口 500 / 数据异常 / CI 变红）
title: "[bug] "
labels: ["bug"]
assignees: ["YanYuas"]
---

## 现象

<!-- 一句话：什么场景下发生了什么 -->

## 复现步骤

1.
2.
3.

## 期望行为

## 实际行为 / 关键报错

<!--
后端日志：`var/logs/<时间>-backend-FastAPI.err.log`（跑 ops/start.ps1 -Verify 时生成）
前端报错：浏览器 Console / Network，或 `npm run typecheck` 输出
粘贴时请脱敏（token、路径中的用户名、API Key）
-->

```text

```

## 环境

| 项 | 值 |
|---|---|
| 系统 | Windows 11 / macOS / Linux（版本） |
| 版本 | 仓库根 `VERSION` 的值（或页面显示的版本） |
| 后端 Python | 3.11.x（`backend/.venv`） |
| 前端 Node | 24.x |
| 启动方式 | `start-dev.bat` / `ops/start.ps1 -Mode dev -Verify` / 其他 |

## 影响范围

- [ ] 阻断使用（无法启动 / 核心流程不可用）
- [ ] 局部功能异常（哪个模块：）
- [ ] 仅日志/告警异常，功能正常

## 可能相关的改动（可选）

<!-- 最近改动 / Dependabot 升级 / 迁移号，便于定位 -->
