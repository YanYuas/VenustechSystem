# 启明星系统 · 前端开发说明

> 版本：v1.0 | 更新日期：2026-08-29 | 技术栈：Vue 3 + TypeScript + Vite + Element Plus

## 一、项目架构

### 1.1 目录结构

> ⚠️ **2026-10-27 起目录分层已变更，以 [ADR-0007](../architecture/ADR/0007-frontend-feature-architecture.md) 与
> [`frontend/src/features/README.md`](../../frontend/src/features/README.md) 为准。**
>
> 现行分层：`app/`（入口 / 路由 / 应用壳）→ `kernel/`（无业务底座：http / toast / modal / offline /
> async / device）→ `shared/`（设计系统与壳：components / styles / constants / directives / theme /
> types / composables / test）→ `features/<domain>/`（27 个领域唯一所有权落点：22 个页面域 +
> 5 个 API-only 域）。
>
> **P3 全量迁移 + P4 壳清理已完成**：`api/ composables/ stores/ constants/ directives/ types/ utils/
> views/ components/ styles/ test/` 已全部从 `src/` 根消失。其中样式与测试前置归位为：
> `src/styles/*.scss` → `src/shared/styles/*.scss`（`app/main.ts` 按
> variables → element-plus → global → animations 顺序注入），
> `src/test/setup.ts` → `src/shared/test/setup.ts`（`vitest.config.ts` 的 `setupFiles` 已同步）。
> `auto-imports.d.ts` / `components.d.ts`（unplugin 生成产物）与 `env.d.ts`（全局环境声明）
> **保留在 `src/` 根**：它们是构建工具/TS 的声明入口，不是分层资产（详见
> [`frontend/src/shared/README.md`](../../frontend/src/shared/README.md)）。
>
> 下面这棵树是**迁移中的历史快照**，数量与部分文件（如已删除的 BaseConfirm/BaseTooltip）
> 已不代表现状 —— 用于理解历史结构，不要据此新增文件。

```
frontend/
├── src/
│   ├── api/                    # API 层（与后端对接）
│   │   ├── http.ts             # HTTP 客户端封装（重试/超时/SSE）
│   │   ├── auth.ts             # 认证 & 用户配置
│   │   ├── task.ts             # 任务模块
│   │   ├── document.ts         # 知识模块
│   │   ├── conversation.ts     # 第二分身
│   │   ├── review.ts           # 复盘模块
│   │   ├── dashboard.ts        # 仪表盘 & 备份
│   │   ├── panel.ts            # 左侧信息面板
│   │   ├── notification.ts     # 统一通知
│   │   └── index.ts            # 统一导出
│   ├── app/                    # 应用入口
│   │   ├── main.ts             # 入口文件
│   │   ├── App.vue             # 根组件
│   │   ├── errorHandler.ts     # 全局错误处理
│   │   └── router/             # 路由配置
│   ├── components/
│   │   ├── common/             # 通用基础组件（16个）
│   │   │   ├── BaseButton.vue
│   │   │   ├── BaseCard.vue
│   │   │   ├── BaseInput.vue
│   │   │   ├── BaseSelect.vue
│   │   │   ├── BaseModal.vue
│   │   │   ├── BaseDrawer.vue
│   │   │   ├── BaseTag.vue
│   │   │   ├── BaseSwitch.vue
│   │   │   ├── BaseEmpty.vue
│   │   │   ├── BaseSkeleton.vue
│   │   │   ├── BasePagination.vue
│   │   │   ├── BaseTooltip.vue
│   │   │   ├── BaseConfirm.vue
│   │   │   ├── BaseToast.vue
│   │   │   ├── AppIcon.vue
│   │   │   └── index.ts
│   │   ├── layout/             # 布局组件
│   │   │   ├── DefaultLayout.vue   # 主布局（三栏式）
│   │   │   ├── TopNav.vue          # 顶部水平导航
│   │   │   ├── AppHeader.vue       # 顶栏（备用）
│   │   │   ├── LeftInfoPanel.vue   # 左侧信息面板
│   │   │   ├── AppTitleBar.vue     # 窗口标题栏
│   │   │   ├── GlobalSearch.vue    # 全局搜索
│   │   │   ├── CommandPalette.vue  # 命令面板
│   │   │   └── ...
│   │   └── pet/                # 桌宠组件
│   │       └── DesktopPet.vue
│   ├── composables/            # 组合式函数
│   │   ├── useAsync.ts         # 异步请求封装
│   │   ├── useToast.ts         # Toast 通知
│   │   ├── useModal.ts         # 模态框
│   │   ├── useTheme.ts         # 主题切换（3套主题）
│   │   ├── useAutoSave.ts      # 自动保存
│   │   ├── useNotification.ts  # 通知中心
│   │   ├── useTask.ts          # 任务业务逻辑
│   │   ├── useDocument.ts      # 文档业务逻辑
│   │   ├── useConversation.ts  # 对话业务逻辑
│   │   ├── useReview.ts        # 复盘业务逻辑
│   │   ├── useDashboard.ts     # 仪表盘
│   │   ├── useShortcuts.ts     # 快捷键
│   │   └── useOnline.ts        # 在线状态
│   ├── views/                  # 页面视图
│   │   ├── Dashboard/          # 首页仪表盘
│   │   ├── Task/               # 任务管理
│   │   ├── Document/           # 知识资源（含编辑器）
│   │   ├── Conversation/       # 第二分身
│   │   ├── Review/             # 复盘
│   │   ├── Settings/           # 设置
│   │   └── NotFound/
│   ├── stores/                 # 状态管理
│   ├── types/                  # TypeScript 类型定义
│   ├── styles/                 # 全局样式
│   │   ├── variables.scss      # CSS 变量（设计令牌）
│   │   ├── global.scss         # 全局样式
│   │   ├── animations.scss     # 动画
│   │   └── element-plus.scss   # Element Plus 覆盖
│   ├── constants/              # 常量
│   ├── directives/             # 自定义指令
│   └── utils/                  # 工具函数
├── index.html
├── vite.config.ts
├── tsconfig.json
└── package.json
```

