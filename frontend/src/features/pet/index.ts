// ============================================================
// features/pet/index.ts —— pet 领域唯一公开出口（迁移批次 P3，ADR-0007）
//
// 跨领域只能从这里 import；view 只导出懒加载入口函数（不得静态 re-export，
// 否则 import 本 index 的模块会把整页 view 拉进主包）。
// ============================================================
export * from './api'
export * from './model'
export * from './composables/usePetEvent'
// 跨域组件（本域组件被其它域/index 使用时才导出）
export { default as DesktopPet } from './components/DesktopPet.vue'
export const petSettingsView = () => import('./views/PetSettingsView.vue').then((m) => m.default)
