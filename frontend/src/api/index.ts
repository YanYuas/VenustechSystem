// ============================================================
// API 统一导出入口
// 用法: import { taskApi, documentApi } from '@/api'
// ============================================================
export * from './http'
export { authApi } from './auth'
export { taskApi } from './task'
export { documentApi } from './document'
export { conversationApi, aiApi } from './conversation'
export { reviewApi } from './review'
export { dashboardApi, backupApi } from './dashboard'
export { panelApi } from './panel'
export { notificationApi } from './notification'
export { projectApi } from './project'

export { resourceApi } from './resource'
export { learningApi } from './learning'
export { lifeApi } from './life'
export { assetApi } from './asset'
export { growthApi } from './growth'
// petApi 已真实迁移到 features/pet（迁移批次 P2，ADR-0007），本桶不再转发；
// 跨域请从 '@/features/pet' 导入。
export { systemApi } from './system'
export { settingsApi, NOTIFY_KEYS } from './settings'
export { identityApi } from './identity'
export { experienceApi } from './experience'
export { workspaceApi } from './workspace'
export { reportApi } from './report'
export { vaultApi } from './vault'
export { aihotApi } from './aihot'
export { syncApi } from './sync'
export { assistantApi } from './assistant'
export type { SettingsValues } from './settings'