### 1.2 技术选型

| 类别 | 选型 | 说明 |
|------|------|------|
| 框架 | Vue 3 + Composition API | `<script setup>` 语法 |
| 语言 | TypeScript 5.x | 严格模式 |
| 构建 | Vite 5.x | 极速热更新 |
| UI 库 | Element Plus | 按需引入，自定义主题覆盖 |
| 路由 | Vue Router 4 | Hash 模式（Electron 兼容） |
| HTTP | Fetch API 原生封装 | 重试/超时/SSE 流式 |
| 日期 | dayjs | 轻量级日期处理 |

## 二、核心模块说明

### 2.1 主题系统（useTheme）

三套内置主题包 × 明暗模式：
- **奶油糖果**（cream）：温暖柔和，日常使用
- **国风雅集**（guofeng）：古典雅致，文人气息
- **深渊档案**（abyss）：深邃神秘，专注沉浸

主题通过 `data-theme` 属性切换，CSS 变量驱动：
```ts
const { pack, mode, setPack, setMode, toggleMode } = useTheme()
```

### 2.2 通知中心（useNotification）

- 30秒轮询未读计数
- 下拉面板展示通知列表
- 标记已读/全部已读
- 点击通知跳转源页面
- 未读红点 + ping 动画

### 2.3 文档编辑器（DocumentEditor）

- 自动保存：1秒防抖 + 30秒定时 + 失焦立即保存
- 标签管理：最多10个标签
- AI 摘要展示
- AI 建议标签一键添加
- 字数统计 + 版本号显示

### 2.4 第二分身（Conversation）

- SSE 流式输出，打字机效果
- 5种思维模式：标准/深度/创意/批判/头脑风暴
- 对话历史侧栏
- 停止生成按钮

### 2.5 桌宠（DesktopPet）

- SVG 二次元形象
- 6种动作状态：idle/happy/thinking/working/celebrate/sleep
- 可拖拽定位
- 消息气泡互动
- 任务完成庆祝特效

