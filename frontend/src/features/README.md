# features/ —— 领域包（ADR-0007）

一个业务领域 = 一个目录，**唯一所有权落点**。新增/删除领域只需增减一个目录 + 一行路由，
不再跨 `views/`、`components/`、`composables/`、`api/`、`types/` 五个目录改文件。

## 目录约定

```
features/<domain>/
├── api.ts              # 领域接口（只依赖 kernel/http；不得 import 其它 feature 的实现）
├── model.ts            # 领域类型（原 types/<domain>.ts + api 内联类型收编）
├── composables/        # 领域视图逻辑（useXxx）
├── components/         # 领域组件（跨域使用须经 index.ts）
├── views/              # 领域页面（由 app/router 懒加载）
└── index.ts            # **唯一公开出口**：跨域只能从这里 import
```

## 依赖规则（硬约束，`scripts/audit_architecture.py` R14 已强制）

1. `kernel/` 不得 import `shared/` / `features/` / 旧过渡目录（api/views/composables/stores/…）。
2. `shared/` 只能依赖 `kernel/` 与自身。
3. `features/<a>` 只能依赖 `kernel/` / `shared/` / **自身**；**跨领域一律经对方 `index.ts`**，
   禁止深链 `features/<b>/api.ts`、`features/<b>/model.ts`、`features/<b>/components/*`。
4. `views` 不直接 import `api`：视图 → composables → feature `api.ts` → `kernel/http`。
5. 一个领域只有一个数据入口（`api.ts`）与一个公开出口（`index.ts`）。

> R14 实测：`python scripts/audit_architecture.py --strict` → 0 债务；`TRANSITIONAL_AREAS` 已清空，
> 任何对旧目录的依赖都会立刻变红。

### 关于 `views/` 与 `index.ts` 的例外（重要）

`index.ts` 不静态 re-export view 文件，只导出**懒加载入口函数**：

```ts
// features/task/index.ts
export const taskView = () => import('./views/TaskListView.vue').then((m) => m.default)
// app/router/index.ts
component: taskView
```

原因：若公开出口静态 re-export view，任何 import 该 index 的模块（例如布局壳只是要取某个
领域组件）都会把整页 view 静态拉进主包，破坏路由级代码分割。
**跨域的 api / 类型 / composable** 从 `index.ts` 导出；**view 只给路由层用懒加载入口**。

组件导出从严：只有当某域组件**确实需要跨域使用**时才从 index 导出（当前仅 `pet/DesktopPet`，
供 `app/layout` 使用）；其余域内组件由本域 view 用相对路径引用，不进公开出口 ——
因为 router 会静态 import 每个 index 取懒加载函数，index 顺手 re-export 整域组件会把它们
带进主包。需要跨域时再加一行具名 export 即可。

## P3 完成状态（2026-10-27）

- **27 个领域全部迁入**：22 个页面域（aihot / asset / assistant / avatar / conversation /
  dashboard / document / experience / growth / identity / learning / life / pet / project /
  report / resource / review / settings / task / vault / workflow / workspace）
  - 5 个 API-only 域（auth / panel / notification / system / sync）。
- 原 `api/`、`types/`、`views/`、`components/`、`utils/` 目录已清空；
  8 个薄转发壳保留到 P4（见下）。
- `api/index.ts`、`types/index.ts`、`composables/index.ts` 三个桶已删除，跨域一律直连 feature index。
- ADR-0008：请求类型可空字段 `field?: T | null`（省略=不改，null=清空）已落地。

### 与任务书的一处偏差（有据）

`components/layout/` 的 10 个文件没有全部进 `shared/components/layout/`，而是按依赖性质拆分：

- **6 个纯 UI 布局件**（AppTitleBar / Breadcrumb / CommandPalette / DimensionTabs /
  MobileTabBar / OfflineQueueIndicator）→ `shared/components/layout/`；
- **4 个带业务依赖的壳件**（DefaultLayout / TopNav / GlobalSearch / LeftInfoPanel）→ `app/layout/`。
  它们分别依赖桌宠、通知、文档检索、侧栏面板等 feature；放进 shared 会违反 R14
  「shared 只能依赖 kernel」。`app/` 是组合根（入口/路由/全局错误处理 + 应用壳），
  由它依赖 features 属于正常方向。

## 新增一个领域的步骤

1. 建 `features/<domain>/{api,model,composables,components,views,index}`；
2. 把该领域的类型收编到 `model.ts`（含 api 内联类型）；
3. `index.ts` 只导出**跨域需要**的部分（view 用懒加载入口函数）；
4. `app/router` 的 route component 指向 index 的懒加载入口；
5. 在 `docs/architecture/domains.json.frontend_features` 登记；
6. `npm run typecheck` + `npm test` + `npm run build` 全绿（R14 会兜底依赖方向）。

## 批次

- P1：`kernel/` 建立（http / toast / modal / offline）+ 薄转发壳 —— 已完成。
- P2：`features/pet/` 真实迁移 + `shared/` 目录 —— 已完成。
- P3：其余 26 领域全量迁入 + 非领域资产归位（types/composables/components/utils/布局） —— 已完成。
- P4（本轮已完成的部分）：
  - **8 个薄转发壳全部删除**：`api/http.ts`、`api/connectivity.ts`、`composables/useToast.ts`、
    `composables/useModal.ts`、`stores/offlineQueue.ts`、`constants/{index,dimensions}.ts`、
    `directives/index.ts`；`api/ composables/ stores/ constants/ directives/` 五个过渡目录已清空移除。
  - **R14 无 WARN 豁免**：`scripts/audit_architecture.py` 删除 `TRANSITIONAL_AREAS`，
    kernel/shared/features 对旧目录的任何依赖直接 ERROR。
  - **kernel 过渡依赖归零**：kernel 只依赖 kernel 自身（http 契约类型在 `kernel/http/types.ts`）。
  - **`kernel/http` 职责拆分**：`client / errors / request / sse / types / index`，
    公开 API 与行为零变化（导出列表 diff 为空，行为脚本守护）。
- P4 剩余 / 后续：
  - `styles/` → `shared/styles/`（需同步 `app/main.ts` 注入顺序 + vite scss 配置 + 视觉回归）；
  - `test/setup.ts`、`*.d.ts` 等工程文件归位（需同步 vite/vitest 配置）；
  - ESLint `no-restricted-imports` 边界规则进 CI（由并行任务负责安装配置）；
  - `docs/architecture/domains.json` 的 legacy 目录文档条目/根 README 路径清理。
