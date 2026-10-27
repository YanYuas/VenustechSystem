# shared/ —— 设计系统与外壳（迁移批次 P1/P3，ADR-0007）

`shared/` 放**跨领域复用的 UI 设计系统与外壳**。与 `kernel/` 的区别：kernel 是"看不见的技术底座"
（http / toast / modal / offline / theme 引擎），shared 是"看得见的公共 UI"（组件、样式、常量、指令、工具）。

## 依赖规则（硬约束）

1. `shared` **只能依赖 `kernel`**（含 vue / pinia 等第三方库）。
2. `shared` 不得 import `features/`、`api/`、`views/`、`composables/`、`stores/`（过渡目录同理）。
3. 业务语义不进 shared：凡知道"任务/复盘/桌宠"等业务概念的代码，属于对应 `features/<domain>`。
4. 反向：`features/<d>` 可以依赖 `shared`；`kernel` 不得依赖 `shared`。

过渡期唯一例外：`shared/constants/dimensions.ts` 仍 import `@/types/common` 的 `NavItem`
（类型目录 P3 才归位），这是**有意的临时依赖**，P3 一并解决。

## 当前目录（本轮已真实迁入）

```
shared/
├── constants/
│   ├── index.ts            # 应用常量唯一真源（APP / STORAGE_KEYS / ROUTES / TASK_STATUS / THEME_PACKS …）
│   ├── dimensions.ts       # 六大维度导航配置（DIMENSIONS / ROUTE_TO_DIMENSION / MAIN_NAV_ITEMS）
│   └── __tests__/constants.spec.ts
├── directives/
│   └── index.ts            # 全局指令：v-focus / v-click-outside / v-copy
└── README.md
```

旧路径（`@/constants`、`@/constants/dimensions`、`@/directives`）保留**薄转发壳**，
只做 re-export、壳内禁止写实现；P4 统一删除。

## P3 迁移计划（本轮**故意不动**的部分及原因）

| 待迁模块 | 目标位置 | 本轮不动的原因 |
|---|---|---|
| `styles/`（variables/global/element-plus/animations.scss） | `shared/styles/` | 样式通过 `main.ts` 的 4 条副作用 import 注入，且被 `vite.config` 的 scss 配置/全局主题变量依赖；移动会同时改注入顺序与构建配置，风险 > 收益，需独立批次 + 视觉回归 |
| `components/common/`（Base* 16 个组件 + 宿主组件） | `shared/components/common/` | 全仓 100+ 处 import；且 `components.d.ts` 的自动注册路径与 `unplugin-vue-components` 扫描目录绑定，需同步改 vite 配置（本轮禁止改构建配置） |
| `components/layout/`（DefaultLayout/TopNav 等 12 个） | `shared/layout/` | 路由壳（DefaultLayout）与导航/主题/设备探测耦合，需与 `app/` 层一起迁；改动面大且缺 UI 回归网 |
| `utils/`（offlineQueueCore/Idb、reportHtml、electron） | `shared/utils/` 或 `kernel/` | `offlineQueue` 已被 kernel/offline 依赖（P1），其 core/idb 属技术底座更应进 `kernel/offline/`；`reportHtml` 是纯函数需先补/迁移测试，`electron` 属运行时探测。统一放 P3 处理，避免本轮 kernel 目录反复搬 |
| `types/common.ts`（Semantic / NavItem / ThemePack …） | `shared/types/` 或保留 | 类型跨 kernel/shared/features 共用，归位需要与各 feature 的 `model.ts` 一起规划，属 P3 |

**P4**：删除薄壳、清空按类型平铺目录、ESLint `no-restricted-imports` 进 CI 后把上述依赖规则变成**强制**。