## 三、开发规范

### 3.1 组件命名

- 通用组件：`Base` 前缀（BaseButton, BaseCard）
- 布局组件：`App` 前缀或语义化命名（TopNav, LeftInfoPanel）
- 页面组件：`XxxView` 命名

### 3.2 API 调用规范

```ts
// 1. 在 api/ 目录定义 API 函数
export const taskApi = {
  list(params?: TaskListQuery) {
    return http.get<PaginatedData<Task>>('/tasks', params)
  },
}

// 2. 在 composables/ 中封装业务逻辑
export function useTask() {
  const { loading, execute: fetchTasks } = useAsync(async () => {
    const res = await taskApi.list(query.value)
    tasks.value = res.list
  })
  return { tasks, loading, fetchTasks }
}

// 3. 在视图中使用
const { tasks, loading, fetchTasks } = useTask()
```

### 3.3 样式规范

- 使用 CSS 变量（设计令牌），不硬编码颜色
- 类名采用 BEM 变体：`block__element--modifier`
- 组件样式使用 `<style scoped lang="scss">`
- 动画使用 `var(--ease-soft)` / `var(--ease-spring)` 缓动

### 3.4 类型规范

- 所有 API 响应必须定义类型
- Props 使用 `defineProps<{...}>()` 类型声明
- Emits 使用 `defineEmits<{...}>()` 类型声明
- 禁止使用 `any`，必要时用 `unknown`

## 四、构建与部署

### 4.1 开发命令

```bash
npm install       # 安装依赖
npm run dev       # 启动开发服务器（端口 5173）
npm run build     # 生产构建
npm run preview   # 预览构建结果
npm run typecheck # 类型检查（vue-tsc --noEmit）
npm run test      # 单元测试（vitest run，单次）
npm run test:watch# 单元测试（监听模式）
```

### 4.1.1 单元测试（vitest + jsdom，2026-10-11 起）

- 配置文件：`vitest.config.ts`（**独立于** `vite.config.ts` —— 后者挂了
  AutoImport / Components，会改写 `src/*.d.ts`，单元测试不需要）
- 全局前置：`src/test/setup.ts`（补 jsdom 缺失的 `window.matchMedia`，可切换 `matches`）
- 用例位置：`src/**/__tests__/**/*.spec.ts`
- 已纳入一键入口：仓库根 `python scripts/check_all.py` 第 12 项

写法约定：

1. **不依赖 globals**：一律 `import { describe, it, expect, vi } from 'vitest'`
   （`tsconfig.json` 没有 `types: ['vitest/globals']`，靠显式 import 才过 `vue-tsc`）
2. **模块级单例要 `vi.resetModules()` + 动态 import**（如 `useTheme`）——
   否则测不到「冷启动读 localStorage」这条真实路径
3. **断言要断言行为，不要断言实现**：例如报告体积格式化只测渲染出的
   `1.0 KB / 1.0 MB`，不去 import 私有的 `size()`
4. **发现缺陷当场修**：首轮 75 条用例就测出 3 处前端缺陷（详见 `CHANGELOG.md`），
   修完把用例留着当回归

### 4.2 环境变量

- `.env.development`：开发环境配置
- `.env.production`：生产环境配置
- `VITE_API_BASE`：API 基础地址

### 4.3 构建产物

- 代码分割：按路由懒加载
- 第三方库单独打包（vue-vendor）
- 资源哈希命名，支持长期缓存

## 五、与后端对接

### 5.1 API 基础地址

- 开发：`http://127.0.0.1:8765/api/v1`
- 生产：通过环境变量配置

### 5.2 统一响应格式

```ts
interface ApiResponse<T> {
  code: number      // 0=成功
  message: string
  data: T
  timestamp?: number
}
```

### 5.3 错误处理

- HTTP 错误：自动解析后端 message
- 网络错误：1次重试，间隔2秒
- 超时：15秒
- 业务错误：Toast 提示 + 抛出异常

## 六、一期功能清单

