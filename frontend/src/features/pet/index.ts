// ============================================================
// features/pet/index.ts —— 桌宠领域唯一公开出口（迁移批次 P2，ADR-0007）
//
// 跨域（其它 feature / shared / views）只能从这里 import，禁止深链
// features/pet/api.ts、model.ts、components/*、views/*。
//
// 为什么不直接 `export { default as PetSettingsView } from './views/...'`：
// view 是路由级懒加载资源，若在公开出口里**静态** re-export，任何 import
// 本 index 的模块（如 DefaultLayout 取 DesktopPet）都会把整页 view 静态拉进
// 主包。故这里只导出**懒加载入口函数**，路由用 `component: petSettingsView`。
// ============================================================

// ---------- api ----------
export { petApi } from './api'

// ---------- 类型（跨域需要时使用；type-only 不影响运行时 chunk） ----------
export type {
  PetConfig,
  PetAvatar,
  PetState,
  PetStats,
  PetVitals,
  PetStatsDelta,
  PetAction,
} from './model'

// ---------- 组件 ----------
export { default as DesktopPet } from './components/DesktopPet.vue'

// ---------- composable / 事件总线 ----------
export { emitPetAction, PET_ACTION_EVENT } from './composables/usePetEvent'
export type { PetActionName } from './composables/usePetEvent'

// ---------- view（路由专用懒加载入口，避免 view 被静态打进主包） ----------
export const petSettingsView = () => import('./views/PetSettingsView.vue').then((m) => m.default)
