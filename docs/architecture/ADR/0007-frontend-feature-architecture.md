# ADR-0007 前端采用 kernel / shared / features 分层，按领域逐步收口

- 状态：**已采纳，pet 试点完成**（2026-10-27）
- 相关：[ARCHITECTURE.md](../../../ARCHITECTURE.md) §4.2、§11；`frontend/src/kernel`、`frontend/src/shared`、`frontend/src/features`

## 背景

前端目前按**文件类型**平铺：`views/`、`components/`、`composables/`、`api/`、`types/`。
2026-10 前端审计的实测代价：

- **领域没有所有权落点**：同一个「桌宠」领域散落在 `views/Pet`、`components/pet`、`api/pet.ts`、
  `composables/usePetEvent.ts`、`types`（内联）五处；新增/删除一个领域要动五个目录。
- **跨领域靠全局桶**：`api/index.ts` fan-in 38、`types/index.ts` fan-in 60，新增领域要改 27 条 export；
  桶已出现漏导出（`avatarApi`/`workflowApi` 只能深链）。
- **边界靠自觉**：24/26 个 view 直接 `import @/api`，2 处裸 `fetch` 硬编码 `127.0.0.1:8765`
  （移动端必坏）；`http.ts` 一个文件承担 9 类职责、31 个 importer。
- **死代码静默堆积**：因"没有领域入口"，`useAsset/useLearning/useLife/useResource` 写完没人用，
  曾累计 1188 行死代码（Phase 1 已删）。

## 决策

采用 **kernel / shared / features** 三分层，用**渐进式（strangler）迁移**，不做一次性重排：

```
frontend/src/
├── kernel/          # 无业务语义的技术底座：http、toast、modal、async、offline、theme 引擎
├── shared/          # 设计系统与壳：components/common、layout、styles、constants、directives、utils
├── features/<domain>/   # 一个领域一个包，唯一所有权落点
│   ├── api.ts           # 领域接口（只依赖 kernel/http）
│   ├── model.ts         # 领域类型（原 types/<domain>.ts）
│   ├── composables/     # 领域视图逻辑
│   ├── components/      # 领域组件
│   ├── views/           # 领域页面
│   └── index.ts         # 唯一公开出口（跨领域只能从这里 import）
├── app/             # 入口、路由、全局错误处理（保持不变）
└── （过渡期保留）api/ types/ composables/ components/ views/ —— 逐步清空
```

**依赖规则（防线，后续纳入守护）**：

1. `kernel` 不得 import `shared` / `features` / `api` / `views`（纯技术底座）。
2. `shared` 只能依赖 `kernel`。
3. `features/<a>` 只能依赖 `kernel` / `shared` / **自身**；跨领域一律经对方 `index.ts`。
4. `views` 不直接 import `api`：视图 → composables → feature api → kernel/http。
5. 一个领域只有一个数据入口（`features/<d>/api.ts`）与一个公开出口（`index.ts`）。

**过渡策略（关键）**：被移动的公共模块保留**薄转发壳**（re-export），
例如 `api/http.ts` → `export * from '@/kernel/http'`。这样试点领域可以真实使用新结构，
同时其余 30 个 api 模块零改动；壳上标注 `@deprecated` 与迁移批次，P4 统一清除。
禁止在壳里写实现（避免"两个真相"）。

## 试点范围（本轮）

选 **companion/pet** 作为第一个领域：它有 view、api、composable、components 四类资产，
足以验证结构但不庞大（PetSettingsView 443 行）。

- `features/pet/{api.ts, model.ts, composables/usePetEvent.ts, views/PetSettingsView.vue, components/*, index.ts}`
- `kernel/`：先迁 `http`（含 SSE/离线队列/错误映射）、`toast`、`modal`、`offlineQueue`，其余保留壳。
- `shared/`：先建目录 + 迁 `styles`/`components/common` 的**引用入口**（文件暂不动，避免大面积 import churn）。
- 路由、Settings 等既有引用改为从 `features/pet` 或过渡壳 import，`typecheck + build` 必须通过。

## 后果

- ✅ 新增/删除领域 = 一个目录 + 一行路由；死代码不再"写在无人使用的孤岛"。
- ✅ kernel 收口后 `http.ts` 的职责可继续拆（重试 / 离线 / SSE / 错误提示），移动端地址不再硬编码。
- ⚠️ 过渡期存在转发壳，`api/http.ts` 等旧路径仍可用 —— 这是**有意的**，P4 才清除；
  必须在壳上标 deprecation，且守护要禁止"壳里写实现"。
- ⚠️ 前端边界目前只由 `typecheck/build` + 评审保证；ESLint `no-restricted-imports`（D-13）
  落地后升级为 CI 强制。

## 迁移批次

| 批次 | 内容 | 状态 |
|---|---|---|
| P1 | `kernel/` 建立（http/toast/modal/offline）+ 薄壳 | 本轮 |
| P2 | `features/pet/` 真实迁移 + `shared/` 目录 | 本轮 |
| P3 | 其余领域逐个迁移（每领域一个 PR；优先 AiHot/Experience 等小域） | 下一轮 |
| P4 | 删除转发壳、清空按类型目录、ESLint 边界规则进 CI | 后续 |

## 试点结果（2026-10-27）

| 项 | 结果 |
|---|---|
| kernel | `kernel/http`（含 connectivity）、`kernel/ui`（toast/modal）、`kernel/offline`（Pinia 队列）真实迁移；旧路径 4 个薄壳 |
| shared | `shared/constants`（含测试随迁）、`shared/directives` 真实迁移；styles/components/layout/utils 留 P3（`shared/README.md` 记录原因） |
| features/pet | api + model（内联类型与组件内重复类型收编）+ composable + component + view + `index.ts`；**旧路径全删、无壳**；view 用懒加载入口避免主包污染 |
| 引用方 | DefaultLayout / FocusTimer / TaskListView / router / api 桶 共 6 处改新入口 |
| 守护 | 新增 **R14**（kernel/shared/features 依赖方向 + 跨域只走 index）+ `domains.json.frontend_features` 登记；负向测试证明会变红 |
| 验证 | typecheck 0 / vitest **86 passed** / build 成功；`PetSettingsView` chunk **14,236 B（与迁移前逐字节同大小）**、主入口 +28 B、SettingsView 不变 |
| 过渡债 | 8 条已登记：kernel→types/utils、shared→types、features→components/common（P3 归位后 R14 从 WARN 转 ERROR） |

## 替代方案

- **保持按类型分包**：成本已量化（桶 fan-in、跨五目录、死代码静默堆积）。否决。
- **一次性全量重排 155 个文件**：改动面过大且缺 UI 回归网，风险不成比例。否决。
- **直接上 Nx/Turborepo 多包**：单应用、单团队，收益不足。否决。