| 模块 | 功能 | 状态 |
|------|------|------|
| 首页仪表盘 | 今日最重要/执行列表/项目/资源/生活/资产 | ✅ 完成 |
| 任务管理 | CRUD/子任务/优先级/截止日期/今日最重要 | ✅ 完成 |
| 知识资源 | 文件夹管理(创建/重命名/删除/层级)/文档CRUD/编辑器/自动保存/标签/AI摘要 | ✅ 完成 |
| 第二分身 | 对话/SSE流式/思维模式/历史记录/对话删除/引用文档 | ✅ 完成 |
| 复盘 | 日报/自动数据填充/历史/详情展开 | ✅ 完成 |
| 通知中心 | 列表/未读统计/标记已读/轮询/点击跳转/全部已读 | ✅ 完成 |
| 设置 | 主题/AI配置/数据管理/第二分身/关于 | ✅ 完成 |
| 桌宠 | SVG形象/动作/拖拽/互动 | ✅ 完成 |
| 全局搜索 | 任务/文档/对话搜索 | ✅ 完成 |
| 命令面板 | 主题切换/设置/快捷键 | ✅ 完成 |
| 左侧面板 | 快速待办/提醒/系统状态 | ✅ 完成 |

## 七、迭代记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0 | 2026-08-29 | 初始版本，前端骨架全线推进后沉淀 |
| v1.1 | 2026-09-04 | 一期打磨收尾：①补全文件夹管理UI（创建/重命名/删除/层级导航）②补全对话删除功能 ③通知点击跳转（按类型路由到对应页面）④首页一屏自适应优化 ⑤useDocument新增文件夹CRUD方法 ⑥useConversation新增deleteConversation方法 ⑦TypeScript严格模式零错误验证 ⑧生产构建成功验证（5.08s） |
| v1.3 | 2026-10-27 | 目录分层重构：`kernel/`（http/ui/offline/device/async）+ `shared/`（设计系统/主题/常量/指令）+ `features/<domain>/`（27 个领域，唯一所有权落点），旧按类型目录已删除；引入 ESLint 9 flat + Prettier 并纳入 CI，其中 ESLint 用 `no-restricted-imports` 强制 ADR-0007 分层边界 |
| v1.2 | 2026-10-11 | 引入单元测试体系（vitest + jsdom）并修 3 处缺陷：①`vitest.config.ts` + `src/test/setup.ts`，4 个 spec / **75 条用例**，纳入 `check_all.py` 第 12 项（11 项 → 12 项）②**修 `useTheme` 的 `isDark` 不响应系统明暗**（computed 依赖里只有 `config`，系统切换时 `data-theme` 变了但 `isDark` 不重算）③**修 `THEME_PACKS` 漏 `epic`**（常量 3 套 vs 类型/useTheme/设置页 4 套）④**修 `useQueryAction` 处理器抛错变成未捕获 Promise rejection**（改为捕获 + 记日志 + 保留 action 参数以便重试） |
| v1.4 | 2026-10-28 | 测试质量基建（D-13 后续）：接入 `@vitest/coverage-v8` + `npm run test:coverage`（v8 provider，先观测不设阈值），新增 kernel/http、kernel/offline、shared 与 features composable 的一批行为测试；CI 增加覆盖率步骤（`continue-on-error`，只观测） |

## 八、Lint 与格式化（D-13）

```bash
npm run lint          # ESLint 9 flat config：正确性 + ADR-0007 分层边界
npm run format        # Prettier 统一格式（写）
npm run format:check  # CI 用：只检查不写
npm run typecheck     # vue-tsc --noEmit
```

- 规则基调**正确性优先**（非类型检查的 TS/Vue 推荐集 + `eslint-config-prettier`）；风格交给 Prettier，两者不重叠。
- **边界由 ESLint 强制**（ADR-0007）：`kernel/` 不得 import `shared/`/`features/`；`shared/` 不得 import `features/`；`features/a` 不得深链 `features/b` 内部文件（只能 `@/features/b` 入口）。违反 `npm run lint` 直接失败。

