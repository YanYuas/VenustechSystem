# features/ —— 领域包（ADR-0007）

一个业务领域 = 一个目录，**唯一所有权落点**。新增/删除领域只需增减一个目录 + 一行路由，
不再跨 `views/`、`components/`、`composables/`、`api/`、`types/` 五个目录改文件。

## 目录约定

```
features/<domain>/
├── api.ts              # 领域接口（只依赖 kernel/http；不得 import 其它 feature）
├── model.ts            # 领域类型（原 types/<domain>.ts 与 api 内联类型的归点）
├── composables/        # 领域视图逻辑（useXxx）
├── components/         # 领域组件（只被本领域或经 index.ts 跨域使用）
├── views/              # 领域页面（由 app/router 懒加载）
└── index.ts            # **唯一公开出口**：跨域只能从这里 import
```

## 依赖规则（硬约束，P4 起由 ESLint `no-restricted-imports` 强制）

1. `kernel/` 不得 import `shared/` / `features/` / `api/` / `views/`（纯技术底座）。
2. `shared/` 只能依赖 `kernel/`。
3. `features/<a>` 只能依赖 `kernel/` / `shared/` / **自身**；**跨领域一律经对方 `index.ts`**，
   禁止深链 `features/<b>/api.ts`、`features/<b>/components/*`。
4. `views` 不直接 import `api`：视图 → composables → feature `api.ts` → `kernel/http`。
5. 一个领域只有一个数据入口（`api.ts`）与一个公开出口（`index.ts`）。

### 关于 `views/` 与 `index.ts` 的例外（重要）

`index.ts` 不静态 re-export view 文件，只导出**懒加载入口函数**（如 `petSettingsView`）：

```ts
// features/pet/index.ts
export const petSettingsView = () => import('./views/PetSettingsView.vue').then((m) => m.default)
// app/router/index.ts
component: petSettingsView
```

原因：若公开出口静态 re-export view，任何 import 该 index 的模块（例如 `DefaultLayout`
只是要取 `DesktopPet`）都会把整页 view 静态拉进主包，破坏路由级代码分割。
**跨域组件/api/composable/类型** 正常从 `index.ts` 导出；**view 只给路由层用懒加载入口**。

## 当前状态

| 领域 | 状态 | 备注 |
|---|---|---|
| `pet/`（companion） | ✅ P2 试点完成（真实迁移，旧路径已删除、无转发壳） | api / model / composable / components / views / index 全量迁入；`PetAction` 从组件收编到 model，消除 composable → 组件反向依赖 |
| 其余 25 个领域 | ⏳ P3 逐域迁移 | 仍按类型平铺在 `api/ views/ components/ composables/ types/`；迁移时优先小域（AiHot / Experience 等） |

### 仍未迁入 shared 的过渡依赖（P3 处理）

`features/pet` 目前还 import 了 `@/components/common/BaseCard.vue`（桌宠设置页）与
`@/components/common/AppIcon.vue`（桌宠组件）。`components/common` 属 shared 设计系统，
P3 随 `shared/components/common/` 一起迁移，届时改为从 `@/shared` 入口导入。
详见 `frontend/src/shared/README.md` 的 P3 计划。

## 新增一个领域的步骤

1. 建 `features/<domain>/{api,model,components,composables,views,index}.ts`；
2. 把该领域的类型从 `types/` 或 api 内联处收编到 `model.ts`；
3. 在 `index.ts` 只导出**跨域需要**的部分（view 用懒加载入口函数）；
4. `app/router` 的 route component 指向 `index.ts` 的懒加载入口；
5. 旧路径直接删除（试点区域不留转发壳），全仓检索旧 import 确认 0 命中；
6. `npm run typecheck` + `npm test` + `npm run build` 全绿。

## 批次

- P1：`kernel/` 建立（http / toast / modal / offline）+ 薄转发壳 —— 已完成。
- P2：`features/pet/` 真实迁移 + `shared/` 目录与 constants/directives 真实迁入 —— 已完成。
- P3：其余领域逐域迁移；`shared/styles`、`components/common`、`layout`、`utils`、`types` 归位。
- P4：删除全部转发壳、清空按类型平铺目录、依赖规则进 CI。
