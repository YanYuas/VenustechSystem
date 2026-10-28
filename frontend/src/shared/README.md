# shared/ —— 设计系统与外壳（ADR-0007，P3/P4 已完成）

`shared/` 放**跨领域复用的 UI 设计系统与通用能力**。与 `kernel/` 的区别：kernel 是"看不见的技术底座"
（http / toast / modal / offline / device / electron），shared 是"看得见的公共 UI 与中立能力"。

## 依赖规则（硬约束，R14 已强制）

1. `shared` **只能依赖 `kernel`**（含 vue / pinia 等第三方库）与 `shared` 自身。
2. `shared` 不得 import `features/`、以及已删除的旧过渡目录 `api/views/composables/stores/components/types/utils/styles/test`。
3. 业务语义不进 shared：凡知道"任务/复盘/桌宠"等业务概念的代码，属于对应 `features/<domain>`。
4. 反向：`features/<d>` 可以依赖 `shared`（如 `@/shared/components/common/BaseCard.vue`）；
   `kernel` 不得依赖 `shared`。

## 当前目录（P4 完成后）

```
shared/
├── README.md
├── components/
│   ├── common/            # BaseButton/BaseCard/BaseInput/BaseModal/BasePagination/…（17 个）
│   └── layout/            # 6 个纯 UI 布局件（AppTitleBar/Breadcrumb/CommandPalette/…）
├── composables/           # useAutoSave、useQueryAction（+ __tests__）
├── constants/             # index.ts（APP/STORAGE_KEYS/ROUTES/THEME_PACKS…）、dimensions.ts + __tests__
├── directives/            # 全局指令 v-focus / v-click-outside / v-copy
├── styles/                # variables / element-plus / global / animations（由 app/main.ts 按序注入）
├── test/                  # setup.ts（vitest setupFiles：jsdom matchMedia 桩）
├── theme/                 # useTheme.ts（主题引擎）+ __tests__
└── types/                 # common.ts、user.ts（Toast 类型 re-export 自 kernel/ui/types）
```

带业务依赖的 4 个壳件（DefaultLayout / TopNav / GlobalSearch / LeftInfoPanel）放在 `app/layout/`，
不放这里 —— 它们依赖 features，放 shared 会违反 R14（详见 `features/README.md` 的偏差说明）。

`src/auto-imports.d.ts`、`src/components.d.ts`（unplugin 生成产物）与 `src/env.d.ts`（全局环境声明）
**有意保留在 `src/` 根**：它们不是分层资产，而是构建工具/TS 的全局声明入口；移动需同步改
`vite.config` 的 `dts` 输出路径、`.prettierignore` 与 tsconfig include，收益低、风险高。

## P3 已完成的归位

| 旧位置                                                       | 新位置                                                          |
| ------------------------------------------------------------ | --------------------------------------------------------------- |
| `components/common/*`                                        | `shared/components/common/*`                                    |
| `components/layout/*`（6 个纯 UI）                           | `shared/components/layout/*`                                    |
| `composables/useTheme.ts`                                    | `shared/theme/useTheme.ts`                                      |
| `composables/useAutoSave.ts`、`useQueryAction.ts`            | `shared/composables/*`                                          |
| `composables/useAsync.ts`、`useDevice.ts`、`useShortcuts.ts` | `kernel/async/`、`kernel/device/`、`kernel/ui/`                 |
| `types/common.ts`、`types/user.ts`                           | `shared/types/*`                                                |
| `constants/*`、`directives/*`                                | 实现已在 P2 迁入 shared；P3 把消费者全部改指新路径；P4 删除旧壳 |

## P4 状态

- ✅ **8 个薄转发壳已全部删除**，`api/ composables/ stores/ constants/ directives/` 过渡目录清空移除；
  现在所有代码只能从 `@/kernel/*` 或 `@/shared/*` 取用（R14 无 WARN 豁免）。
- ✅ **`src/styles/` → `shared/styles/`**：4 个 scss 字节级不变；`app/main.ts` 注入顺序
  `variables → element-plus → global → animations` 逐字保留；`vite.config` 无 scss 路径配置
  （`additionalData: ''`），无需改动。
- ✅ **`src/test/setup.ts` → `shared/test/setup.ts`**：`vitest.config.ts` 的 `setupFiles` 已同步；
  `useTheme.spec.ts` 的 `@/test/setup` 引用已改 `@/shared/test/setup`。
- 剩余待办：

| 待办                                                             | 原因                                                                                              |
| ---------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| ESLint `no-restricted-imports` 边界规则进 CI                     | ADR-0007 P4 项；由并行任务安装配置，目前由 R14（`scripts/audit_architecture.py`）+ typecheck 兜底 |
| 历史目录文档清理（ARCHITECTURE.md / 根 README 的按类型目录描述） | 代码层已无旧目录，仅文档快照性描述待下一轮统一                                                    |