> ⚠️ **Prettier 陷阱（已踩过）**：配置为 `semi: false`，Prettier 会把 Vue 内联事件处理器里的
> **多语句**打印成换行分隔（无分号），Vue 编译器会报
> `Error parsing JavaScript expression` 导致构建失败。
> 约定：**Vue 模板内联事件处理器必须是单次调用/单表达式**；多语句一律抽成命名函数后 `@click="onXxx(...)"`。

## 九、测试与覆盖率（Phase 5）

```bash
npm test              # vitest run（CI 门禁：必须全绿）
npm run test:watch    # 监听模式（本地开发）
npm run test:coverage # 覆盖率报告（v8；text + json-summary，输出到 frontend/coverage/）
```

### 分层

| 层 | 是否要求单测 | 说明 |
|---|---|---|
| `kernel/**` | **要求** | 纯逻辑/传输语义：http 错误映射与重试、SSE 解析、离线队列重放、async 状态机 |
| `shared/**` | **要求** | 设计系统纯逻辑、composables（自动保存/路由动作/主题） |
| `features/*/**`（api/model/composables） | **要求** | 业务编排：成功/失败/空数据/写后 refetch |
| `features/*/views/**` | 不强制 | 页面级只做路由懒加载冒烟；覆盖率统计中已排除，避免用 DOM 快照凑数 |
| 生成物 / 样式 | 排除 | `*.d.ts`、`src/styles|shared/styles/**`、`__tests__` 自身不计入 |

### 硬规则

1. **禁止真实网络/后端**：http 层用 `vi.stubGlobal('fetch', ...)` 桩响应；领域 composable 用 `vi.mock('../api')` 只测状态编排；涉及离线队列时注入内存版 `QueueStorage`（不碰 IndexedDB）。
2. 每条用例只验证**一个行为**，断言落在返回值/状态/副作用上；禁止"只断言存在"的空测试。
3. 时间相关行为（防抖/重试间隔/定时保存）用 `vi.useFakeTimers()` + `advanceTimersByTimeAsync`，不要 `sleep`。
4. 新测试放在被测模块同级的 `__tests__/<name>.spec.ts`（vitest include 为 `src/**/__tests__/**/*.spec.ts`）。
5. **发现业务 bug 先记录、不在测试里顺手改源码**；测试要如实红，用 `it.fails`/跳过并登记，不要写迎合现状的假断言。

### 覆盖率

- provider `v8`，`reporter: ['text', 'json-summary']`；`include: src/**`、排除 views/生成物/样式（见 `vitest.config.ts`）。
- **阈值棘轮（只许上调）**：`vitest.config.ts` 的 `coverage.thresholds` 当前为
  `{ lines: 31, branches: 76, functions: 59, statements: 31 }`
  （2026-10-30 Phase7 实测 32.24 / 77.7 / 60.42 / 32.24，各留约 1 个百分点余量防抖动；
  上调历史：`{12,65,40,12}`（Phase5）→ `{20,72,52,20}`（Phase6）→ 当前）。
  `npm run test:coverage` 与 CI 的 `Coverage (threshold ratchet)` 步骤**都会因此失败**，即覆盖率回退会直接卡住合并。
- **测试并发**：`test.maxWorkers: 2`。jsdom + `@vue/test-utils` 组件测试内存占用高，默认按 CPU 核数并发在多文件（18+）时会 OOM（本机 16 核曾 `FATAL ERROR: Zone Allocation failed`）；显式限并发使本地与 2 核 CI runner 行为一致。
- **规则**：阈值只允许上调；若因重构/删测试需要下调，**必须在 `CHANGELOG.md` 说明理由**并经评审，不允许静默调低。
- 口径提醒：`lines` 的分母是 `src/**/*.{ts,vue}` 全量实现文件（含大量未测 Vue 组件），且 views 按约定排除；
  v8 provider 对"从未执行的文件"不生成 branch/function 计数，故 `branches/functions` 会显著高于 `lines` —— 评估覆盖率以 **lines** 为主。

---

> 本文档随项目迭代持续更新。前端开发请严格遵守 TypeScript 严格模式，所有变更必须通过 `vue-tsc --noEmit` 类型检查。
